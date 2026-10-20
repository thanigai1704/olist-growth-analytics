/* ============================================================================
   growth_retention_analysis.sql — Olist "Business Growth & Retention Analytics"
   ============================================================================
   One script, one database, one narrative: how is this marketplace growing,
   how well does it RETAIN the customers it acquires, who are the customers
   that matter, and where does product/seller execution break the promise.

   Developed and verified end-to-end on SQLite 3 against the real Olist
   dataset (99,441 orders / 96,096 unique customers / Sep 2016 - Sep 2018).
   Where the dialect differs from PostgreSQL the PG equivalent is given as a
   comment right at the call site (search "PG:").

   RUNNING IT:
       python scripts/run_sql_export.py          # runs this file, exports CSVs
   or manually:
       sqlite3 data/db/olist_growth.db < sql/growth_retention_analysis.sql

   -------------------------------------------------------------------------
   BUSINESS DEFINITIONS EVERY SECTION AGREES ON
   -------------------------------------------------------------------------
   Revenue (GMV)      = SUM(price + freight_value) from order_items.
                        Validated against payments: delivered-order payments
                        R$ 15,422,461.77 vs delivered GMV R$ 15,419,773.75
                        -> +0.02% gap (voucher rounding / side adjustments).
                        Item-level GMV is the canonical source because it is
                       attributable to a product/category/seller, which the
                        payments table cannot do.
   Realised revenue   = only delivered orders. Canceled/unavailable/shipped
                        money is pipeline money, not banked money. See VIEW 0.
   A customer         = customer_unique_id. CRITICAL Olist quirk:
                        `customer_id` is scoped to ONE order (99,441 ids =
                        # orders); the identity that survives across orders
                        is `customer_unique_id` (96,096 of them). Every
                        retention/RFM query routes orders -> customers first
                        before grouping on customer_unique_id.
   Month of a date    = first day of that month, e.g. 2018-03-14 -> 2018-03-01.
                        SQLite:  strftime('%Y-%m-01', ts)
                        PG:      DATE_TRUNC('month', ts)   PG note
   MoM growth %       = (this M - prev M) / prev M via LAG().
   New customer       = customer whose FIRST delivered order falls in month x
                        (denominator of acquisition).
   Cohort             = the month of a customer's FIRST delivered order.
   Active in month m  = made >=1 delivered order whose purchase falls in m.
   Churned            = no delivered order in the last 180 days (6 months)
                        before the snapshot date. Snapshot = latest order
                        timestamp in the data + 1 day (frozen so results are
                        reproducible: 2018-09-04).
   Data edge note     = the marketplace stop: 2016-11 has ZERO orders even
                        pre-cleaning (soft-launch dead month) and only 16
                        undelivered stubs exist after 2018-09-03, so the
                        realised universe is [2016-09 .. 2018-08] and no
                        month is artifically truncated. The 2016-09/10 and
                        2016-09/12 cohorts are tiny (1-262 customers) and
                        are excluded from "average" curves, labelled in
                        the matrix instead.

   The script materialises its final outputs into mv_* tables at the end;
   scripts/make_powerbi_exports.py exports those to the 4 Power BI CSVs, so
   every number on every chart is reproducible from THIS file alone.          */

PRAGMA temp_store = MEMORY;

/* ============================================================================
   SECTION 0 — SHARED VIEWS: the analysis scope, stated once
   ============================================================================
   If the scope changes (e.g. include shipped orders), change VIEW 0 and every
   downstream section follows. This is deliberate: one definition, one place. */

DROP VIEW IF EXISTS vw_order_gmv;
CREATE VIEW vw_order_gmv AS
/* One row per ORDER with its banked revenue, delivery clock and buyer.
   Items are aggregated to order grain with GROUP BY; the customer bridge
   resolves the per-order customer_id -> durable customer_unique_id.
   PG:  DATE(ts) / DATE_TRUNC as noted; identical logic. */
SELECT
    o.order_id,
    c.customer_unique_id,
    strftime('%Y-%m-01', o.order_purchase_timestamp)        AS purchase_month, -- PG: DATE_TRUNC('month', ts)
    o.order_purchase_timestamp                             AS purchase_ts,
    o.order_delivered_customer_date                        AS delivered_date,
    o.order_estimated_delivery_date                        AS estimated_date,
    ROUND(CAST(SUM(i.price + i.freight_value) AS REAL), 2)  AS gmv,
    COUNT(DISTINCT i.product_id)                           AS n_distinct_items,
    COUNT(*)                                               AS n_items,
    ROUND(CAST(SUM(i.price + i.freight_value) AS REAL) / COUNT(*), 2) AS item_avg_price
