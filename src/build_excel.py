"""Build reports/Olist_Executive_Report.xlsx from the SQL outputs in outputs/sql/.

Design rule: raw facts (counts, sums) are written as values; every ratio, share, growth
rate and lookup is a live Excel formula, so the workbook can be audited cell by cell.
The KPI sheet recomputes each headline number from the detail sheets and compares it
with the control total that came straight from SQL.
"""
from datetime import date

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

from config import EXCEL_REPORT, REPORT_DIR, SQL_OUTPUT_DIR

# ---- look and feel ---------------------------------------------------------------
NAVY, BLUE, ORANGE, INK, MUTED = "1F3A5F", "2A78D6", "EB6834", "0B0B0B", "52514E"
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
INPUT_FILL = PatternFill("solid", fgColor="FFF4CC")
TOTAL_FILL = PatternFill("solid", fgColor="EEF2F7")
THIN = Side(style="thin", color="D0D4DA")
FMT_INT, FMT_MONEY, FMT_PCT, FMT_PCT2 = "#,##0", '"R$" #,##0.00', "0.0%", "0.00%"
FMT_MONEY0, FMT_DEC2, FMT_DEC3, FMT_MONTH = '"R$" #,##0', "0.00", "0.000", "mmm yyyy"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(SQL_OUTPUT_DIR / f"{name}.csv")


def month_to_date(year_month: str) -> date:
    return date(int(year_month[:4]), int(year_month[5:7]), 1)


def title(ws, text: str, subtitle: str) -> None:
    ws["A1"] = text
    ws["A1"].font = Font(size=16, bold=True, color=NAVY)
    ws["A2"] = subtitle
    ws["A2"].font = Font(size=10, italic=True, color=MUTED)


def header(ws, row: int, labels: list[str], widths: list[int] | None = None) -> None:
    for col, label in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=col, value=label)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=THIN)
    ws.row_dimensions[row].height = 32
    for col, width in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(col)].width = width


def set_formats(ws, first_row: int, last_row: int, formats: dict[str, str]) -> None:
    for column, number_format in formats.items():
        for row in range(first_row, last_row + 1):
            ws[f"{column}{row}"].number_format = number_format


def name_range(wb: Workbook, name: str, sheet: str, cells: str) -> None:
    wb.defined_names[name] = DefinedName(name, attr_text=f"'{sheet}'!{cells}")


def style_chart(chart, chart_title: str, y_title: str, y_format: str, width=22.0, height=9.0) -> None:
    chart.title = chart_title
    chart.y_axis.title = y_title
    chart.y_axis.number_format = y_format
    chart.x_axis.delete = False  # openpyxl hides axes by default in recent Excel builds
    chart.y_axis.delete = False
    chart.width, chart.height = width, height


def colour(series, hex_colour: str, line: bool = False) -> None:
    if line:
        series.graphicalProperties.line.solidFill = hex_colour
        series.graphicalProperties.line.width = 25400  # 2 pt
        series.smooth = False
    else:
        series.graphicalProperties.solidFill = hex_colour
        series.graphicalProperties.line.solidFill = hex_colour


