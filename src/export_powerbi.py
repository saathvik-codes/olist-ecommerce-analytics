"""Export the star schema as CSVs for Power BI (powerbi/data/).

Only the columns the report needs are exported. Dates are written as ISO yyyy-mm-dd so
Power BI parses them the same way under any regional setting. Flags are 0/1 integers so
they can be summed in DAX.
"""
from config import POWERBI_DATA_DIR
from db import connect

EXPORTS = {
    "dim_date": """
        SELECT date_key, date, year, quarter, year_quarter, month, month_name, year_month,
               month_start, month_index, day_of_week, day_name, is_weekend, is_analysis_window
        FROM dim_date ORDER BY date_key
    """,
    # RFM scores from sql/analysis/03 are attached so segments can be sliced in the report.
    "dim_customer": """
        SELECT c.customer_key, c.customer_unique_id, c.customer_city, c.customer_state,
               c.orders_placed, c.delivered_orders, c.first_order_date, c.last_order_date,
               c.cohort_month, c.lifetime_revenue, c.is_repeat_customer,
               r.recency_days, r.r_score, r.f_score, r.m_score,
               coalesce(r.rfm_segment, 'No delivered order') AS rfm_segment
        FROM dim_customer AS c
        LEFT JOIN mart_customer_rfm AS r USING (customer_key)
        ORDER BY c.customer_key
    """,
    "dim_geography": """
        SELECT geography_key, zip_code_prefix, city, state, state_name, region, latitude, longitude
        FROM dim_geography ORDER BY geography_key
    """,
    "dim_product": """
        SELECT product_key, product_id, category, category_pt, photos_qty, weight_g,
               volume_cm3, weight_band
        FROM dim_product ORDER BY product_key
    """,
    "dim_seller": """
        SELECT seller_key, seller_id, seller_zip_code_prefix, seller_city, seller_state, seller_region
        FROM dim_seller ORDER BY seller_key
    """,
    "fact_orders": """
        SELECT order_id, customer_key, geography_key, purchase_date_key, purchase_date,
               order_status, is_delivered, item_count, seller_count, items_value, freight_value,
               order_value, payment_value, payment_type, payment_installments,
               has_delivery_date, days_to_deliver, estimated_days, delivery_delay_days,
               is_late, delivery_status, delivery_band, review_score, is_low_review,
               customer_order_seq, months_since_first_order
        FROM fact_orders ORDER BY purchased_at, order_id
    """,
    "fact_order_items": """
        SELECT order_id, order_item_id, product_key, seller_key, customer_key, geography_key,
               purchase_date_key, purchase_date, order_status, is_delivered, price,
               freight_value, delivery_status, is_late, review_score
        FROM fact_order_items ORDER BY order_id, order_item_id
    """,
}


def main() -> None:
    POWERBI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    for table, query in EXPORTS.items():
        target = POWERBI_DATA_DIR / f"{table}.csv"
        con.execute(
            f"COPY ({query}) TO '{target.as_posix()}' (HEADER, DELIMITER ',', DATEFORMAT '%Y-%m-%d')"
        )
        rows = con.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]
        print(f"  {table:<18}{rows:>9,} rows  {target.stat().st_size / 1e6:6.1f} MB")
    con.close()


if __name__ == "__main__":
    main()
