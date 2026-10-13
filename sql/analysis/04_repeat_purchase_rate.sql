-- =============================================================================
-- 04  How many customers buy again, how fast, and how much do they contribute?
-- One row per "number of delivered orders" bucket, plus an ALL row (ROLLUP).
-- Days to second order uses LEAD() over each customer's order history.
-- =============================================================================
WITH ordered AS (
    SELECT
        customer_key,
        customer_order_seq,
        purchase_date,
        items_value,
        lead(purchase_date) OVER (PARTITION BY customer_key ORDER BY customer_order_seq) AS next_purchase_date
    FROM fact_orders
    WHERE is_delivered = 1
),
per_customer AS (
    SELECT
        customer_key,
        count(*)         AS orders,
        sum(items_value) AS revenue,
        max(date_diff('day', purchase_date, next_purchase_date))
            FILTER (WHERE customer_order_seq = 1) AS days_to_second_order
    FROM ordered
    GROUP BY customer_key
),
bucketed AS (
    SELECT
        *,
        CASE WHEN orders >= 4 THEN '4+ orders'
             WHEN orders = 1  THEN '1 order'
             ELSE orders || ' orders' END AS order_bucket
    FROM per_customer
)
SELECT
    coalesce(b.order_bucket, 'ALL')                             AS order_bucket,
    count(*)                                                    AS customers,
    round(100.0 * count(*) / max(t.total_customers), 2)         AS pct_of_customers,
    sum(b.orders)                                               AS orders,
    round(sum(b.revenue), 2)                                    AS revenue,
    round(100.0 * sum(b.revenue) / max(t.total_revenue), 2)     AS pct_of_revenue,
    round(sum(b.revenue) / count(*), 2)                         AS revenue_per_customer,
    median(b.days_to_second_order)                              AS median_days_to_second_order,
    round(100.0 * count(*) FILTER (WHERE b.days_to_second_order <= 30)
          / nullif(count(b.days_to_second_order), 0), 1)        AS pct_second_order_within_30d
FROM bucketed AS b
CROSS JOIN (SELECT count(*) AS total_customers, sum(revenue) AS total_revenue
            FROM per_customer) AS t
GROUP BY ROLLUP (b.order_bucket)
ORDER BY order_bucket;