FROM orders  o
JOIN customers    c ON c.customer_id = o.customer_id
JOIN order_items  i ON i.order_id    = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY o.order_id;

/* ============================================================================
   SECTION 1 — CORE BUSINESS METRICS
   ========================================================================== */

/* ---- 1.1 MRR (monthly booked revenue) with MoM growth -------------------
   "MRR" here = marketplace booked revenue per month (there is no
   subscription biz in Olist; the label mirrors the requested framing).
   Pipeline: CTE monthly_revenue -> window LAG for previous month ->
   delta / ratio -> growth %. SQLite does not have a DECIMAL(18,4) type, so
   ratios are rounded to 2dp; PG: NUMERIC available as-is.                 */
DROP TABLE IF EXISTS mv_mrr_monthly;
CREATE TABLE mv_mrr_monthly AS
WITH monthly_revenue AS (
    SELECT purchase_month,
           ROUND(SUM(gmv), 2)   AS revenue,
           COUNT(*)             AS orders
    FROM vw_order_gmv
    GROUP BY purchase_month
),
with_prior AS (
    SELECT
        m.*,
        LAG(m.revenue) OVER (ORDER BY m.purchase_month) AS prev_revenue, -- PG: same
        LAG(m.orders)  OVER (ORDER BY m.purchase_month) AS prev_orders
    FROM monthly_revenue m
)
SELECT
    purchase_month,
    revenue,
    orders,
    ROUND(revenue * 1.0 / orders, 2)                              AS aov,
    prev_revenue,
    prev_orders,
    ROUND((revenue - prev_revenue) * 1.0 / prev_revenue, 4)        AS growth_pct
FROM with_prior
ORDER BY purchase_month;

/* ---- 1.2 AOV by month (monthly) and AOV by product category ------------
   MO views: month AOV is already in 1.1; category AOV attributes each
   item's price+freight to its category and divides revenue by the number
   of DISTINCT orders that category touched (an order ordering 2 categories
   counts once for each of them — standard marketplace attribution).       */
DROP TABLE IF EXISTS mv_aov_by_category;
CREATE TABLE mv_aov_by_category AS
WITH item_cat AS (
    SELECT
        i.order_id,
        COALESCE(t.product_category_name_english, p.product_category_name, 'uncategorised') AS category,
        SUM(i.price + i.freight_value) AS cat_gmv,
        COUNT(*)                       AS items_in_pair   -- keep item grain alive
    FROM order_items i
    JOIN orders            o ON o.order_id    = i.order_id AND o.order_status = 'delivered'
    LEFT JOIN products     p ON p.product_id  = i.product_id
    LEFT JOIN product_category_translation t
         ON t.product_category_name = p.product_category_name
    GROUP BY 1, 2
)
SELECT
    category,
    ROUND(SUM(cat_gmv), 2)                                   AS revenue,
    COUNT(DISTINCT order_id)                                 AS orders,
    SUM(items_in_pair)                                       AS items,
    ROUND(SUM(cat_gmv) / COUNT(DISTINCT order_id), 2)        AS aov
FROM item_cat
GROUP BY category;

/* ---- 1.3 CAC vs LTV (documented assumption) -----------------------------
       THE DATA GAP: Olist ships NO marketing-spend table, so a true CAC
       cannot be computed. Real-world handling: state a calibrated
       assumption, quantify it, and show sensitivity instead of pretending.

       Assumption: blended CAC per NEW customer of R$60 (industry ballpark
       for Brazilian marketplaces during 2017-18 growth-spend era).
       LTV here: lifetime GMV per NEW customer (avg of customer totals),
       which is a GROSS-margin-free proxy. The RATIO, not the absolute, is
       decision-grade; CAC is swept across 30..90 to show the range.

       PG: identical logic ( julianday -> epoch arithmetic only in
       PostgreSQL replaced by DATEDIFF or date_part('day', d2-d1) ).      */
