"""Load the raw order-item file, then run the SQL layer in DuckDB."""
import duckdb
import pandas as pd

from config import COLUMNS, RAW_FILE, SQL_DIR


def _statements(path):
    lines = [ln for ln in path.read_text().splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def build():
    raw = pd.read_csv(RAW_FILE, encoding="latin-1", usecols=list(COLUMNS)).rename(columns=COLUMNS)
    raw["order_ts"] = pd.to_datetime(raw["order_ts"], format="%m/%d/%Y %H:%M")
    raw["ship_ts"] = pd.to_datetime(raw["ship_ts"], format="%m/%d/%Y %H:%M")

    con = duckdb.connect()
    con.register("raw_items_df", raw)
    con.execute("CREATE TABLE raw_items AS SELECT * FROM raw_items_df")

    print("Data quality checks")
    for stmt in _statements(SQL_DIR / "01_quality_checks.sql"):
        print("  ", con.execute(stmt).df().to_dict("records")[0])

    for name in ["02_orders.sql", "03_otif_kpis.sql"]:
        for stmt in _statements(SQL_DIR / name):
            con.execute(stmt)

    tables = {t: con.execute(f"SELECT * FROM {t}").df()
              for t in ["orders", "otif_by_mode", "otif_by_month", "transit_vs_promise"]}
    print(f"   order lines: {len(raw):,} | orders: {len(tables['orders']):,} | "
          f"{tables['orders'].order_ts.min():%Y-%m-%d} to {tables['orders'].order_ts.max():%Y-%m-%d}")
    return tables
