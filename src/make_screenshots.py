"""Regenerate every README screenshot from the live warehouse.db.

Every number in every image comes from a fresh run of the pipeline
(`generate_sample_data.py` + `etl.py --demo-sqlite --report`) and from
queries against the warehouse.db that run produced -- nothing is
hard-coded. Re-run any time the data or the code changes:

    python3 src/make_screenshots.py

Outputs (docs/screenshots/):
  01-demo-run.png        terminal capture of the fresh ETL run
  03-warehouse-tables.png  fact_sales, first 5 rows
  04-data-quality-log.png  dq_log, all rejected rows
  05-sales-summary.png    total sales by category and by region
  06-monthly-sales.png   total sales by month

02-star-schema.png is a schema diagram (no numbers in it) and is not
regenerated here; it is drawn from sql/schema.sql by hand.

Needs matplotlib (see requirements.txt). The ETL itself does not need it.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "warehouse.db"
SHOTS = BASE / "docs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

ORANGE = "#ea580c"
ORANGE_LIGHT = "#fb923c"
BLUE_BG = "#dbeafe"
DARK = "#1e293b"


def money(v):
    return f"{v:,.2f}"


def run(cmd):
    """Run a script; return (stdout, stderr) as separate strings."""
    r = subprocess.run([sys.executable, *cmd], cwd=BASE,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        sys.exit(f"command failed: {' '.join(cmd)}")
    return r.stdout, r.stderr


def relative(text):
    """Show paths as the user sees them (data/...), not absolute VM paths."""
    return text.replace(str(BASE) + "/", "").replace(str(BASE), ".")


def wrap(line, width=100):
    """Wrap one long terminal line at a space, like a terminal would."""
    if len(line) <= width:
        return [line]
    cut = line.rfind(" ", 0, width)
    if cut == -1:
        cut = width
    return [line[:cut]] + wrap("    " + line[cut + 1:].lstrip(), width)


# ---------------------------------------------------------------- 01 demo run
def shot_demo_run():
    # Fresh from scratch: delete the DB first, so surrogate keys / log_ids
    # start at 1 exactly as they do on a first run anywhere.
    if DB.exists():
        DB.unlink()
    gen_out, _ = run(["src/generate_sample_data.py"])
    # INFO log lines go to stderr, the report to stdout. In a real terminal
    # they interleave as: Extracted, DQ, report, Done -- but piped stdout
    # is block-buffered, so rebuild that order explicitly instead of
    # merging the streams (merging puts Done before the report).
    etl_out, etl_err = run(["src/etl.py", "--demo-sqlite", "--report"])
    err_lines = [relative(l) for l in etl_err.strip().splitlines()]
    done = [l for l in err_lines if "Done." in l]
    head = [l for l in err_lines if "Done." not in l]
    lines = ["$ python3 src/generate_sample_data.py",
             relative(gen_out.strip()), "",
             "$ python3 src/etl.py --demo-sqlite --report"]
    for l in head:
        lines += wrap(l)
    lines += [relative(l) for l in etl_out.strip().splitlines()]
    lines += done
    n = len(lines)
    fig, ax = plt.subplots(figsize=(10.5, 0.9 + 0.21 * n))
    fig.patch.set_facecolor("#1f2937")
    ax.set_facecolor("#1f2937")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    # window dots + title bar
    for i, c in enumerate(["#ef4444", "#f59e0b", "#22c55e"]):
        ax.add_patch(plt.Circle((0.03 + i * 0.025, 0.955), 0.011,
                                color=c, transform=ax.transAxes))
    ax.text(0.5, 0.955, "Terminal — python3 src/etl.py --demo-sqlite --report",
            color="white", ha="center", va="center",
            fontsize=11, fontweight="bold", family="monospace",
            transform=ax.transAxes)
    body = "\n".join(lines)
    ax.text(0.02, 0.92, body, color="#e5e7eb", fontsize=10,
            family="monospace", va="top", ha="left", transform=ax.transAxes)
    fig.savefig(SHOTS / "01-demo-run.png", dpi=130,
                facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print("wrote 01-demo-run.png")


# ---------------------------------------------------------------- tables
def table_shot(filename, title, columns, rows, wrap_widths=None,
               col_widths=None):
    """Render a DB table as an image. wrap_widths/col_widths are per-column:
    wrap_widths[i] is the max characters per line in column i, col_widths[i]
    its share of the table width. Both must match, or long text overflows
    the figure instead of wrapping."""
    import textwrap
    if wrap_widths is None:
        wrap_widths = [30] * len(columns)
    wrapped = []
    max_lines = 1
    for row in rows:
        wrow = []
        for v, w in zip(row, wrap_widths):
            parts = textwrap.wrap(str(v), w) or [""]
            max_lines = max(max_lines, len(parts))
            wrow.append("\n".join(parts))
        wrapped.append(wrow)
    width = 11.0
    height = 0.75 + 0.34 * max_lines * len(rows) + 0.3
    fig, ax = plt.subplots(figsize=(width, height))
    ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=10)
    tbl = ax.table(cellText=wrapped, colLabels=columns, loc="upper center",
                   cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.1 * max_lines + 0.4)
    if col_widths:
        for (r, c), cell in tbl.get_celld().items():
            cell.set_width(col_widths[c])
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#cbd5e1")
        cell.set_linewidth(0.8)
        if r == 0:
            cell.set_facecolor(ORANGE)
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#f8fafc")
        else:
            cell.set_facecolor("white")
    fig.savefig(SHOTS / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {filename}")


# ---------------------------------------------------------------- bar charts
def bar_shot(filename, title, panels, horizontal=False):
    """panels: list of (panel_title, labels, values)."""
    n = len(panels)
    if horizontal:
        fig, axes = plt.subplots(n, 1, figsize=(9.5, 2.2 + 0.55 * max(len(p[1]) for p in panels)))
    else:
        fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 4.6))
    if n == 1:
        axes = [axes]
    fig.suptitle(title, fontsize=13, fontweight="bold")
    for ax, (ptitle, labels, values) in zip(axes, panels):
        colors = [ORANGE, ORANGE_LIGHT, "#fdba74", "#fed7aa",
                  "#ffedd5", "#ea580c", "#fb923c", "#fdba74",
                  "#fed7aa", "#ffedd5"][:len(labels)]
        if horizontal:
            bars = ax.barh(labels, values, color=colors, height=0.6)
            ax.set_title(ptitle, fontsize=12, fontweight="bold", pad=10)
            ax.set_xlabel("Sales amount")
            ax.ticklabel_format(style="plain", axis="x")
            ax.invert_yaxis()  # first month on top
            ax.spines[["top", "right"]].set_visible(False)
            for b, v in zip(bars, values):
                ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
                        f"  {v:,.0f}", ha="left", va="center",
                        fontsize=11, fontweight="bold")
            ax.set_xlim(0, max(values) * 1.2)
        else:
            bars = ax.bar(labels, values, color=colors, width=0.6)
            ax.set_title(ptitle, fontsize=12, fontweight="bold", pad=10)
            ax.set_ylabel("Sales amount")
            ax.ticklabel_format(style="plain", axis="y")
            ax.spines[["top", "right"]].set_visible(False)
            for b, v in zip(bars, values):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                        f"{v:,.0f}", ha="center", va="bottom",
                        fontsize=11, fontweight="bold")
            ax.set_ylim(0, max(values) * 1.15)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(SHOTS / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {filename}")


def main():
    shot_demo_run()  # re-runs the pipeline fresh; warehouse.db is rebuilt
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    total_sales, total_profit = cur.execute(
        "SELECT SUM(sales_amount), SUM(profit) FROM fact_sales").fetchone()
    n_fact = cur.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]

    fact5 = cur.execute(
        "SELECT sale_id, date_key, customer_key, product_key, store_key,"
        " quantity, unit_price, sales_amount, profit FROM fact_sales"
        " ORDER BY sale_id LIMIT 5").fetchall()
    table_shot("03-warehouse-tables.png",
               f"fact_sales — first 5 rows ({n_fact} rows loaded)",
               ["order_id", "date_key", "cust", "prod", "store", "qty",
                "unit_price", "sales", "profit"],
               [[r[0], r[1], r[2], r[3], r[4], r[5],
                 f"{r[6]:,.2f}", f"{r[7]:,.2f}", f"{r[8]:,.2f}"]
                for r in fact5],
               wrap_widths=[12, 10, 5, 5, 6, 4, 11, 11, 10],
               col_widths=[0.15, 0.13, 0.07, 0.07, 0.08, 0.06,
                           0.15, 0.15, 0.14])

    dq = cur.execute(
        "SELECT log_id, order_id, check_name, detail FROM dq_log"
        " ORDER BY log_id").fetchall()
    table_shot("04-data-quality-log.png",
               f"dq_log — {len(dq)} bad rows rejected, none loaded into the warehouse",
               ["log_id", "order_id", "check_name", "detail"],
               [[str(v) for v in row] for row in dq],
               wrap_widths=[7, 12, 18, 58],
               col_widths=[0.07, 0.13, 0.20, 0.60])

    by_cat = cur.execute(
        "SELECT p.category, SUM(f.sales_amount) FROM fact_sales f"
        " JOIN dim_product p ON p.product_key = f.product_key"
        " GROUP BY p.category ORDER BY SUM(f.sales_amount) DESC").fetchall()
    by_region = cur.execute(
        "SELECT s.region, SUM(f.sales_amount) FROM fact_sales f"
        " JOIN dim_store s ON s.store_key = f.store_key"
        " GROUP BY s.region ORDER BY SUM(f.sales_amount) DESC").fetchall()
    bar_shot("05-sales-summary.png",
             f"Sales summary — from fact_sales ({n_fact} rows, total {money(total_sales)})",
             [("Total sales by category", [r[0] for r in by_cat], [r[1] for r in by_cat]),
              ("Total sales by region", [r[0] for r in by_region], [r[1] for r in by_region])])

    by_month = cur.execute(
        "SELECT d.month_name, SUM(f.sales_amount) FROM fact_sales f"
        " JOIN dim_date d ON d.date_key = f.date_key"
        " GROUP BY d.month ORDER BY d.month").fetchall()
    bar_shot("06-monthly-sales.png",
             f"Sales by month, Jan–Oct 2026 — from fact_sales (total {money(total_sales)})",
             [("Total sales by month",
               [r[0] for r in by_month], [r[1] for r in by_month])],
             horizontal=True)

    conn.close()
    print(f"done. total sales {money(total_sales)}, total profit {money(total_profit)}")


if __name__ == "__main__":
    main()
