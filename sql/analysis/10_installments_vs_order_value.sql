-- =============================================================================
-- 10  Do instalments unlock bigger baskets?
-- Delivered orders whose primary payment method is credit card, banded by the
-- number of instalments. Descriptive only: bigger purchases may simply cause
-- people to choose instalments, not the other way round.
-- =============================================================================
WITH card_orders AS (
    SELECT
        order_id,
        items_value,
        payment_installments,
        CASE
            WHEN payment_installments <= 1  THEN '1. pay in full'
            WHEN payment_installments <= 3  THEN '2. 2-3 instalments'
            WHEN payment_installments <= 6  THEN '3. 4-6 instalments'
            WHEN payment_installments <= 10 THEN '4. 7-10 instalments'
            ELSE                                 '5. 11+ instalments'
        END AS installment_band
    FROM fact_orders
    WHERE is_delivered = 1
      AND payment_type = 'credit_card'
),
by_band AS (
    SELECT
        installment_band,
        count(*)               AS orders,
        sum(items_value)       AS revenue,
        avg(items_value)       AS avg_order_value,
        median(items_value)    AS median_order_value
    FROM card_orders
    GROUP BY installment_band
)
SELECT
    installment_band,
    orders,
    round(100.0 * orders / sum(orders) OVER (), 2)        AS pct_of_card_orders,
    round(revenue, 2)                                     AS revenue,
    round(100.0 * revenue / sum(revenue) OVER (), 2)      AS pct_of_card_revenue,
    round(avg_order_value, 2)                             AS avg_order_value,
    round(median_order_value, 2)                          AS median_order_value,
    round(avg_order_value / first_value(avg_order_value) OVER (ORDER BY installment_band), 2)
                                                          AS aov_multiple_of_pay_in_full
FROM by_band
ORDER BY installment_band;