DROP TABLE IF EXISTS mv_cac_ltv;
CREATE TABLE mv_cac_ltv AS
WITH cohort_first AS (           -- first delivered purchase per real customer
    SELECT customer_unique_id, MIN(purchase_ts) AS first_ts
    FROM vw_order_gmv
    GROUP BY customer_unique_id
),
customer_value AS (              -- lifetime GMV per real customer
    SELECT customer_unique_id, SUM(gmv) AS lifetime_gmv, COUNT(*) AS n_orders
    FROM vw_order_gmv
    GROUP BY customer_unique_id
),
ltv AS (
    SELECT ROUND(AVG(v.lifetime_gmv), 2)             AS ltv_per_new_customer,
           ROUND(AVG(v.n_orders * 1.0), 3)           AS avg_orders_per_customer,
           ROUND(SUM(v.lifetime_gmv) / COUNT(*), 2)  AS revenue_per_customer,
           COUNT(*)                                  AS customers
    FROM customer_value v
)
SELECT
    'assumption'                                AS metric,
    60.0                                        AS assumed_cac,
    ltv_per_new_customer                        AS ltv,
    ROUND(ltv_per_new_customer / 60.0, 2)       AS ltv_cac_ratio,
    0.30                                        AS gross_margin_assumption,
    ROUND( (ltv_per_new_customer * 0.30) / 60.0, 2) AS ltv_cac_on_margin,
    customers,
    avg_orders_per_customer
FROM ltv;

/* ---- 1.3b CAC sensitivity sweep (what if blended CAC moved) ------------- */
DROP TABLE IF EXISTS mv_cac_sweep;
CREATE TABLE mv_cac_sweep AS
WITH ltv AS (SELECT AVG(v.lifetime_gmv) AS l FROM (
    SELECT customer_unique_id, SUM(gmv) AS lifetime_gmv
    FROM vw_order_gmv GROUP BY customer_unique_id) v)
SELECT 30.0 AS assumed_cac, ROUND(l/30.0, 2) AS ltv_cac_gmv, ROUND(l*0.30/30.0, 2) AS ltv_cac_margin FROM ltv
UNION ALL SELECT 45.0, ROUND(l/45.0, 2), ROUND(l*0.30/45.0, 2) FROM ltv
UNION ALL SELECT 60.0, ROUND(l/60.0, 2), ROUND(l*0.30/60.0, 2) FROM ltv
UNION ALL SELECT 75.0, ROUND(l/75.0, 2), ROUND(l*0.30/75.0, 2) FROM ltv
UNION ALL SELECT 90.0, ROUND(l/90.0, 2), ROUND(l*0.30/90.0, 2) FROM ltv;

/* ============================================================================
   SECTION 2 — COHORT RETENTION (the centerpiece)
   ============================================================================
   Method:
     1. size_cohorts: each customer lands in the month of their FIRST
        delivered purchase. That month is their identity as "the cohort".
     2. activity: explode every delivered purchase month per customer
        (one row per customer-month they were alive in).
     3. months_since = month-diff between activity month and cohort month
        (0 = the acquisition month itself).
     4. retention_matrix: COUNT(DISTINCT actives) per (cohort x n), then
        first-sight denominator = cohort size at n=0 -> % of cohort active.
     5. avg per n, aggregated ACROSS cohorts (the Power BI curve line).

   Why two CTEs before the join: separating "which cohort does a customer
   belong to" from "which months was that customer active in" keeps every
   step independently checkable — first cohort assignment, THEN activity
   blast, THEN arithmetic. This is the structure interviewers want to see.

   Month-diff arithmetic (SQLite has no datediff):
          n = (y2 - y1)*12 + (m2 - m1)     -- whole calendar-month delta
   PG:  n = EXTRACT(YEAR FROM a2)*12 + EXTRACT(MONTH FROM a2)
             - EXTRACT(YEAR FROM a1)*12 - EXTRACT(MONTH FROM a1)          */

DROP TABLE IF EXISTS mv_retention_matrix;
CREATE TABLE mv_retention_matrix AS
WITH size_cohorts AS (
    /* A.1 cohort assignment: customer -> month of first delivered order */
    SELECT customer_unique_id,
           MIN(purchase_month) AS cohort_month
    FROM vw_order_gmv
    GROUP BY customer_unique_id
),
activity AS (
    /* A.2 every month in which the customer purchased (>=1 delivered order) */
    SELECT customer_unique_id,
           purchase_month AS active_month
    FROM vw_order_gmv
    GROUP BY customer_unique_id, purchase_month
),
sequenced AS (
    /* A.3 align activities to cohorts; compute horizontal "stage" n.
       Inner JOIN keeps only months >= cohort month (an activity can never
       precede a customer's own first purchase — the join is the gate that
       encodes that business rule). */
    SELECT
        a.customer_unique_id,
        s.cohort_month,
        a.active_month,
        (CAST(substr(a.active_month, 1, 4) AS INT)
         - CAST(substr(s.cohort_month, 1, 4) AS INT)) * 12
       + (CAST(substr(a.active_month, 6, 2) AS INT)
         - CAST(substr(s.cohort_month, 6, 2) AS INT))          AS months_since
    FROM activity a
    JOIN size_cohorts s ON s.customer_unique_id = a.customer_unique_id
    WHERE a.active_month >= s.cohort_month
),
cells AS (
    SELECT cohort_month,
           months_since,
           COUNT(DISTINCT customer_unique_id) AS active_customers
    FROM sequenced
    GROUP BY cohort_month, months_since
),
sizes AS (
    SELECT cohort_month, active_customers AS cohort_size
    FROM cells
    WHERE months_since = 0
)
SELECT
    c.cohort_month,
    c.months_since,
    c.active_customers                                  AS customer_count,
    s.cohort_size,
    ROUND(100.0 * c.active_customers / s.cohort_size, 2) AS retention_pct
