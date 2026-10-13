-- =============================================================================
-- 09  How do customers pay? Payment-method mix on delivered orders.
-- Works at payment-line grain because one order can combine methods
-- (e.g. voucher + credit card), so "orders using" can add up to more than 100%.
-- =============================================================================
WITH lines AS (
    SELECT *
    FROM fact_payments
    WHERE is_delivered = 1
),
by_type AS (
    SELECT
        payment_type,
        count(*)                                        AS payment_lines,
        count(DISTINCT order_id)                        AS orders_using,
        sum(payment_value)                              AS payment_value,
        avg(payment_value)                              AS avg_payment_value,
        avg(payment_installments)                       AS avg_installments,
        avg(CAST(payment_installments > 1 AS INTEGER))  AS installment_share
    FROM lines
    GROUP BY payment_type
)
SELECT
    payment_type,
    payment_lines,
    orders_using,
    round(100.0 * orders_using / (SELECT count(DISTINCT order_id) FROM lines), 2) AS pct_of_orders_using,
    round(payment_value, 2)                                             AS payment_value,
    round(100.0 * payment_value / sum(payment_value) OVER (), 2)        AS pct_of_payment_value,
    rank() OVER (ORDER BY payment_value DESC)                           AS value_rank,
    round(avg_payment_value, 2)                                         AS avg_payment_value,
    round(avg_installments, 2)                                          AS avg_installments,
    round(100.0 * installment_share, 2)                                 AS pct_paid_in_installments
FROM by_type
ORDER BY payment_value DESC;
