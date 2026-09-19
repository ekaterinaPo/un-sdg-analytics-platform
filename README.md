# UN SDG AI Analytics Platform

**SQLite Database · LangChain SQL Agent · Power BI Dashboard**

**Build status:** Phase 1 (Power BI dashboard) is scoped and the source data is in hand — see `Dashboard/`. Phases 2–3 (SQLite database, LangChain agent) are not yet built. The sections below describe the full target architecture; only Phase 1 is underway.

---

## Business problem

The UN's Sustainable Development Goals database contains 232 indicators for 193 countries.
The people who need to understand it — policy staff, NGO programme managers, country
representatives — cannot write SQL.

**Core questions:**
1. Can an AI agent answer complex policy questions about global development data by reasoning
   over a structured SQLite database — explaining its steps, not just returning a table?
2. Which countries are on track to meet their 2030 SDG commitments?

---

## Why I built this

I worked at UNDP (UN Development Programme) as a Finance Clerk. I watched programme staff
struggle to get answers from data that technically existed — it just required SQL skills they
didn't have. This project is the tool I wish we had.

---

## Architecture

```
UN SDG Data (CSV)  ──► SQLite Database (.db)
                               │
                    LangChain SQL Agent
                    (Claude + langchain)
                               │
                    notebooks/05_ai_agent_demo
                               │
                    Power BI Dashboard (see Dashboard/)
```

### Layer 1 — SQLite database
Python's built-in `sqlite3` — no installation, no server, single `.db` file.
5-table schema: `countries`, `sdg_goals`, `sdg_indicators`, `sdg_values`, `sdg_index_scores`.
Loaded via pandas `to_sql()` from official UN CSV exports.

### Layer 2 — LangChain SQL Agent
Uses `langchain.agents.create_sql_agent()` with `ChatAnthropic(model="claude-opus-4-8")`.
The agent can inspect the schema, write SQL, execute it, observe the result, and decide if
it needs to refine — multi-step reasoning, not one-shot lookup.
Demonstrated in `notebooks/05_ai_agent_demo.ipynb` with 10+ example policy questions.

### Layer 3 — Power BI (see `Dashboard/`)
Built directly from the Sustainable Development Report 2026 workbook (`Dashboard/data/database_2026.xlsx`) rather than waiting on Layers 1–2, so a finished piece exists while the SQLite/agent layers are still in progress.

---

## Dashboard (Phase 1 — Power BI)

**Business question, framed as a variance:** the SDG Index runs 0–100, where 100 means all goals achieved — so `100 − score` is a **gap to target**, structurally identical to a budget variance (a committed target, an actual position, a difference to explain). This is the angle that connects the dashboard to Kate's accounting background: UN Finance roles ask for experience "analysing variances between approved budgets and actual expenditures," and gap-to-target is that same analysis applied to development data.

**Data model:** star schema — `DimCountry`, `DimGoal`, `DimDate` (marked as a proper date table), `FactSDG` (country × goal × year grain). Built via Power Query from the workbook's `SDR2026 Data` / `Overview` sheets. Full build plan and DAX measures: `Dashboard/BUILD_PLAN.md`, `Dashboard/DAX_measures.md`.

**Pages:**
1. **Global Overview** — KPI row, choropleth by SDG Index score, regional bar chart, top/bottom 10 countries
2. **Country Analysis** — score trend over time, breakdown across all 17 goals, rank and gap to target vs. regional average
3. **Goal Analysis** — country ranking and trend for a selected goal, regional comparison, gap-to-target view

**Assumptions (stated openly, not hidden):**
- **On-track threshold:** a goal is treated as on track at a score ≥ 75 — an analytical judgement call, not an official UN cutoff, documented because it materially affects the "% goals on track" figure.
- **Coverage:** the SDG Index covers 167 countries, not all 193 UN member states; small island/microstate coverage is incomplete, so global figures average reporting countries only.

**Skills demonstrated:** Power Query transformation (unpivot, type handling, dimension splitting), dimensional modelling (star schema, dedicated date table), DAX filter context (`CALCULATE`, time intelligence, `RANKX` with `ALL`, safe division with `DIVIDE`), dashboard/KPI design, honest treatment of data gaps and stated assumptions.

---

## Key findings

- Indicator with worst data coverage: `[name]` — `[X]%` of countries have no data
- Agent successfully answers `[X]%` of 20 test policy questions without manual SQL

*(Replace with actual results after running analysis)*

---

## Example agent questions (from `notebooks/05_ai_agent_demo.ipynb`)

> *"Which Sub-Saharan African countries improved most in SDG 3 (Good Health) since 2015?"*

> *"Show all low-income countries where the SDG Index score declined between 2019 and 2023."*

> *"Which SDG goals have the worst data coverage for South Asian countries?"*

> *"Compare average SDG Index scores for low-income vs. high-income countries in 2023."*

---

## Datasets

| Dataset | Source | Used for |
|---|---|---|
| UN SDG Global Indicators | https://unstats.un.org/sdgs/indicators/database/ | Core database, 232 indicators |
| Sustainable Development Report 2026 | https://dashboards.sdgindex.org/ | Country index scores + trend data (in hand — `Dashboard/data/database_2026.xlsx`) |
| World Bank via wbgapi | https://github.com/tgherzog/wbgapi | GDP, health/education enrichment |

---

## Tools

`Python` · `SQLite` · `LangChain` · `Claude API (Anthropic)` · `pandas` · `wbgapi` · `Power BI` · `DAX` · `Power Query`

---

## Notebooks

| Notebook | Content |
|---|---|
| `01_eda.ipynb` | Data quality, coverage gaps, distributions |
| `02_database_build.ipynb` | Load CSVs → SQLite, World Bank enrichment |
| `05_ai_agent_demo.ipynb` | LangChain SQL agent — 10+ example queries with reasoning |

---

## Files

```
08-UN-SDG-Analytics-Platform/
├── Dashboard/              ← Phase 1 (Power BI) — see "Dashboard" section above
│   ├── powerbi/
│   │   └── UN_SDG_Dashboard.pbix
│   ├── data/
│   │   └── database_2026.xlsx
│   ├── screenshots/
│   ├── DAX_measures.md
│   └── BUILD_PLAN.md
├── sql/
│   └── 01_schema.sql
├── src/
│   └── sql_agent.py
├── notebooks/              ← Phases 2–3, not yet built
├── data/raw/
├── CLAUDE.md
├── README.md
└── requirements.txt
```
