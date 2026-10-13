-- =============================================================================
-- 02_dimensions.sql
-- Conformed dimensions. Every dimension gets an integer surrogate key assigned
-- in natural-key order, so keys are stable across rebuilds.
-- =============================================================================

-- ---------- dim_date ----------------------------------------------------------
-- Grain: one row per calendar day, full years 2016-2018 (Power BI needs whole years).
-- is_analysis_window marks Jan-2017..Aug-2018: the only months with complete trading
-- (2016 has 329 orders in total and Sep/Oct-2018 have 20 - see the data-quality report).
CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)                 AS date_key,
    CAST(d AS DATE)                                        AS date,
    year(d)                                                AS year,
    quarter(d)                                             AS quarter,
    'Q' || quarter(d) || ' ' || year(d)                    AS year_quarter,
    month(d)                                               AS month,
    strftime(d, '%b')                                      AS month_name,
    strftime(d, '%Y-%m')                                   AS year_month,
    CAST(date_trunc('month', d) AS DATE)                   AS month_start,
    (year(d) - 2016) * 12 + month(d)                       AS month_index,
    isodow(d)                                              AS day_of_week,
    strftime(d, '%a')                                      AS day_name,
    CAST(isodow(d) IN (6, 7) AS INTEGER)                   AS is_weekend,
    CAST(d BETWEEN DATE '2017-01-01' AND DATE '2018-08-31' AS INTEGER) AS is_analysis_window
FROM generate_series(DATE '2016-01-01', DATE '2018-12-31', INTERVAL 1 DAY) AS t(d);

-- ---------- dim_geography -----------------------------------------------------
-- Grain: one row per 5-digit zip-code prefix seen in customers, sellers or geolocation.
-- City/state: most frequent spelling, preferring the customer table, then sellers,
-- then the geolocation file. Coordinates: median of geolocation points inside Brazil's
-- bounding box (the file contains a handful of points in Europe/Atlantic).
CREATE OR REPLACE TABLE dim_geography AS
WITH zip_names AS (
    SELECT zip_code_prefix, city, state, 1 AS source_priority FROM stg_customers
    UNION ALL
    SELECT zip_code_prefix, city, state, 2 FROM stg_sellers
    UNION ALL
    SELECT lpad(geolocation_zip_code_prefix, 5, '0'),
           lower(trim(geolocation_city)),
           upper(trim(geolocation_state)),
           3
    FROM raw_geolocation
),
name_votes AS (
    SELECT zip_code_prefix, city, state, source_priority, count(*) AS votes
    FROM zip_names
    GROUP BY ALL
),
best_name AS (
    SELECT zip_code_prefix, city, state
    FROM name_votes
    QUALIFY row_number() OVER (
        PARTITION BY zip_code_prefix
        ORDER BY source_priority, votes DESC, state, city
    ) = 1
),
coordinates AS (
    SELECT
        lpad(geolocation_zip_code_prefix, 5, '0') AS zip_code_prefix,
        round(median(geolocation_lat), 5)         AS latitude,
        round(median(geolocation_lng), 5)         AS longitude
    FROM raw_geolocation
    WHERE geolocation_lat BETWEEN -33.75 AND 5.27
      AND geolocation_lng BETWEEN -73.99 AND -34.79
    GROUP BY 1
),
regions (state, state_name, region) AS (
    VALUES
        ('AC', 'Acre', 'North'),             ('AL', 'Alagoas', 'Northeast'),
        ('AM', 'Amazonas', 'North'),         ('AP', 'Amapa', 'North'),
        ('BA', 'Bahia', 'Northeast'),        ('CE', 'Ceara', 'Northeast'),
        ('DF', 'Distrito Federal', 'Center-West'), ('ES', 'Espirito Santo', 'Southeast'),
        ('GO', 'Goias', 'Center-West'),      ('MA', 'Maranhao', 'Northeast'),
        ('MG', 'Minas Gerais', 'Southeast'), ('MS', 'Mato Grosso do Sul', 'Center-West'),
        ('MT', 'Mato Grosso', 'Center-West'), ('PA', 'Para', 'North'),
        ('PB', 'Paraiba', 'Northeast'),      ('PE', 'Pernambuco', 'Northeast'),
        ('PI', 'Piaui', 'Northeast'),        ('PR', 'Parana', 'South'),
        ('RJ', 'Rio de Janeiro', 'Southeast'), ('RN', 'Rio Grande do Norte', 'Northeast'),
        ('RO', 'Rondonia', 'North'),         ('RR', 'Roraima', 'North'),
        ('RS', 'Rio Grande do Sul', 'South'), ('SC', 'Santa Catarina', 'South'),
        ('SE', 'Sergipe', 'Northeast'),      ('SP', 'Sao Paulo', 'Southeast'),
        ('TO', 'Tocantins', 'North')
)
SELECT
    CAST(row_number() OVER (ORDER BY n.zip_code_prefix) AS INTEGER) AS geography_key,
    n.zip_code_prefix,
    n.city,
    n.state,
    r.state_name,
    r.region,
    c.latitude,
    c.longitude
