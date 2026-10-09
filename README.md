# SchemaScope

SQL-first retail analytics on UK Online Retail II. SQL capstone of
[Bits to Builds](https://bitstobuilds.com). DuckDB warehouse, 4 materialised
views (RFM, cohort retention, top products, daily revenue), free-form SQL Lab
in the UI, and a 5-pattern NL→SQL mapper with None-safe fallback.

**Live demo:** <https://schemascope-fr6rukcvakjyfv8fgeatqg.streamlit.app/>
**Source:** <https://github.com/PJsAcademy/schemascope>

---

## What it does

| Phase | Deliverable |
|-------|-------------|
| 1. Ingest | Pandas → DuckDB `retail.db`; 3 cleaning rules documented |
| 2. Views  | `vw_rfm`, `vw_cohort_retention`, `vw_top_products`, `vw_daily_revenue` as `CREATE OR REPLACE VIEW` |
| 3. NL-SQL | 5-pattern regex mapper + None fallback (safety by default) |

## Run locally

```bash
pip install -r requirements.txt
python src/phase1_ingest.py  # ~3s synth; writes retail.db
python src/phase2_views.py   # ~1s; creates 4 views
python src/phase3_nlsql.py   # ~0.1s; prints example mappings
pytest tests/ -q             # 20 invariants should pass
streamlit run streamlit_app.py
```

## Deploy to Streamlit Community Cloud (free)

```bash
REPO=schemascope ../portfolio/publish.sh
```

Then at <https://share.streamlit.io>: Create app → pick this repo → main file
`streamlit_app.py` → Deploy.

## Honest limits

- Synthesises a 500-customer / ~10k-row sample when the real UCI CSV isn't
  present. The **SQL is the deliverable**, not the specific numbers.
- DuckDB file is ephemeral on Streamlit Cloud; bootstrap rebuilds it on cold
  start.
- SQL Lab is read-only but unrestricted — a hostile `WITH RECURSIVE` could
  stall. The honest upgrade is a wall-time limit + statement validator.
- RFM uses NTILE quintiles; segment thresholds are hardcoded. See Methodology
  tab for the "chose/why/would change" writeup.

## Credits

Dataset: UK Online Retail II (UCI ML Repository, CC-BY-4.0). Built from the
[Bits to Builds](https://bitstobuilds.com) curriculum.