# ---- sheets ----------------------------------------------------------------------
def monthly_sheet(wb: Workbook) -> dict:
    df = read("01_monthly_revenue_growth")
    ws = wb.create_sheet("Monthly Trend")
    title(ws, "Monthly trend", "Delivered orders by purchase month. Growth is only computed between "
          "complete months (Jan-2017 to Aug-2018); partial months are flagged 0.")
    header(
        ws, 4,
        ["Month", "Complete month", "Orders", "Revenue", "Freight", "Items sold", "AOV", "Revenue MoM %",
         "Revenue YoY %", "Rolling 3M revenue", "Cumulative revenue", "Orders with delivery date",
         "Late orders", "Late delivery %", "Reviewed orders", "Review score sum", "Avg review", "New customers"],
        [12, 10, 10, 15, 14, 10, 12, 11, 11, 16, 16, 13, 10, 10, 11, 11, 9, 11],
    )
    first, last = 5, 4 + len(df)
    for r, row in enumerate(df.itertuples(), start=first):
        ws[f"A{r}"] = month_to_date(row.year_month)
        ws[f"B{r}"] = int(row.is_complete_month)
        ws[f"C{r}"] = int(row.orders)
        ws[f"D{r}"] = float(row.revenue)
        ws[f"E{r}"] = float(row.freight)
        ws[f"F{r}"] = int(row.items_sold)
        ws[f"G{r}"] = f"=D{r}/C{r}"
        # the first row has no previous month; an empty-string formula keeps lookups consistent
        ws[f"H{r}"] = f'=IF(AND(B{r}=1,B{r - 1}=1),D{r}/D{r - 1}-1,"")' if r > first else '=""'
        if r - 12 >= first:
            ws[f"I{r}"] = f'=IF(AND(B{r}=1,B{r - 12}=1),D{r}/D{r - 12}-1,"")'
        if r - 2 >= first:
            ws[f"J{r}"] = f'=IF(AND(B{r}=1,B{r - 2}=1),SUM(D{r - 2}:D{r}),"")'
        ws[f"K{r}"] = f"=SUM($D${first}:D{r})"
        ws[f"L{r}"] = int(row.orders_with_delivery_date)
        ws[f"M{r}"] = int(row.late_orders)
        ws[f"N{r}"] = f"=M{r}/L{r}"
        ws[f"O{r}"] = int(row.reviewed_orders)
        ws[f"P{r}"] = int(row.review_score_sum)
        ws[f"Q{r}"] = f"=P{r}/O{r}"
        ws[f"R{r}"] = int(row.new_customers)

    total = last + 2
    ws[f"A{total}"] = "Total"
    for column in "CDEFLMOPR":
        ws[f"{column}{total}"] = f"=SUM({column}{first}:{column}{last})"
    ws[f"G{total}"] = f"=D{total}/C{total}"
    ws[f"N{total}"] = f"=M{total}/L{total}"
    ws[f"Q{total}"] = f"=P{total}/O{total}"
    for cell in ws[total]:
        cell.font, cell.fill = Font(bold=True), TOTAL_FILL

    set_formats(ws, first, total, {
        "A": FMT_MONTH, "C": FMT_INT, "D": FMT_MONEY, "E": FMT_MONEY, "F": FMT_INT, "G": FMT_MONEY,
        "H": FMT_PCT, "I": FMT_PCT, "J": FMT_MONEY, "K": FMT_MONEY, "L": FMT_INT, "M": FMT_INT,
        "N": FMT_PCT2, "O": FMT_INT, "P": FMT_INT, "Q": FMT_DEC3, "R": FMT_INT,
    })
    ws[f"A{total}"].number_format = "General"
    ws.freeze_panes = "B5"
    ws.conditional_formatting.add(
        f"H{first}:I{last}", FormulaRule(formula=[f"AND(ISNUMBER(H{first}),H{first}<0)"], font=Font(color="C0392B"))
    )

    for name, column in {
        "Monthly_Month": "A", "Monthly_Orders": "C", "Monthly_Revenue": "D", "Monthly_Freight": "E",
        "Monthly_Items": "F", "Monthly_AOV": "G", "Monthly_MoM": "H", "Monthly_OrdersWithDate": "L",
        "Monthly_LateOrders": "M", "Monthly_LatePct": "N", "Monthly_Reviewed": "O",
        "Monthly_ReviewSum": "P", "Monthly_AvgReview": "Q",
    }.items():
        name_range(wb, name, ws.title, f"${column}${first}:${column}${last}")

    # Charts use complete months only.
    complete = [r for r, flag in enumerate(df.is_complete_month, start=first) if flag == 1]
    c_first, c_last = complete[0], complete[-1]
    months = Reference(ws, min_col=1, min_row=c_first, max_row=c_last)

    revenue = LineChart()
    revenue.add_data(Reference(ws, min_col=4, min_row=c_first, max_row=c_last), titles_from_data=False)
    revenue.set_categories(months)
    colour(revenue.series[0], BLUE, line=True)
    style_chart(revenue, "Monthly revenue (R$), complete months", "Revenue", '#,##0')
    revenue.x_axis.number_format, revenue.legend = "mmm yy", None
    ws.add_chart(revenue, "T4")

    orders = BarChart()
    orders.add_data(Reference(ws, min_col=3, min_row=c_first, max_row=c_last), titles_from_data=False)
    orders.set_categories(months)
    colour(orders.series[0], BLUE)
    style_chart(orders, "Delivered orders per month", "Orders", "#,##0")
    orders.x_axis.number_format, orders.legend, orders.gapWidth = "mmm yy", None, 60
    ws.add_chart(orders, "T23")

    late = LineChart()
    late.add_data(Reference(ws, min_col=14, min_row=c_first, max_row=c_last), titles_from_data=False)
    late.set_categories(months)
    colour(late.series[0], ORANGE, line=True)
    style_chart(late, "Late delivery rate by purchase month", "Late %", "0%")
    late.x_axis.number_format, late.legend = "mmm yy", None
    ws.add_chart(late, "T42")
    return {"first": first, "last": last, "total": total}