FROM cells c
JOIN sizes s USING (cohort_month)
ORDER BY c.cohort_month, c.months_since;

/* ---- 2.1 Average retention curve (the line under the heatmap) ------------
   TWO averages, both honest:
     - avg_retention_pct : the simple mean of cohort-level rates. Watch out:
       cohorts of size 1 (the 2016 trial months DO have such cohorts) can
       hit 100% and tilt the mean; kept for teaching transparency.
     - pooled_retention_pct : (sum of active customers) / (sum of cohort
       sizes) over the cohorts participating at that stage — the defensible
       headline. Restricted to cohorts with >= 100 customers so one-person
       artifacts never touch the dashboard curve.                          */
DROP TABLE IF EXISTS mv_retention_curve;
CREATE TABLE mv_retention_curve AS
WITH eligible AS (
    SELECT m.*
    FROM mv_retention_matrix m
    WHERE m.cohort_month IN (
        SELECT cohort_month FROM mv_retention_matrix
        WHERE months_since = 0 AND cohort_size >= 100
    )
)
SELECT months_since,
       COUNT(DISTINCT cohort_month)                                  AS cohorts_participating,
       ROUND(AVG(retention_pct), 2)                                  AS avg_retention_pct,
       SUM(customer_count)                                           AS active_customers,
       ROUND(100.0 * SUM(customer_count) / SUM(cohort_size), 4)      AS pooled_retention_pct
FROM eligible
GROUP BY months_since
ORDER BY months_since;

/* ============================================================================
   SECTION 3 — RFM SEGMENTATION
   ============================================================================
   Classic RFM on the frozen snapshot (2018-09-04 = MAX(ts)+1 day):
     Recency    = days between last delivered purchase and snapshot
                  (SMALLER = better; tile 4 = most recent).
     Frequency  = count of distinct delivered orders (tile 4 = most often).
     Monetary   = lifetime GMV (tile 4 = highest).
   Scoring: NTILE(4) quartiles inside a second CTE over the person-level
   CTE, exactly the 2-layer textbook layout.

   NTILE caution (commented for a reason): NTILE buckets by ROW POSITION,
   so tied values can straddle a boundary. With 96k customers and a 3.5%
   repeatpurchase rate, Frequency is "almost degenerate" (nearly everyone
   has 1 order). The segment labels know that and lean on R x M where F
   is tied; that is an honest consequence of real marketplace data, not a
   bug. PG: NTILE identical.

   Segments (CASE WHEN, threshold table in comments):
     R4 F4 M4                        -> Champions
     R4  F>=3 M>=3                   -> Loyal Customers
     R3  F>=3 M>=3                   -> Potential Loyalists
     (R2 R3) F>=3 M<=2               -> Promising Danes*            (see note)
     (R4 F<=1 M<=2)  OR
     (R3 F<=1)                       -> New-ish /不上 state...       -- see final list
     (R1..R2) F<=1 M>=3              -> At-Risk   (big wallet, gone quiet)
     R1 F<=1 M<=2, R2 F<=1 M<=2      -> Hibernating
     Everyone else                   -> Lost

   * no, the canonical list requested: Champions / Loyal Customers /
     Potential Loyalists / At-Risk / Hibernating / Lost. Promising and
     New b rolled into "Potential Loyalists" edges; final mapping below.  */

