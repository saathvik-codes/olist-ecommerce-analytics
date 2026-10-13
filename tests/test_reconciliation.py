"""Headline KPIs must agree across the warehouse, the SQL outputs, the Excel report
and the Power BI expected values."""
import re

import pandas as pd
import pytest

from config import POWERBI_DATA_DIR, POWERBI_DIR, SQL_OUTPUT_DIR, STAR_TABLES
from conftest import scalar


def named_range(workbook, name: str) -> list:
    """Values of a named range (single column or row) as a flat list."""
    sheet, cells = workbook.defined_names[name].attr_text.split("!")
    block = workbook[sheet.strip("'")][cells.replace("$", "")]
    return [cell.value for row in block for cell in row]


# ---- SQL output vs warehouse -------------------------------------------------------
def test_kpi_file_matches_warehouse(con, kpi):
    assert kpi.total_revenue == pytest.approx(
        scalar(con, "SELECT sum(price) FROM fact_order_items WHERE is_delivered = 1"), abs=0.01
    )
    assert kpi.delivered_orders == scalar(con, "SELECT count(*) FROM fact_orders WHERE is_delivered = 1")
    assert kpi.customers == scalar(con, "SELECT count(*) FROM dim_customer WHERE delivered_orders >= 1")
    assert kpi.repeat_customers == scalar(con, "SELECT sum(is_repeat_customer) FROM dim_customer")
    assert kpi.avg_order_value == pytest.approx(kpi.total_revenue / kpi.delivered_orders, abs=0.005)


def test_sql_outputs_agree_with_each_other(kpi):
    monthly = pd.read_csv(SQL_OUTPUT_DIR / "01_monthly_revenue_growth.csv")
    pareto = pd.read_csv(SQL_OUTPUT_DIR / "08_category_pareto.csv")
    rfm = pd.read_csv(SQL_OUTPUT_DIR / "03_rfm_segmentation.csv")
    sellers = pd.read_csv(SQL_OUTPUT_DIR / "11_seller_concentration.csv")
    baskets = pd.read_csv(SQL_OUTPUT_DIR / "12_basket_size.csv")
    repeat = pd.read_csv(SQL_OUTPUT_DIR / "04_repeat_purchase_rate.csv").set_index("order_bucket")
    for frame in (monthly, pareto, rfm, sellers, baskets):
        assert frame.revenue.sum() == pytest.approx(kpi.total_revenue, abs=0.05)
    assert monthly.orders.sum() == kpi.delivered_orders
    assert monthly.new_customers.sum() == kpi.customers
    assert rfm.customers.sum() == kpi.customers
    assert baskets.orders.sum() == kpi.delivered_orders
    assert repeat.loc["ALL", "customers"] == kpi.customers
    assert pareto.cumulative_share_pct.iloc[-1] == pytest.approx(100, abs=0.001)
    assert pareto.cumulative_share_pct.is_monotonic_increasing


# ---- Excel report ------------------------------------------------------------------
def test_excel_control_totals_equal_sql(workbook, kpi):
    ws = workbook["KPI Summary"]
    controls = {ws[f"A{r}"].value: ws[f"C{r}"].value for r in range(5, 19)}
    assert controls["Total revenue"] == pytest.approx(kpi.total_revenue, abs=0.005)
    assert controls["Delivered orders"] == kpi.delivered_orders
    assert controls["Average order value"] == pytest.approx(kpi.avg_order_value, abs=0.005)
    assert controls["Customers"] == kpi.customers
    assert controls["Repeat customer rate"] == pytest.approx(kpi.repeat_customer_rate_pct / 100, abs=1e-9)
    assert controls["Late delivery rate"] == pytest.approx(kpi.late_delivery_rate_pct / 100, abs=1e-9)
    assert controls["Average review score"] == pytest.approx(kpi.avg_review_score, abs=1e-9)


