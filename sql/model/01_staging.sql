-- =============================================================================
-- 01_staging.sql
-- Layer 1 (raw_*): the nine source CSVs loaded as-is, zip codes kept as text.
-- Layer 2 (stg_*): one clean row per business entity, ready for the star schema.
-- Run from the project root (paths are relative to it).
-- =============================================================================

-- ---------- raw layer ---------------------------------------------------------
CREATE OR REPLACE TABLE raw_orders AS
SELECT * FROM read_csv('data/raw/olist_orders_dataset.csv', header = true);

CREATE OR REPLACE TABLE raw_order_items AS
SELECT * FROM read_csv('data/raw/olist_order_items_dataset.csv', header = true);

CREATE OR REPLACE TABLE raw_payments AS
SELECT * FROM read_csv('data/raw/olist_order_payments_dataset.csv', header = true);

CREATE OR REPLACE TABLE raw_reviews AS
SELECT * FROM read_csv('data/raw/olist_order_reviews_dataset.csv', header = true);

CREATE OR REPLACE TABLE raw_customers AS
SELECT * FROM read_csv('data/raw/olist_customers_dataset.csv', header = true,
                       types = {'customer_zip_code_prefix': 'VARCHAR'});

CREATE OR REPLACE TABLE raw_sellers AS
SELECT * FROM read_csv('data/raw/olist_sellers_dataset.csv', header = true,
                       types = {'seller_zip_code_prefix': 'VARCHAR'});

CREATE OR REPLACE TABLE raw_products AS
SELECT * FROM read_csv('data/raw/olist_products_dataset.csv', header = true);

CREATE OR REPLACE TABLE raw_geolocation AS
SELECT * FROM read_csv('data/raw/olist_geolocation_dataset.csv', header = true,
                       types = {'geolocation_zip_code_prefix': 'VARCHAR'});

CREATE OR REPLACE TABLE raw_category_translation AS
SELECT * FROM read_csv('data/raw/product_category_name_translation.csv', header = true);

-- ---------- staging layer -----------------------------------------------------

-- Orders: clearer column names; the delivery promise is a date, not a timestamp.
CREATE OR REPLACE TABLE stg_orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp              AS purchased_at,
    order_approved_at                     AS approved_at,
    order_delivered_carrier_date          AS shipped_at,
    order_delivered_customer_date         AS delivered_at,
    CAST(order_estimated_delivery_date AS DATE) AS estimated_delivery_date
FROM raw_orders;

-- Customers: Olist issues a new customer_id per order; customer_unique_id is the person.
CREATE OR REPLACE TABLE stg_customers AS
SELECT
    customer_id,
    customer_unique_id,
    lpad(customer_zip_code_prefix, 5, '0') AS zip_code_prefix,
    lower(trim(customer_city))             AS city,
    upper(trim(customer_state))            AS state
FROM raw_customers;

CREATE OR REPLACE TABLE stg_sellers AS
SELECT
    seller_id,
    lpad(seller_zip_code_prefix, 5, '0') AS zip_code_prefix,
    lower(trim(seller_city))             AS city,
    upper(trim(seller_state))            AS state
FROM raw_sellers;

CREATE OR REPLACE TABLE stg_order_items AS
SELECT
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date AS shipping_limit_at,
    price,
    freight_value
FROM raw_order_items;

-- Payments: an order can be paid in several parts (e.g. voucher + card).
-- Collapse to one row per order; the "primary" method is the one carrying the most value.
CREATE OR REPLACE TABLE stg_order_payments AS
WITH ranked AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY order_id
            ORDER BY payment_value DESC, payment_sequential
        ) AS value_rank
    FROM raw_payments
)
SELECT
    order_id,
    round(sum(payment_value), 2)                          AS payment_value,
    max(payment_type) FILTER (WHERE value_rank = 1)       AS payment_type,
    max(payment_installments)                             AS payment_installments,
    count(*)                                              AS payment_count,
    count(DISTINCT payment_type)                          AS payment_type_count
FROM ranked
GROUP BY order_id;

-- Reviews: a few orders were reviewed more than once. Keep the latest answer per order.
CREATE OR REPLACE TABLE stg_order_reviews AS
SELECT
    order_id,
    review_id,
    review_score,
    review_creation_date    AS review_created_at,
    review_answer_timestamp AS review_answered_at
FROM raw_reviews
QUALIFY row_number() OVER (
    PARTITION BY order_id
    ORDER BY review_answer_timestamp DESC, review_creation_date DESC, review_id
) = 1;

-- Products: attach the English category; fall back to the Portuguese name, then 'unknown'.
CREATE OR REPLACE TABLE stg_products AS
SELECT
    p.product_id,
    coalesce(p.product_category_name, 'unknown')                               AS category_pt,
    CASE  -- two categories are missing from the Olist translation file
        WHEN p.product_category_name = 'pc_gamer' THEN 'pc_gamer'
        WHEN p.product_category_name = 'portateis_cozinha_e_preparadores_de_alimentos'
            THEN 'kitchen_portables_and_food_preparers'
        ELSE coalesce(t.product_category_name_english, p.product_category_name, 'unknown')
    END                                                                        AS category,
    p.product_photos_qty     AS photos_qty,
    p.product_weight_g       AS weight_g,
    p.product_length_cm      AS length_cm,
    p.product_height_cm      AS height_cm,
    p.product_width_cm       AS width_cm
FROM raw_products AS p
LEFT JOIN raw_category_translation AS t USING (product_category_name);
