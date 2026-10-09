"""Phase 2 — SchemaScope SQL analytics views.

Reads retail.db and creates:
  - vw_rfm              Recency + Frequency + Monetary per customer, with 1-5 score + segment label
  - vw_cohort_retention Monthly cohort → month-N retention % matrix
  - vw_top_products     Top 20 products by revenue
  - vw_daily_revenue    Daily revenue + cumulative

Each view is `CREATE OR REPLACE VIEW` so phase2 is idempotent. The DuckDB queries
are the deliverable — the SQL itself is what Phase 2 of this capstone teaches.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent.parent
DB_PATH = HERE / "checkpoints" / "retail.db"


RFM_SQL = """
CREATE OR REPLACE VIEW vw_rfm AS
WITH ref AS (
  SELECT MAX(InvoiceDate)::DATE AS asof FROM transactions
),
rfm AS (
  SELECT
    t.Customer_ID,
    DATEDIFF('day', MAX(t.InvoiceDate)::DATE, ref.asof) AS recency_days,
    COUNT(DISTINCT t.Invoice)                            AS frequency,
    SUM(t.Revenue)                                       AS monetary
  FROM transactions t CROSS JOIN ref
  GROUP BY t.Customer_ID, ref.asof
),
scored AS (
  SELECT *,
    NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
    NTILE(5) OVER (ORDER BY frequency)         AS f_score,
    NTILE(5) OVER (ORDER BY monetary)          AS m_score
  FROM rfm
)
SELECT *,
  CASE
    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
    WHEN r_score >= 4 AND f_score >= 3                  THEN 'Loyal'
    WHEN r_score >= 4 AND m_score >= 4                  THEN 'Big Spenders'
    WHEN r_score >= 3 AND f_score <= 2                  THEN 'Promising'
    WHEN r_score <= 2 AND f_score >= 4                  THEN 'At Risk'
    WHEN r_score <= 2 AND m_score >= 4                  THEN 'Can''t Lose'
    WHEN r_score <= 2 AND f_score <= 2                  THEN 'Hibernating'
    ELSE 'Needs Attention'
  END AS segment
FROM scored
"""


COHORT_SQL = """
CREATE OR REPLACE VIEW vw_cohort_retention AS
WITH customer_cohort AS (
  SELECT Customer_ID,
         DATE_TRUNC('month', MIN(InvoiceDate))::DATE AS cohort_month
  FROM transactions GROUP BY Customer_ID
),
customer_activity AS (
  SELECT t.Customer_ID,
         c.cohort_month,
         DATE_TRUNC('month', t.InvoiceDate)::DATE AS activity_month,
         DATEDIFF('month', c.cohort_month, DATE_TRUNC('month', t.InvoiceDate)::DATE) AS cohort_index
  FROM transactions t
  JOIN customer_cohort c USING (Customer_ID)
),
cohort_size AS (
  SELECT cohort_month, COUNT(DISTINCT Customer_ID) AS cohort_customers
  FROM customer_cohort GROUP BY cohort_month
),
retention AS (
  SELECT cohort_month, cohort_index, COUNT(DISTINCT Customer_ID) AS active_customers
  FROM customer_activity GROUP BY cohort_month, cohort_index
)
SELECT r.cohort_month, r.cohort_index, r.active_customers, s.cohort_customers,
       ROUND(100.0 * r.active_customers / s.cohort_customers, 1) AS retention_pct
FROM retention r JOIN cohort_size s USING (cohort_month)
ORDER BY r.cohort_month, r.cohort_index
"""


TOP_PRODUCTS_SQL = """
CREATE OR REPLACE VIEW vw_top_products AS
SELECT StockCode, Description,
       COUNT(DISTINCT Invoice)       AS orders,
       SUM(Quantity)                 AS units_sold,
       ROUND(SUM(Revenue), 2)        AS total_revenue,
       ROUND(AVG(Price), 2)          AS avg_price
FROM transactions
GROUP BY StockCode, Description
ORDER BY total_revenue DESC
LIMIT 20
"""


DAILY_REVENUE_SQL = """
CREATE OR REPLACE VIEW vw_daily_revenue AS
SELECT InvoiceDate::DATE AS day,
       COUNT(DISTINCT Invoice) AS orders,
       ROUND(SUM(Revenue), 2) AS revenue,
       ROUND(SUM(SUM(Revenue)) OVER (ORDER BY InvoiceDate::DATE), 2) AS cumulative_revenue
FROM transactions
GROUP BY InvoiceDate::DATE
ORDER BY day
"""


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    for name, sql in [
        ("vw_rfm", RFM_SQL),
        ("vw_cohort_retention", COHORT_SQL),
        ("vw_top_products", TOP_PRODUCTS_SQL),
        ("vw_daily_revenue", DAILY_REVENUE_SQL),
    ]:
        con.execute(sql)
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"[phase2] {name}: {n:,} rows")

    seg_counts = con.execute(
        "SELECT segment, COUNT(*) AS n FROM vw_rfm GROUP BY segment ORDER BY n DESC"
    ).fetch_df()
    print("[phase2] RFM segments:")
    print(seg_counts.to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
