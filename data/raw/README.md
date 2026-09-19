# Data — Raw

## Dataset 1 — UN SDG Global Indicators Database (PRIMARY)
URL: https://unstats.un.org/sdgs/indicators/database/

Download: click "Download Data" → CSV bulk download
File: SDG_global_database.csv  (may be split by goal)

Coverage: 232 indicators, 193 countries, 1990–2024
Note: Coverage is uneven. Many developing countries have significant data gaps.
This is documented honestly in notebooks/01_eda.ipynb.

Place in: data/raw/un_sdg/

## Dataset 2 — Sustainable Development Report 2026 (SDG Index) — ALREADY IN HAND
URL: https://dashboards.sdgindex.org/

Already downloaded to `../Dashboard/data/database_2026.xlsx` (used for the Phase 1 Power BI
dashboard — see `../Dashboard/BUILD_PLAN.md`). Contains 7 sheets: country-level 2026 scores/ranks
(`Overview`, `SDR2026 Data`), 124 raw indicators × country × year 2000–2025 (`All Raw Data`),
normalized indicator scores + composite index per country-year (`Backdated SDG Index`), rank
history 2015–2022+ (`Backdated - Ranks over time`), and a `Codebook` sheet with indicator
definitions and green/red thresholds.

This is the Sachs/SDSN dataset used by Bertelsmann Foundation and UNDP internally.
Best for: Power BI choropleth, and — since it already includes raw indicator values — a
possible source for Layer 1's SQLite build too, without waiting on Dataset 1 below.

## Dataset 3 — World Bank enrichment (via Python, no manual download)
Library: wbgapi  (install: pip install wbgapi)
GitHub: https://github.com/tgherzog/wbgapi

Indicators to pull programmatically in notebooks/02_database_build.ipynb:
- NY.GDP.PCAP.CD    — GDP per capita (current USD)
- SH.XPD.CHEX.GD.ZS — Current health expenditure (% of GDP)
- SE.XPD.TOTL.GD.ZS — Government education expenditure (% of GDP)
- SP.POP.TOTL       — Population

Code:
    import wbgapi as wb
    gdp = wb.data.DataFrame('NY.GDP.PCAP.CD', mrv=10).reset_index()

Place processed output in: data/processed/world_bank_enrichment.csv

## Data quality notes (document these in notebooks)
- UN SDG database: many indicators have <50% country coverage
- SDG Index: 167 countries ranked (not all 193 UN members — missing microstates etc.)
- World Bank: some indicators missing for recent years; use most-recent-value (mrv) carefully
- Time range: UN SDG data goes back to 1990 for some indicators, others only from 2015

These gaps are not a weakness — they are realistic data science challenges worth discussing.
