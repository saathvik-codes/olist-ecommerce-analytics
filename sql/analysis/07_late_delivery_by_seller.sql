-- =============================================================================
-- 07  Which sellers drive late deliveries?
-- Sellers with at least 50 delivered orders. Two different "late" measures:
--   late_delivery_rate = customer received it after the promised date (outcome)
--   late_handoff_rate  = seller gave it to the carrier after the shipping limit
--                        (the part the seller actually controls)
-- An order with items from several sellers counts once for each of those sellers.
-- =============================================================================
WITH seller_orders AS (
    SELECT
        i.seller_key,
        i.order_id,
        sum(i.price)              AS revenue,
        max(i.shipping_limit_at)  AS shipping_limit_at
    FROM fact_order_items AS i
    WHERE i.is_delivered = 1
    GROUP BY i.seller_key, i.order_id
),
by_seller AS (
    SELECT
        so.seller_key,
        count(*)                                                    AS delivered_orders,
        sum(so.revenue)                                             AS revenue,
        sum(o.is_late)                                              AS late_orders,
        avg(o.is_late)                                              AS late_delivery_rate,
        avg(CAST(o.shipped_at > so.shipping_limit_at AS INTEGER))   AS late_handoff_rate,
        avg(o.review_score)                                         AS avg_review
    FROM seller_orders AS so
    JOIN fact_orders AS o USING (order_id)
    WHERE o.has_delivery_date = 1
    GROUP BY so.seller_key
    HAVING count(*) >= 50
)
SELECT
    rank() OVER (ORDER BY b.late_delivery_rate DESC, b.delivered_orders DESC) AS late_rate_rank,
    s.seller_id,
    s.seller_state,
    b.delivered_orders,
    round(b.revenue, 2)                                         AS revenue,
    b.late_orders,
    round(100.0 * b.late_delivery_rate, 2)                      AS late_delivery_rate_pct,
    round(100.0 * b.late_handoff_rate, 2)                       AS late_handoff_rate_pct,
    round(b.avg_review, 3)                                      AS avg_review,
    round(100.0 * b.late_orders / sum(b.late_orders) OVER (), 2) AS pct_of_late_orders_in_group,
    ntile(10) OVER (ORDER BY b.late_delivery_rate DESC, b.delivered_orders DESC) AS late_rate_decile
FROM by_seller AS b
JOIN dim_seller AS s USING (seller_key)
ORDER BY late_rate_rank;
