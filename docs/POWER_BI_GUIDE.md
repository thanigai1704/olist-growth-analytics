# Power BI Dashboard Build Guide — Olist Growth & Retention

Build all three pages in **3–4 hours** with the four export CSVs from
`data/exports/`. Every visual's numbers come from a named SQL result described
in Section 6, so you can defend each chart in an interview against the exact
query that produced it.

**Files to load (Power BI → Get Data → Text/CSV):**

| file | used on |
|---|---|
| `monthly_revenue_metrics.csv` | Page 1 |
| `revenue_by_category.csv` | Page 1 (donut) |
| `cohort_retention_matrix.csv` | Page 2 |
| `retention_curve.csv` | Page 2 (average curve) |
| `rfm_segments.csv` | Page 3 (breakout table) |
| `rfm_segment_summary.csv` | Page 3 (segment-level visuals) |

Loading tips (one-time, in Power Query):
- `cohort_retention_matrix` / `monthly_revenue_metrics`: set `cohort_month`/`month`
  to **Date** type.
- `rfm_segments`: 93,358 rows; fine as-is. Column `customer_id` contains the
  durable `customer_unique_id` values (see README §data caveats).
- Do **not** create relationships between tables — each file is self-sufficient
  for its page (single-fact-per-page design keeps this build simple and fast).

---

## PAGE 1 — Executive Summary

### 1.1 Data prep (Power Query)
Nothing required beyond the type fixes above; `monthly_revenue_metrics.csv`
already has `month`, `mrr`, `aov`, `growth_pct`, `order_count`, `prev_mrr`,
`new_customers`.

### 1.2 DAX measures (Home → New measure)
Create table `Measures` via "Enter data" with a single row, then add:

```DAX
-- source columns (implicit), then explicit measures:
Total Revenue = SUM ( monthly_revenue_metrics[mrr] )

Total Orders = SUM ( monthly_revenue_metrics[order_count] )

Avg Order Value =
    DIVIDE ( [Total Revenue], [Total Orders] )

Total Customers = SUM ( monthly_revenue_metrics[new_customers] )

-- the flagship line: current month revenue vs the prior month, as a ratio.
-- The export already carries prev_revenue per row (computed with SQL LAG()),
-- so this measure works without any date-intelligence setup.
MRR Growth % =
    VAR current_rev =
        LASTNONBLANK ( monthly_revenue_metrics[month], [Total Revenue] )
    VAR prev_rev =
        CALCULATE (
            [Total Revenue],
            OFFSET ( -1, ALLSELECTED ( monthly_revenue_metrics[month] ) )
        )
    RETURN
        DIVIDE ( current_rev - prev_rev, prev_rev )

Cumulative Revenue =
    CALCULATE (
        [Total Revenue],
        FILTER (
            ALLSELECTED ( monthly_revenue_metrics ),
            monthly_revenue_metrics[month] <= MAX ( monthly_revenue_metrics[month] )
        )
    )
```

> Alternative (purely from the export, zero DAX risk): use the exported
> `growth_pct` column directly in visuals; it was produced by SQL `LAG()`.
> The DAX above is included to demonstrate the measure-writing pattern.

### 1.3 Visuals
- **KPI cards (4)**: New card visual (or Card) with New card visual → fields:
  `[Total Revenue]`, `[MRR Growth %]` (word format: trim display to 1 dp),
  `[Total Customers]`, `[Avg Order Value]`. Rename callout values.
- **Line chart**: X = `month`, Y = `[Total Revenue]`; add trend line
  (Analytics pane → Trend line). Set X axis type **categorical** so 2016-11
  (zero orders — real data hole) shows honestly.
- **Donut chart**: Legend = `revenue_by_category[category]`, values =
  `revenue_by_category[revenue]`. The export is already "Top 5 + Others" (SQL
  did the ranking).
- **Slicer** (optional): `month` between-slicer for 2018 focus.

### 1.4 Formatting
- Colors: revenue #10B981; Others grey #94A3B8; page background #FFFFFF;
  callout background #F3F4F6.
- Number format for `[Total Revenue]`: Display units = Thousands/Millions,
  2 decimals; Money symbol: custom "R$".

---

## PAGE 2 — Retention Deep-Dive (Cohort Heatmap)

### 2.1 The cohort matrix (the centerpiece)
Insert a **Matrix** visual:
- **Rows** = `cohort_retention_matrix[cohort_month]` (sort ascending, but read
  it as "acquisition month").
- **Columns** = `cohort_retention_matrix[months_since_first_purchase]`
  (rename header label "Months since first purchase"; set Data type = whole
  number).