def cohort_sheet(wb: Workbook) -> None:
    df = read("02_cohort_retention")
    ws = wb.create_sheet("Cohort Retention")
    title(ws, "Cohort retention", "Cohort = month of a customer's first delivered order. Blank = month not "
          "observed yet. Top block: returning customers (counts). Bottom block: retention % (formulas).")
    offsets = [f"m{n}" for n in range(1, 13)]
    header(ws, 4, ["Cohort", "Cohort size"] + [f"Month {n}" for n in range(1, 13)], [12, 12] + [9] * 12)
    first, last = 5, 4 + len(df)
    for r, row in enumerate(df.itertuples(index=False), start=first):
        ws[f"A{r}"] = month_to_date(row.cohort_month)
        ws[f"B{r}"] = int(row.cohort_size)
        for c, offset in enumerate(offsets, start=3):
            value = getattr(row, offset)
            if pd.notna(value):
                ws.cell(row=r, column=c, value=int(value))
    set_formats(ws, first, last, {"A": FMT_MONTH, "B": FMT_INT})

    pct_header = last + 4
    ws[f"A{pct_header - 1}"] = "Retention % of cohort"
    ws[f"A{pct_header - 1}"].font = Font(bold=True, color=NAVY, size=12)
    header(ws, pct_header, ["Cohort", "Month 0"] + [f"Month {n}" for n in range(1, 13)])
    p_first, p_last = pct_header + 1, pct_header + len(df)
    for i in range(len(df)):
        src, dst = first + i, p_first + i
        ws[f"A{dst}"] = f"=A{src}"
        ws[f"B{dst}"] = f"=B{src}/B{src}"
        for c in range(3, 15):
            col = get_column_letter(c)
            ws[f"{col}{dst}"] = f'=IF({col}{src}="","",{col}{src}/$B{src})'
    weighted = p_last + 2
    ws[f"A{weighted}"] = "All cohorts (weighted)"
    ws[f"B{weighted}"] = 1
    for c in range(3, 15):
        col = get_column_letter(c)
        # returning customers / size of the cohorts that have been observed for that month
        ws[f"{col}{weighted}"] = (
            f'=SUM({col}{first}:{col}{last})/SUMIFS($B${first}:$B${last},{col}{first}:{col}{last},"<>")'
        )
    for cell in ws[weighted]:
        cell.font, cell.fill = Font(bold=True), TOTAL_FILL
    set_formats(ws, p_first, weighted, {"A": FMT_MONTH, **{get_column_letter(c): FMT_PCT2 for c in range(2, 15)}})
    ws[f"A{weighted}"].number_format = "General"

    ws.conditional_formatting.add(
        f"C{p_first}:N{p_last}",
        ColorScaleRule(start_type="min", start_color="F7FBFF", mid_type="percentile", mid_value=50,
                       mid_color="9EC5EE", end_type="max", end_color="1F5FA8"),
    )
    ws.freeze_panes = "C5"
    name_range(wb, "Cohort_Sizes", ws.title, f"$B${first}:$B${last}")
    name_range(wb, "Cohort_RetentionPct", ws.title, f"$C${p_first}:$N${p_last}")
    name_range(wb, "Cohort_WeightedRetention", ws.title, f"$C${weighted}:$N${weighted}")

    curve = LineChart()
    curve.add_data(Reference(ws, min_col=3, max_col=14, min_row=weighted), from_rows=True, titles_from_data=False)
    curve.set_categories(Reference(ws, min_col=3, max_col=14, min_row=pct_header))
    colour(curve.series[0], BLUE, line=True)
    style_chart(curve, "Share of a cohort ordering again, by months since first order", "Retention %", "0.0%",
                width=20, height=8)
    curve.legend = None
    ws.add_chart(curve, "P4")


