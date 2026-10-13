-- =============================================================================
-- 01  How is the business trending month to month?
-- Monthly orders, revenue, AOV, MoM / YoY growth, rolling 3-month and cumulative
-- revenue. Growth figures are only computed inside Jan-2017..Aug-2018 because the
-- months outside it are partial (see the data-quality report).
-- =============================================================================
WITH monthly AS (
    SELECT
        d.year_month,
        d.month_start,
        max(d.is_analysis_window)                         AS is_complete_month,
        count(*)                                          AS orders,
        count(DISTINCT o.customer_key)                    AS customers,
        count(*) FILTER (WHERE o.customer_order_seq = 1)  AS new_customers,
        round(sum(o.items_value), 2)                      AS revenue,
        round(sum(o.freight_value), 2)                    AS freight,
        sum(o.item_count)                                 AS items_sold,
        sum(o.has_delivery_date)                          AS orders_with_delivery_date,
        sum(o.is_late)                                    AS late_orders,
        count(o.review_score)                             AS reviewed_orders,
        sum(o.review_score)                               AS review_score_sum
    FROM fact_orders AS o
    JOIN dim_date AS d ON d.date_key = o.purchase_date_key
    WHERE o.is_delivered = 1
    GROUP BY d.year_month, d.month_start
),
with_history AS (
    SELECT
        *,
        -- Compare against the calendar month, not simply the previous row,
        -- so a missing month can never be mistaken for "last month".
        lag(revenue)     OVER w AS prev_row_revenue,
        lag(month_start) OVER w AS prev_row_month,
        lag(revenue, 12)     OVER w AS year_ago_row_revenue,
        lag(month_start, 12) OVER w AS year_ago_row_month,
        sum(revenue) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)  AS rolling_3m_sum,
        count(*)     OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)  AS rolling_3m_months
    FROM monthly
    WHERE is_complete_month = 1
    WINDOW w AS (ORDER BY month_start)
)
SELECT
    m.year_month,
    m.is_complete_month,
    m.orders,
    m.customers,
    m.new_customers,
    m.revenue,
    m.freight,
    m.items_sold,
    round(m.revenue / m.orders, 2)                                   AS avg_order_value,
    CASE WHEN h.prev_row_month = m.month_start - INTERVAL 1 MONTH
         THEN round(100.0 * (m.revenue / h.prev_row_revenue - 1), 2) END      AS revenue_mom_pct,
    CASE WHEN h.year_ago_row_month = m.month_start - INTERVAL 12 MONTH
         THEN round(100.0 * (m.revenue / h.year_ago_row_revenue - 1), 2) END  AS revenue_yoy_pct,
    CASE WHEN h.rolling_3m_months = 3 THEN round(h.rolling_3m_sum, 2) END    AS revenue_rolling_3m,
    round(sum(m.revenue) OVER (ORDER BY m.month_start), 2)           AS cumulative_revenue,
    m.orders_with_delivery_date,
    m.late_orders,
    round(100.0 * m.late_orders / m.orders_with_delivery_date, 2)    AS late_delivery_rate_pct,
    m.reviewed_orders,
    m.review_score_sum,
    round(m.review_score_sum / m.reviewed_orders, 3)                 AS avg_review_score
FROM monthly AS m
LEFT JOIN with_history AS h USING (year_month)
ORDER BY m.year_month;
