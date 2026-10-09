"""Phase 1 — SchemaScope ingest.

Loads UK Online Retail II CSV if present, else synthesises a representative
sample (~500 customers × ~5000 transactions × ~200 products over 2 years).
Writes everything into DuckDB at checkpoints/retail.db as the `transactions`
table.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
RAW = HERE / "data" / "online_retail_ii.csv"
CHECKPOINTS = HERE / "checkpoints"
CHECKPOINTS.mkdir(exist_ok=True)
DB_PATH = CHECKPOINTS / "retail.db"

COUNTRIES = ["United Kingdom"] * 20 + [
    "Germany", "France", "EIRE", "Spain", "Netherlands", "Belgium",
    "Switzerland", "Portugal", "Australia", "Norway",
]
PRODUCT_FAMILIES = [
    ("LANTERN", 8.75), ("CANDLE HOLDER", 2.95), ("HEART DECORATION", 4.25),
    ("MUG CERAMIC", 3.75), ("TEA TOWEL VINTAGE", 2.95), ("CUSHION COVER", 5.95),
    ("GARDEN BUNTING", 7.95), ("WRAPPING PAPER", 1.25), ("GREETING CARD", 0.65),
    ("STORAGE JAR", 4.25), ("BISCUIT TIN", 6.95), ("JIGSAW PUZZLE", 3.95),
    ("CHALKBOARD", 5.25), ("CLOCK WOODEN", 12.95), ("APRON", 6.75),
]


def synthesise(n_customers: int = 500, n_months: int = 24, seed: int = 42) -> pd.DataFrame:
    """Deterministic UK Online Retail II-shaped sample with realistic patterns
    for cohort retention + RFM segmentation."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2022-01-01")

    # Build the product catalog (StockCode + Description + UnitPrice)
    products = []
    stock_id = 10000
    for family, base_price in PRODUCT_FAMILIES:
        for variant in ("RED", "WHITE", "BLUE", "GREEN", "PINK",
                        "VINTAGE", "MINI", "LARGE", "SET OF 3", "SET OF 6",
                        "WITH FLOWERS", "WITH STARS", "ANTIQUE"):
            products.append({
                "StockCode": str(stock_id),
                "Description": f"{family} {variant}".strip(),
                "UnitPrice": round(base_price * rng.uniform(0.85, 1.25), 2),
            })
            stock_id += 1
    products_df = pd.DataFrame(products)

    # Each customer gets a signup month + lifetime orders drawn from a Pareto-ish
    # distribution (long tail of one-time buyers, small core of regulars).
    rows = []
    for cid in range(1, n_customers + 1):
        signup_month = int(rng.integers(0, n_months - 1))
        lifetime_orders = int(np.clip(rng.pareto(1.3) * 4 + 1, 1, 40))
        country = rng.choice(COUNTRIES)

        for _ in range(lifetime_orders):
            # Days since signup, decaying activity probability
            days_offset = int(rng.exponential(90))
            order_date = start + pd.Timedelta(days=signup_month * 30 + days_offset)
            if order_date >= start + pd.Timedelta(days=n_months * 30):
                continue

            # 1-5 line items per order
            n_lines = int(rng.integers(1, 6))
            invoice = f"5{int(rng.integers(10000, 99999))}"
            for _ in range(n_lines):
                p = products_df.sample(1, random_state=int(rng.integers(0, 10**9))).iloc[0]
                qty = int(rng.integers(1, 13))
                rows.append({
                    "Invoice": invoice,
                    "StockCode": p["StockCode"],
                    "Description": p["Description"],
                    "Quantity": qty,
                    "InvoiceDate": order_date,
                    "Price": p["UnitPrice"],
                    "Customer_ID": cid,
                    "Country": country,
                })

    df = pd.DataFrame(rows)
    # Plant a few dirty rows for Phase 1 to catch
    bad_qty = rng.choice(df.index, size=20, replace=False)
    df.loc[bad_qty, "Quantity"] = -1
    bad_price = rng.choice(df.index, size=15, replace=False)
    df.loc[bad_price, "Price"] = 0.0
    return df


def load_bronze() -> pd.DataFrame:
    if RAW.exists():
        print(f"[bronze] reading {RAW}")
        return pd.read_csv(RAW)
    print(f"[bronze] {RAW} missing — synthesising sample (seed=42)")
    return synthesise()


def clean(bronze: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    df = bronze.copy()
    rejects = {
        "R1_non_positive_qty":   int((df["Quantity"] <= 0).sum()),
        "R2_zero_price":          int((df["Price"] <= 0).sum()),
        "R3_missing_customer":    int(df["Customer_ID"].isna().sum()),
    }
    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    df = df.dropna(subset=["Customer_ID"])
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Revenue"] = df["Quantity"] * df["Price"]
    return df.reset_index(drop=True), rejects


def main() -> None:
    bronze = load_bronze()
    print(f"[bronze] {len(bronze):,} rows")
    silver, rejects = clean(bronze)
    print(f"[silver] {len(silver):,} rows after cleaning")
    for rule, n in rejects.items():
        print(f"  rejected {n:>4}  {rule}")

    # Fresh DuckDB file every time; small enough that rebuild is cheaper than merge.
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    con.register("silver_df", silver)
    con.execute("CREATE TABLE transactions AS SELECT * FROM silver_df")
    n = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    print(f"[duckdb] wrote transactions ({n:,} rows) to {DB_PATH}")
    con.close()


if __name__ == "__main__":
    main()