def rfm_sheet(wb: Workbook) -> None:
    rfm, freq = read("03_rfm_segmentation"), read("04_repeat_purchase_rate")
    ws = wb.create_sheet("RFM Segments")
    title(ws, "RFM customer segments", "Recency and Monetary scored by quintile; Frequency by rule "
          "(1 order = 1, 2 orders = 3, 3+ = 5). Shares, value per customer and the index are formulas.")
    header(ws, 4, ["Segment", "Customers", "% of customers", "Revenue", "% of revenue", "Avg recency (days)",
                   "Avg orders", "Revenue per customer", "Revenue index (% rev / % cust)"],
           [32, 12, 12, 16, 12, 12, 10, 14, 16])
    first, last = 5, 4 + len(rfm)
    total = last + 1
    for r, row in enumerate(rfm.itertuples(), start=first):
        ws[f"A{r}"] = row.rfm_segment
        ws[f"B{r}"] = int(row.customers)
        ws[f"C{r}"] = f"=B{r}/$B${total}"
        ws[f"D{r}"] = float(row.revenue)
        ws[f"E{r}"] = f"=D{r}/$D${total}"
        ws[f"F{r}"] = float(row.avg_recency_days)
        ws[f"G{r}"] = float(row.avg_orders)
        ws[f"H{r}"] = f"=D{r}/B{r}"
        ws[f"I{r}"] = f"=E{r}/C{r}"
    ws[f"A{total}"] = "Total"
    ws[f"B{total}"] = f"=SUM(B{first}:B{last})"
    ws[f"C{total}"] = f"=SUM(C{first}:C{last})"
    ws[f"D{total}"] = f"=SUM(D{first}:D{last})"
    ws[f"E{total}"] = f"=SUM(E{first}:E{last})"
    ws[f"H{total}"] = f"=D{total}/B{total}"
    for cell in ws[total]:
        cell.font, cell.fill = Font(bold=True), TOTAL_FILL
    set_formats(ws, first, total, {"B": FMT_INT, "C": FMT_PCT, "D": FMT_MONEY, "E": FMT_PCT,
                                   "F": "0.0", "G": FMT_DEC3, "H": FMT_MONEY, "I": FMT_DEC2})
    ws.conditional_formatting.add(
        f"I{first}:I{last}", DataBarRule(start_type="num", start_value=0, end_type="max", color=BLUE)
    )
    name_range(wb, "RFM_Segment", ws.title, f"$A${first}:$A${last}")
    name_range(wb, "RFM_Customers", ws.title, f"$B${first}:$B${last}")
    name_range(wb, "RFM_Revenue", ws.title, f"$D${first}:$D${last}")

    # Order-frequency table (drives the repeat-rate KPI through SUMIFS).
    f_header = total + 4
    ws[f"A{f_header - 1}"] = "Customers by number of delivered orders"
    ws[f"A{f_header - 1}"].font = Font(bold=True, color=NAVY, size=12)
    header(ws, f_header, ["Orders placed", "Min orders", "% of customers", "Customers", "% of revenue",
                          "Orders", "Revenue", "Revenue per customer", "Median days to 2nd order"])
    buckets = freq[freq.order_bucket != "ALL"].reset_index(drop=True)
    f_first, f_last = f_header + 1, f_header + len(buckets)
    f_total = f_last + 1
    for r, row in enumerate(buckets.itertuples(), start=f_first):
        ws[f"A{r}"] = row.order_bucket
        ws[f"B{r}"] = int(row.order_bucket.split()[0].rstrip("+"))
        ws[f"C{r}"] = f"=D{r}/$D${f_total}"
        ws[f"D{r}"] = int(row.customers)
        ws[f"E{r}"] = f"=G{r}/$G${f_total}"
        ws[f"F{r}"] = int(row.orders)
        ws[f"G{r}"] = float(row.revenue)
        ws[f"H{r}"] = f"=G{r}/D{r}"
        if pd.notna(row.median_days_to_second_order):
            ws[f"I{r}"] = float(row.median_days_to_second_order)
    ws[f"A{f_total}"] = "Total"
    for column in "DFG":
        ws[f"{column}{f_total}"] = f"=SUM({column}{f_first}:{column}{f_last})"
    ws[f"H{f_total}"] = f"=G{f_total}/D{f_total}"
    for cell in ws[f_total]:
        cell.font, cell.fill = Font(bold=True), TOTAL_FILL
    set_formats(ws, f_first, f_total, {"C": FMT_PCT2, "D": FMT_INT, "E": FMT_PCT2, "F": FMT_INT,
                                       "G": FMT_MONEY, "H": FMT_MONEY, "I": "0"})
    name_range(wb, "Freq_MinOrders", ws.title, f"$B${f_first}:$B${f_last}")
    name_range(wb, "Freq_Customers", ws.title, f"$D${f_first}:$D${f_last}")
    name_range(wb, "Freq_Revenue", ws.title, f"$G${f_first}:$G${f_last}")
    ws.freeze_panes = "B5"

    chart = BarChart()
    chart.type, chart.gapWidth = "bar", 60
    chart.add_data(Reference(ws, min_col=3, min_row=4, max_row=last), titles_from_data=True)
    chart.add_data(Reference(ws, min_col=5, min_row=4, max_row=last), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=first, max_row=last))
    colour(chart.series[0], BLUE)
    colour(chart.series[1], ORANGE)
    style_chart(chart, "Share of customers vs share of revenue by segment", "Share", "0%", width=20, height=11)
    chart.x_axis.scaling.orientation = "maxMin"  # first segment at the top
    chart.legend.position = "b"
    ws.add_chart(chart, "K4")


