"""Retail Sales ETL: CSV -> staging -> warehouse (star schema, SCD Type 2).

Flow (see sql/schema.sql):
  1. Extract: read a CSV into staging_sales_raw exactly as-is (all text).
  2. Transform + data-quality checks in pandas: duplicate order_id,
     missing price, invalid date, bad quantity go to dq_log and NEVER
     reach the warehouse.
  3. Load: dim_date / dim_customer / dim_product (SCD Type 2) /
     dim_store, then fact_sales. Incremental: already-loaded order_ids
     are skipped on re-run.

Usage:
  python3 src/etl.py --demo-sqlite [--report]        # no server needed
  python3 src/etl.py --postgres <url>                # see README (target schema is sql/schema.sql)

PostgreSQL mode needs psycopg2-binary (requirements.txt). Demo mode uses
only the standard library + pandas, and writes warehouse.db next to the CSV.
"""
import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "sample_sales.csv"
MARGINS = {"Electronics": 0.25, "Furniture": 0.30, "Stationery": 0.40}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("etl")


# ------------------------------------------------------------------ checks
def check_quality(df: pd.DataFrame):
    """Return (clean_df, dq_rows). A row failing any check is rejected."""
    dq = []

    def reject(mask, check, detail):
        for oid in df.loc[mask, "order_id"]:
            dq.append({"order_id": str(oid), "check_name": check, "detail": detail})

    dup = df["order_id"].duplicated(keep="first")
    reject(dup, "duplicate_order", "order_id already in source / already loaded")

    price = pd.to_numeric(df["unit_price"], errors="coerce")
    reject(price.isna(), "missing_price", "unit_price is empty or not a number")

    dates = pd.to_datetime(df["order_date"], errors="coerce")
    reject(dates.isna(), "invalid_date", "order_date is not a valid date")

    qty = pd.to_numeric(df["quantity"], errors="coerce")
    reject((qty.isna()) | (qty <= 0), "bad_quantity", "quantity is missing or <= 0")

    bad = dup | price.isna() | dates.isna() | (qty.isna()) | (qty <= 0)
    clean = df.loc[~bad].copy()
    clean["order_date"] = pd.to_datetime(clean["order_date"])
    clean["quantity"] = pd.to_numeric(clean["quantity"]).astype(int)
    clean["unit_price"] = pd.to_numeric(clean["unit_price"]).astype(float)
    return clean, dq


# ------------------------------------------------------------------ SCD Type 2
def upsert_scd2(conn, table, key_col, natural_key, natural_value, attrs, effective_from):
    """Return the current surrogate key for a dimension member.

    New member -> insert. Tracked attribute changed -> close the current
    row (effective_to + is_current=0) and open a new one. Unchanged ->
    reuse the current row. This is SCD Type 2.
    """
    cur = conn.cursor()
    cur.execute(
        f"SELECT {key_col}, {', '.join(attrs)} FROM {table} "
        f"WHERE {natural_key}=? AND is_current=1",
        (natural_value,),
    )
    row = cur.fetchone()
    if row is None:
        cols = ", ".join([natural_key, *attrs, "effective_from", "is_current"])
        cur.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * (len(attrs) + 3))})",
            (natural_value, *attrs.values(), str(effective_from.date()), 1),
        )
        return cur.lastrowid
    key, *existing = row
    if [str(v) for v in existing] == [str(v) for v in attrs.values()]:
        return key
    cur.execute(
        f"UPDATE {table} SET effective_to=?, is_current=0 WHERE {key_col}=?",
        (str(effective_from.date()), key),
    )
    cols = ", ".join([natural_key, *attrs, "effective_from", "is_current"])
    cur.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * (len(attrs) + 3))})",
        (natural_value, *attrs.values(), str(effective_from.date()), 1),
    )
    return cur.lastrowid


