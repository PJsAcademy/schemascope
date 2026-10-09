"""Phase 1 invariants (6)."""
from pathlib import Path
import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "checkpoints" / "retail.db"


@pytest.fixture(scope="module")
def con():
    if not DB_PATH.exists():
        pytest.skip("retail.db missing — run `python src/phase1_ingest.py` first")
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def test_transactions_exists(con):
    rows = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert rows > 0


def test_required_columns(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(transactions)").fetchall()}
    assert {"Invoice", "StockCode", "Quantity", "InvoiceDate", "Price",
            "Customer_ID", "Country", "Revenue"}.issubset(cols)


def test_no_non_positive_quantity(con):
    assert con.execute("SELECT COUNT(*) FROM transactions WHERE Quantity <= 0").fetchone()[0] == 0


def test_no_zero_price(con):
    assert con.execute("SELECT COUNT(*) FROM transactions WHERE Price <= 0").fetchone()[0] == 0


def test_no_missing_customer(con):
    assert con.execute("SELECT COUNT(*) FROM transactions WHERE Customer_ID IS NULL").fetchone()[0] == 0


def test_revenue_matches_qty_price(con):
    diff = con.execute(
        "SELECT MAX(ABS(Revenue - Quantity * Price)) FROM transactions"
    ).fetchone()[0]
    assert diff < 0.01, f"Revenue column drifted from Quantity * Price (max diff {diff})"