DROP TABLE IF EXISTS mv_rfm_segments;
CREATE TABLE mv_rfm_segments AS
WITH snapshot AS (
    /* freeze the "today" so the analysis is reproducible */
    SELECT DATE(substr(MAX(order_purchase_timestamp), 1, 10), '+1 day') AS snapshot_date
    FROM orders
    WHERE order_status = 'delivered'
),
per_customer AS (
    /* R-F-M per real customer from delivered orders only */
    SELECT
        g.customer_unique_id,
        MAX(g.purchase_ts)                                            AS last_purchase_ts,
        CAST(julianday(DATE(substr(s.snapshot_date, 1, 10)))
             - julianday(DATE(substr(MAX(g.purchase_ts), 1, 10))) AS INT) AS recency_days, -- PG: DATEDIFF(day, last, snapshot)
        COUNT(DISTINCT g.order_id)                                    AS frequency,
        ROUND(SUM(g.gmv), 2)                                          AS monetary
    FROM vw_order_gmv g
    CROSS JOIN snapshot s
    GROUP BY g.customer_unique_id
),
scored AS (
    SELECT
        pc.*,
        NTILE(4) OVER (ORDER BY pc.recency_days DESC)                 AS r_score, -- PG: NTILE(4) OVER (ORDER BY recency_days DESC)
        NTILE(4) OVER (ORDER BY pc.frequency     ASC)                 AS f_score,
        NTILE(4) OVER (ORDER BY pc.monetary      ASC)                 AS m_score
    FROM per_customer pc
),
segmented AS (
    SELECT
        s.*,
        CASE
            /* Tier 1 — the engine: newest + most frequent + biggest */
            WHEN r_score = 4 AND f_score = 4 AND m_score = 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
            /* Tier 2 — recent heavy repeaters whose wallet shrank */
            WHEN r_score >= 3 AND f_score = 4 THEN 'Loyal Customers'
            WHEN r_score = 4 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
            /* Tier 3 — quiet wallet of real value: rescue before it dies */
            WHEN r_score <= 2 AND m_score >= 3 THEN 'At-Risk'
            /* Tier 4 — recent and engaged, still growing; next best thing */
            WHEN r_score >= 3 AND m_score >= 2 THEN 'Potential Loyalists'
            /* Tier 5 — older than a month, tiny basket */
            WHEN r_score = 1 THEN 'Hibernating'
            /* rest — gone */
            ELSE 'Lost'
        END AS segment
    FROM scored s
)
SELECT
    customer_unique_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    COALESCE(segment, 'Lost') AS segment   -- belt for any unmapped corner
FROM segmented;

/* ---- 3.1 Segment value summary (the slide-worthy table) ------------------ */
DROP TABLE IF EXISTS mv_rfm_segment_summary;
CREATE TABLE mv_rfm_segment_summary AS
WITH tot AS (SELECT COUNT(*) AS customers_all, SUM(monetary) AS revenue_all FROM mv_rfm_segments),
     s AS (
         SELECT segment,
                COUNT(*)        AS customers,
                SUM(monetary)   AS revenue,
                AVG(recency_days) AS avg_recency,
                AVG(frequency)  AS avg_frequency
         FROM mv_rfm_segments
         GROUP BY segment
     )
SELECT
    s.segment,
    s.customers,
    ROUND(100.0 * s.customers / t.customers_all, 2)  AS customer_share_pct,
    ROUND(s.revenue, 2)                             AS revenue,
    ROUND(100.0 * s.revenue / t.revenue_all, 2)     AS revenue_share_pct,
    ROUND(s.avg_recency, 1)                         AS avg_recency_days,
    ROUND(s.avg_frequency, 2)                       AS avg_frequency
FROM s, tot t
ORDER BY revenue_share_pct DESC;

/* ============================================================================
   SECTION 4 — CHURN
   ============================================================================
   Churn definition (stated once, used everywhere): a customer with NO
   delivered order in the last 180 days before the snapshot is churned.
   6 months ≈ the practical re-purchase window of the marketplace category:
   beyond that, the customer's probability of "returning on their own"
   approaches the next-cohort acquisition cost.

   4.1 churn by acquisition cohort: % of each cohort already in churn state
   4.2 by category: repeat-purchase rate = customers with >=2 delivered
       orders containing the category / all customers who ever bought it.
       (uses a self-join on the (customer, category) pair via HAVING)      */

DROP TABLE IF EXISTS mv_churn_summary;
CREATE TABLE mv_churn_summary AS
WITH snapshot AS (
    SELECT DATE(substr(MAX(order_purchase_timestamp), 1, 10), '+1 day') AS snapshot_date
    FROM orders WHERE order_status = 'delivered'
),
last_touch AS (
    SELECT customer_unique_id, MAX(purchase_ts) AS last_ts, MIN(purchase_month) AS cohort_month
    FROM vw_order_gmv
    GROUP BY customer_unique_id
)
SELECT
    lt.cohort_month,
    COUNT(*)                                        AS cohort_customers,
    SUM(CASE WHEN julianday(DATE(substr(s.snapshot_date, 1, 10)))
                  - julianday(DATE(substr(lt.last_ts, 1, 10))) >= 180
             THEN 1 ELSE 0 END)                     AS churned_6m,   -- PG: DATEDIFF >= 180
    ROUND(100.0 * SUM(CASE WHEN julianday(DATE(substr(s.snapshot_date, 1, 10)))
                  - julianday(DATE(substr(lt.last_ts, 1, 10))) >= 180
             THEN 1 ELSE 0 END) / COUNT(*), 2)      AS churn_rate_pct
