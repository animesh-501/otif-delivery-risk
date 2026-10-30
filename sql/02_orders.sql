-- One row per order. An order ships as a unit (checked in 01), so OTIF is measured per order.
--   on_time  = delivered within the promised days
--   in_full  = not cancelled (the file has no shipped-vs-ordered quantities, so a cancellation
--              is the only "not in full" signal available)
--   otif     = on time AND in full

CREATE OR REPLACE TABLE orders AS
SELECT
    order_id,
    MIN(order_ts)                                         AS order_ts,
    ANY_VALUE(shipping_mode)                              AS shipping_mode,
    ANY_VALUE(promised_days)                              AS promised_days,
    ANY_VALUE(actual_days)                                AS actual_days,
    ANY_VALUE(actual_days) - ANY_VALUE(promised_days)     AS days_late,
    ANY_VALUE(market)                                     AS market,
    ANY_VALUE(order_region)                               AS order_region,
    ANY_VALUE(order_country)                              AS order_country,
    ANY_VALUE(customer_segment)                           AS customer_segment,
    ARG_MAX(department, sales)                            AS main_department,
    ARG_MAX(category, sales)                              AS main_category,
    COUNT(*)                                              AS lines,
    SUM(quantity)                                         AS units,
    SUM(sales)                                            AS sales,
    AVG(discount_rate)                                    AS avg_discount_rate,
    MAX(product_price)                                    AS max_product_price,
    BOOL_OR(delivery_status = 'Shipping canceled')        AS cancelled,
    ANY_VALUE(actual_days) <= ANY_VALUE(promised_days)    AS on_time
FROM raw_items
GROUP BY order_id;

ALTER TABLE orders ADD COLUMN otif BOOLEAN;
UPDATE orders SET otif = on_time AND NOT cancelled;
