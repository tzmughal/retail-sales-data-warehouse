# Retail Sales Data Warehouse & ETL Pipeline

## What this is

An end-to-end pipeline that takes retail sales data from CSV / Excel / API sources, loads it into a staging area, transforms it, and loads it into a star-schema data warehouse with data marts for reporting.

```
CSV / Excel / API sources
        ↓
Staging Area (PostgreSQL) — raw data as-is
        ↓
Transform (Python + Pandas) — clean, deduplicate, business rules, data-quality checks
        ↓
Data Warehouse — star schema, SCD Type 2
        ↓
Data Marts — Sales Mart, Product Mart
        ↓
Power BI Dashboard — revenue, region, category KPIs
```

## Warehouse design

- `dim_date`, `dim_customer`, `dim_product`, `dim_store`
- `fact_sales` — quantity, unit price, sales amount, profit, order date
- SCD Type 2 for customer / product changes, so history is kept when attributes change
- Data-quality checks: duplicate orders, missing prices, invalid dates, negative quantities — bad rows are logged, not silently loaded

## Files

| File | What it does |
|---|---|
| `src/generate_sample_data.py` | Creates `data/sample_sales.csv` (200 rows) plus a few intentional bad rows, so the DQ checks have something to catch |
| `sql/schema.sql` | PostgreSQL DDL: `staging` + `warehouse` schemas, star schema, SCD Type 2 columns, DQ log table |
| `src/etl.py` | The ETL: extract → staging load → transform + DQ checks → warehouse load (SCD Type 2) → marts |
| `requirements.txt` | `pandas`, `psycopg2-binary` (PostgreSQL only; the demo mode needs neither) |
| `data/sample_sales.csv` | Sample source data — regenerate any time with the generator |

## Run it (demo mode, no PostgreSQL needed)

```bash
cd retail-sales-data-warehouse
python3 src/generate_sample_data.py        # creates data/sample_sales.csv
python3 src/etl.py --demo-sqlite          # full run into warehouse.db (SQLite)
python3 src/etl.py --demo-sqlite --report  # prints row counts + DQ log
```

Demo mode uses SQLite so the whole flow can run without installing PostgreSQL. The logic (staging → transform → SCD Type 2 → fact) is identical; only the connection changes.

## Run it with PostgreSQL

```bash
pip install -r requirements.txt
createdb retail_dw
psql -d retail_dw -f sql/schema.sql
python3 src/etl.py --postgres "postgresql://localhost/retail_dw"
```

Or set `DATABASE_URL=postgresql://localhost/retail_dw` and run `python3 src/etl.py`.
