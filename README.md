# Retail Sales Data Warehouse & ETL Pipeline — Starter

**For:** Muhammad Talha Zahid (Mughal) — the project listed as "(in progress)" on the TenX Data Engineer CV (final CV PDF, 13 Nov 2026, 14:05 UTC).
**Status:** starter, built 13 Nov 2026. Not a finished project — finish it by running the steps below, then you can defend it in interview.

## What this is

The exact gap in the CV: no real Data Warehouse project. This is one end-to-end pipeline that covers the TenX job description in one repo:

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

Warehouse design (matches the CV wording exactly):
- `dim_date`, `dim_customer`, `dim_product`, `dim_store`
- `fact_sales` — quantity, unit price, sales amount, profit, order date
- SCD Type 2 for customer / product changes, so you can talk about slowly changing dimensions in interview
- Data-quality checks: duplicate orders, missing prices, invalid dates, negative quantities — logged, not silently loaded

## Files

| File | What it does |
|---|---|
| `src/generate_sample_data.py` | Creates `data/sample_sales.csv` (200 rows) plus a few intentional bad rows, so the DQ checks have something to catch |
| `sql/schema.sql` | PostgreSQL DDL: `staging` + `warehouse` schemas, star schema, SCD Type 2 columns, DQ log table |
| `src/etl.py` | The ETL: extract → staging load → transform + DQ checks → warehouse load (SCD Type 2) → marts |
| `requirements.txt` | `pandas`, `psycopg2-binary` (PostgreSQL only; the demo mode needs neither) |
| `data/sample_sales.csv` | Generated sample source — regenerate any time with the generator |

## Run it tonight (no PostgreSQL needed — demo mode)

```bash
cd retail-sales-warehouse-starter
python3 src/generate_sample_data.py        # creates data/sample_sales.csv
python3 src/etl.py --demo-sqlite          # full run into warehouse.db (SQLite)
python3 src/etl.py --demo-sqlite --report  # prints row counts + DQ log
```

Demo mode uses SQLite so you can prove the whole flow works before installing PostgreSQL. The logic (staging → transform → SCD Type 2 → fact) is identical; only the connection changes.

## Run it for real (PostgreSQL)

```bash
pip install -r requirements.txt
createdb retail_dw
psql -d retail_dw -f sql/schema.sql
python3 src/etl.py --postgres "postgresql://localhost/retail_dw"
```

Or set `DATABASE_URL=postgresql://localhost/retail_dw` and run `python3 src/etl.py`.

## What to do next (7–10 day plan from the CV discussion)

1. **Days 1–2:** Read `sql/schema.sql`, run the demo, draw the star schema on paper. Know the grain: one row in `fact_sales` = one order line.
2. **Days 3–5:** Point the ETL at real data — reuse your `powerbi-sales-sample` generator for the source, add an Excel source, add incremental load (only new `order_id`s).
3. **Day 6:** Data-quality checks + logging + this README's architecture diagram. Make the DQ log a table the interviewer can be shown.
4. **Days 7–8:** Rebuild the core job in Talend Open Studio (CSV → tMap → PostgreSQL). That gives you a real Talend project to back up the Talend skill on the CV.
5. **Days 9–10:** Power BI dashboard on the warehouse (not on the raw files), push everything to GitHub as a public repo.

## What you can say in interview (once you have run it)

> "I built a staging → warehouse → data mart pipeline, with a star schema, SCD Type 2, and data quality rules. Source data comes from CSV/Excel, I load it to staging first, then transform and load it to the warehouse, and Power BI reads from the data mart, not the raw files."

## Honesty rule

Do not claim this is production, or that you ran it on a Hadoop cluster, or that the Talend rebuild is done until it is. The CV says "(in progress)" — keep it that way until Days 9–10 are done. The Talend, SSIS and Hadoop skills on the CV are skills-only with no project behind them yet; this project is how Talend gets its proof. SSIS and Hadoop still need their own small proof before you claim hands-on experience with them.

## Sources

- TenX Data Engineer posting (LinkedIn 4487457553): Data Warehouse/ETL, staging area, data warehouse and data marts, data modelling, BI, SQL/RDBMS, Talend/SSIS, Hadoop preferred.
- Mughal's CV: Honda BI (Power BI/DAX/Power Query/SQL), Fiverr Python pipelines, TenX internship Dec 2024–Jan 2025.
- Design agreed with Mughal on 13 Nov 2026: staging in PostgreSQL, Python ETL, star schema, SCD Type 2, data marts, Power BI; Talend rebuild of the same job.
