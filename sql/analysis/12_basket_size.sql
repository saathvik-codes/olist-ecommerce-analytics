-- =============================================================================
-- 12  How big is a basket? Items per delivered order and what larger baskets are worth.
-- =============================================================================
WITH baskets AS (
    SELECT
        order_id,
        item_count,
        seller_count,
        items_value,
        freight_value,
        CASE WHEN item_count >= 4 THEN '4+ items'
             WHEN item_count = 1  THEN '1 item'
             ELSE item_count || ' items' END AS basket_size
    FROM fact_orders
    WHERE is_delivered = 1
),
by_size AS (
    SELECT
        basket_size,
        count(*)                                     AS orders,
        sum(items_value)                             AS revenue,
        avg(items_value)                             AS avg_order_value,
        avg(items_value / item_count)                AS avg_item_price,
        avg(CAST(seller_count > 1 AS INTEGER))       AS multi_seller_share,
        sum(freight_value) / sum(items_value)        AS freight_to_revenue
    FROM baskets
    GROUP BY basket_size
)
SELECT
    basket_size,
    orders,
    round(100.0 * orders / sum(orders) OVER (), 2)       AS pct_of_orders,
    round(revenue, 2)                                    AS revenue,
    round(100.0 * revenue / sum(revenue) OVER (), 2)     AS pct_of_revenue,
    round(avg_order_value, 2)                            AS avg_order_value,
    round(avg_item_price, 2)                             AS avg_item_price,
    round(100.0 * multi_seller_share, 2)                 AS pct_multi_seller,
    round(100.0 * freight_to_revenue, 2)                 AS freight_pct_of_revenue
FROM by_size
ORDER BY basket_size;
