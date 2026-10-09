"""SchemaScope — SQL analytics on UK Online Retail II (synthesised sample).

The SQL IS the deliverable here, so the UI makes SQL first-class:
  - Dashboard: cohort retention heatmap + daily revenue + top countries bar + RFM segments donut
  - RFM Explorer: Recency × Frequency × Monetary scatter, colored by segment
  - SQL Lab: free-form editor; writes/reads live DuckDB; chart-from-result when
             the result shape allows it
  - Analytics (NL->SQL): 7 example chips + pattern-based mapper
  - Methodology: 5 decisions + "what a staff engineer would flag"
  - About
"""
from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

HERE = Path(__file__).parent
CHECKPOINTS = HERE / "checkpoints"
DB_PATH = CHECKPOINTS / "retail.db"

BRAND_PRIMARY = "#4A90E2"  # SQL blue
BRAND_YELLOW = "#FFC72C"
BRAND_RED = "#E63946"
BRAND_GREEN = "#50C878"
BRAND_INK = "#0E1117"
BRAND_INK2 = "#171B22"
BRAND_INK3 = "#232833"
BRAND_FG = "#E7E9EC"
BRAND_FG_DIM = "#9AA3B2"

sys.path.insert(0, str(HERE / "src"))

st.set_page_config(
    page_title="SchemaScope — SQL on UK Retail",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ======================================================= bootstrap

@st.cache_resource(show_spinner="First-time setup: ingesting + building views (~10s)...")
def bootstrap() -> None:
    required = [DB_PATH]
    if all(p.exists() for p in required):
        try:
            con = duckdb.connect(str(DB_PATH), read_only=True)
            con.execute("SELECT COUNT(*) FROM vw_rfm").fetchone()
            con.close()
            return
        except Exception:
            pass
    CHECKPOINTS.mkdir(exist_ok=True)
    import phase1_ingest, phase2_views
    phase1_ingest.main()
    phase2_views.main()


bootstrap()


# ======================================================= DuckDB helpers

@st.cache_resource
def get_con():
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data
def sql_df(query: str) -> pd.DataFrame:
    return get_con().execute(query).fetch_df()


# ======================================================= NL->SQL (import from phase3)

from phase3_nlsql import nl_to_sql  # noqa: E402


# ======================================================= Global CSS (shared B2B theme)

st.markdown(
    f"""
    <style>
    #MainMenu, footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{background: transparent;}}

    .kpi-card {{
        background: linear-gradient(135deg, {BRAND_INK2} 0%, {BRAND_INK3} 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-left: 4px solid var(--accent, {BRAND_PRIMARY});
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        height: 100%;
    }}
    .kpi-card .kpi-label {{color: {BRAND_FG_DIM}; font-size: 12px; font-weight: 500;
                          text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;}}
    .kpi-card .kpi-value {{color: {BRAND_FG}; font-size: clamp(16px, 1.9vw, 30px);
                          font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums;
                          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
    .kpi-card .kpi-delta {{display: inline-block; margin-top: 6px; color: {BRAND_FG_DIM};
                          font-size: 12px;}}
    .kpi-icon {{float: right; font-size: 20px; opacity: 0.35; margin-left: 4px;}}
    @media (max-width: 1100px) {{ .kpi-icon {{display: none;}} }}

    .insight {{background: {BRAND_INK2}; border: 1px solid rgba(74,144,226,0.18);
              border-radius: 10px; padding: 10px 14px; font-size: 13px;
              color: {BRAND_FG}; line-height: 1.45;}}
    .insight .insight-tag {{color: {BRAND_PRIMARY}; font-weight: 600; font-size: 11px;
                           text-transform: uppercase; letter-spacing: 0.07em; margin-right: 6px;}}

    .hero {{background: radial-gradient(circle at top left, rgba(74,144,226,0.14) 0%, rgba(14,17,23,0) 55%);
           padding: 10px 0 16px; margin-bottom: 10px;}}
    .hero h1 {{font-size: 36px !important; font-weight: 800 !important; margin-bottom: 4px !important;}}
    .hero .tagline {{color: {BRAND_FG_DIM}; font-size: 15px;}}

    section[data-testid="stSidebar"] {{background: {BRAND_INK};}}
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(label: str, value: str, delta: str = "", icon: str = "", accent: str = BRAND_PRIMARY):
    st.markdown(
        f"""<div class="kpi-card" style="--accent:{accent};">
          <div class="kpi-icon">{icon}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-delta">{delta}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def compact(n: float, prefix: str = "") -> str:
    if n >= 1_000_000: return f"{prefix}{n/1_000_000:.1f}M"
    if n >= 100_000:   return f"{prefix}{n/1_000:.0f}K"
    if n >= 10_000:    return f"{prefix}{n/1_000:.1f}K"
    if n >= 1_000:     return f"{prefix}{n/1_000:.2f}K"
    return f"{prefix}{n:,.0f}"


# ======================================================= Load aggregates

rfm = sql_df("SELECT * FROM vw_rfm")
cohort = sql_df("SELECT * FROM vw_cohort_retention WHERE cohort_index <= 12")
top_prod = sql_df("SELECT * FROM vw_top_products")
daily = sql_df("SELECT * FROM vw_daily_revenue")
countries = sql_df(
    "SELECT Country, COUNT(DISTINCT Customer_ID) AS customers, "
    "ROUND(SUM(Revenue), 2) AS revenue FROM transactions GROUP BY Country ORDER BY revenue DESC"
)

n_customers = len(rfm)
n_orders = int(sql_df("SELECT COUNT(DISTINCT Invoice) AS n FROM transactions")["n"].iloc[0])
total_revenue = float(sql_df("SELECT SUM(Revenue) AS r FROM transactions")["r"].iloc[0])
n_countries = int(countries.shape[0])
repeat_rate = float((rfm["frequency"] > 1).mean() * 100)


# ======================================================= Sidebar

with st.sidebar:
    st.markdown("### 🧮 SchemaScope")
    st.caption("Bits to Builds · SQL capstone")
    st.divider()
    st.markdown("##### Data")
    st.caption(f"**{n_customers:,}** customers")
    st.caption(f"**{n_orders:,}** orders")
    st.caption(f"**{compact(total_revenue, '£')}** total revenue")
    st.caption(f"**{n_countries}** countries")

    st.markdown("##### Downloads")
    st.download_button(
        "⬇ Top-20 products (CSV)", top_prod.to_csv(index=False).encode(),
        "top_products.csv", "text/csv", use_container_width=True,
    )
    st.download_button(
        "⬇ RFM segments (CSV)", rfm.to_csv(index=False).encode(),
        "rfm.csv", "text/csv", use_container_width=True,
    )
    st.download_button(
        "⬇ Cohort retention (CSV)", cohort.to_csv(index=False).encode(),
        "cohort.csv", "text/csv", use_container_width=True,
    )

    st.divider()
    st.markdown("##### Links")
    st.markdown("[💻 Source on GitHub](https://github.com/PJsAcademy/schemascope)")
    st.markdown("[📚 Bits to Builds](https://bitstobuilds.com)")
    st.markdown("[🛒 Online Retail II dataset](https://archive.ics.uci.edu/dataset/502/online+retail+ii)")


# ======================================================= Hero + KPIs

st.markdown(
    """<div class="hero">
      <h1>🧮 SchemaScope</h1>
      <div class="tagline">SQL-first retail analytics on UK Online Retail II · SQL capstone of
      <a href="https://bitstobuilds.com" style="color:#FFC72C;">Bits to Builds</a></div>
    </div>""",
    unsafe_allow_html=True,
)

k1, k2, k3, k4, k5 = st.columns(5)
with k1: kpi_card("Customers", compact(n_customers), "distinct Customer_ID", "👥")
with k2: kpi_card("Orders", compact(n_orders), "distinct Invoice", "📦", BRAND_YELLOW)
with k3: kpi_card("Revenue", compact(total_revenue, "£"), "SUM(Quantity × Price)", "💷", BRAND_GREEN)
with k4: kpi_card("Countries", f"{n_countries}", "distinct Country", "🌍", BRAND_PRIMARY)
with k5: kpi_card("Repeat rate", f"{repeat_rate:.0f}%", "customers with >1 order", "🔁", BRAND_RED)

# Insight pills
seg_counts = sql_df("SELECT segment, COUNT(*) AS n FROM vw_rfm GROUP BY segment ORDER BY n DESC")
top_seg = seg_counts.iloc[0]
top_prod_row = top_prod.iloc[0]
top_country = countries.iloc[0]
m1_retention = cohort[cohort["cohort_index"] == 1]["retention_pct"].mean()

st.markdown("")
i1, i2, i3, i4 = st.columns(4)
pills = [
    ("Top segment", f"<b>{top_seg['segment']}</b> leads with {int(top_seg['n'])} customers."),
    ("Top product", f"<b>{top_prod_row['Description']}</b> at £{float(top_prod_row['total_revenue']):,.0f} revenue."),
    ("Top market", f"<b>{top_country['Country']}</b> — {int(top_country['customers'])} customers, £{float(top_country['revenue']):,.0f}."),
    ("Month-1 retention", f"<b>{m1_retention:.0f}%</b> of signups return the following month."),
]
for col, (tag, body) in zip([i1, i2, i3, i4], pills):
    with col:
        st.markdown(f'<div class="insight"><span class="insight-tag">{tag}</span>{body}</div>',
                    unsafe_allow_html=True)

st.markdown("")
st.divider()

tab_dash, tab_rfm, tab_sql, tab_analytics, tab_method, tab_about = st.tabs(
    ["📊 Dashboard", "👥 RFM", "💻 SQL Lab", "💬 Analytics", "🛠 Methodology", "ℹ️ About"]
)


# ------- Dashboard tab -------
with tab_dash:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Cohort retention heatmap")
        st.caption("Each row = sign-up month cohort. Columns = months since signup. Values = % still active.")
        heat = (
            alt.Chart(cohort).mark_rect(stroke=BRAND_INK, strokeWidth=1).encode(
                x=alt.X("cohort_index:O", title="Months since signup"),
                y=alt.Y("cohort_month:T", title="Cohort month", sort="descending"),
                color=alt.Color("retention_pct:Q",
                                scale=alt.Scale(scheme="blues"),
                                title="Retention %",
                                legend=alt.Legend(orient="right")),
                tooltip=["cohort_month:T", "cohort_index",
                         alt.Tooltip("retention_pct:Q", format=".1f"),
                         "cohort_customers", "active_customers"],
            ).properties(height=360)
        )
        st.altair_chart(heat, use_container_width=True)

    with c2:
        st.subheader("RFM segment distribution")
        donut = (
            alt.Chart(seg_counts).mark_arc(innerRadius=60, cornerRadius=4).encode(
                theta="n:Q",
                color=alt.Color("segment:N", title=None,
                                scale=alt.Scale(scheme="category10")),
                tooltip=["segment", "n"],
            ).properties(height=360)
        )
        st.altair_chart(donut, use_container_width=True)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Daily revenue (with cumulative)")
        rev_line = alt.Chart(daily).mark_area(
            line={"color": BRAND_PRIMARY, "strokeWidth": 2},
            color=alt.Gradient(gradient="linear",
                               stops=[alt.GradientStop(color=BRAND_PRIMARY, offset=0),
                                      alt.GradientStop(color=BRAND_INK2, offset=1)],
                               x1=1, x2=1, y1=1, y2=0),
        ).encode(
            x=alt.X("day:T", title=None),
            y=alt.Y("revenue:Q", title="Daily revenue (£)"),
            tooltip=["day:T", alt.Tooltip("revenue:Q", format="£,.2f"), "orders"],
        ).properties(height=280)
        st.altair_chart(rev_line, use_container_width=True)

    with c2:
        st.subheader("Top countries by revenue")
        country_bar = (
            alt.Chart(countries.head(10)).mark_bar(cornerRadius=4).encode(
                x=alt.X("revenue:Q", title="Revenue (£)"),
                y=alt.Y("Country:N", sort="-x", title=None),
                color=alt.Color("revenue:Q", scale=alt.Scale(scheme="blues"), legend=None),
                tooltip=["Country", alt.Tooltip("revenue:Q", format="£,.2f"), "customers"],
            ).properties(height=280)
        )
        st.altair_chart(country_bar, use_container_width=True)


# ------- RFM tab -------
with tab_rfm:
    st.subheader("Recency × Frequency × Monetary — one dot per customer")
    st.caption("Color = segment, size = lifetime value. "
               "Zoom with the scrollwheel; hover for customer details.")
    rfm_plot = rfm.copy()
    rfm_plot["monetary_clip"] = rfm_plot["monetary"].clip(upper=rfm_plot["monetary"].quantile(0.95))
    scatter = (
        alt.Chart(rfm_plot).mark_circle(opacity=0.72).encode(
            x=alt.X("recency_days:Q", title="Recency (days since last order)"),
            y=alt.Y("frequency:Q", title="Frequency (orders)"),
            size=alt.Size("monetary_clip:Q", title="Monetary (£)", scale=alt.Scale(range=[20, 400])),
            color=alt.Color("segment:N", scale=alt.Scale(scheme="category10"), title="Segment"),
            tooltip=["Customer_ID", "segment", "recency_days", "frequency",
                     alt.Tooltip("monetary:Q", format="£,.2f")],
        ).properties(height=440).interactive()
    )
    st.altair_chart(scatter, use_container_width=True)

    st.divider()
    st.subheader("Top 20 customers by lifetime value")
    top_cust = sql_df(
        "SELECT Customer_ID, segment, recency_days, frequency, "
        "ROUND(monetary, 2) AS monetary FROM vw_rfm "
        "ORDER BY monetary DESC LIMIT 20"
    )
    mon_max = float(top_cust["monetary"].max())
    st.dataframe(
        top_cust, use_container_width=True, hide_index=True, height=460,
        column_config={
            "Customer_ID": st.column_config.NumberColumn(width="small"),
            "monetary": st.column_config.ProgressColumn(
                "Lifetime value (£)", format="£%.2f",
                min_value=0, max_value=mon_max,
            ),
        },
    )


# ------- SQL Lab tab -------
with tab_sql:
    st.subheader("Free-form SQL on the DuckDB warehouse")
    st.caption("Tables: `transactions`, `vw_rfm`, `vw_cohort_retention`, "
               "`vw_top_products`, `vw_daily_revenue`. Read-only connection.")

    if "sql_query" not in st.session_state:
        st.session_state.sql_query = (
            "SELECT segment, COUNT(*) AS customers, "
            "ROUND(AVG(monetary), 2) AS avg_ltv\n"
            "FROM vw_rfm GROUP BY segment ORDER BY avg_ltv DESC"
        )

    presets = {
        "Segment summary": st.session_state.sql_query,
        "Revenue by month": (
            "SELECT DATE_TRUNC('month', InvoiceDate)::DATE AS month, "
            "ROUND(SUM(Revenue), 2) AS revenue FROM transactions GROUP BY 1 ORDER BY 1"
        ),
        "Top 10 countries": (
            "SELECT Country, COUNT(DISTINCT Customer_ID) AS customers, "
            "ROUND(SUM(Revenue), 2) AS revenue FROM transactions "
            "GROUP BY Country ORDER BY revenue DESC LIMIT 10"
        ),
        "Average order value": (
            "SELECT ROUND(AVG(order_total), 2) AS aov FROM "
            "(SELECT Invoice, SUM(Revenue) AS order_total FROM transactions "
            "GROUP BY Invoice)"
        ),
    }
    cols = st.columns(len(presets))
    for col, label in zip(cols, presets):
        if col.button(label, use_container_width=True, key=f"sql_preset_{label}"):
            st.session_state.sql_query = presets[label]

    q = st.text_area("Your SQL", key="sql_query", height=140)
    if st.button("▶ Run", type="primary"):
        try:
            result = sql_df(q)
            st.success(f"{len(result):,} rows in result")
            st.dataframe(result, use_container_width=True, hide_index=True)

            # Attempt auto-chart: if 2 cols (1 ordinal/temporal + 1 numeric)
            if result.shape[1] == 2:
                col0, col1 = result.columns
                if pd.api.types.is_numeric_dtype(result[col1]):
                    st.caption("Auto-chart from result (2 columns detected)")
                    chart = alt.Chart(result).mark_bar(cornerRadius=4).encode(
                        x=alt.X(f"{col0}:N" if not pd.api.types.is_numeric_dtype(result[col0])
                                else f"{col0}:T" if pd.api.types.is_datetime64_any_dtype(result[col0])
                                else f"{col0}:Q", title=col0),
                        y=alt.Y(f"{col1}:Q", title=col1),
                        color=alt.Color(f"{col1}:Q", scale=alt.Scale(scheme="blues"), legend=None),
                    ).properties(height=320)
                    st.altair_chart(chart, use_container_width=True)

            d1, d2 = st.columns(2)
            d1.download_button("⬇ Download SQL", q.encode(), "query.sql",
                               "text/plain", use_container_width=True)
            d2.download_button("⬇ Download result (CSV)", result.to_csv(index=False).encode(),
                               "result.csv", "text/csv", use_container_width=True)
        except Exception as e:
            st.error(f"Query failed:\n```\n{e}\n```")


# ------- Analytics (NL->SQL) tab -------
with tab_analytics:
    st.subheader("Natural-language query")
    st.caption("Deterministic pattern mapper. Matches one of 5 patterns; "
               "returns 'not supported' for anything else (safety by default).")

    if "nl_query" not in st.session_state:
        st.session_state.nl_query = "revenue by country"

    examples = ["revenue by country", "orders by month", "customers in champions",
                "top 10 products", "total revenue", "retention month 3"]
    cols = st.columns(len(examples))
    for col, ex in zip(cols, examples):
        if col.button(ex, use_container_width=True, key=f"nl_{ex}"):
            st.session_state.nl_query = ex

    q = st.text_input("Your question", key="nl_query")
    if q:
        sql = nl_to_sql(q)
        if sql is None:
            st.warning("No pattern matched. Try one of the example chips above.")
        else:
            st.code(sql, language="sql")
            try:
                result = sql_df(sql)
                st.dataframe(result, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Execution failed:\n```\n{e}\n```")


# ------- Methodology tab -------
with tab_method:
    st.markdown(
        """
        ## Methodology — decisions, tradeoffs, honest shortcuts

        ---
        ### Decision 1 — Why DuckDB over Postgres or SQLite?

        **Chose:** DuckDB file-based warehouse in `checkpoints/retail.db`.

        **Why:** For a single-container Streamlit demo, DuckDB is the right call. It's an
        OLAP engine (columnar, vectorised), handles the retail queries sub-50ms, speaks
        PostgreSQL-flavored SQL (window functions, CTEs, NTILE, DATE_TRUNC all work), and
        requires zero server. SQLite is OLTP-oriented and lacks NTILE/QUALIFY. Postgres
        needs a server, auth, networking — nothing is free on Streamlit Cloud's 1 GB tier.

        **What I'd change with 10× the time:** keep DuckDB as the serving layer, add a
        dbt project for the view definitions so schema changes are reviewable PRs instead
        of hand-edited `CREATE OR REPLACE VIEW` strings.

        ---
        ### Decision 2 — Why NTILE for RFM scoring, not fixed thresholds?

        **Chose:** `NTILE(5)` over recency/frequency/monetary for 1-5 scores.

        **Why:** Fixed thresholds (e.g. "frequency > 5 = high") assume knowledge of the
        business's volume. Quintiles self-calibrate: the top 20% always score 5 regardless
        of absolute scale. The segments ("Champions", "At Risk", "Hibernating") then come
        from stable rules on the 1-5 scores. This is the standard RFM pattern used by
        every CRM team.

        **What I'd change with 10× the time:** make the segment rules configurable (a
        YAML in the repo) and show A/B differences between rule versions in the UI.

        ---
        ### Decision 3 — Why synthesise instead of ship the real UCI CSV?

        **Chose:** `np.random.default_rng(42)` → 500 customers × ~5000 transactions.

        **Why (honest):** The real UK Online Retail II is 1M+ rows. Streamlit Cloud's
        free tier (1 GB RAM, 1 GB storage) chokes before loading. The synthesised sample
        preserves the schema and has realistic patterns (Pareto-distributed order counts,
        heavy UK skew, 2-year date range) — enough that every demo query returns
        meaningful numbers. Pointing `phase1_ingest.py` at the real CSV is one `if-exists`
        swap.

        **What I'd change with 10× the time:** ship a partitioned parquet of the real
        dataset in S3 behind an HTTP range-request fetcher so DuckDB can query it
        directly without loading into memory.

        ---
        ### Decision 4 — Why materialised views, not CTEs re-run every query?

        **Chose:** `CREATE OR REPLACE VIEW` for RFM / cohort / top products / daily.

        **Why:** Materialised views are the cheapest "query cache" DuckDB has — the first
        reference computes, subsequent references scan the result. Rebuilt each time
        `phase2_views.py` runs, which is deterministic and fast. The alternative (bake
        the CTEs into every ad-hoc SQL in the UI) couples presentation to analytics logic
        and makes "which cohort definition does the dashboard use?" ambiguous.

        **What I'd change with 10× the time:** convert the views to dbt models with
        `materialized='table'` + schema tests. Also add incremental materialisation so
        new daily data doesn't force a full rebuild.

        ---
        ### Decision 5 — Why a 5-pattern regex for NL→SQL, not an LLM?

        **Chose:** Deterministic regex that returns `None` on no match.

        **Why:** For 5 known-shape questions ("revenue by country", "top 10 products",
        etc.), a regex is a 50-line safety-first implementation that never hallucinates
        a destructive query. An LLM for 5 patterns is engineering theater. The honest
        upgrade is a hybrid: LLM-generated SQL wrapped in a SELECT-only parser gate
        that reads the AST and rejects anything with WRITE/DDL/DELETE.

        **What I'd change with 10× the time:** build the hybrid LLM + SELECT-only
        allowlist, keep the 5 regex patterns as the fast-path.

        ---

        ## What a staff engineer would flag that I left in

        - **No connection pooling.** `get_con()` is `@st.cache_resource` so Streamlit
          reuses one connection — fine for a single-user demo, breaks under real
          concurrency. Should migrate to a pooled read-replica.
        - **The SQL Lab accepts any SQL** including views that could lock the file. In
          prod we'd open a strict read-only sub-session per query, with a 5-second
          wall-time limit.
        - **Cohort retention counts first-order month as index=0.** Some teams prefer
          index=1 ("month-after-signup is month 1"). Document whichever convention you
          pick in the view definition's header comment.
        - **No multi-currency.** Prices are £GBP. Real UCI data has implicit mixed
          currencies via Country; the pipeline silently treats all values as GBP.
        """
    )


# ------- About tab -------
with tab_about:
    st.markdown(
        f"""
        ## About

        **SchemaScope** is the SQL capstone of the [Bits to Builds](https://bitstobuilds.com)
        course. The deliverable is **SQL that you can read in production** — RFM, cohort
        retention and top-product views modeled against a real retail schema, with a free-form
        SQL Lab in the UI for ad-hoc exploration.

        | Phase | Deliverable |
        |-------|-------------|
        | 1. Ingest | Pandas → DuckDB `retail.db`; 3 cleaning rules with reject counts |
        | 2. Views  | 4 materialised views: RFM, cohort retention, top-20 products, daily revenue |
        | 3. NL-SQL | 5-pattern regex mapper + None-safe fallback |

        ## Data

        [UK Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
        (UCI Machine Learning Repository, CC-BY-4.0). This Space uses a deterministic
        synthesised sample so cold-starts fit in the free tier; the pipeline runs on
        the real 1M-row CSV when pointed at it.

        ## Honest limits

        - Synthesised {n_customers:,}-customer / {n_orders:,}-order sample on the deployed
          version. Numbers here are illustrative; the SQL is the real deliverable.
        - DuckDB file lives on the Space's filesystem — ephemeral. On restart, bootstrap
          rebuilds it from source.
        - SQL Lab is read-only but unrestricted; a hostile `WITH RECURSIVE` could stall.
          Fix: wall-time limit + statement validator (see Methodology).

        ## Source

        [github.com/PJsAcademy/schemascope](https://github.com/PJsAcademy/schemascope)
        """
    )
