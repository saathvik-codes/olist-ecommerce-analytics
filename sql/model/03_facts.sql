-- =============================================================================
-- 03_facts.sql
-- fact_orders       grain: one row per order            (delivery, review, payment)
-- fact_order_items  grain: one row per order line item  (revenue, product, seller)
--
-- Both facts keep every order status. Revenue-type metrics are always scoped to
-- is_delivered = 1 so that cancelled / unavailable orders never count as sales,
-- while fulfilment-rate questions can still see them.
-- =============================================================================

CREATE OR REPLACE TABLE fact_orders AS
WITH item_totals AS (
    SELECT
        order_id,
        count(*)                    AS item_count,
        count(DISTINCT seller_id)   AS seller_count,
        round(sum(price), 2)        AS items_value,
        round(sum(freight_value), 2) AS freight_value
    FROM stg_order_items
    GROUP BY order_id
),
base AS (
    SELECT
        o.order_id,
        dc.customer_key,
        g.geography_key,
        CAST(o.purchased_at AS DATE)                AS purchase_date,
        o.purchased_at,
        o.approved_at,
        o.shipped_at,
        o.delivered_at,
        o.estimated_delivery_date,
        o.order_status,
        o.order_status = 'delivered'                AS delivered,
        o.order_status = 'delivered'
            AND o.delivered_at IS NOT NULL          AS delivery_known,
        coalesce(i.item_count, 0)                   AS item_count,
        coalesce(i.seller_count, 0)                 AS seller_count,
        coalesce(i.items_value, 0)                  AS items_value,
        coalesce(i.freight_value, 0)                AS freight_value,
        p.payment_value,
        p.payment_type,
        p.payment_installments,
        p.payment_count,
        r.review_score
    FROM stg_orders AS o
    JOIN stg_customers AS c USING (customer_id)
    JOIN dim_customer AS dc USING (customer_unique_id)
    LEFT JOIN dim_geography AS g ON g.zip_code_prefix = c.zip_code_prefix
    LEFT JOIN item_totals AS i USING (order_id)
    LEFT JOIN stg_order_payments AS p USING (order_id)
    LEFT JOIN stg_order_reviews AS r USING (order_id)
),
sequenced AS (
    -- Position of each delivered order in its customer's history, and the
    -- customer's first delivered purchase (the cohort anchor).
    SELECT
        order_id,
        row_number() OVER (PARTITION BY customer_key ORDER BY purchased_at, order_id) AS customer_order_seq,
        min(purchase_date) OVER (PARTITION BY customer_key)                            AS first_order_date
    FROM base
    WHERE delivered
)
SELECT
    b.order_id,
    b.customer_key,
    b.geography_key,
    CAST(strftime(b.purchase_date, '%Y%m%d') AS INTEGER) AS purchase_date_key,
    b.purchase_date,
    b.purchased_at,
    b.approved_at,
    b.shipped_at,
    b.delivered_at,
    b.estimated_delivery_date,
    b.order_status,
    CAST(b.delivered AS INTEGER)       AS is_delivered,
    b.item_count,
    b.seller_count,
    b.items_value,
    b.freight_value,
    round(b.items_value + b.freight_value, 2) AS order_value,
    b.payment_value,
    b.payment_type,
    b.payment_installments,
    b.payment_count,
    -- Delivery metrics exist only for delivered orders that carry a delivery date.
    CAST(b.delivery_known AS INTEGER)  AS has_delivery_date,
    CASE WHEN b.delivery_known
         THEN date_diff('day', b.purchase_date, CAST(b.delivered_at AS DATE)) END AS days_to_deliver,
    date_diff('day', b.purchase_date, b.estimated_delivery_date)                  AS estimated_days,
    -- Positive = arrived after the promised date; negative = arrived early.
    CASE WHEN b.delivery_known
         THEN date_diff('day', b.estimated_delivery_date, CAST(b.delivered_at AS DATE)) END AS delivery_delay_days,
    CASE WHEN b.delivery_known
         THEN CAST(CAST(b.delivered_at AS DATE) > b.estimated_delivery_date AS INTEGER) END AS is_late,
    CASE
        WHEN NOT b.delivery_known                                   THEN 'Not delivered'
        WHEN CAST(b.delivered_at AS DATE) > b.estimated_delivery_date THEN 'Late'
        ELSE                                                             'On time'
    END                                AS delivery_status,
    CASE
        WHEN NOT b.delivery_known THEN NULL
        WHEN date_diff('day', b.purchase_date, CAST(b.delivered_at AS DATE)) <= 3  THEN '1. 0-3 days'
        WHEN date_diff('day', b.purchase_date, CAST(b.delivered_at AS DATE)) <= 7  THEN '2. 4-7 days'
        WHEN date_diff('day', b.purchase_date, CAST(b.delivered_at AS DATE)) <= 14 THEN '3. 8-14 days'
        WHEN date_diff('day', b.purchase_date, CAST(b.delivered_at AS DATE)) <= 21 THEN '4. 15-21 days'
        WHEN date_diff('day', b.purchase_date, CAST(b.delivered_at AS DATE)) <= 28 THEN '5. 22-28 days'
        ELSE                                                                            '6. 29+ days'
    END                                AS delivery_band,
    b.review_score,
    CAST(b.review_score <= 2 AS INTEGER) AS is_low_review,
    s.customer_order_seq,
    date_diff('month', s.first_order_date, b.purchase_date) AS months_since_first_order
FROM base AS b
LEFT JOIN sequenced AS s USING (order_id);


CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    dp.product_key,
    ds.seller_key,
    o.customer_key,
    o.geography_key,
    o.purchase_date_key,
    o.purchase_date,
    o.order_status,
    o.is_delivered,
    i.price,
    i.freight_value,
    i.shipping_limit_at,
    -- Order-level attributes repeated on each line so product / seller views can use
    -- them. Always aggregate these per DISTINCT order_id, never per row.
    o.delivery_status,
    o.is_late,
    o.review_score
FROM stg_order_items AS i
JOIN fact_orders AS o USING (order_id)
LEFT JOIN dim_product AS dp USING (product_id)
LEFT JOIN dim_seller AS ds USING (seller_id);


-- Payment lines are kept for the payment-mix analysis (an order can have several).
CREATE OR REPLACE TABLE fact_payments AS
SELECT
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    p.payment_value,
    o.purchase_date_key,
    o.is_delivered
FROM raw_payments AS p
JOIN fact_orders AS o USING (order_id);
