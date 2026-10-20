"""
make_powerbi_exports.py — Olist Growth & Retention Analytics
=============================================================

STAGE 3 of the pipeline: the mv_* analytics tables produced by
sql/growth_retention_analysis.sql  ->  clean flat CSVs in data/exports/,
each one shaped for ONE dashboard layer (Power BI page or Streamlit page).

Nothing is recomputed here. Every number exported is the direct output of
a query in growth_retention_analysis.sql — if a CSV cell changes, the SQL
file is where the change is auditable.

Exports
-------
 1. monthly_revenue_metrics.csv   (Power BI page 1, Streamlit Exec Summary)
                                  month, mrr, aov, growth_pct, order_count,
                                  prev_revenue, new_customers
 2. cohort_retention_matrix.csv   (Power BI page 2, Streamlit Cohort page)
                                  cohort_month, months_since_first_purchase,
                                  retention_pct, customer_count
 3. rfm_segments.csv              (Power BI page 3, Streamlit Segments page)
                                  customer_id (NOTE: durable customer_unique_id
                                  value, see README), recency, frequency,
                                  monetary, rfm_segment
 4. category_performance.csv      (Streamlit Category page)
                                  category, revenue, order_volume, avg_rating,
                                  avg_delivery_days, aov, customers
 5. retention_curve.csv           (avg-curve line under the heatmap)
 6. rfm_segment_summary.csv       (segment shares for treemap + tables)
 7. delivery_vs_review.csv        (delivery buckets vs rating scatter)
 8. seller_ranking.csv            (RANK() leaderboard table)
 9. churn_by_cohort.csv           (churn rate by acquisition cohort)
10. cohort_repeat.csv             (repeat-buyer rate by acquisition cohort)
11. revenue_by_category.csv       (donut top-5 + Others, pre-aggregated)
12. cac_ltv.csv                   (CAC:LTV assumption + sensitivity sweep)

Run:  python scripts/make_powerbi_exports.py
"""
import os
import sqlite3
import time

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "db", "olist_growth.db")
OUT = os.path.join(BASE, "data", "exports")