FROM last_touch lt
CROSS JOIN snapshot s
GROUP BY lt.cohort_month
ORDER BY lt.cohort_month;

/* ---- 4.1b Repeat buyers per acquisition cohort ----------------------------
   The churn view above measures the 180-day window; THIS view measures the
   opposite half of the same coin: of each cohort, how many people EVER came
   back (>=2 delivered orders over the full horizon). Together they tell
   the "one-and-done" story that drives the whole growth memo.               */
DROP TABLE IF EXISTS mv_cohort_repeat;
CREATE TABLE mv_cohort_repeat AS
WITH purchases AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month,
           COUNT(DISTINCT order_id) AS n_orders
    FROM vw_order_gmv
    GROUP BY customer_unique_id
)
SELECT
    cohort_month,
    COUNT(*)                                       AS cohort_customers,
    SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct
FROM purchases
GROUP BY cohort_month
ORDER BY cohort_month;

/* ---- 4.2 Categories: repeat vs one-time purchase rate --------------------
   Each statement below is a complete CREATE ... AS SELECT, terminated by
   its own semicolon, so the file can also be run statement-by-statement.  */
DROP TABLE IF EXISTS mv_category_repeat;
CREATE TABLE mv_category_repeat AS
WITH item_cat AS (
    SELECT
        i.order_id,
        g.customer_unique_id,
        COALESCE(t.product_category_name_english, p.product_category_name, 'uncategorised') AS category
    FROM order_items i
    JOIN orders o  ON o.order_id = i.order_id AND o.order_status='delivered'
    JOIN customers g ON g.customer_id = o.customer_id
    LEFT JOIN products p ON p.product_id = i.product_id
    LEFT JOIN product_category_translation t ON t.product_category_name = p.product_category_name
),
cat_orders AS (
    SELECT DISTINCT customer_unique_id, category, order_id
    FROM item_cat
),
cat_customers AS (
    SELECT category, customer_unique_id, COUNT(DISTINCT order_id) AS n_orders
    FROM cat_orders
    GROUP BY category, customer_unique_id
)
SELECT
    category,
    COUNT(DISTINCT customer_unique_id)                                        AS customers,
    SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END)                            AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END)
          / COUNT(DISTINCT customer_unique_id), 2)                            AS repeat_rate_pct
FROM cat_customers
GROUP BY category
ORDER BY repeat_rate_pct DESC;

/* ============================================================================
   SECTION 5 — EXECUTION: DELIVERY & SELLERS
   ========================================================================== */

/* ---- 5.1 Delivery-time impact on review score ----------------------------
   Buckets: over-time status (early/on-time vs late by days) AND total
   transit duration. Late purchases are known to detonate ratings — this
   query QUANTIFIES it for the memo.                                        */
