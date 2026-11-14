-- Retail Sales Data Warehouse — PostgreSQL DDL
-- Grain: one row in warehouse.fact_sales = one order line.
-- SCD Type 2 on dim_customer and dim_product: a changed attribute closes
-- the old row (effective_to + is_current = false) and opens a new row.
-- Run:  psql -d retail_dw -f sql/schema.sql

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;

-- ---------------------------------------------------------------- staging
-- Raw data as-is: everything text, no cleaning here. Cleaning happens
-- in Python between staging and warehouse, so a bad source row never
-- corrupts the warehouse and can always be traced back to its file.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.sales_raw (
    order_id     TEXT,
    order_date   TEXT,
    customer_id  TEXT,
    customer_name TEXT,
    customer_city TEXT,
    product_id   TEXT,
    product_name TEXT,
    category     TEXT,
    store_id     TEXT,
    store_name   TEXT,
    region       TEXT,
    quantity     TEXT,
    unit_price   TEXT,
    source_file  TEXT,
    loaded_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------- dimensions
CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key     INT PRIMARY KEY,          -- YYYYMMDD, e.g. 20260115
    full_date    DATE NOT NULL,
    year         INT NOT NULL,
    month        INT NOT NULL,
    month_name   TEXT NOT NULL,
    quarter      INT NOT NULL,
    day_of_week  TEXT NOT NULL,
    is_weekend   BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_key  SERIAL PRIMARY KEY,     -- surrogate key (SCD Type 2)
    customer_id   TEXT NOT NULL,          -- natural key from source
    customer_name TEXT NOT NULL,
    city          TEXT,
    effective_from DATE NOT NULL,
    effective_to   DATE,                  -- NULL = current row
    is_current    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouse.dim_product (
    product_key   SERIAL PRIMARY KEY,
    product_id    TEXT NOT NULL,
    product_name  TEXT NOT NULL,
    category      TEXT,
    effective_from DATE NOT NULL,
    effective_to   DATE,
    is_current    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouse.dim_store (
    store_key  SERIAL PRIMARY KEY,
    store_id   TEXT NOT NULL UNIQUE,
    store_name TEXT NOT NULL,
    region     TEXT
);

-- ---------------------------------------------------------------- fact
CREATE TABLE IF NOT EXISTS warehouse.fact_sales (
    sale_id       TEXT PRIMARY KEY,        -- order_id + line, natural key
    date_key      INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    customer_key  INT NOT NULL REFERENCES warehouse.dim_customer(customer_key),
    product_key   INT NOT NULL REFERENCES warehouse.dim_product(product_key),
    store_key     INT NOT NULL REFERENCES warehouse.dim_store(store_key),
    quantity      INT NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    sales_amount  NUMERIC(12,2) NOT NULL, -- quantity * unit_price
    profit        NUMERIC(12,2) NOT NULL  -- sales_amount * category margin (see etl.py)
);

-- ---------------------------------------------------------------- data quality log
-- Bad rows go here, never into the warehouse. Show this table in interview:
-- it proves you check data instead of silently loading it.
CREATE TABLE IF NOT EXISTS warehouse.dq_log (
    log_id       SERIAL PRIMARY KEY,
    order_id     TEXT,
    check_name   TEXT NOT NULL,           -- duplicate_order | missing_price | invalid_date | bad_quantity
    detail       TEXT,
    logged_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------- data marts (views on the warehouse)
-- A mart is a subject-area slice of the warehouse, built for one team's
-- reporting. Power BI reads from the mart, not from raw files.
CREATE OR REPLACE VIEW warehouse.mart_sales AS
SELECT f.sale_id, d.full_date, d.year, d.month, d.month_name,
       c.customer_name, c.city, p.product_name, p.category,
       s.store_name, s.region,
       f.quantity, f.unit_price, f.sales_amount, f.profit
FROM warehouse.fact_sales f
JOIN warehouse.dim_date d     ON d.date_key = f.date_key
JOIN warehouse.dim_customer c ON c.customer_key = f.customer_key
JOIN warehouse.dim_product p  ON p.product_key = f.product_key
JOIN warehouse.dim_store s    ON s.store_key = f.store_key;

CREATE OR REPLACE VIEW warehouse.mart_product AS
SELECT p.category, p.product_name,
       COUNT(*) AS order_lines, SUM(f.quantity) AS units_sold,
       SUM(f.sales_amount) AS revenue, SUM(f.profit) AS profit
FROM warehouse.fact_sales f
JOIN warehouse.dim_product p ON p.product_key = f.product_key
GROUP BY p.category, p.product_name;
