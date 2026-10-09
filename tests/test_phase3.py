"""Phase 3 invariants (7)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from phase3_nlsql import nl_to_sql  # noqa: E402


def test_revenue_by_country():
    sql = nl_to_sql("revenue by country")
    assert "Country" in sql and "ORDER BY revenue DESC" in sql


def test_orders_by_month():
    sql = nl_to_sql("orders by month")
    assert "DATE_TRUNC('month'" in sql and "COUNT(DISTINCT Invoice)" in sql


def test_segment_lookup_champions():
    sql = nl_to_sql("customers in champions")
    assert "vw_rfm" in sql and "'champions'" in sql


def test_top_n_products():
    assert nl_to_sql("top 10 products") == "SELECT * FROM vw_top_products LIMIT 10"
    assert nl_to_sql("top 5 products")  == "SELECT * FROM vw_top_products LIMIT 5"


def test_top_default_10():
    assert "LIMIT 10" in nl_to_sql("top products")


def test_total_aggregates():
    for word, expected_frag in [("revenue", "SUM(Revenue)"), ("orders", "COUNT(DISTINCT Invoice)"),
                                 ("customers", "COUNT(DISTINCT Customer_ID)"), ("units", "SUM(Quantity)")]:
        assert expected_frag in nl_to_sql(f"total {word}")


def test_safety_none_on_nonsense():
    for q in ("", "   ", None, "tell me a story", "DROP TABLE transactions"):
        assert nl_to_sql(q) is None
