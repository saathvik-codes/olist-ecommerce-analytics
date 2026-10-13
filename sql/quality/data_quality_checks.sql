-- =============================================================================
-- data_quality_checks.sql
-- One row per check: how many rows are affected, out of how many, and how the
-- model handles it. Run after sql/model/*.sql. Every count is computed, none typed.
-- =============================================================================
WITH checks (check_group, check_name, affected_rows, total_rows, handling) AS (

    -- ---------- duplicates on declared keys ----------
    SELECT 'Duplicates', 'raw_orders: duplicate order_id',
           count(*) - count(DISTINCT order_id), count(*), 'none needed'
    FROM raw_orders
    UNION ALL
    SELECT 'Duplicates', 'raw_order_items: duplicate (order_id, order_item_id)',
           count(*) - count(DISTINCT (order_id, order_item_id)), count(*), 'none needed'
    FROM raw_order_items
    UNION ALL
    SELECT 'Duplicates', 'raw_customers: duplicate customer_id',
           count(*) - count(DISTINCT customer_id), count(*), 'none needed'
    FROM raw_customers
    UNION ALL
    SELECT 'Duplicates', 'raw_customers: customer_id rows beyond one per customer_unique_id',
           count(*) - count(DISTINCT customer_unique_id), count(*),
           'expected: customer_id is per order; dim_customer is keyed on customer_unique_id'
    FROM raw_customers
    UNION ALL
    SELECT 'Duplicates', 'raw_products: duplicate product_id',
           count(*) - count(DISTINCT product_id), count(*), 'none needed'
    FROM raw_products
    UNION ALL
    SELECT 'Duplicates', 'raw_sellers: duplicate seller_id',
           count(*) - count(DISTINCT seller_id), count(*), 'none needed'
    FROM raw_sellers
    UNION ALL
    SELECT 'Duplicates', 'raw_reviews: extra reviews beyond one per order',
           count(*) - count(DISTINCT order_id), count(*),
           'stg_order_reviews keeps the latest-answered review per order'
    FROM raw_reviews
    UNION ALL
    SELECT 'Duplicates', 'raw_reviews: review_id reused across rows',
           count(*) - count(DISTINCT review_id), count(*),
           'review_id is not a key; reviews are keyed on order_id'
    FROM raw_reviews
    UNION ALL
    SELECT 'Duplicates', 'raw_geolocation: fully identical rows',
           (SELECT count(*) FROM raw_geolocation)
               - (SELECT count(*) FROM (SELECT DISTINCT * FROM raw_geolocation)),
           (SELECT count(*) FROM raw_geolocation),
           'dim_geography collapses to one row per zip prefix'
    UNION ALL
    SELECT 'Duplicates', 'raw_geolocation: rows beyond one per zip prefix',
           count(*) - count(DISTINCT geolocation_zip_code_prefix), count(*),
           'dim_geography collapses to one row per zip prefix'
    FROM raw_geolocation

    -- ---------- nulls ----------
    UNION ALL
    SELECT 'Nulls', 'raw_orders: order_approved_at is null',
           count(*) FILTER (WHERE order_approved_at IS NULL), count(*), 'kept as null'
    FROM raw_orders
    UNION ALL
    SELECT 'Nulls', 'raw_orders: order_delivered_carrier_date is null',
           count(*) FILTER (WHERE order_delivered_carrier_date IS NULL), count(*), 'kept as null'
    FROM raw_orders
    UNION ALL
    SELECT 'Nulls', 'raw_orders: order_delivered_customer_date is null',
           count(*) FILTER (WHERE order_delivered_customer_date IS NULL), count(*),
           'delivery metrics are null; delivery_status = Not delivered'
    FROM raw_orders
    UNION ALL
    SELECT 'Nulls', 'raw_products: product_category_name is null',
           count(*) FILTER (WHERE product_category_name IS NULL), count(*),
           'category set to unknown'
    FROM raw_products
    UNION ALL
    SELECT 'Nulls', 'raw_products: category has no English translation',
           count(*) FILTER (WHERE t.product_category_name IS NULL
                              AND p.product_category_name IS NOT NULL),
           count(*), 'two categories translated manually in stg_products'
    FROM raw_products AS p
    LEFT JOIN raw_category_translation AS t USING (product_category_name)
    UNION ALL
    SELECT 'Nulls', 'raw_products: weight or any dimension is null',
           count(*) FILTER (WHERE product_weight_g IS NULL OR product_length_cm IS NULL
                               OR product_height_cm IS NULL OR product_width_cm IS NULL),
           count(*), 'weight_band = unknown; volume null'
    FROM raw_products
    UNION ALL
    SELECT 'Nulls', 'raw_reviews: review has no comment text',
           count(*) FILTER (WHERE review_comment_message IS NULL), count(*),
           'comment text is not used'
    FROM raw_reviews
    UNION ALL
    SELECT 'Nulls', 'fact_orders: order has no review',
           count(*) FILTER (WHERE review_score IS NULL), count(*),
           'excluded from review averages'
    FROM fact_orders
    UNION ALL
    SELECT 'Nulls', 'fact_orders: order has no payment record',
           count(*) FILTER (WHERE payment_value IS NULL), count(*),
           'payment fields null; revenue uses item price, not payments'
    FROM fact_orders
    UNION ALL
    SELECT 'Nulls', 'fact_orders: order has no line items',
           count(*) FILTER (WHERE item_count = 0), count(*),
           'all are non-delivered statuses; they contribute zero revenue'
    FROM fact_orders
    UNION ALL
    SELECT 'Nulls', 'fact_orders: DELIVERED order has no line items',
           count(*) FILTER (WHERE item_count = 0 AND is_delivered = 1), count(*),
           'none, so order counts from either fact table agree'
    FROM fact_orders
    UNION ALL
    SELECT 'Nulls', 'dim_geography: zip prefix has no usable coordinates',
           count(*) FILTER (WHERE latitude IS NULL), count(*),
           'latitude / longitude null; state and region still populated'
    FROM dim_geography

    -- ---------- orphan keys in the source ----------
    UNION ALL
    SELECT 'Orphan keys', 'raw_orders.customer_id not in raw_customers',
           count(*) FILTER (WHERE c.customer_id IS NULL), count(*), 'none needed'
    FROM raw_orders AS o LEFT JOIN raw_customers AS c USING (customer_id)
    UNION ALL
    SELECT 'Orphan keys', 'raw_order_items.order_id not in raw_orders',
           count(*) FILTER (WHERE o.order_id IS NULL), count(*), 'none needed'
    FROM raw_order_items AS i LEFT JOIN raw_orders AS o USING (order_id)
    UNION ALL
    SELECT 'Orphan keys', 'raw_order_items.product_id not in raw_products',
           count(*) FILTER (WHERE p.product_id IS NULL), count(*), 'none needed'
    FROM raw_order_items AS i LEFT JOIN raw_products AS p USING (product_id)
    UNION ALL
    SELECT 'Orphan keys', 'raw_order_items.seller_id not in raw_sellers',
           count(*) FILTER (WHERE s.seller_id IS NULL), count(*), 'none needed'
    FROM raw_order_items AS i LEFT JOIN raw_sellers AS s USING (seller_id)
    UNION ALL
    SELECT 'Orphan keys', 'raw_payments.order_id not in raw_orders',
           count(*) FILTER (WHERE o.order_id IS NULL), count(*), 'none needed'
    FROM raw_payments AS p LEFT JOIN raw_orders AS o USING (order_id)
    UNION ALL
    SELECT 'Orphan keys', 'raw_reviews.order_id not in raw_orders',
           count(*) FILTER (WHERE o.order_id IS NULL), count(*), 'none needed'
    FROM raw_reviews AS r LEFT JOIN raw_orders AS o USING (order_id)
    UNION ALL
    SELECT 'Orphan keys', 'customer zip prefix missing from the geolocation file',
           count(*) FILTER (WHERE g.zip IS NULL), count(*),
           'dim_geography row built from the customer record (no coordinates)'
    FROM stg_customers AS c
    LEFT JOIN (SELECT DISTINCT lpad(geolocation_zip_code_prefix, 5, '0') AS zip
               FROM raw_geolocation) AS g ON g.zip = c.zip_code_prefix
    UNION ALL
    SELECT 'Orphan keys', 'seller zip prefix missing from the geolocation file',
           count(*) FILTER (WHERE g.zip IS NULL), count(*),
           'dim_geography row built from the seller record (no coordinates)'
    FROM stg_sellers AS s
    LEFT JOIN (SELECT DISTINCT lpad(geolocation_zip_code_prefix, 5, '0') AS zip
               FROM raw_geolocation) AS g ON g.zip = s.zip_code_prefix

    -- ---------- date and status anomalies ----------
    UNION ALL
    SELECT 'Date anomalies', 'status = delivered but no delivery date',
           count(*) FILTER (WHERE order_status = 'delivered' AND delivered_at IS NULL),
           count(*), 'has_delivery_date = 0; excluded from delivery metrics'
    FROM stg_orders
    UNION ALL
    SELECT 'Date anomalies', 'status <> delivered but a delivery date exists',
           count(*) FILTER (WHERE order_status <> 'delivered' AND delivered_at IS NOT NULL),
           count(*), 'treated as not delivered (status is the source of truth)'
    FROM stg_orders
    UNION ALL
    SELECT 'Date anomalies', 'delivered to customer before handed to carrier',
           count(*) FILTER (WHERE delivered_at < shipped_at), count(*),
           'kept; delivery time is measured from purchase, not from hand-over'
    FROM stg_orders
    UNION ALL
    SELECT 'Date anomalies', 'handed to carrier before purchase timestamp',
           count(*) FILTER (WHERE shipped_at < purchased_at), count(*), 'kept; not used'
    FROM stg_orders
    UNION ALL
    SELECT 'Date anomalies', 'delivered before purchase timestamp',
           count(*) FILTER (WHERE delivered_at < purchased_at), count(*), 'none needed'
    FROM stg_orders
    UNION ALL
    SELECT 'Date anomalies', 'approved before purchase timestamp',
           count(*) FILTER (WHERE approved_at < purchased_at), count(*), 'none needed'
    FROM stg_orders
    UNION ALL
    SELECT 'Date anomalies', 'delivery took more than 60 days',
           count(*) FILTER (WHERE days_to_deliver > 60),
           count(*) FILTER (WHERE has_delivery_date = 1),
           'kept (real long-tail deliveries); medians reported next to means'
    FROM fact_orders
    UNION ALL
    SELECT 'Date anomalies', 'orders purchased outside Jan-2017..Aug-2018',
           count(*) FILTER (WHERE d.is_analysis_window = 0), count(*),
           'kept in totals; excluded from trend / growth analysis (partial months)'
    FROM fact_orders AS o JOIN dim_date AS d ON d.date_key = o.purchase_date_key
    UNION ALL
    SELECT 'Date anomalies', 'calendar months present with fewer than 400 orders (partial)',
           count(*) FILTER (WHERE n < 400), count(*),
           'months outside Jan-2017..Aug-2018; flagged by dim_date.is_analysis_window = 0'
    FROM (SELECT strftime(purchase_date, '%Y-%m') AS ym, count(*) AS n
          FROM fact_orders GROUP BY 1)

    -- ---------- value anomalies ----------
    UNION ALL
    SELECT 'Value anomalies', 'order items with price <= 0',
           count(*) FILTER (WHERE price <= 0), count(*), 'none needed'
    FROM raw_order_items
    UNION ALL
    SELECT 'Value anomalies', 'order items with zero freight',
           count(*) FILTER (WHERE freight_value = 0), count(*), 'kept (free shipping)'
    FROM raw_order_items
    UNION ALL
    SELECT 'Value anomalies', 'payments with value = 0',
           count(*) FILTER (WHERE payment_value = 0), count(*), 'kept (vouchers / not_defined)'
    FROM raw_payments
    UNION ALL
    SELECT 'Value anomalies', 'payments with payment_type = not_defined',
           count(*) FILTER (WHERE payment_type = 'not_defined'), count(*),
           'kept; outside delivered-order metrics if the order was not delivered'
    FROM raw_payments
    UNION ALL
    SELECT 'Value anomalies', 'payments with 0 installments',
           count(*) FILTER (WHERE payment_installments = 0), count(*), 'kept as reported'
    FROM raw_payments
    UNION ALL
    SELECT 'Value anomalies', 'delivered orders where payments differ from items + freight by > 0.05',
           count(*) FILTER (WHERE abs(payment_value - order_value) > 0.05),
           count(*),
           'revenue is defined on item price, so it is unaffected'
    FROM fact_orders
    WHERE is_delivered = 1
    UNION ALL
    SELECT 'Value anomalies', 'geolocation points outside the bounding box of Brazil',
           count(*) FILTER (WHERE NOT (geolocation_lat BETWEEN -33.75 AND 5.27
                                   AND geolocation_lng BETWEEN -73.99 AND -34.79)),
           count(*), 'excluded before taking the median coordinate per zip prefix'
    FROM raw_geolocation
    UNION ALL
    SELECT 'Value anomalies', 'orders whose zip-prefix state differs from the customer record',
           count(*) FILTER (WHERE g.state <> c.state), count(*), 'none needed'
    FROM stg_orders AS o
    JOIN stg_customers AS c USING (customer_id)
    JOIN dim_geography AS g USING (zip_code_prefix)

    -- ---------- star-schema integrity ----------
    UNION ALL
    SELECT 'Star schema', 'fact_orders rows with no dim_customer match',
           count(*) FILTER (WHERE d.customer_key IS NULL), count(*), 'must be 0'
    FROM fact_orders AS f LEFT JOIN dim_customer AS d USING (customer_key)
    UNION ALL
    SELECT 'Star schema', 'fact_orders rows with no dim_geography match',
           count(*) FILTER (WHERE d.geography_key IS NULL), count(*), 'must be 0'
    FROM fact_orders AS f LEFT JOIN dim_geography AS d USING (geography_key)
    UNION ALL
    SELECT 'Star schema', 'fact_orders rows with no dim_date match',
           count(*) FILTER (WHERE d.date_key IS NULL), count(*), 'must be 0'
    FROM fact_orders AS f LEFT JOIN dim_date AS d ON d.date_key = f.purchase_date_key
    UNION ALL
    SELECT 'Star schema', 'fact_order_items rows with no dim_product match',
           count(*) FILTER (WHERE d.product_key IS NULL), count(*), 'must be 0'
    FROM fact_order_items AS f LEFT JOIN dim_product AS d USING (product_key)
    UNION ALL
    SELECT 'Star schema', 'fact_order_items rows with no dim_seller match',
           count(*) FILTER (WHERE d.seller_key IS NULL), count(*), 'must be 0'
    FROM fact_order_items AS f LEFT JOIN dim_seller AS d USING (seller_key)
    UNION ALL
    SELECT 'Star schema', 'fact_order_items rows with no fact_orders match',
           count(*) FILTER (WHERE o.order_id IS NULL), count(*), 'must be 0'
    FROM fact_order_items AS f LEFT JOIN fact_orders AS o USING (order_id)
)
SELECT
    check_group,
    check_name,
    affected_rows,
    total_rows,
    round(100.0 * affected_rows / nullif(total_rows, 0), 3) AS pct_of_rows,
    handling
FROM checks;
