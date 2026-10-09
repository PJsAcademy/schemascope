"""Phase 2 invariants (7)."""
from pathlib import Path
import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "checkpoints" / "retail.db"


@pytest.fixture(scope="module")
def con():
    if not DB_PATH.exists():
        pytest.skip("retail.db missing — run `python src/phase2_views.py` first")
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def test_vw_rfm_exists(con):
    n = con.execute("SELECT COUNT(*) FROM vw_rfm").fetchone()[0]
    assert n > 0


def test_rfm_has_all_segments_present_or_valid(con):
    valid = {"Champions", "Loyal", "Big Spenders", "Promising",
             "At Risk", "Can't Lose", "Hibernating", "Needs Attention"}
    actual = {r[0] for r in con.execute("SELECT DISTINCT segment FROM vw_rfm").fetchall()}
    assert actual.issubset(valid), f"unexpected segments: {actual - valid}"


def test_rfm_scores_in_1_5(con):
    for col in ("r_score", "f_score", "m_score"):
        bad = con.execute(f"SELECT COUNT(*) FROM vw_rfm WHERE {col} < 1 OR {col} > 5").fetchone()[0]
        assert bad == 0, f"{col} out of 1-5 range in {bad} rows"


def test_cohort_retention_pct_in_0_100(con):
    bad = con.execute(
        "SELECT COUNT(*) FROM vw_cohort_retention WHERE retention_pct < 0 OR retention_pct > 100"
    ).fetchone()[0]
    assert bad == 0


def test_cohort_month_0_is_100_pct(con):
    """Every cohort has 100% retention at index 0 by definition (they just signed up)."""
    off = con.execute(
        "SELECT COUNT(*) FROM vw_cohort_retention WHERE cohort_index = 0 AND retention_pct < 99.9"
    ).fetchone()[0]
    assert off == 0, "cohort-0 retention should always be 100%"


def test_top_products_sorted_desc(con):
    rows = con.execute("SELECT total_revenue FROM vw_top_products").fetchall()
    rev = [r[0] for r in rows]
    assert rev == sorted(rev, reverse=True)


def test_daily_revenue_cumulative_monotonic(con):
    rows = con.execute("SELECT cumulative_revenue FROM vw_daily_revenue").fetchall()
    cum = [r[0] for r in rows]
    assert all(a <= b for a, b in zip(cum, cum[1:])), "cumulative revenue is not monotonic"
