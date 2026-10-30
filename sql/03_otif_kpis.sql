-- KPI views used in the README and charts.

-- OTIF and on-time by shipping mode
CREATE OR REPLACE TABLE otif_by_mode AS
SELECT
    shipping_mode,
    ANY_VALUE(promised_days)                                          AS promised_days,
    COUNT(*)                                                          AS orders,
    COUNT(*) / SUM(COUNT(*)) OVER ()                                  AS share_of_orders,
    AVG(otif::INT)                                                    AS otif_rate,
    AVG(on_time::INT) FILTER (WHERE NOT cancelled)                    AS on_time_rate_shipped,
    AVG(cancelled::INT)                                               AS cancel_rate,
    AVG(actual_days)                                                  AS avg_actual_days,
    MIN(actual_days)                                                  AS min_actual_days,
    MAX(actual_days)                                                  AS max_actual_days,
    SUM(sales) FILTER (WHERE NOT on_time AND NOT cancelled)           AS late_sales
FROM orders
GROUP BY shipping_mode
UNION ALL
SELECT
    'All orders', NULL, COUNT(*), 1.0,
    AVG(otif::INT),
    AVG(on_time::INT) FILTER (WHERE NOT cancelled),
    AVG(cancelled::INT),
    AVG(actual_days), MIN(actual_days), MAX(actual_days),
    SUM(sales) FILTER (WHERE NOT on_time AND NOT cancelled)
FROM orders;

-- Monthly OTIF trend
CREATE OR REPLACE TABLE otif_by_month AS
SELECT
    DATE_TRUNC('month', order_ts)::DATE  AS month,
    COUNT(*)                             AS orders,
    AVG(otif::INT)                       AS otif_rate
FROM orders
GROUP BY 1
ORDER BY 1;

-- Distribution of actual transit days for each mode, next to what was promised
CREATE OR REPLACE TABLE transit_vs_promise AS
SELECT
    shipping_mode,
    ANY_VALUE(promised_days)                                     AS promised_days,
    actual_days,
    COUNT(*)                                                     AS orders,
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY shipping_mode)   AS share
FROM orders
WHERE NOT cancelled
GROUP BY shipping_mode, actual_days
ORDER BY shipping_mode, actual_days;
