-- Data quality checks on the raw order-line file.

-- 1. Coverage
SELECT COUNT(*) AS order_lines, COUNT(DISTINCT order_id) AS orders,
       MIN(order_ts) AS first_order, MAX(order_ts) AS last_order
FROM raw_items;

-- 2. Duplicate order lines
SELECT COUNT(*) - COUNT(DISTINCT order_item_id) AS duplicate_lines FROM raw_items;

-- 3. Orders whose lines disagree on shipping mode or transit days (should be zero:
--    the whole order ships together, so it can be analysed at order level)
SELECT COUNT(*) AS inconsistent_orders
FROM (
    SELECT order_id
    FROM raw_items
    GROUP BY order_id
    HAVING COUNT(DISTINCT shipping_mode) > 1
        OR COUNT(DISTINCT promised_days) > 1
        OR COUNT(DISTINCT actual_days) > 1
);

-- 4. Missing key fields
SELECT COUNT(*) AS lines_missing_keys
FROM raw_items
WHERE order_id IS NULL OR shipping_mode IS NULL OR promised_days IS NULL OR actual_days IS NULL;

-- 5. Does the source's own late flag match actual > promised? It only disagrees on cancelled orders,
--    where the source sets the flag to 0, so lateness is recomputed from the day counts here.
SELECT
    SUM(CASE WHEN late_flag_raw <> (actual_days > promised_days)::INT THEN 1 ELSE 0 END) AS flag_mismatches,
    SUM(CASE WHEN late_flag_raw <> (actual_days > promised_days)::INT
              AND delivery_status <> 'Shipping canceled' THEN 1 ELSE 0 END) AS mismatches_on_shipped_orders
FROM raw_items;
