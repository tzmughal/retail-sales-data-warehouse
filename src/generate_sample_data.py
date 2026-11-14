"""Generate sample retail sales data for the warehouse starter.

Creates data/sample_sales.csv (200 clean rows + a few intentional bad rows
so the ETL's data-quality checks have something to catch):
  - 1 duplicate order_id
  - 1 row with a missing unit_price
  - 1 row with an invalid order_date
  - 1 row with a negative quantity

Run:  python3 src/generate_sample_data.py
"""
import csv
import random
from pathlib import Path

random.seed(42)

OUT = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"

CUSTOMERS = [
    ("C001", "Ayesha Khan", "Lahore"), ("C002", "Bilal Ahmed", "Rawalpindi"),
    ("C003", "Sara Malik", "Islamabad"), ("C004", "Usman Ali", "Karachi"),
    ("C005", "Hina Shah", "Lahore"), ("C006", "Omar Farooq", "Faisalabad"),
]
PRODUCTS = [
    ("P001", "Wireless Mouse", "Electronics", 1500),
    ("P002", "Mechanical Keyboard", "Electronics", 8500),
    ("P003", "Office Chair", "Furniture", 22000),
    ("P004", "Notebook Pack", "Stationery", 450),
    ("P005", "LED Desk Lamp", "Furniture", 3200),
    ("P006", "USB-C Hub", "Electronics", 4800),
]
STORES = [("S01", "Lahore Main", "Punjab"), ("S02", "Rawalpindi Branch", "Punjab"),
          ("S03", "Karachi South", "Sindh")]


def main() -> None:
    rows = []
    for i in range(1, 201):
        cust = random.choice(CUSTOMERS)
        prod = random.choice(PRODUCTS)
        store = random.choice(STORES)
        rows.append({
            "order_id": f"ORD-{1000 + i}",
            "order_date": f"2026-{random.randint(1, 10):02d}-{random.randint(1, 28):02d}",
            "customer_id": cust[0], "customer_name": cust[1], "customer_city": cust[2],
            "product_id": prod[0], "product_name": prod[1], "category": prod[2],
            "store_id": store[0], "store_name": store[1], "region": store[2],
            "quantity": random.randint(1, 5),
            "unit_price": prod[3],
        })
    # Intentional bad rows for the DQ checks (see src/etl.py).
    rows.append(dict(rows[0]))  # duplicate order_id
    bad = dict(rows[1]); bad["order_id"] = "ORD-9991"; bad["unit_price"] = ""; rows.append(bad)
    bad = dict(rows[2]); bad["order_id"] = "ORD-9992"; bad["order_date"] = "not-a-date"; rows.append(bad)
    bad = dict(rows[3]); bad["order_id"] = "ORD-9993"; bad["quantity"] = -2; rows.append(bad)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT} (200 clean + 4 bad, by design)")


if __name__ == "__main__":
    main()
