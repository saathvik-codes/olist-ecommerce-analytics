-- =============================================================================
-- 08  Which product categories carry the business? Pareto (ABC) analysis.
-- Categories ranked by delivered revenue with running cumulative share.
-- ABC class: A = categories making up the first 80% of revenue, B = next 15%, C = rest.
-- =============================================================================
WITH by_category AS (
    SELECT
        p.category,
        count(DISTINCT i.order_id)   AS orders,
        count(*)                     AS items_sold,
        sum(i.price)                 AS revenue,
        avg(i.price)                 AS avg_item_price
    FROM fact_order_items AS i
    JOIN dim_product AS p USING (product_key)
    WHERE i.is_delivered = 1
    GROUP BY p.category
),
ranked AS (
    SELECT
        *,
        row_number() OVER (ORDER BY revenue DESC, category)                AS revenue_rank,
        revenue / sum(revenue) OVER ()                                     AS revenue_share,
        sum(revenue) OVER (ORDER BY revenue DESC, category) / sum(revenue) OVER () AS cumulative_share
    FROM by_category
)
SELECT
    revenue_rank,
    category,
    orders,
    items_sold,
    round(revenue, 2)                      AS revenue,
    round(avg_item_price, 2)               AS avg_item_price,
    round(100.0 * revenue_share, 3)        AS revenue_share_pct,
    round(100.0 * cumulative_share, 3)     AS cumulative_share_pct,
    CASE
        -- a category is class A if the revenue BEFORE it was still under 80%
        WHEN cumulative_share - revenue_share < 0.80 THEN 'A'
        WHEN cumulative_share - revenue_share < 0.95 THEN 'B'
        ELSE 'C'
    END                                    AS abc_class
FROM ranked
ORDER BY revenue_rank;