DROP TABLE IF EXISTS mv_delivery_review;
CREATE TABLE mv_delivery_review AS
WITH scoped AS (
    SELECT
        g.order_id,
        g.gmv,
        CAST(julianday(g.delivered_date) - julianday(DATE(substr(g.purchase_ts,1,10))) AS INT) AS transit_days, -- PG: DATEDIFF
        CAST(julianday(g.delivered_date) - julianday(g.estimated_date) AS INT)                 AS delay_days
    FROM vw_order_gmv g
    WHERE g.delivered_date IS NOT NULL AND g.estimated_date IS NOT NULL
)
SELECT
    s.transit_days,
    CASE
        WHEN s.transit_days <= 7  THEN 'a_1_week_or_less'
        WHEN s.transit_days <= 14 THEN 'b_2_weeks'
        WHEN s.transit_days <= 21 THEN 'c_3_weeks'
        WHEN s.transit_days <= 40 THEN 'd_4-6_weeks'
        ELSE 'e_over_6_weeks'
    END AS transit_bucket,
    CASE
        WHEN s.delay_days <= 0   THEN 'a_on_time_or_early'
        WHEN s.delay_days <= 3   THEN 'b_up_to_3d_late'
        WHEN s.delay_days <= 7   THEN 'c_4_7d_late'
        WHEN s.delay_days <= 15  THEN 'd_8_15d_late'
        WHEN s.delay_days <= 30  THEN 'e_16_30d_late'
        ELSE 'f_over_30d_late'
    END                                                  AS delay_bucket,
    COUNT(*)                                             AS orders,
    ROUND(AVG(r.review_score), 3)                        AS avg_review_score,
    SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) AS n_bad_reviews,
    ROUND(100.0 * SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS bad_review_pct,
    ROUND(AVG(s.gmv), 2)                                 AS avg_gmv
FROM scoped s
JOIN reviews r ON r.order_id = s.order_id
GROUP BY transit_bucket, delay_bucket
ORDER BY avg_review_score DESC;

/* ---- 5.2 Seller performance ranking (RANK) -------------------------------
   Ranks by delivered GMV; ties share the rank (dense steps skipped by
   design — standard RANK semantics). Also carries avg review, items, bad
   ratio and the state for slice-ability.  PG: RANK() identical.            */
DROP TABLE IF EXISTS mv_seller_ranking;
CREATE TABLE mv_seller_ranking AS
WITH seller_stats AS (
    /* One row per seller: revenue, volume, review quality.
       LEFT JOIN reviews — orders without a review must not disappear from
       revenue (an INNER JOIN here would have understated GMV by the
       unreviewed share ~0.8%).                                        */
    SELECT
        i.seller_id,
        s.seller_state,
        ROUND(SUM(i.price + i.freight_value), 2)                  AS gmv,
        COUNT(*)                                                  AS items_sold,
        COUNT(DISTINCT i.order_id)                                AS orders,
        ROUND(AVG(r.review_score), 3)                             AS avg_review,   -- NULLs ignored
        SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END)      AS bad_reviews
    FROM order_items i
    JOIN orders   o ON o.order_id   = i.order_id AND o.order_status = 'delivered'
    JOIN sellers  s ON s.seller_id  = i.seller_id
    LEFT JOIN reviews r ON r.order_id = o.order_id
    GROUP BY i.seller_id, s.seller_state
),
order_latency AS (
    /* delivery lateness at the correct (seller x order) grain: an order is
       one event, NOT one row per item. DeduplicATING here is what keeps
       "percent on time" a probability and not a 125% mistake.            */
    SELECT DISTINCT
        i.seller_id,
        o.order_id,
        julianday(o.order_delivered_customer_date)
      - julianday(o.order_estimated_delivery_date)                AS delay_days -- PG: DATEDIFF
    FROM order_items i
    JOIN orders o ON o.order_id = i.order_id AND o.order_status = 'delivered'
),
seller_latency AS (
    SELECT seller_id,
           ROUND(AVG(delay_days), 2)                              AS avg_delay_days,
           ROUND(100.0 * COUNT(DISTINCT CASE WHEN delay_days <= 0 THEN order_id END)
                 / COUNT(DISTINCT order_id), 2)                   AS ontime_pct
    FROM order_latency
    GROUP BY seller_id
)
SELECT
    w.*,
    l.avg_delay_days,
    l.ontime_pct,
    RANK() OVER (ORDER BY w.gmv DESC)     AS revenue_rank,   -- PG: same
    ROUND(100.0 * w.bad_reviews / NULLIF(w.orders, 0), 2) AS bad_review_pct
FROM seller_stats w
JOIN seller_latency l USING (seller_id)
ORDER BY w.gmv DESC;

/* ============================================================================
   SECTION 6 — CATEGORY PERFORMANCE (feeds dashboard page 4)
   ============================================================================
   The famous "rank by revenue vs rank by volume disagree" insight:
   chair-cases (bed_bath_table, computers...) rank high on VOLUME but
   lower on AOV/AOV-adjusted REVENUE. The two rankings are computed in
   parallel columns and their rank-delta is surfaced for the memo.         */