- **Values** = average of `retention_pct`.
- **Conditional formatting** (Cell elements → Background color → Format by
  rules): 
  - Rule type **Gradient**, based on `retention_pct`, min = 0 → red
    (#FEE2E2), midpoint = 15 → amber (#FCD34D), max = 100 → emerald (#059669).
  - Turn OFF "Show values" switch only if you prefer cells without numbers;
  keep numbers ON for interviews.

Expected shape: M0 column solid green (100% by definition), M1 collapses to
~0.3–0.6%, far columns blank (later cohorts haven't aged). Say this out loud
in demos — it is a real-data honesty feature, not a bug.

### 2.2 Average retention curve (below the heatmap)
- **Line chart**: X = `retention_curve[months_since]`,
  Y = `retention_curve[pooled_retention_pct]` (the defensible average:
  sum of actives ÷ sum of cohort sizes, cohorts ≥ 100 customers only).
  Title: "Average retention curve — pooled".
- Optional second series: `retention_curve[avg_retention_pct]` (simple mean)
  shown dashed to demonstrate the small-cohort distortion — a great talking
  point.

### 2.3 Headline KPI card
- **Card visual**: create measure
  ```DAX
  Avg Month-1 Retention =
      CALCULATE (
          MAX ( retention_curve[pooled_retention_pct] ),
          retention_curve[months_since] = 1
      )
  ```
  Display with 2 decimals + %. (Export value: 0.48%.)

### 2.4 Slicer
- **Slicer** on `cohort_month` (DropDown or Between). Connect it (Edit
  interactions) to BOTH the matrix and the line chart, but **not** to the KPI
  card if you want the headline number stable.

---

## PAGE 3 — Customer Segments (RFM)

### 3.1 Segment-level visuals (from `rfm_segment_summary`)
- **Clustered bar** (or **Treemap**): Category/Labels = `segment`,
  Values = `[Customers]` =
  ```DAX
  Customers = SUM ( rfm_segment_summary[customers] )
  Revenue = SUM ( rfm_segment_summary[revenue] )
  ```
- **Table** with conditional formatting: columns `segment`, `customers`,
  `customer_share_pct`, `revenue`, `revenue_share_pct`,
  `avg_recency_days`, `avg_frequency`. Apply **Data bars** on
  `revenue_share_pct` (emerald) and **background gradient** on
  `customer_share_pct`.

### 3.2 Drill into a segment (per-customer breakout, from `rfm_segments`)
- **Table** on `rfm_segments[customer_id]`, `[recency]`, `[frequency]`,
  `[monetary]`, `[rfm_segment]`, with TopN filter (Top 10 by `monetary`).
- **Slicer**: `rfm_segment` (single-select) to swap the sample customers shown.

### 3.3 Action cards
For each segment add a **Text box** styled with the segment color and the
copy below (match to `rfm_segment_summary` so the %s are always true):

- **Champions (25.4% of customers, 41.0% of revenue)** → "Reward with early
  access to new products; open a members-only deal; ask for the review."
- **Loyal Customers (0.2% / 0.1%)** → "Upsell bundles; newsletter; points
  multiplier — preserve, do not discount."
- **Potential Loyalists (12.1% / 6.1%)** → "First cross-category offer within
  14 days of delivery; social proof in transactional email."
- **At-Risk (24.5% / 39.6%)** → "20% discount re-engagement campaign limited
  to favourite categories; cap at repeat-purchase basket value."
- **Hibernating (13.0% / 5.0%)** → "Free channels only; entry-level free
  shipping; seasonal re-openers."
- **Lost (25.0% / 8.2%)** → "Automated brand presence only; reallocate budget
  to Potential Loyalists."

### 3.4 Why the segment table looks like it does (use this in the demo)
Frequency is nearly degenerate (3.0% lifetime repeat), so RFM leans on
Recency × Monetary. That is why "At-Risk" is huge and "Loyal Customers" is
tiny — and it is the honest reading of real marketplace data.

---

## 6. Chart → SQL traceability

Every Power BI field above is an output of `sql/growth_retention_analysis.sql`:

| Visual | SQL source table in the same file |
|---|---|
| Page 1 KPIs / line | `mv_mrr_monthly` (§1.1, LAG window) |
| Page 1 donut | `mv_category_performance` top-5 + Others (§6) |
| Page 2 matrix | `mv_retention_matrix` (§2, size_cohorts/activity/sequenced CTEs) |
| Page 2 card + curve | `mv_retention_curve` (pooled = Σactives / Σcohort sizes) |
| Page 3 segment visuals | `mv_rfm_segment_summary` (§3.1) |
| Page 3 customer table | `mv_powerbi_rfm` (§7) |

Run `python scripts/make_powerbi_exports.py` (executes the SQL first) to
reproduce all of them.
