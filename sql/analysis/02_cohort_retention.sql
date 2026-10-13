-- =============================================================================
-- 02  Do customers come back? Monthly acquisition cohorts and their retention.
-- A cohort = customers whose FIRST delivered order fell in that month.
-- Retention at month N = share of the cohort placing a delivered order N calendar
-- months after their first one. Month 0 is 100% by construction.
-- Builds mart_cohort_retention (long form) and returns the cohort x month matrix.
-- =============================================================================
CREATE OR REPLACE TABLE mart_cohort_retention AS
WITH activity AS (
    -- one row per customer per active month-offset
    SELECT DISTINCT
        c.cohort_month,
        o.customer_key,
        o.months_since_first_order AS month_offset
    FROM fact_orders AS o
    JOIN dim_customer AS c USING (customer_key)
    WHERE o.is_delivered = 1
      AND c.cohort_month BETWEEN '2017-01' AND '2018-08'
),
cohort_counts AS (
    SELECT cohort_month, month_offset, count(*) AS active_customers
    FROM activity
    GROUP BY cohort_month, month_offset
)
SELECT
    cohort_month,
    month_offset,
    first_value(active_customers) OVER w                         AS cohort_size,
    active_customers,
    round(100.0 * active_customers / first_value(active_customers) OVER w, 3) AS retention_pct
FROM cohort_counts
WINDOW w AS (PARTITION BY cohort_month ORDER BY month_offset)
ORDER BY cohort_month, month_offset;

-- Matrix of returning-customer COUNTS (the Excel report turns these into % with formulas).
-- A cell is NULL when the month lies beyond the last complete month (Aug-2018): that is
-- "not observed yet", which is different from "nobody came back" (0).
SELECT
    cohort_month,
    max(cohort_size) AS cohort_size,
    CASE WHEN cohort_month <= '2018-07'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 1), 0) END AS m1,
    CASE WHEN cohort_month <= '2018-06'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 2), 0) END AS m2,
    CASE WHEN cohort_month <= '2018-05'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 3), 0) END AS m3,
    CASE WHEN cohort_month <= '2018-04'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 4), 0) END AS m4,
    CASE WHEN cohort_month <= '2018-03'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 5), 0) END AS m5,
    CASE WHEN cohort_month <= '2018-02'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 6), 0) END AS m6,
    CASE WHEN cohort_month <= '2018-01'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 7), 0) END AS m7,
    CASE WHEN cohort_month <= '2017-12'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 8), 0) END AS m8,
    CASE WHEN cohort_month <= '2017-11'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 9), 0) END AS m9,
    CASE WHEN cohort_month <= '2017-10'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 10), 0) END AS m10,
    CASE WHEN cohort_month <= '2017-09'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 11), 0) END AS m11,
    CASE WHEN cohort_month <= '2017-08'
         THEN coalesce(sum(active_customers) FILTER (WHERE month_offset = 12), 0) END AS m12
FROM mart_cohort_retention
GROUP BY cohort_month
ORDER BY cohort_month;