DROP TABLE IF EXISTS mv_category_performance;
CREATE TABLE mv_category_performance AS
WITH pair AS (
    /* (category x order) grain: revenue attribution + buyer identity */
    SELECT
        COALESCE(t.product_category_name_english, p.product_category_name, 'uncategorised') AS category,
        o.order_id,
        g.customer_unique_id,
        SUM(i.price + i.freight_value) AS rev
    FROM order_items i
    JOIN orders    o ON o.order_id  = i.order_id AND o.order_status='delivered'
    JOIN customers g ON g.customer_id = o.customer_id
    LEFT JOIN products p ON p.product_id = i.product_id
    LEFT JOIN product_category_translation t ON t.product_category_name = p.product_category_name
    GROUP BY 1, 2, 3
),
with_order_ctx AS (
    /* attach order-level attributes exactly once per (category, order) */
    SELECT
        pr.category,
        pr.order_id,
        pr.customer_unique_id,
        pr.rev,
        r.review_score,
        julianday(o.order_delivered_customer_date)
      - julianday(o.order_estimated_delivery_date) AS delay_days -- PG: DATEDIFF
    FROM pair pr
    JOIN orders o ON o.order_id = pr.order_id
    LEFT JOIN reviews r ON r.order_id = pr.order_id
),
cat_agg AS (
    SELECT
        category,
        SUM(rev)  AS revenue,
        COUNT(DISTINCT order_id) AS order_volume,
        SUM(rev) / COUNT(DISTINCT order_id) AS aov,
        AVG(review_score) AS avg_rating,
        AVG(delay_days)   AS avg_delay_days,
        COUNT(DISTINCT customer_unique_id) AS customers
    FROM with_order_ctx
    GROUP BY category
)
SELECT
    category,
    ROUND(revenue, 2)                                   AS revenue,
    order_volume,
    ROUND(aov, 2)                                       AS aov,
    ROUND(avg_rating, 2)                                AS avg_rating,
    ROUND(avg_delay_days, 2)                            AS avg_delay_days,
    customers,
    RANK() OVER (ORDER BY revenue DESC)                 AS rank_revenue,
    RANK() OVER (ORDER BY order_volume DESC)            AS rank_volume
FROM cat_agg;

/* ============================================================================
   SECTION 7 — MATERIALIZED EXPORT LAYER (feeds the Power BI CSVs)
   ============================================================================
   Consolidates what the CSV exporter into data/exports/ needs:

   mv_monthly_revenue_metrics  <- Section 1.1 + new-customer overlay
   mv_cohort_matrix            <- Section 2    (already mv_retention_matrix)
   mv_powerbi_rfm              <- per-customer RFM with segment (1:1 cp)
   mv_powerbi_categories       <- Section 6 with review/delivery enrich

   Only GLUE below (add columns, no re-numbering of business logic).       */
DROP TABLE IF EXISTS mv_powerbi_rfm;
CREATE TABLE mv_powerbi_rfm AS
SELECT customer_unique_id,
       recency_days,
       frequency,
       monetary,
       segment,
       r_score, f_score, m_score
FROM mv_rfm_segments;

/* new customers per month — the "growth engine vs acquired base" overlay */
DROP TABLE IF EXISTS mv_monthly_new;
CREATE TABLE mv_monthly_new AS
WITH first_month AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
    FROM vw_order_gmv
    GROUP BY customer_unique_id
)
SELECT cohort_month,
       COUNT(*) AS new_customers
FROM first_month
GROUP BY cohort_month
ORDER BY cohort_month;

/* daily revenue — enables the Monthly/Weekly toggle on the dashboard.
   Same order-grain source as everything else (vw_order_gmv), just at date
   granularity; weekly sums are derived from THIS table, never re-joined.  */
DROP TABLE IF EXISTS mv_daily_revenue;
CREATE TABLE mv_daily_revenue AS
SELECT
    DATE(substr(purchase_ts, 1, 10)) AS day,
    ROUND(SUM(gmv), 2)               AS revenue,
    COUNT(*)                         AS orders
FROM vw_order_gmv
GROUP BY DATE(substr(purchase_ts, 1, 10))
ORDER BY day;

/* ============================================================================
   END OF ANALYSIS
   ============================================================================
   Tables created (all get exported to CSV by make_powerbi_exports.py):
     mv_mrr_monthly          1.1  MRR + MoM growth + AOV
     mv_aov_by_category      1.2  category AOV
     mv_cac_ltv / sweep      1.3  CAC:LTV + sensitivity
     mv_retention_matrix     2    cohort heatmap (rows, cols, %)
     mv_retention_curve      2.1  average curve
     mv_rfm_segments         3    per-customer RFM
     mv_rfm_segment_summary  3.1  segment shares (%, revenue contribution)
     mv_churn_summary        4.1  churn per cohort
     mv_category_repeat      4.2  repeat vs one-time by category
     mv_delivery_review      5.1  delivery buckets vs review score
     mv_seller_ranking       5.2  RANK() seller leaderboard
     mv_category_performance 6    category two-way ranking
     mv_powerbi_rfm          7    CSV bridge
     mv_monthly_new          7    new customers per month
============================================================================ */
