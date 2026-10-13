-- =============================================================================
-- dax_expected_values.sql
-- Independent SQL re-computation of every DAX measure in powerbi/measures.dax, in a
-- stated filter context. After building the Power BI report, apply the same filter
-- and compare. unit: currency | int | pct (already x100) | dec
-- Top seller used for seller checks: seller_id 4869f7a5dfa277a7dca6462dcf3b52b2
-- =============================================================================
WITH o AS (            -- delivered orders with their calendar and place
    SELECT f.*, d.year_month, d.year, d.month_index, g.state
    FROM fact_orders AS f
    JOIN dim_date AS d ON d.date_key = f.purchase_date_key
    JOIN dim_geography AS g USING (geography_key)
    WHERE f.is_delivered = 1
),
i AS (                 -- delivered item lines with their dimensions
    SELECT f.*, d.year_month, d.year, d.month_index, p.category, s.seller_id
    FROM fact_order_items AS f
    JOIN dim_date AS d ON d.date_key = f.purchase_date_key
    JOIN dim_product AS p USING (product_key)
    JOIN dim_seller AS s USING (seller_key)
    WHERE f.is_delivered = 1
),
month_revenue AS (
    SELECT year_month, sum(price) AS revenue FROM i GROUP BY year_month
),
category_revenue AS (
    SELECT
        category,
        sum(price) AS revenue,
        dense_rank() OVER (ORDER BY sum(price) DESC)                         AS revenue_rank,
        sum(sum(price)) OVER (ORDER BY sum(price) DESC) / sum(sum(price)) OVER () AS cumulative_share
    FROM i
    GROUP BY category
),
order_reviews_by_category AS (   -- one review score per distinct order within a category
    SELECT category, order_id, max(review_score) AS review_score
    FROM i GROUP BY category, order_id
),
seller_orders AS (               -- one row per distinct order per seller
    SELECT seller_id, order_id, max(delivery_status) AS delivery_status
    FROM i GROUP BY seller_id, order_id
),
expected (sort_order, measure, filter_context, expected_value, unit) AS (
    -- ---------------- sales ----------------
    SELECT 1, 'Total Revenue', 'No filters', round(sum(price), 2), 'currency' FROM i
    UNION ALL
    SELECT 2, 'Total Revenue', 'dim_date[year_month] = 2018-08', round(sum(price), 2), 'currency'
    FROM i WHERE year_month = '2018-08'
    UNION ALL
    SELECT 3, 'Total Revenue', 'dim_product[category] = health_beauty', round(sum(price), 2), 'currency'
    FROM i WHERE category = 'health_beauty'
    UNION ALL
    SELECT 3, 'Total Revenue', 'dim_date[is_analysis_window] = 1 (page filter on pages 1 and 3)',
           round(sum(price), 2), 'currency'
    FROM i JOIN dim_date AS w ON w.date_key = i.purchase_date_key WHERE w.is_analysis_window = 1
    UNION ALL
    SELECT 4, 'Freight Revenue', 'No filters', round(sum(freight_value), 2), 'currency' FROM i
    UNION ALL
    SELECT 5, 'Total Orders', 'No filters', count(DISTINCT order_id), 'int' FROM i
    UNION ALL
    SELECT 6, 'Total Orders', 'dim_product[category] = health_beauty', count(DISTINCT order_id), 'int'
    FROM i WHERE category = 'health_beauty'
    UNION ALL
    SELECT 6, 'Total Orders', 'dim_date[is_analysis_window] = 1 (page filter on pages 1 and 3)',
           count(DISTINCT order_id), 'int'
    FROM i JOIN dim_date AS w ON w.date_key = i.purchase_date_key WHERE w.is_analysis_window = 1
    UNION ALL
    SELECT 7, 'Items Sold', 'No filters', count(*), 'int' FROM i
    UNION ALL
    SELECT 8, 'AOV', 'No filters', round(sum(price) / count(DISTINCT order_id), 2), 'currency' FROM i
    UNION ALL
    SELECT 9, 'AOV', 'dim_date[year_month] = 2018-08', round(sum(price) / count(DISTINCT order_id), 2), 'currency'
    FROM i WHERE year_month = '2018-08'
    UNION ALL
    SELECT 10, 'Avg Basket Size', 'No filters', round(count(*) / count(DISTINCT order_id), 3), 'dec' FROM i
    UNION ALL
    SELECT 11, 'Freight % of Revenue', 'No filters', round(100.0 * sum(freight_value) / sum(price), 2), 'pct' FROM i

    -- ---------------- time intelligence ----------------
    UNION ALL
    SELECT 20, 'Revenue MoM %', 'dim_date[year_month] = 2018-08',
           round(100.0 * (cur.revenue / prev.revenue - 1), 2), 'pct'
    FROM month_revenue AS cur, month_revenue AS prev
    WHERE cur.year_month = '2018-08' AND prev.year_month = '2018-07'
    UNION ALL
    SELECT 21, 'Revenue MoM %', 'dim_date[year_month] = 2017-11 (Black Friday month)',
           round(100.0 * (cur.revenue / prev.revenue - 1), 2), 'pct'
    FROM month_revenue AS cur, month_revenue AS prev
    WHERE cur.year_month = '2017-11' AND prev.year_month = '2017-10'
    UNION ALL
    SELECT 22, 'Revenue YoY %', 'dim_date[year_month] = 2018-08',
           round(100.0 * (cur.revenue / prev.revenue - 1), 2), 'pct'
    FROM month_revenue AS cur, month_revenue AS prev
    WHERE cur.year_month = '2018-08' AND prev.year_month = '2017-08'
    UNION ALL
    SELECT 23, 'Revenue Rolling 3M', 'dim_date[year_month] = 2018-08 (Jun+Jul+Aug 2018)',
           round(sum(revenue), 2), 'currency'
    FROM month_revenue WHERE year_month IN ('2018-06', '2018-07', '2018-08')
    UNION ALL
    SELECT 24, 'Revenue YTD', 'dim_date[year_month] = 2018-08 (Jan-Aug 2018)',
           round(sum(revenue), 2), 'currency'
    FROM month_revenue WHERE year_month BETWEEN '2018-01' AND '2018-08'
    UNION ALL
    SELECT 25, 'Cumulative Revenue', 'dim_date[year_month] = 2017-12 (everything up to 31-Dec-2017)',
           round(sum(revenue), 2), 'currency'
    FROM month_revenue WHERE year_month <= '2017-12'

    -- ---------------- customers ----------------
    UNION ALL
    SELECT 30, 'Active Customers', 'No filters', count(DISTINCT customer_key), 'int' FROM o
    UNION ALL
    SELECT 31, 'Active Customers', 'dim_date[year_month] = 2018-08', count(DISTINCT customer_key), 'int'
    FROM o WHERE year_month = '2018-08'
    UNION ALL
    SELECT 32, 'New Customers', 'dim_date[year_month] = 2018-08',
           count(DISTINCT customer_key) FILTER (WHERE customer_order_seq = 1), 'int'
    FROM o WHERE year_month = '2018-08'
    UNION ALL
    SELECT 33, 'Returning Customers', 'dim_date[year_month] = 2018-08',
           count(DISTINCT customer_key) FILTER (WHERE customer_order_seq > 1), 'int'
    FROM o WHERE year_month = '2018-08'
    UNION ALL
    SELECT 34, 'Returning Customer %', 'dim_date[year_month] = 2018-08',
           round(100.0 * count(DISTINCT customer_key) FILTER (WHERE customer_order_seq > 1)
                 / count(DISTINCT customer_key), 2), 'pct'
    FROM o WHERE year_month = '2018-08'
    UNION ALL
    SELECT 35, 'Repeat Customers', 'No filters', count(*), 'int'
    FROM (SELECT customer_key FROM o GROUP BY customer_key HAVING count(*) >= 2)
    UNION ALL
    SELECT 36, 'Repeat Customer Rate', 'No filters',
           round(100.0 * count(*) FILTER (WHERE n >= 2) / count(*), 2), 'pct'
    FROM (SELECT customer_key, count(*) AS n FROM o GROUP BY customer_key)
    UNION ALL
    SELECT 37, 'Repeat Customer Rate', 'dim_date[year] = 2018 (2+ orders within 2018)',
           round(100.0 * count(*) FILTER (WHERE n >= 2) / count(*), 2), 'pct'
    FROM (SELECT customer_key, count(*) AS n FROM o WHERE year = 2018 GROUP BY customer_key)
    UNION ALL
    SELECT 38, 'Revenue per Customer', 'No filters',
           round((SELECT sum(price) FROM i) / count(DISTINCT customer_key), 2), 'currency'
    FROM o
    UNION ALL
    SELECT 39, 'Cohort Retention %', 'cohort_month = 2017-05, months_since_first_order = 1',
           retention_pct, 'pct'
    FROM mart_cohort_retention WHERE cohort_month = '2017-05' AND month_offset = 1
    UNION ALL
    SELECT 40, 'Cohort Retention %', 'cohort_month = 2017-11, months_since_first_order = 1',
           retention_pct, 'pct'
    FROM mart_cohort_retention WHERE cohort_month = '2017-11' AND month_offset = 1
    UNION ALL
    SELECT 41, 'Cohort Retention %', 'cohort_month = 2017-05, months_since_first_order = 0',
           retention_pct, 'pct'
    FROM mart_cohort_retention WHERE cohort_month = '2017-05' AND month_offset = 0

    -- ---------------- delivery and satisfaction ----------------
    UNION ALL
    SELECT 50, 'Orders Placed', 'No filters', count(*), 'int' FROM fact_orders
    UNION ALL
    SELECT 51, 'Delivered Orders', 'No filters', count(*), 'int' FROM o
    UNION ALL
    SELECT 52, 'Delivered Order Rate', 'No filters',
           round(100.0 * sum(is_delivered) / count(*), 2), 'pct' FROM fact_orders
    UNION ALL
    SELECT 53, 'Late Delivery %', 'No filters',
           round(100.0 * sum(is_late) / sum(has_delivery_date), 2), 'pct' FROM o
    UNION ALL
    SELECT 54, 'Late Delivery %', 'dim_geography[state] = RJ',
           round(100.0 * sum(is_late) / sum(has_delivery_date), 2), 'pct' FROM o WHERE state = 'RJ'
    UNION ALL
    SELECT 55, 'Late Delivery %', 'dim_date[year_month] = 2018-03',
           round(100.0 * sum(is_late) / sum(has_delivery_date), 2), 'pct' FROM o WHERE year_month = '2018-03'
    UNION ALL
    SELECT 56, 'Avg Delivery Days', 'No filters', round(avg(days_to_deliver), 2), 'dec' FROM o
    UNION ALL
    SELECT 57, 'Avg Delivery Days', 'dim_geography[state] = SP', round(avg(days_to_deliver), 2), 'dec'
    FROM o WHERE state = 'SP'
    UNION ALL
    SELECT 58, 'Avg Delay vs Promise', 'No filters', round(avg(delivery_delay_days), 2), 'dec' FROM o
    UNION ALL
    SELECT 59, 'Avg Review Score', 'No filters', round(avg(review_score), 3), 'dec' FROM o
    UNION ALL
    SELECT 60, 'Low Review %', 'No filters',
           round(100.0 * sum(is_low_review) / count(review_score), 2), 'pct' FROM o
    UNION ALL
    SELECT 61, 'Avg Review - Late', 'No filters', round(avg(review_score), 3), 'dec'
    FROM o WHERE delivery_status = 'Late'
    UNION ALL
    SELECT 62, 'Avg Review - On Time', 'No filters', round(avg(review_score), 3), 'dec'
    FROM o WHERE delivery_status = 'On time'

    -- ---------------- products and sellers ----------------
    UNION ALL
    SELECT 70, 'Category Revenue Share %', 'dim_product[category] = health_beauty',
           round(100.0 * revenue / (SELECT sum(revenue) FROM category_revenue), 2), 'pct'
    FROM category_revenue WHERE category = 'health_beauty'
    UNION ALL
    SELECT 71, 'Category Rank', 'dim_product[category] = watches_gifts', revenue_rank, 'int'
    FROM category_revenue WHERE category = 'watches_gifts'
    UNION ALL
    SELECT 72, 'Pareto Cumulative %', 'dim_product[category] = watches_gifts (rank 2)',
           round(100.0 * cumulative_share, 2), 'pct'
    FROM category_revenue WHERE category = 'watches_gifts'
    UNION ALL
    SELECT 73, 'Pareto Cumulative %', 'dim_product[category] = toys (rank 10)',
           round(100.0 * cumulative_share, 2), 'pct'
    FROM category_revenue WHERE category = 'toys'
    UNION ALL
    SELECT 74, 'Active Sellers', 'No filters', count(DISTINCT seller_key), 'int' FROM i
    UNION ALL
    SELECT 75, 'Late Delivery % (Product View)', 'No filters (must equal Late Delivery %)',
           round(100.0 * count(DISTINCT order_id) FILTER (WHERE delivery_status = 'Late')
                 / count(DISTINCT order_id) FILTER (WHERE delivery_status IN ('Late', 'On time')), 2), 'pct'
    FROM i
    UNION ALL
    SELECT 76, 'Late Delivery % (Product View)', 'dim_seller[seller_id] = 4869f7a5dfa277a7dca6462dcf3b52b2',
           round(100.0 * count(*) FILTER (WHERE delivery_status = 'Late')
                 / count(*) FILTER (WHERE delivery_status IN ('Late', 'On time')), 2), 'pct'
    FROM seller_orders WHERE seller_id = '4869f7a5dfa277a7dca6462dcf3b52b2'
    UNION ALL
    SELECT 77, 'Avg Review (Product View)', 'No filters (must equal Avg Review Score)',
           round(avg(review_score), 3), 'dec'
    FROM (SELECT order_id, max(review_score) AS review_score FROM i GROUP BY order_id)
    UNION ALL
    SELECT 78, 'Avg Review (Product View)', 'dim_product[category] = health_beauty',
           round(avg(review_score), 3), 'dec'
    FROM order_reviews_by_category WHERE category = 'health_beauty'
    UNION ALL
    SELECT 79, 'Avg Review (Product View)', 'dim_product[category] = office_furniture',
           round(avg(review_score), 3), 'dec'
    FROM order_reviews_by_category WHERE category = 'office_furniture'

    -- ---------------- payments ----------------
    UNION ALL
    SELECT 90, 'Credit Card Order Share', 'No filters',
           round(100.0 * count(*) FILTER (WHERE payment_type = 'credit_card') / count(*), 2), 'pct'
    FROM o
    UNION ALL
    SELECT 91, 'Avg Installments (Card)', 'No filters', round(avg(payment_installments), 2), 'dec'
    FROM o WHERE payment_type = 'credit_card'
)
SELECT measure, filter_context, expected_value, unit
FROM expected
ORDER BY sort_order;