def pareto_sheet(wb: Workbook) -> None:
    df = read("08_category_pareto")
    ws = wb.create_sheet("Category Pareto")
    title(ws, "Category Pareto (ABC)", "Categories ranked by delivered revenue. Share, cumulative share and "
          "ABC class are formulas: A = first 80% of revenue, B = next 15%, C = the rest.")
    header(ws, 4, ["Rank", "Category", "Orders", "Items sold", "Revenue", "Revenue share", "Cumulative share",
                   "ABC class"], [7, 40, 10, 11, 16, 12, 13, 9])
    first, last = 5, 4 + len(df)
    for r, row in enumerate(df.itertuples(), start=first):
        ws[f"A{r}"] = int(row.revenue_rank)
        ws[f"B{r}"] = row.category
        ws[f"C{r}"] = int(row.orders)
        ws[f"D{r}"] = int(row.items_sold)
        ws[f"E{r}"] = float(row.revenue)
        ws[f"F{r}"] = f"=E{r}/SUM($E${first}:$E${last})"
        ws[f"G{r}"] = f"=SUM($F${first}:F{r})"
        ws[f"H{r}"] = f'=IF(G{r}-F{r}<0.8,"A",IF(G{r}-F{r}<0.95,"B","C"))'
        ws[f"H{r}"].alignment = Alignment(horizontal="center")
    set_formats(ws, first, last, {"C": FMT_INT, "D": FMT_INT, "E": FMT_MONEY, "F": FMT_PCT2, "G": FMT_PCT2})
    ws.conditional_formatting.add(
        f"H{first}:H{last}", FormulaRule(formula=[f'$H{first}="A"'], fill=PatternFill("solid", bgColor="CFE3F8"))
    )
    ws.freeze_panes = "C5"
    for name, column in {"Pareto_Category": "B", "Pareto_Revenue": "E", "Pareto_Share": "F",
                         "Pareto_Cumulative": "G", "Pareto_Class": "H"}.items():
        name_range(wb, name, ws.title, f"${column}${first}:${column}${last}")

    top = first + 19
    bars = BarChart()
    bars.type, bars.gapWidth = "bar", 50
    bars.add_data(Reference(ws, min_col=5, min_row=first, max_row=top), titles_from_data=False)
    bars.set_categories(Reference(ws, min_col=2, min_row=first, max_row=top))
    colour(bars.series[0], BLUE)
    style_chart(bars, "Revenue by category, top 20 (R$)", "Revenue", "#,##0", width=20, height=13)
    bars.x_axis.scaling.orientation, bars.legend = "maxMin", None
    ws.add_chart(bars, "J4")

    line = LineChart()
    line.add_data(Reference(ws, min_col=7, min_row=first, max_row=last), titles_from_data=False)
    line.set_categories(Reference(ws, min_col=1, min_row=first, max_row=last))
    colour(line.series[0], ORANGE, line=True)
    style_chart(line, "Cumulative share of revenue by category rank", "Cumulative share", "0%", width=20, height=9)
    line.x_axis.title, line.legend = "Category rank", None
    line.y_axis.scaling.min, line.y_axis.scaling.max = 0, 1
    ws.add_chart(line, "J31")