FROM best_name AS n
LEFT JOIN regions AS r USING (state)
LEFT JOIN coordinates AS c USING (zip_code_prefix);

-- ---------- dim_product -------------------------------------------------------
-- Grain: one row per product_id.
CREATE OR REPLACE TABLE dim_product AS
SELECT
    CAST(row_number() OVER (ORDER BY product_id) AS INTEGER) AS product_key,
    product_id,
    category,
    category_pt,
    photos_qty,
    weight_g,
    length_cm * height_cm * width_cm AS volume_cm3,
    CASE
        WHEN weight_g IS NULL  THEN 'unknown'
        WHEN weight_g < 500    THEN '1. under 0.5 kg'
        WHEN weight_g < 2000   THEN '2. 0.5-2 kg'
        WHEN weight_g < 10000  THEN '3. 2-10 kg'
        ELSE                        '4. 10 kg+'
    END AS weight_band
FROM stg_products;

-- ---------- dim_seller --------------------------------------------------------
-- Grain: one row per seller_id. Location is denormalised onto the seller because
-- dim_geography is reserved for the customer (delivery) location in the facts.
CREATE OR REPLACE TABLE dim_seller AS
SELECT
    CAST(row_number() OVER (ORDER BY s.seller_id) AS INTEGER) AS seller_key,
    s.seller_id,
    s.zip_code_prefix AS seller_zip_code_prefix,
    s.city            AS seller_city,
    s.state           AS seller_state,
    g.region          AS seller_region
FROM stg_sellers AS s
LEFT JOIN dim_geography AS g USING (zip_code_prefix);

-- ---------- dim_customer ------------------------------------------------------
-- Grain: one row per customer_unique_id (a real person, across all their orders).
-- Lifetime attributes are computed on DELIVERED orders only, the same base as revenue.
-- Location = address on the customer's most recent order.
CREATE OR REPLACE TABLE dim_customer AS
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        c.zip_code_prefix,
        c.city,
        c.state,
        o.order_id,
        o.order_status,
        o.purchased_at
    FROM stg_customers AS c
    JOIN stg_orders AS o USING (customer_id)
),
latest_address AS (
    SELECT customer_unique_id, zip_code_prefix, city, state
    FROM customer_orders
    QUALIFY row_number() OVER (
        PARTITION BY customer_unique_id ORDER BY purchased_at DESC, order_id
    ) = 1
),
order_revenue AS (
    SELECT order_id, sum(price) AS items_value
    FROM stg_order_items
    GROUP BY order_id
),
lifetime AS (
    SELECT
        co.customer_unique_id,
        count(*)                              AS orders_placed,
        count(*) FILTER (WHERE co.order_status = 'delivered')                 AS delivered_orders,
        CAST(min(co.purchased_at) FILTER (WHERE co.order_status = 'delivered') AS DATE) AS first_order_date,
        CAST(max(co.purchased_at) FILTER (WHERE co.order_status = 'delivered') AS DATE) AS last_order_date,
        round(coalesce(sum(r.items_value) FILTER (WHERE co.order_status = 'delivered'), 0), 2) AS lifetime_revenue
    FROM customer_orders AS co
    LEFT JOIN order_revenue AS r USING (order_id)
    GROUP BY co.customer_unique_id
)
SELECT
    CAST(row_number() OVER (ORDER BY l.customer_unique_id) AS INTEGER) AS customer_key,
    l.customer_unique_id,
    a.city                                   AS customer_city,
    a.state                                  AS customer_state,
    l.orders_placed,
    l.delivered_orders,
    l.first_order_date,
    l.last_order_date,
    strftime(l.first_order_date, '%Y-%m')    AS cohort_month,
    l.lifetime_revenue,
    CAST(l.delivered_orders >= 2 AS INTEGER) AS is_repeat_customer
FROM lifetime AS l
JOIN latest_address AS a USING (customer_unique_id);
