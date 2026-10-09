"""Phase 3 — SchemaScope NL->SQL.

Deterministic 5-pattern regex mapper for common retail-analytics questions.
Returns None on no match (safety). The upgrade path is a real LLM + a
SELECT-only validator.
"""
from __future__ import annotations

import re


SEGMENTS = ("champions", "loyal", "big spenders", "promising",
            "at risk", "can't lose", "hibernating", "needs attention")


def nl_to_sql(question: str) -> str | None:
    if not question:
        return None
    q = question.lower().strip().rstrip("?.")

    # Pattern 1: revenue / orders / customers by country/month/day
    m = re.search(r"(revenue|orders|customers)\s+by\s+(country|month|day)", q)
    if m:
        metric_sql = {
            "revenue": "ROUND(SUM(Revenue), 2) AS revenue",
            "orders": "COUNT(DISTINCT Invoice) AS orders",
            "customers": "COUNT(DISTINCT Customer_ID) AS customers",
        }[m.group(1)]
        dim_sql = {
            "country": "Country",
            "month": "DATE_TRUNC('month', InvoiceDate)::DATE AS month",
            "day":   "InvoiceDate::DATE AS day",
        }[m.group(2)]
        order = "revenue DESC" if m.group(1) == "revenue" else (
            "orders DESC" if m.group(1) == "orders" else "customers DESC"
        )
        order = {"country": order, "month": "1", "day": "1"}[m.group(2)]
        return f"SELECT {dim_sql}, {metric_sql} FROM transactions GROUP BY 1 ORDER BY {order}"

    # Pattern 2: customers in <segment>
    for seg in SEGMENTS:
        if seg in q:
            return f"SELECT * FROM vw_rfm WHERE LOWER(segment) = '{seg}' ORDER BY monetary DESC"

    # Pattern 3: top N <products|customers>
    m = re.search(r"top\s*(\d+)?\s*(products|customers)", q)
    if m:
        n = int(m.group(1) or 10)
        if m.group(2) == "products":
            return f"SELECT * FROM vw_top_products LIMIT {n}"
        return (f"SELECT Customer_ID, SUM(Revenue) AS lifetime_value "
                f"FROM transactions GROUP BY Customer_ID "
                f"ORDER BY lifetime_value DESC LIMIT {n}")

    # Pattern 4: total <revenue|orders|customers>
    m = re.search(r"total\s+(revenue|orders|customers|units)", q)
    if m:
        agg = {
            "revenue": "ROUND(SUM(Revenue), 2) AS total_revenue",
            "orders":  "COUNT(DISTINCT Invoice) AS total_orders",
            "customers": "COUNT(DISTINCT Customer_ID) AS total_customers",
            "units":   "SUM(Quantity) AS total_units",
        }[m.group(1)]
        return f"SELECT {agg} FROM transactions"

    # Pattern 5: retention [month N]
    m = re.search(r"retention(?:\s+month\s+(\d+))?", q)
    if m:
        n = int(m.group(1) or 1)
        return (f"SELECT cohort_month, retention_pct FROM vw_cohort_retention "
                f"WHERE cohort_index = {n} ORDER BY cohort_month")

    return None


def main() -> None:
    for q in (
        "revenue by country",
        "orders by month",
        "customers in champions",
        "top 10 products",
        "total revenue",
        "retention month 3",
        "random nonsense",
    ):
        print(f"  Q: {q!r:40} -> SQL: {nl_to_sql(q)!r}")


if __name__ == "__main__":
    main()
