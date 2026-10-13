-- =============================================================================
-- 00  Headline KPIs: the single source of truth every other deliverable
--     (Excel report, Power BI expected values, README) is reconciled against.
-- Definitions
--   revenue        = item price on delivered orders (freight reported separately)
--   late delivery  = delivered on a date after the promised (estimated) date
--   repeat customer= a person (customer_unique_id) with 2+ delivered orders
-- =============================================================================
WITH orders AS (
    SELECT * FROM fact_orders WHERE is_delivered = 1
),
order_kpis AS (
    SELECT
        count(*)                                   AS delivered_orders,
        sum(items_value)                           AS revenue,
        sum(freight_value)                         AS freight,
        sum(item_count)                            AS items_sold,
        count(DISTINCT customer_key)               AS customers,
        sum(has_delivery_date)                     AS orders_with_delivery_date,
        sum(is_late)                               AS late_orders,
        avg(days_to_deliver)                       AS avg_days_to_deliver,
        median(days_to_deliver)                    AS median_days_to_deliver,
        count(review_score)                        AS reviewed_orders,
        avg(review_score)                          AS avg_review_score,
        sum(is_low_review)                         AS low_review_orders
    FROM orders
),
customer_kpis AS (
    SELECT count(*) FILTER (WHERE delivered_orders >= 2) AS repeat_customers
    FROM dim_customer
),
all_orders AS (
    SELECT count(*) AS orders_placed FROM fact_orders
)
SELECT metric, value
FROM order_kpis, customer_kpis, all_orders,
LATERAL (
    VALUES
        ('orders_placed',              orders_placed::DOUBLE),
        ('delivered_orders',           delivered_orders),
        ('delivered_order_rate_pct',   round(100.0 * delivered_orders / orders_placed, 2)),
        ('total_revenue',              round(revenue, 2)),
        ('total_freight',              round(freight, 2)),
        ('freight_pct_of_revenue',     round(100.0 * freight / revenue, 2)),
        ('items_sold',                 items_sold),
        ('avg_order_value',            round(revenue / delivered_orders, 2)),
        ('avg_items_per_order',        round(items_sold / delivered_orders, 3)),
        ('customers',                  customers),
        ('repeat_customers',           repeat_customers),
        ('repeat_customer_rate_pct',   round(100.0 * repeat_customers / customers, 2)),
        ('revenue_per_customer',       round(revenue / customers, 2)),
        ('orders_with_delivery_date',  orders_with_delivery_date),
        ('late_orders',                late_orders),
        ('late_delivery_rate_pct',     round(100.0 * late_orders / orders_with_delivery_date, 2)),
        ('avg_days_to_deliver',        round(avg_days_to_deliver, 2)),
        ('median_days_to_deliver',     median_days_to_deliver),
        ('reviewed_orders',            reviewed_orders),
        ('avg_review_score',           round(avg_review_score, 3)),
        ('low_review_orders',          low_review_orders),
        ('low_review_rate_pct',        round(100.0 * low_review_orders / reviewed_orders, 2))
) AS kpi (metric, value);