def delivery_sheet(wb: Workbook) -> None:
    bands, states = read("05_delivery_time_vs_review"), read("06_late_delivery_by_state")
    ws = wb.create_sheet("Delivery & Reviews")
    title(ws, "Delivery performance and customer satisfaction", "Late = delivered after the promised date. "
          "Review score is 1-5; a low review is 1 or 2 stars.")
    header(ws, 4, ["Delivery time", "Reviewed orders", "% of orders", "Avg review", "Low reviews %",
                   "5-star %", "Late %"], [18, 20, 14, 12, 12, 12, 14, 12, 10, 10])
    first, last = 5, 4 + len(bands)
    for r, row in enumerate(bands.itertuples(), start=first):
        ws[f"A{r}"] = row.delivery_band
        ws[f"B{r}"] = int(row.orders)
        ws[f"C{r}"] = f"=B{r}/SUM($B${first}:$B${last})"
        ws[f"D{r}"] = float(row.avg_review)
        ws[f"E{r}"] = row.low_review_rate_pct / 100
        ws[f"F{r}"] = row.five_star_rate_pct / 100
        ws[f"G{r}"] = row.late_rate_pct / 100
    set_formats(ws, first, last, {"B": FMT_INT, "C": FMT_PCT, "D": FMT_DEC3, "E": FMT_PCT, "F": FMT_PCT, "G": FMT_PCT})

    s_header = last + 4
    ws[f"A{s_header - 1}"] = "Late delivery by customer state (sorted by late rate)"
    ws[f"A{s_header - 1}"].font = Font(bold=True, color=NAVY, size=12)
    header(ws, s_header, ["State", "State name", "Region", "Delivered orders", "Late orders", "Late %",
                          "vs national (pp)", "Avg days to deliver", "Avg review", "Late-rate rank"])
    s_first, s_last = s_header + 1, s_header + len(states)
    for r, row in enumerate(states.itertuples(), start=s_first):
        ws[f"A{r}"] = row.state
        ws[f"B{r}"] = row.state_name
        ws[f"C{r}"] = row.region
        ws[f"D{r}"] = int(row.delivered_orders)
        ws[f"E{r}"] = int(row.late_orders)
        ws[f"F{r}"] = f"=E{r}/D{r}"
        ws[f"G{r}"] = f"=(F{r}-SUM($E${s_first}:$E${s_last})/SUM($D${s_first}:$D${s_last}))*100"
        ws[f"H{r}"] = float(row.avg_days_to_deliver)
        ws[f"I{r}"] = float(row.avg_review)
        ws[f"J{r}"] = f"=RANK(F{r},$F${s_first}:$F${s_last})"
    set_formats(ws, s_first, s_last, {"D": FMT_INT, "E": FMT_INT, "F": FMT_PCT2, "G": "+0.00;-0.00",
                                      "H": "0.0", "I": FMT_DEC3})
    ws.conditional_formatting.add(
        f"F{s_first}:F{s_last}", DataBarRule(start_type="num", start_value=0, end_type="max", color=ORANGE)
    )
    ws.freeze_panes = "B5"
    for name, column in {"State_Code": "A", "State_Orders": "D", "State_LateOrders": "E",
                         "State_LateRate": "F", "State_AvgDays": "H", "State_AvgReview": "I"}.items():
        name_range(wb, name, ws.title, f"${column}${s_first}:${column}${s_last}")

    review = BarChart()
    review.add_data(Reference(ws, min_col=4, min_row=first, max_row=last), titles_from_data=False)
    review.set_categories(Reference(ws, min_col=1, min_row=first, max_row=last))
    colour(review.series[0], BLUE)
    style_chart(review, "Average review score by delivery time", "Avg review (1-5)", "0.0", width=18, height=8)
    review.legend, review.gapWidth = None, 60
    review.y_axis.scaling.min, review.y_axis.scaling.max = 0, 5
    ws.add_chart(review, "L4")

    state_chart = BarChart()
    state_chart.add_data(Reference(ws, min_col=6, min_row=s_first, max_row=s_last), titles_from_data=False)
    state_chart.set_categories(Reference(ws, min_col=1, min_row=s_first, max_row=s_last))
    colour(state_chart.series[0], ORANGE)
    style_chart(state_chart, "Late delivery rate by customer state", "Late %", "0%", width=22, height=9)
    state_chart.legend, state_chart.gapWidth = None, 50
    ws.add_chart(state_chart, "L22")


