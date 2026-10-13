-- =============================================================================
-- 11  How dependent is the marketplace on its biggest sellers?
-- Sellers ranked by delivered revenue and grouped into tiers; the HHI column
-- (sum of squared revenue shares x 10,000) is the standard concentration index:
-- below 1,500 is considered unconcentrated.
-- =============================================================================
WITH seller_revenue AS (
    SELECT
        seller_key,
        sum(price)                  AS revenue,
        count(DISTINCT order_id)    AS orders
    FROM fact_order_items
    WHERE is_delivered = 1
    GROUP BY seller_key
),
ranked AS (
    SELECT
        *,
        row_number() OVER (ORDER BY revenue DESC, seller_key) AS revenue_rank,
        count(*) OVER ()                                      AS seller_count,
        revenue / sum(revenue) OVER ()                        AS revenue_share
    FROM seller_revenue
),
tiered AS (
    SELECT
        *,
        CASE
            WHEN revenue_rank <= ceil(0.01 * seller_count) THEN '1. top 1%'
            WHEN revenue_rank <= ceil(0.05 * seller_count) THEN '2. next 4% (top 5%)'
            WHEN revenue_rank <= ceil(0.10 * seller_count) THEN '3. next 5% (top 10%)'
            WHEN revenue_rank <= ceil(0.20 * seller_count) THEN '4. next 10% (top 20%)'
            WHEN revenue_rank <= ceil(0.50 * seller_count) THEN '5. next 30% (top 50%)'
            ELSE                                                '6. bottom 50%'
        END AS seller_tier
    FROM ranked
)
SELECT
    seller_tier,
    count(*)                                                      AS sellers,
    sum(orders)                                                   AS seller_orders,
    round(sum(revenue), 2)                                        AS revenue,
    round(100.0 * sum(revenue_share), 2)                          AS pct_of_revenue,
    round(100.0 * sum(sum(revenue_share)) OVER (ORDER BY seller_tier), 2) AS cumulative_pct_of_revenue,
    round(sum(revenue) / count(*), 2)                             AS revenue_per_seller,
    round(max(revenue), 2)                                        AS largest_seller_revenue,
    round((SELECT 10000 * sum(revenue_share * revenue_share) FROM ranked), 1) AS marketplace_hhi
FROM tiered
GROUP BY seller_tier
ORDER BY seller_tier;
