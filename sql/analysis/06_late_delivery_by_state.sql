-- =============================================================================
-- 06  Where are delivery promises being broken? Late-delivery rate by customer state.
-- Each state is ranked and compared with the national rate; the last columns show
-- how much of ALL late orders each state accounts for (volume matters, not just rate).
-- =============================================================================
WITH by_state AS (
    SELECT
        g.state,
        g.state_name,
        g.region,
        count(*)                               AS delivered_orders,
        sum(o.is_late)                         AS late_orders,
        avg(o.is_late)                         AS late_rate,
        avg(o.days_to_deliver)                 AS avg_days_to_deliver,
        median(o.days_to_deliver)              AS median_days_to_deliver,
        avg(o.estimated_days)                  AS avg_promised_days,
        avg(o.review_score)                    AS avg_review,
        sum(o.freight_value) / sum(o.items_value) AS freight_to_revenue
    FROM fact_orders AS o
    JOIN dim_geography AS g USING (geography_key)
    WHERE o.is_delivered = 1
      AND o.has_delivery_date = 1
    GROUP BY g.state, g.state_name, g.region
)
SELECT
    state,
    state_name,
    region,
    delivered_orders,
    late_orders,
    round(100.0 * late_rate, 2)                                              AS late_rate_pct,
    rank() OVER (ORDER BY late_rate DESC)                                    AS late_rate_rank,
    round(100.0 * (late_rate - sum(late_orders) OVER () / sum(delivered_orders) OVER ()), 2)
                                                                             AS vs_national_pp,
    round(100.0 * late_orders / sum(late_orders) OVER (), 2)                 AS pct_of_all_late_orders,
    round(100.0 * delivered_orders / sum(delivered_orders) OVER (), 2)       AS pct_of_all_orders,
    round(avg_days_to_deliver, 1)                                            AS avg_days_to_deliver,
    median_days_to_deliver,
    round(avg_promised_days, 1)                                              AS avg_promised_days,
    round(avg_review, 3)                                                     AS avg_review,
    round(100.0 * freight_to_revenue, 1)                                     AS freight_pct_of_revenue
FROM by_state
ORDER BY late_rate DESC;
