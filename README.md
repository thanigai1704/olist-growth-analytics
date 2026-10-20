# 📈 GrowthLens — Olist Business Growth & Retention Analytics

> A defensible, end-to-end growth & retention study of the **real** Olist Brazilian
> e-commerce dataset (100K+ orders): SQL-first analysis (CTEs + window functions),
> a Power BI dashboard layer, and an interactive **GrowthLens** Streamlit app —
> with every number on every chart traceable to the one SQL file that produced it.

| | |
|---|---|
| **Business problem** | Olist grows by buying new customers, but 97% never buy twice. Where do the dollars leak, and which levers pay back first? |
| **Data** | [olistbr/brazilian-ecommerce on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — 9 relational CSVs, 99,441 orders, Sep 2016 – Aug 2018 (CC BY-NC-SA 4.0; analysis & teaching use, source credited) |
| **Key artefacts** | `sql/growth_retention_analysis.sql` (core), `streamlit_app/` (UI), `docs/POWER_BI_GUIDE.md` (BI), `docs/business_memo.md` (exec), `docs/schema.md` (data model) |
| **Stack** | Python 3.14 · pandas · SQLite · SQL (SQLite dialect, PG-equivalents annotated) · Plotly · Streamlit · Power BI Desktop |

---

## 1. Why this project

An e-commerce marketplace has two growth engines: **acquisition** (new buyers)
and **retention** (buyers who return). Leadership asked one question: *"are we
buying growth or compounding it?"* — then demanded the answers be defensible:
every chart must survive the question*"where exactly does this number come
from?"* That is why the whole project funnels through a single auditable SQL
file — no hidden spreadsheets, no hand-waved metrics.

The analysis answers, in order:

1. **Is revenue growing?** monthly MRR, MoM growth %, AOV — and where the flat
   patches are (plateau Mar–Aug 2018).
2. **Do customers come back?** acquisition-cohort retention matrix + pooled
   average curve (the centerpiece).
3. **Who are the customers that matter?** RFM segmentation with
   revenue-share-per-segment (the number business stakeholders actually act on).
4. **Where does execution break?** categories, delivery-lateness vs ratings,
   seller quality ranking.

## 2. Methodology

### 2.1 Pipeline (3 scripts, fully reproducible)

```
data/raw/*.csv (9 files, downloaded from Kaggle)
   │
   ▼  scripts/build_database.py
data/db/olist_growth.db            (SQLite, PK/FK schema, cleaning rules R1–R7
   │                                logged to data/db_load_report.txt)
   ▼  sql/growth_retention_analysis.sql        (run via scripts/run_sql.py)
16 analytics tables (mv_*)         (MRR, cohorts, RFM, churn, delivery, sellers)
   │
   ▼  scripts/make_powerbi_exports.py
data/exports/*.csv (12 files)      (shaped for Power BI / Streamlit; 1:1 with mv_*)
   │
   ├─► streamlit_app/  (python -m streamlit run streamlit_app/app.py)
   └─► Power BI Desktop (build guide: docs/POWER_BI_GUIDE.md)
```

Verified end-to-end on the real dataset; web smoke tests
(`scripts/test_app_pages.py`) cover every app page.

### 2.2 Metric definitions (stated once, used everywhere)

- **Revenue (GMV)** = `SUM(price + freight_value)` per delivered order.
  Cross-checked at +0.02% against delivered-order `payments` (R$15.42M vs
  R$15.42M). Item-level is canonical because only it is attributable to
  product/category/seller.
- **Customer** = `customer_unique_id` (critical Olist quirk: `customer_id` is
  per-order; identity across orders is `customer_unique_id`, 96,096 of them).
- **Cohort** = the month of a customer's *first delivered order*.
- **Active in month m** = ≥1 delivered purchase in that month.
- **Churned** = no delivered order in the last 180 days before snapshot
  (2018-09-04).
- **RFM** = NTILE(4) scores per customer at the snapshot; segments:
  Champions, Loyal Customers, Potential Loyalists, At-Risk, Hibernating, Lost.

### 2.3 Documented assumptions & limitations (a real analyst's data gaps)

- **CAC is an assumption, not a fact — and that is the honest finding.** Olist
  ships no marketing-spend table. Handled the professional way: calibrated a
  blended CAC of **R$60** (industry ballpark for Brazilian marketplaces
  2017–18), quantified **LTV = R$165** lifetime GMV per customer, presented a
  **sensitivity sweep** (CAC 30→90 ⇒ LTV:CAC 5.5x→1.8x gross; 0.83x after a
  30% margin at R$60). The *ratio*, not the absolute, is decision-grade.
- **"MRR" framing**: marketplace revenue is transactional (no subscriptions);
  the monthly-revenue construction mirrors the requested MRR lens, labelled as
  such.
- **Currency stays R$** (BRL). No FX conversion; README-level framing that
  "revenue" = nominal BRL. Converting currencies would only distort cent-level
  readability without insight gain.
- **Nov 2016 = zero orders** (soft-launch dead month) and **first/last tiny
  cohorts** (1 customer in Sep 2016 / Dec 2016) are kept visible and excluded
  from averages, labelled in comments and app copy.
- **The dataset has no returns/costs/traffic data**; unit economics beyond
  GMV are out of scope by data availability, stated rather than fudged.

## 3. Key findings (all real, all reproducible)

1. **Growth flattened, then declined.** Revenue grew through the Black
   Friday spike (Nov 2017: R$1.15M, +53.6% MoM), then **plateaued at
   R$1.0–1.13M/month Mar–Aug 2018** oscillating in a ±10% band — the market
   stopped compounding.
2. **97% of customers never buy twice.** 2,801 of 93,358 customers (3.0%)
   have ≥2 delivered orders; the pooled **Month-1 retention rate is 0.48%**
   (0.34% by month 2) — if the second-purchase habit does not form
   immediately, it forms never.
3. **40% of all revenue is parked in "At-Risk" wallets**: 24.5% of customers
   spent well then went quiet (**R$6.1M**). Meanwhile Champions — recent,
   top-spending (25.4%) — carry **41.0% of revenue**. Concentration is the
   upside and the single point of failure.
4. **Late delivery deletes loyalty on contact**: on-time/early orders score
   **4.29★**; 3 days late = **3.29★**; 8–15 days late = **1.67★** with **80%**
   bad reviews (16–30d: 1.60★, 82% bad). Late arrivals are only ~7% of orders
   but generate **32.5% of all bad reviews**.
5. **Volume leadership ≠ revenue leadership.** `health_beauty` tops revenue
   (R$1.41M) while `bed_bath_table` wins order volume (9,272 orders); the two
   rankings diverge by up to **28 positions** (`computers`: #23 by volume,
   high-ticket). Cheap popular categories buy reach, high-AOV ones
   (`watches_gifts` at R$230/order) buy money. Marketing budget should follow
   the goal, not the leaderboard.
6. **The CAC:LTV verdict**: at a blending-assumed R$60 CAC, LTV repays
   **2.75x in GMV but only 0.83x after margin** — the model only closes if
   second purchases become normal. (Full sensitivity sweep in
   `data/exports/cac_sensitivity.csv`.)

The executive version of these is `docs/business_memo.md` (1 page, zero jargon).

## 4. Streamlit app — "GrowthLens Analytics"

```bash
pip install -r requirements.txt
python -m streamlit run streamlit_app/app.py
```

- **Page 1 · Executive Summary** — date-range filter, monthly/weekly toggle,
  MRR trend, category donut (top-5 + Others), CSV report download.
- **Page 2 · Cohort Retention** — interactive heatmap (hover any cell for the
  exact %), cohort drill-down vs pooled curve, how-to-read explainer, and a
  **"What-If +10% retention"** button that quantifies revenue impact.
- **Page 3 · Customer Segments** — RFM treemap, scorecard, per-segment
  drill-down (top customers by spend) and one-click **campaign email drafts**
  per segment.
- **Page 4 · Category Insights** — sortable category rankings (revenue /
  volume / rating / AOV), delivery-vs-rating scatter, search across 74
  categories, RANK() seller leaderboard.

## 5. Power BI dashboard

All four exported CSVs are Power BI-ready. Exact step-by-step build
instructions + DAX formulas (`MRR Growth %`, `Avg Month-1 Retention`, etc.)
in **`docs/POWER_BI_GUIDE.md`**.

_Screenshots (to attach after build): `docs/img/powerbi_page1.png`,
`powerbi_page2.png`, `powerbi_page3.png`._

## 6. Directory structure

```
olist-growth-analytics/
├── data/
│   ├── raw/                      # 9 Kaggle CSVs (downloaded via kagglehub)
│   ├── db/olist_growth.db        # cleaned relational SQLite DB
│   ├── db_load_report.txt        # cleaning + integrity verification log
│   └── exports/                  # 12 CSVs (1:1 with SQL mv_* tables)
├── sql/
│   └── growth_retention_analysis.sql   # ⭐ the core deliverable
├── scripts/
│   ├── build_database.py         # load + clean + verify (stage 2)
│   ├── run_sql.py                # executes the SQL file (stage 3)
│   ├── make_powerbi_exports.py   # exports CSVs (stage 4)
│   └── test_app_pages.py         # headless smoke test of all app pages
├── streamlit_app/
│   ├── app.py                    # Home
│   ├── common.py                 # shared theme/data helpers
│   ├── pages/                    # 4 analysis pages
│   └── .streamlit/config.toml    # emerald/white/gray theme
├── docs/
│   ├── schema.md                 # ER diagram description + dictionary
│   ├── POWER_BI_GUIDE.md         # exact DAX + visual steps
│   └── business_memo.md          # 1-page VP-of-Growth memo
├── requirements.txt
└── README.md
```

## 7. Setup

```bash
# 1. clone + env
python -m venv .venv && .venv\Scripts\activate   # (Windows)
pip install -r requirements.txt

# 2. download the raw CSVs (kagglehub, no API key needed for public datasets)
python -c "import kagglehub; print(kagglehub.dataset_download('olistbr/brazilian-ecommerce'))"
# then place the 9 CSVs into data/raw/  (or let kagglehub point you there)

# 3. build & analyse
python scripts/build_database.py          # cleans + loads the DB, verifies FKs
python scripts/run_sql.py                 # runs sql/growth_retention_analysis.sql
python scripts/make_powerbi_exports.py    # refreshes the 12 dashboard CSVs

# 4. open the app
python -m streamlit run streamlit_app/app.py
```

## 8. Data caveats worth saying out loud

- Reviews table is ~99% coverage of orders; INNER joins to it are avoided in
  revenue aggregates (documented at the join sites inside the SQL).
- The raw dataset's text-washed edition (Kaggle "versions/2") is the one used
  here; row-level view counts match the canonical release (99,441 orders /
  1,000,163 geolocation rows).
- Analysis snapshot frozen at 2018-09-04 for reproducibility.

## 9. License/credits

- Dataset © Olist (olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0 — credited and
  linked throughout; **non-commercial, attribution-bearing** use only.
- All analysis code and narrative in this repository written for the
  portfolio purpose of demonstrating production-grade SQL + BI + app skills.