def export(conn, csv_name, sql, rename=None) -> pd.DataFrame:
    df = pd.read_sql_query(sql, conn)
    if rename:
        df = df.rename(columns=rename)
    path = os.path.join(OUT, csv_name)
    df.to_csv(path, index=False)
    print(f"[export] {csv_name:<32} {len(df):>8,} rows  -> {os.path.relpath(path, BASE)}")
    return df


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    conn = sqlite3.connect(DB)

    # ------------------------------------------------------------------ 1
    export(
        conn,
        "monthly_revenue_metrics.csv",
        """
        SELECT
            m.purchase_month                               AS month,
            ROUND(m.revenue, 2)                            AS mrr,
            ROUND(m.aov, 2)                                AS aov,
            ROUND(m.growth_pct, 4)                         AS growth_pct,
            m.orders                                       AS order_count,
            ROUND(m.prev_revenue, 2)                       AS prev_mrr,
            COALESCE(n.new_customers, 0)                   AS new_customers
        FROM mv_mrr_monthly m
        LEFT JOIN mv_monthly_new n
            ON n.cohort_month = m.purchase_month
        ORDER BY m.purchase_month
        """,
    )

    # ------------------------------------------------------------------ 2
    export(
        conn,
        "cohort_retention_matrix.csv",
        """
        SELECT
            cohort_month                                   AS cohort_month,
            months_since                                   AS months_since_first_purchase,
            retention_pct                                  AS retention_pct,
            customer_count                                 AS customer_count,
            cohort_size                                    AS cohort_size
        FROM mv_retention_matrix
        ORDER BY cohort_month, months_since_first_purchase
        """,
    )

    # ------------------------------------------------------------------ 3
    export(
        conn,
        "rfm_segments.csv",
        """
        SELECT
            customer_unique_id                             AS customer_id,
            recency_days                                   AS recency,
            frequency                                      AS frequency,
            ROUND(monetary, 2)                             AS monetary,
            ROUND(monetary, 2)                             AS total_revenue_contribution,
            segment                                        AS rfm_segment,
            r_score                                        AS r_score,
            f_score                                        AS f_score,
            m_score                                        AS m_score
        FROM mv_powerbi_rfm
        ORDER BY monetary DESC
        """,
    )

    # ------------------------------------------------------------------ 4
    cat = export(
        conn,
        "category_performance.csv",
        """
        SELECT
            category                                       AS category,
            ROUND(revenue, 2)                              AS revenue,
            order_volume                                   AS order_volume,
            ROUND(avg_rating, 3)                           AS avg_rating,
            ROUND(avg_delay_days, 2)                       AS avg_delivery_days,
            ROUND(aov, 2)                                  AS aov,
            customers                                      AS customers,
            rank_revenue                                   AS rank_revenue,
            rank_volume                                    AS rank_volume
        FROM mv_category_performance
        ORDER BY revenue DESC
        """,
    )

    # donut with top-5 + Others (page 1)
    top5 = cat.head(5)[["category", "revenue"]].copy()
    others = pd.DataFrame(
        [{"category": "Others", "revenue": round(cat["revenue"][5:].sum(), 2)}]
    )
    pd.concat([top5, others], ignore_index=True).to_csv(
        os.path.join(OUT, "revenue_by_category.csv"), index=False
    )
    print("[export] revenue_by_category.csv       "
          f"{len(top5) + 1:>8} rows  (top5 + Others)")

    # ------------------------------------------------------------------ 5
    export(
        conn,
        "retention_curve.csv",
        """
        SELECT
            months_since                                   AS months_since,
            cohorts_participating                          AS cohorts,
            avg_retention_pct                              AS avg_retention_pct,
            pooled_retention_pct                           AS pooled_retention_pct,
            active_customers                               AS active_customers
        FROM mv_retention_curve
        ORDER BY months_since
        """,
    )

    # ------------------------------------------------------------------ 6
    export(
        conn,
        "rfm_segment_summary.csv",
        """
        SELECT
            segment                                        AS segment,
            customers                                      AS customers,
            customer_share_pct                             AS customer_share_pct,
            ROUND(revenue, 2)                              AS revenue,
            revenue_share_pct                              AS revenue_share_pct,
            avg_recency_days                               AS avg_recency_days,
            avg_frequency                                  AS avg_frequency
        FROM mv_rfm_segment_summary
        ORDER BY revenue_share_pct DESC
        """,
    )

    # ------------------------------------------------------------------ 7
    export(
        conn,
        "delivery_vs_review.csv",
        """
        SELECT
            transit_bucket                                 AS transit_bucket,
            delay_bucket                                   AS delay_bucket,
            orders                                         AS orders,
            avg_review_score                               AS avg_review_score,
            n_bad_reviews                                  AS bad_reviews,
            bad_review_pct                                 AS bad_review_pct,
            avg_gmv                                        AS avg_gmv,
            transit_days                                   AS transit_days
        FROM mv_delivery_review
        ORDER BY transit_bucket, delay_bucket
        """,
    )

    # ------------------------------------------------------------------ 8
    export(
        conn,
        "seller_ranking.csv",
        """
        SELECT
            seller_id                                      AS seller_id,
            seller_state                                   AS seller_state,
            gmv                                            AS revenue,
            items_sold                                     AS items_sold,
            orders                                         AS orders,
            avg_review                                     AS avg_review,
            avg_delay_days                                 AS avg_delay_days,
            ontime_pct                                     AS ontime_pct,
            bad_review_pct                                 AS bad_review_pct,
            revenue_rank                                   AS revenue_rank
        FROM mv_seller_ranking
        ORDER BY revenue_rank
        LIMIT 100
        """,
    )

    # ------------------------------------------------------------------ 9
    export(
        conn,
        "churn_by_cohort.csv",
        """
        SELECT
            cohort_month                                   AS cohort_month,
            cohort_customers                               AS cohort_customers,
            churned_6m                                     AS churned_customers,
            churn_rate_pct                                 AS churn_rate_pct
        FROM mv_churn_summary
        ORDER BY cohort_month
        """,
    )

    # ------------------------------------------------------------------ 10
    export(
        conn,
        "cohort_repeat.csv",
        """
        SELECT
            cohort_month                                   AS cohort_month,
            cohort_customers                               AS cohort_customers,
            repeat_customers                               AS repeat_customers,
            repeat_rate_pct                                AS repeat_rate_pct
        FROM mv_cohort_repeat
        ORDER BY cohort_month
        """,
    )

    # ------------------------------------------------------------------ 12
    export(
        conn,
        "revenue_daily.csv",
        """
        SELECT
            day                                            AS day,
            ROUND(revenue, 2)                              AS revenue,
            orders                                         AS orders
        FROM mv_daily_revenue
        ORDER BY day
        """,
    )
    export(
        conn,
        "cac_ltv.csv",
        """
        SELECT
            metric                                         AS metric,
            assumed_cac                                    AS assumed_cac,
            ltv                                            AS ltv,
            ltv_cac_ratio                                  AS ltv_cac_gmv_ratio,
            gross_margin_assumption                        AS gross_margin_assumption,
            ltv_cac_on_margin                              AS ltv_cac_margin_ratio,
            customers                                      AS customers,
            avg_orders_per_customer                        AS avg_orders_per_customer
        FROM mv_cac_ltv
        """,
    )
    export(
        conn,
        "cac_sensitivity.csv",
        """
        SELECT
            assumed_cac                                    AS assumed_cac,
            ltv_cac_gmv                                    AS ltv_cac_gmv_ratio,
            ltv_cac_margin                                 AS ltv_cac_margin_ratio
        FROM mv_cac_sweep
        ORDER BY assumed_cac
        """,
    )

    conn.close()
    print(f"\n[done] 12 export files ready in data/exports/ in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
