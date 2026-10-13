"""Central paths and constants shared by every pipeline step."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"

SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
SQL_OUTPUT_DIR = OUTPUT_DIR / "sql"
STATS_OUTPUT_DIR = OUTPUT_DIR / "stats"
CHART_DIR = OUTPUT_DIR / "charts"
REPORT_DIR = ROOT / "reports"
POWERBI_DIR = ROOT / "powerbi"
POWERBI_DATA_DIR = POWERBI_DIR / "data"

EXCEL_REPORT = REPORT_DIR / "Olist_Executive_Report.xlsx"

# Public mirror of the Olist dataset published by Olist itself on GitHub.
SOURCE_BASE_URL = (
    "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
)

# file name -> row count published for the Olist dataset (verified after download)
RAW_FILES = {
    "olist_orders_dataset.csv": 99_441,
    "olist_order_items_dataset.csv": 112_650,
    "olist_order_payments_dataset.csv": 103_886,
    "olist_order_reviews_dataset.csv": 99_224,
    "olist_customers_dataset.csv": 99_441,
    "olist_sellers_dataset.csv": 3_095,
    "olist_products_dataset.csv": 32_951,
    "olist_geolocation_dataset.csv": 1_000_163,
    "product_category_name_translation.csv": 71,
}

STAR_TABLES = [
    "dim_date",
    "dim_customer",
    "dim_geography",
    "dim_product",
    "dim_seller",
    "fact_orders",
    "fact_order_items",
]