def test_excel_kpi_formulas_reproduce_sql(workbook, kpi):
    """Evaluate the KPI formulas by hand from the same named ranges Excel uses."""
    ws = workbook["KPI Summary"]
    formulas = {ws[f"A{r}"].value: ws[f"B{r}"].value for r in range(5, 19)}
    assert formulas["Total revenue"] == "=SUM(Monthly_Revenue)"
    assert formulas["Delivered orders"] == "=SUM(Monthly_Orders)"
    assert formulas["Repeat customers"] == '=SUMIFS(Freq_Customers,Freq_MinOrders,">=2")'
    assert formulas["Late delivery rate"] == "=SUM(Monthly_LateOrders)/SUM(Monthly_OrdersWithDate)"
    assert formulas["Average review score"] == "=SUM(Monthly_ReviewSum)/SUM(Monthly_Reviewed)"

    revenue = sum(named_range(workbook, "Monthly_Revenue"))
    orders = sum(named_range(workbook, "Monthly_Orders"))
    customers = named_range(workbook, "Freq_Customers")
    min_orders = named_range(workbook, "Freq_MinOrders")
    repeat = sum(c for c, n in zip(customers, min_orders) if n >= 2)
    late_rate = sum(named_range(workbook, "Monthly_LateOrders")) / sum(named_range(workbook, "Monthly_OrdersWithDate"))
    avg_review = sum(named_range(workbook, "Monthly_ReviewSum")) / sum(named_range(workbook, "Monthly_Reviewed"))

    assert revenue == pytest.approx(kpi.total_revenue, abs=0.01)
    assert orders == kpi.delivered_orders
    assert revenue / orders == pytest.approx(kpi.avg_order_value, abs=0.005)
    assert sum(customers) == kpi.customers
    assert repeat == kpi.repeat_customers
    assert 100 * repeat / sum(customers) == pytest.approx(kpi.repeat_customer_rate_pct, abs=0.005)
    assert 100 * late_rate == pytest.approx(kpi.late_delivery_rate_pct, abs=0.005)
    assert avg_review == pytest.approx(kpi.avg_review_score, abs=0.0005)
    assert sum(named_range(workbook, "Pareto_Revenue")) == pytest.approx(kpi.total_revenue, abs=0.01)
    assert sum(named_range(workbook, "RFM_Revenue")) == pytest.approx(kpi.total_revenue, abs=0.05)


def test_excel_workbook_structure(workbook):
    expected_sheets = ["KPI Summary", "Monthly Trend", "Cohort Retention", "RFM Segments",
                       "Category Pareto", "Delivery & Reviews", "About"]
    assert workbook.sheetnames == expected_sheets

    formulas = [
        cell.value
        for ws in workbook.worksheets for row in ws.iter_rows() for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=")
    ]
    assert len(formulas) > 500
    text = " ".join(formulas)
    for function in ("SUMIFS(", "XLOOKUP(", "INDEX(", "MATCH(", "COUNTIF(", "IFERROR(", "RANK("):
        assert function in text, f"{function} missing from the workbook"

    charts = {ws.title: len(ws._charts) for ws in workbook.worksheets}
    assert charts["Monthly Trend"] == 3
    assert charts["Cohort Retention"] == 1
    assert charts["RFM Segments"] == 1
    assert charts["Category Pareto"] == 2
    assert charts["Delivery & Reviews"] == 2

    for name in ("Monthly_Revenue", "Monthly_Month", "SelectedMonth", "SelectedState",
                 "Freq_Customers", "Pareto_Class", "State_LateRate", "Cohort_RetentionPct"):
        assert name in workbook.defined_names

    for sheet in expected_sheets[:-1]:
        assert workbook[sheet].freeze_panes is not None
    assert len(workbook["Cohort Retention"].conditional_formatting) >= 1
    assert len(workbook["KPI Summary"].data_validations.dataValidation) == 2
    assert workbook["Monthly Trend"]["D8"].number_format == '"R$" #,##0.00'


# ---- Power BI hand-off -------------------------------------------------------------
@pytest.mark.parametrize("table", STAR_TABLES)
def test_powerbi_csv_matches_warehouse(con, table):
    exported = pd.read_csv(POWERBI_DATA_DIR / f"{table}.csv", usecols=[0])
    assert len(exported) == scalar(con, f"SELECT count(*) FROM {table}")


def test_every_dax_measure_has_an_expected_value(kpi):
    dax = (POWERBI_DIR / "measures.dax").read_text(encoding="utf-8")
    measures = re.findall(r"^\s*MEASURE\s+fact_orders\[(.+?)\]\s*=", dax, flags=re.MULTILINE)
    expected = pd.read_csv(POWERBI_DIR / "expected_values.csv")
    assert len(measures) >= 20
    assert len(measures) == len(set(measures))
    assert set(measures) == set(expected.measure)

    unfiltered = expected[expected.filter_context == "No filters"].set_index("measure").expected_value
    assert unfiltered["Total Revenue"] == pytest.approx(kpi.total_revenue, abs=0.005)
    assert unfiltered["Total Orders"] == kpi.delivered_orders
    assert unfiltered["AOV"] == pytest.approx(kpi.avg_order_value, abs=0.005)
    assert unfiltered["Repeat Customer Rate"] == pytest.approx(kpi.repeat_customer_rate_pct, abs=0.005)
    assert unfiltered["Late Delivery %"] == pytest.approx(kpi.late_delivery_rate_pct, abs=0.005)
    assert unfiltered["Avg Review Score"] == pytest.approx(kpi.avg_review_score, abs=0.0005)


def test_product_view_measures_equal_order_view_when_unfiltered():
    expected = pd.read_csv(POWERBI_DIR / "expected_values.csv")

    def value(measure: str, context: str) -> float:
        match = expected[(expected.measure == measure) & expected.filter_context.str.startswith(context)]
        return match.expected_value.iloc[0]

    assert value("Late Delivery % (Product View)", "No filters") == value("Late Delivery %", "No filters")
    assert value("Avg Review (Product View)", "No filters") == value("Avg Review Score", "No filters")
