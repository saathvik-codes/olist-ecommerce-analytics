"""Star-schema integrity: keys are unique and non-null, and no fact row is orphaned."""
import pandas as pd
import pytest

from config import OUTPUT_DIR, RAW_FILES
from conftest import scalar

# (table, key expression): surrogate / grain keys and the natural keys behind them
UNIQUE_KEYS = [
    ("dim_date", "date_key"),
    ("dim_date", "date"),
    ("dim_customer", "customer_key"),
    ("dim_customer", "customer_unique_id"),
    ("dim_geography", "geography_key"),
    ("dim_geography", "zip_code_prefix"),
    ("dim_product", "product_key"),
    ("dim_product", "product_id"),
    ("dim_seller", "seller_key"),
    ("dim_seller", "seller_id"),
    ("fact_orders", "order_id"),
    ("fact_order_items", "(order_id, order_item_id)"),
]

FOREIGN_KEYS = [
    ("fact_orders", "customer_key", "dim_customer", "customer_key"),
    ("fact_orders", "geography_key", "dim_geography", "geography_key"),
    ("fact_orders", "purchase_date_key", "dim_date", "date_key"),
    ("fact_order_items", "product_key", "dim_product", "product_key"),
    ("fact_order_items", "seller_key", "dim_seller", "seller_key"),
    ("fact_order_items", "customer_key", "dim_customer", "customer_key"),
    ("fact_order_items", "geography_key", "dim_geography", "geography_key"),
    ("fact_order_items", "purchase_date_key", "dim_date", "date_key"),
    ("fact_order_items", "order_id", "fact_orders", "order_id"),
]


@pytest.mark.parametrize("table, key", UNIQUE_KEYS)
def test_key_is_unique_and_not_null(con, table, key):
    rows, distinct, nulls = con.execute(
        f"SELECT count(*), count(DISTINCT {key}), count(*) FILTER (WHERE {key} IS NULL) FROM {table}"
    ).fetchone()
    assert rows > 0
    assert rows == distinct, f"{table}.{key} is not unique"
    assert nulls == 0, f"{table}.{key} contains nulls"


@pytest.mark.parametrize("fact, fk, dim, pk", FOREIGN_KEYS)
def test_no_orphan_fact_rows(con, fact, fk, dim, pk):
    orphans = scalar(
        con,
        f"SELECT count(*) FROM {fact} AS f LEFT JOIN {dim} AS d ON d.{pk} = f.{fk} "
        f"WHERE f.{fk} IS NULL OR d.{pk} IS NULL",
    )
    assert orphans == 0, f"{orphans} rows in {fact} have no match in {dim}"


def test_facts_keep_every_source_row(con):
    assert scalar(con, "SELECT count(*) FROM fact_orders") == RAW_FILES["olist_orders_dataset.csv"]
    assert scalar(con, "SELECT count(*) FROM fact_order_items") == RAW_FILES["olist_order_items_dataset.csv"]
    assert scalar(con, "SELECT count(*) FROM dim_product") == RAW_FILES["olist_products_dataset.csv"]
    assert scalar(con, "SELECT count(*) FROM dim_seller") == RAW_FILES["olist_sellers_dataset.csv"]


def test_revenue_survives_the_model_unchanged(con):
    raw = scalar(
        con,
        "SELECT sum(i.price) FROM raw_order_items i JOIN raw_orders o USING (order_id) "
        "WHERE o.order_status = 'delivered'",
    )
    items = scalar(con, "SELECT sum(price) FROM fact_order_items WHERE is_delivered = 1")
    orders = scalar(con, "SELECT sum(items_value) FROM fact_orders WHERE is_delivered = 1")
    assert items == pytest.approx(raw, abs=0.01)
    assert orders == pytest.approx(raw, abs=0.01)


def test_date_dimension_is_gap_free(con):
    days, first, last = con.execute("SELECT count(*), min(date), max(date) FROM dim_date").fetchone()
    assert days == (last - first).days + 1


def test_delivery_flags_are_consistent(con):
    bad = scalar(
        con,
        """
        SELECT count(*) FROM fact_orders
        WHERE (has_delivery_date = 1) <> (is_late IS NOT NULL)
           OR (coalesce(is_late, 0) = 1) <> (delivery_status = 'Late')
           OR (has_delivery_date = 1 AND days_to_deliver < 0)
           OR (is_delivered = 0 AND customer_order_seq IS NOT NULL)
           OR (is_delivered = 1 AND customer_order_seq IS NULL)
        """,
    )
    assert bad == 0


def test_data_quality_report_has_no_star_schema_failures():
    report = pd.read_csv(OUTPUT_DIR / "data_quality_report.csv")
    star = report[report.check_group == "Star schema"]
    assert len(star) >= 6
    assert (star.affected_rows == 0).all()