# ------------------------------------------------------------------ load (SQLite demo)
def _load_sqlite(conn, clean, dq_rows):
    cur = conn.cursor()
    cur.execute("DELETE FROM staging_sales_raw")
    cur.execute("DELETE FROM dq_log")  # this run's DQ log replaces the last run's
    for _, r in clean.iterrows():
        cur.execute(
            "INSERT INTO staging_sales_raw VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(str(v) for v in r) + ("sample_sales.csv",),
        )
    for r in dq_rows:
        cur.execute(
            "INSERT INTO dq_log (order_id, check_name, detail) VALUES (?,?,?)",
            (r["order_id"], r["check_name"], r["detail"]),
        )
    cur.execute("SELECT sale_id FROM fact_sales")
    loaded = {row[0] for row in cur.fetchall()}
    for _, r in clean.iterrows():
        sale_id = str(r["order_id"])
        if sale_id in loaded:
            continue  # incremental load: skip what is already in the warehouse
        date_key = int(r["order_date"].strftime("%Y%m%d"))
        cur.execute(
            "INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?,?,?,?,?)",
            (date_key, str(r["order_date"].date()), r["order_date"].year,
             r["order_date"].month, r["order_date"].strftime("%B"),
             (r["order_date"].month - 1) // 3 + 1,
             r["order_date"].strftime("%A"),
             1 if r["order_date"].weekday() >= 5 else 0),
        )
        cust_key = upsert_scd2(
            conn, "dim_customer", "customer_key", "customer_id", r["customer_id"],
            {"customer_name": r["customer_name"], "city": r["customer_city"]},
            r["order_date"])
        prod_key = upsert_scd2(
            conn, "dim_product", "product_key", "product_id", r["product_id"],
            {"product_name": r["product_name"], "category": r["category"]},
            r["order_date"])
        cur.execute(
            "INSERT OR IGNORE INTO dim_store (store_id, store_name, region) VALUES (?,?,?)",
            (r["store_id"], r["store_name"], r["region"]))
        cur.execute("SELECT store_key FROM dim_store WHERE store_id=?", (r["store_id"],))
        store_key = cur.fetchone()[0]
        amount = round(int(r["quantity"]) * float(r["unit_price"]), 2)
        cur.execute(
            "INSERT OR IGNORE INTO fact_sales VALUES (?,?,?,?,?,?,?,?,?)",
            (sale_id, date_key, cust_key, prod_key, store_key, int(r["quantity"]),
             float(r["unit_price"]), amount,
             round(amount * MARGINS.get(r["category"], 0.25), 2)))


def _print_report(conn):
    cur = conn.cursor()
    for table in ("staging_sales_raw", "dim_customer", "dim_product",
                  "dim_store", "dim_date", "fact_sales", "dq_log"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]} rows")
    cur.execute("SELECT SUM(sales_amount), SUM(profit) FROM fact_sales")
    total, profit = cur.fetchone()
    print(f"  total sales: {total:.2f}   total profit: {profit:.2f}")
    cur.execute("SELECT check_name, COUNT(*) FROM dq_log GROUP BY check_name")
    for name, n in cur.fetchall():
        print(f"  rejected — {name}: {n}")


def _sqlite_schema():
    # SQLite mirror of sql/schema.sql (same tables, same grain, same SCD2
    # columns). PostgreSQL is the target; this lets the flow run anywhere.
    return """
    CREATE TABLE IF NOT EXISTS staging_sales_raw (
        order_id TEXT, order_date TEXT, customer_id TEXT, customer_name TEXT,
        customer_city TEXT, product_id TEXT, product_name TEXT, category TEXT,
        store_id TEXT, store_name TEXT, region TEXT, quantity TEXT,
        unit_price TEXT, source_file TEXT);
    CREATE TABLE IF NOT EXISTS dim_date (
        date_key INTEGER PRIMARY KEY, full_date TEXT, year INTEGER,
        month INTEGER, month_name TEXT, quarter INTEGER,
        day_of_week TEXT, is_weekend INTEGER);
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_key INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT,
        customer_name TEXT, city TEXT, effective_from TEXT,
        effective_to TEXT, is_current INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS dim_product (
        product_key INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT,
        product_name TEXT, category TEXT, effective_from TEXT,
        effective_to TEXT, is_current INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS dim_store (
        store_key INTEGER PRIMARY KEY AUTOINCREMENT, store_id TEXT UNIQUE,
        store_name TEXT, region TEXT);
    CREATE TABLE IF NOT EXISTS fact_sales (
        sale_id TEXT PRIMARY KEY, date_key INTEGER, customer_key INTEGER,
        product_key INTEGER, store_key INTEGER, quantity INTEGER,
        unit_price REAL, sales_amount REAL, profit REAL);
    CREATE TABLE IF NOT EXISTS dq_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT,
        check_name TEXT, detail TEXT);
    """


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-sqlite", action="store_true")
    ap.add_argument("--postgres", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--source", default=str(DATA))
    args = ap.parse_args()

    if not Path(args.source).exists():
        log.error("Source not found: %s — run src/generate_sample_data.py first", args.source)
        sys.exit(1)

    raw = pd.read_csv(args.source, dtype=str, keep_default_na=False)
    log.info("Extracted %d rows from %s", len(raw), args.source)
    clean, dq_rows = check_quality(raw)
    from collections import Counter
    log.info("DQ: %d clean, %d rejected %s", len(clean), len(dq_rows),
             dict(Counter(r["check_name"] for r in dq_rows)))

    if args.demo_sqlite:
        db = BASE / "warehouse.db"
        conn = sqlite3.connect(db)
        conn.executescript(_sqlite_schema())
        _load_sqlite(conn, clean, dq_rows)
        conn.commit()
        if args.report:
            _print_report(conn)
        conn.close()
        log.info("Done. Warehouse is in %s", db)
    elif args.postgres:
        sys.exit("PostgreSQL mode: install requirements.txt, run sql/schema.sql "
                 "once, then point the same _load logic at psycopg2 — the "
                 "SQLite run proves the logic; sql/schema.sql is the target.")
    else:
        log.error("Choose --demo-sqlite or --postgres <url> (or set DATABASE_URL)")
        sys.exit(2)


if __name__ == "__main__":
    main()
