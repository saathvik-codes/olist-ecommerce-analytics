-- =============================================================================
-- 05  Does slower delivery hurt satisfaction?
-- Review score by delivery-time band, with each band compared to the overall
-- average and split by whether the promise date was met.
-- =============================================================================
WITH reviewed AS (
    SELECT
        days_to_deliver,
        is_late,
        review_score,
        delivery_band
    FROM fact_orders
    WHERE is_delivered = 1
      AND has_delivery_date = 1
      AND review_score IS NOT NULL
),
by_band AS (
    SELECT
        delivery_band,
        count(*)                                         AS orders,
        avg(review_score)                                AS avg_review,
        avg(CAST(review_score <= 2 AS INTEGER))          AS low_review_rate,
        avg(CAST(review_score = 5 AS INTEGER))           AS five_star_rate,
        avg(is_late)                                     AS late_rate,
        avg(review_score) FILTER (WHERE is_late = 0)     AS avg_review_on_time,
        avg(review_score) FILTER (WHERE is_late = 1)     AS avg_review_late
    FROM reviewed
    GROUP BY delivery_band
)
SELECT
    delivery_band,
    orders,
    round(100.0 * orders / sum(orders) OVER (), 2)                         AS pct_of_orders,
    round(100.0 * sum(orders) OVER (ORDER BY delivery_band) / sum(orders) OVER (), 2) AS cumulative_pct_of_orders,
    round(avg_review, 3)                                                   AS avg_review,
    round(avg_review - sum(avg_review * orders) OVER () / sum(orders) OVER (), 3) AS vs_overall_avg,
    round(100.0 * low_review_rate, 2)                                      AS low_review_rate_pct,
    round(100.0 * five_star_rate, 2)                                       AS five_star_rate_pct,
    round(100.0 * late_rate, 2)                                            AS late_rate_pct,
    round(avg_review_on_time, 3)                                           AS avg_review_on_time,
    round(avg_review_late, 3)                                              AS avg_review_late
FROM by_band
ORDER BY delivery_band;
