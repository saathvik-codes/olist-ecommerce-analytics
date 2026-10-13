-- =============================================================================
-- 03  Which customers are worth what? RFM segmentation.
-- Recency   = days from the customer's last delivered order to the snapshot date
--             (the day after the last delivered purchase in the data).
-- Frequency = number of delivered orders.
-- Monetary  = lifetime item revenue.
-- R and M are scored 1-5 by quintile (NTILE). F is NOT a quintile: 97% of customers
-- have exactly one order, so NTILE would split identical customers at random.
-- F is scored by rule instead: 1 order = 1, 2 orders = 3, 3+ orders = 5.
-- Builds mart_customer_rfm (one row per customer) and returns the segment summary.
-- =============================================================================
CREATE OR REPLACE TABLE mart_customer_rfm AS
WITH snapshot AS (
    SELECT max(purchase_date) + 1 AS snapshot_date
    FROM fact_orders
    WHERE is_delivered = 1
),
customer_rfm AS (
    SELECT
        c.customer_key,
        date_diff('day', c.last_order_date, s.snapshot_date) AS recency_days,
        c.delivered_orders                                   AS frequency,
        c.lifetime_revenue                                   AS monetary
    FROM dim_customer AS c
    CROSS JOIN snapshot AS s
    WHERE c.delivered_orders >= 1
),
scored AS (
    SELECT
        *,
        6 - ntile(5) OVER (ORDER BY recency_days, customer_key) AS r_score,  -- 5 = most recent
        CASE WHEN frequency >= 3 THEN 5 WHEN frequency = 2 THEN 3 ELSE 1 END AS f_score,
        ntile(5) OVER (ORDER BY monetary, customer_key)          AS m_score   -- 5 = top spenders
    FROM customer_rfm
)
SELECT
    *,
    CASE
        WHEN f_score >= 3 AND r_score >= 4              THEN '1. Champions (repeat, recent)'
        WHEN f_score >= 3 AND r_score BETWEEN 2 AND 3   THEN '2. Loyal, cooling'
        WHEN f_score >= 3                               THEN '3. Repeat buyers, lapsed'
        WHEN r_score >= 4 AND m_score >= 4              THEN '4. New high-value'
        WHEN r_score >= 4                               THEN '5. New low-value'
        WHEN r_score BETWEEN 2 AND 3 AND m_score >= 4   THEN '6. Cooling high-value'
        WHEN r_score BETWEEN 2 AND 3                    THEN '7. Cooling low-value'
        WHEN m_score >= 4                               THEN '8. Lost high-value'
        ELSE                                                 '9. Lost low-value'
    END AS rfm_segment
FROM scored;

SELECT
    rfm_segment,
    count(*)                                              AS customers,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2)    AS pct_of_customers,
    round(sum(monetary), 2)                               AS revenue,
    round(100.0 * sum(monetary) / sum(sum(monetary)) OVER (), 2) AS pct_of_revenue,
    round(avg(recency_days), 1)                           AS avg_recency_days,
    round(avg(frequency), 3)                              AS avg_orders,
    round(avg(monetary), 2)                               AS avg_revenue_per_customer
FROM mart_customer_rfm
GROUP BY rfm_segment
ORDER BY rfm_segment;