def kpi_sheet(wb: Workbook) -> None:
    kpi = read("00_headline_kpis").set_index("metric").value
    pareto, monthly, states = read("08_category_pareto"), read("01_monthly_revenue_growth"), read("06_late_delivery_by_state")
    ws = wb["KPI Summary"]
    title(ws, "Olist marketplace - executive KPI summary",
          "Every value in column B is an Excel formula over the detail sheets; column C is the control "
          "total computed in SQL; column D confirms they agree.")
    header(ws, 4, ["KPI", "Value (Excel formula)", "SQL control total", "Check", "How it is calculated"],
           [36, 24, 20, 10, 78])

    # (label, formula, control value, number format, tolerance, definition)
    rows = [
        ("Total revenue", "=SUM(Monthly_Revenue)", kpi.total_revenue, FMT_MONEY, 0.006,
         "Item price on delivered orders; freight excluded"),
        ("Delivered orders", "=SUM(Monthly_Orders)", kpi.delivered_orders, FMT_INT, 0.5,
         "Orders with status = delivered"),
        ("Average order value", "=B5/B6", kpi.avg_order_value, FMT_MONEY, 0.006, "Total revenue / delivered orders"),
        ("Items sold", "=SUM(Monthly_Items)", kpi.items_sold, FMT_INT, 0.5, "Order lines on delivered orders"),
        ("Items per order", "=B8/B6", kpi.avg_items_per_order, FMT_DEC3, 0.0006, "Items sold / delivered orders"),
        ("Freight as % of revenue", "=SUM(Monthly_Freight)/B5", kpi.freight_pct_of_revenue / 100, FMT_PCT2,
         0.00006, "Freight charged / total revenue"),
        ("Customers", "=SUM(Freq_Customers)", kpi.customers, FMT_INT, 0.5,
         "Distinct people (customer_unique_id) with a delivered order"),
        ("Repeat customers", '=SUMIFS(Freq_Customers,Freq_MinOrders,">=2")', kpi.repeat_customers, FMT_INT, 0.5,
         "Customers with 2 or more delivered orders (SUMIFS on the order-frequency table)"),
        ("Repeat customer rate", "=B12/B11", kpi.repeat_customer_rate_pct / 100, FMT_PCT2, 0.00006,
         "Repeat customers / customers"),
        ("Revenue per customer", "=B5/B11", kpi.revenue_per_customer, FMT_MONEY, 0.006, "Total revenue / customers"),
        ("Late delivery rate", "=SUM(Monthly_LateOrders)/SUM(Monthly_OrdersWithDate)",
         kpi.late_delivery_rate_pct / 100, FMT_PCT2, 0.00006,
         "Orders delivered after the promised date / delivered orders with a delivery date"),
        ("Average review score", "=SUM(Monthly_ReviewSum)/SUM(Monthly_Reviewed)", kpi.avg_review_score, FMT_DEC3,
         0.0006, "Mean review score (1-5) of reviewed delivered orders"),
        ("Categories producing 80% of revenue", '=COUNTIF(Pareto_Class,"A")', int((pareto.abc_class == "A").sum()),
         FMT_INT, 0.5, f"Count of class-A categories out of {len(pareto)}"),
        ("Largest category share of revenue", "=MAX(Pareto_Share)", pareto.revenue_share_pct.max() / 100, FMT_PCT2,
         0.00006, "Revenue share of the top category"),
    ]
    first = 5
    for r, (label, formula, control, number_format, tolerance, definition) in enumerate(rows, start=first):
        ws[f"A{r}"], ws[f"B{r}"], ws[f"C{r}"], ws[f"E{r}"] = label, formula, float(control), definition
        ws[f"D{r}"] = f'=IF(ABS(B{r}-C{r})<={tolerance},"OK","CHECK")'
        ws[f"B{r}"].number_format = ws[f"C{r}"].number_format = number_format
        ws[f"B{r}"].font = Font(bold=True, size=12, color=NAVY)
        ws[f"D{r}"].alignment = Alignment(horizontal="center")
    last = first + len(rows) - 1
    ws[f"A{last + 1}"] = "Reconciliation status"
    ws[f"B{last + 1}"] = (
        f'=IF(COUNTIF(D{first}:D{last},"OK")=ROWS(D{first}:D{last}),"All KPIs reconcile to SQL","Differences found")'
    )
    ws[f"A{last + 1}"].font = ws[f"B{last + 1}"].font = Font(bold=True)
    ws.conditional_formatting.add(
        f"D{first}:D{last}", FormulaRule(formula=[f'$D{first}="OK"'], font=Font(color="1E7B34", bold=True))
    )
    ws.conditional_formatting.add(
        f"D{first}:D{last}", FormulaRule(formula=[f'$D{first}="CHECK"'], font=Font(color="C0392B", bold=True))
    )
    name_range(wb, "KPI_TotalRevenue", ws.title, "$B$5")
    name_range(wb, "KPI_DeliveredOrders", ws.title, "$B$6")

    # ---- month explorer: pick a month, look everything up ----
    m = last + 4
    ws[f"A{m - 1}"] = "Month explorer"
    ws[f"A{m - 1}"].font = Font(bold=True, color=NAVY, size=12)
    ws[f"A{m}"], ws[f"B{m}"] = "Select a month (dropdown)", month_to_date(monthly.year_month.iloc[-1])
    ws[f"B{m}"].number_format, ws[f"B{m}"].fill = FMT_MONTH, INPUT_FILL
    name_range(wb, "SelectedMonth", ws.title, f"$B${m}")
    month_list = DataValidation(type="list", formula1="=Monthly_Month", allow_blank=False)
    ws.add_data_validation(month_list)
    month_list.add(ws[f"B{m}"])
    lookups = [
        ("Revenue", "=_xlfn.XLOOKUP(SelectedMonth,Monthly_Month,Monthly_Revenue)", FMT_MONEY, "XLOOKUP"),
        ("Orders", "=INDEX(Monthly_Orders,MATCH(SelectedMonth,Monthly_Month,0))", FMT_INT, "INDEX / MATCH"),
        ("Average order value", "=INDEX(Monthly_AOV,MATCH(SelectedMonth,Monthly_Month,0))", FMT_MONEY, "INDEX / MATCH"),
        ("Revenue vs previous month", '=IFERROR(INDEX(Monthly_MoM,MATCH(SelectedMonth,Monthly_Month,0))+0,"n/a")',
         FMT_PCT, "INDEX / MATCH; n/a when the previous month is partial"),
        ("Late delivery rate", "=_xlfn.XLOOKUP(SelectedMonth,Monthly_Month,Monthly_LatePct)", FMT_PCT2, "XLOOKUP"),
        ("Average review score", "=_xlfn.XLOOKUP(SelectedMonth,Monthly_Month,Monthly_AvgReview)", FMT_DEC3, "XLOOKUP"),
        ("Share of all-time revenue", f"=B{m + 1}/KPI_TotalRevenue", FMT_PCT2, "Month revenue / total revenue"),
    ]
    for r, (label, formula, number_format, note) in enumerate(lookups, start=m + 1):
        ws[f"A{r}"], ws[f"B{r}"], ws[f"E{r}"] = label, formula, note
        ws[f"B{r}"].number_format = number_format

    # ---- state explorer ----
    s = m + len(lookups) + 4
    ws[f"A{s - 1}"] = "State explorer"
    ws[f"A{s - 1}"].font = Font(bold=True, color=NAVY, size=12)
    ws[f"A{s}"], ws[f"B{s}"] = "Select a state (dropdown)", "RJ"
    ws[f"B{s}"].fill = INPUT_FILL
    name_range(wb, "SelectedState", ws.title, f"$B${s}")
    state_list = DataValidation(type="list", formula1="=State_Code", allow_blank=False)
    ws.add_data_validation(state_list)
    state_list.add(ws[f"B{s}"])
    state_lookups = [
        ("Delivered orders", "=_xlfn.XLOOKUP(SelectedState,State_Code,State_Orders)", FMT_INT, "XLOOKUP"),
        ("Late delivery rate", "=INDEX(State_LateRate,MATCH(SelectedState,State_Code,0))", FMT_PCT2, "INDEX / MATCH"),
        ("Late rate vs national (pp)", f"=(B{s + 2}-B15)*100", "+0.00;-0.00", "State rate - national rate"),
        ("Share of all late orders", "=SUMIFS(State_LateOrders,State_Code,SelectedState)/SUM(State_LateOrders)",
         FMT_PCT2, "SUMIFS"),
        ("Average days to deliver", "=_xlfn.XLOOKUP(SelectedState,State_Code,State_AvgDays)", "0.0", "XLOOKUP"),
        ("Average review score", "=_xlfn.XLOOKUP(SelectedState,State_Code,State_AvgReview)", FMT_DEC3, "XLOOKUP"),
    ]
    for r, (label, formula, number_format, note) in enumerate(state_lookups, start=s + 1):
        ws[f"A{r}"], ws[f"B{r}"], ws[f"E{r}"] = label, formula, note
        ws[f"B{r}"].number_format = number_format
    assert len(states) == 27 and ws["A15"].value == "Late delivery rate"
    ws.freeze_panes = "A5"


def about_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("About")
    title(ws, "About this workbook", "Generated by src/build_excel.py - do not edit by hand; re-run python run_all.py.")
    lines = [
        ("Source", "Olist Brazilian E-Commerce public dataset (about 100k orders, Sep-2016 to Oct-2018)."),
        ("Pipeline", "CSV -> DuckDB star schema -> SQL in sql/analysis -> outputs/sql/*.csv -> this workbook."),
        ("Revenue", "Item price on orders with status = delivered. Freight is reported separately."),
        ("Customer", "customer_unique_id (a person). Olist's customer_id is issued per order."),
        ("Late delivery", "Delivered on a calendar date after the promised (estimated) delivery date."),
        ("Repeat customer", "A customer with 2 or more delivered orders."),
        ("Complete months", "Jan-2017 to Aug-2018. Earlier and later months hold only a handful of orders."),
        ("Yellow cells", "Inputs: change the month or state on the KPI Summary sheet."),
        ("Named ranges", "Formulas -> Name Manager lists every range used by the KPI formulas."),
        ("Currency", "Brazilian real (R$)."),
    ]
    for r, (label, text) in enumerate(lines, start=4):
        ws[f"A{r}"], ws[f"B{r}"] = label, text
        ws[f"A{r}"].font = Font(bold=True)
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 20, 110


def main() -> None:
    wb = Workbook()
    wb.active.title = "KPI Summary"  # created first so it is the first tab; filled last
    monthly_sheet(wb)
    cohort_sheet(wb)
    rfm_sheet(wb)
    pareto_sheet(wb)
    delivery_sheet(wb)
    kpi_sheet(wb)
    about_sheet(wb)
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = NAVY if ws.title == "KPI Summary" else BLUE
    REPORT_DIR.mkdir(exist_ok=True)
    wb.save(EXCEL_REPORT)

    formulas = sum(
        1 for ws in wb.worksheets for row in ws.iter_rows() for c in row
        if isinstance(c.value, str) and c.value.startswith("=")
    )
    charts = sum(len(ws._charts) for ws in wb.worksheets)
    print(f"  {EXCEL_REPORT.name}: {len(wb.worksheets)} sheets, {formulas} formulas, "
          f"{charts} charts, {len(wb.defined_names)} named ranges")


if __name__ == "__main__":
    main()
