# -*- coding: utf-8 -*-
"""GrowthLens Analytics — Home page (app entry).

Run:  streamlit run streamlit_app/app.py
"""
import streamlit as st

from common import (
    AMBER, BLUE, PRIMARY, RED, VIOLET, fmt_money, fmt_num, fmt_pct, inject_css,
    kpi_card, load_csv, render_nav_tabs, SQL_FILE,
)

st.set_page_config(
    page_title="GrowthLens Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# ------------------------------------------------------------------ top nav
st.markdown(render_nav_tabs("home"), unsafe_allow_html=True)

# ------------------------------------------------------------------ data
monthly = load_csv("monthly_revenue_metrics.csv")
curve = load_csv("retention_curve.csv")
cat_perf = load_csv("category_performance.csv")
seg = load_csv("rfm_segment_summary.csv")

total_revenue = float(monthly["mrr"].sum())
total_orders = int(monthly["order_count"].sum())
new_customers_total = int(monthly["new_customers"].sum())
m1_pooled = float(curve.loc[curve["months_since"] == 1, "pooled_retention_pct"].iloc[0])
top_cat = cat_perf.iloc[0]
champions = seg[seg["segment"] == "Champions"].iloc[0]
at_risk = seg[seg["segment"] == "At-Risk"].iloc[0]

# ------------------------------------------------------------------ sidebar
sidebar_logo = (
    '<div class="sidebar-logo"><span class="logo-mark">📈</span>'
    '<span class="logo-text">GrowthLens</span></div>'
    '<div class="sidebar-dim">Business Growth &amp; Retention Analytics<br>'
    "Olist Brazilian e-commerce · 2016-2018</div>"
)
with st.sidebar:
    st.markdown(sidebar_logo, unsafe_allow_html=True)

# ------------------------------------------------------------------ hero
st.markdown(
    """
    <div class="hero">
        <div class="kicker">Portfolio project · growth &amp; retention analytics</div>
        <h1>📈 GrowthLens Analytics</h1>
        <p>What does Olist's real order book say about growth, retention, and
        the customers that pay the bills? 100K+ orders, 96K+ real customers,
        every number traceable to one audited SQL file.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ KPIs
c1, c2, c3, c4 = st.columns(4)
c1.markdown(
    kpi_card(
        "Total Revenue",
        fmt_money(total_revenue),
        f"Orders in window: {fmt_num(total_orders)}",
        PRIMARY,
    ),
    unsafe_allow_html=True,
)
c2.markdown(
    kpi_card(
        "Total Customers",
        fmt_num(new_customers_total),
        f"avg {fmt_num(monthly['new_customers'].mean())} new per month",
        BLUE,
    ),
    unsafe_allow_html=True,
)
c3.markdown(
    kpi_card(
        "Avg Retention — Month 1",
        fmt_pct(m1_pooled, 2),
        "share of a cohort still buying 1 month later",
        AMBER,
    ),
    unsafe_allow_html=True,
)
c4.markdown(
    kpi_card(
        "Top Category",
        str(top_cat["category"]).replace("_", " ").title(),
        f"{fmt_money(top_cat['revenue'])} revenue",
        VIOLET,
    ),
    unsafe_allow_html=True,
)

st.write("")

# ------------------------------------------------------------------ about
with st.expander("ℹ️ About this analysis"):
    st.markdown(
        """
**What is this?** A growth & retention study of the real
[Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(99,441 orders, 96,096 unique customers, Sep 2016 — Aug 2018), treated as if
Olist leadership hired a data analyst to answer four questions:

1. **Is revenue growing?** — monthly revenue, MoM growth, AOV. *(Executive Summary)*
2. **Do customers ever come back?** — acquisition-cohort retention matrix. *(Cohort Retention)*
3. **Who are the customers that matter?** — RFM segmentation with revenue shares. *(Customer Segments)*
4. **Where does execution break?** — categories, delivery times, seller quality. *(Category Insights)*

**Defensible by construction.** Every figure shown is an output of
`sql/growth_retention_analysis.sql` — CTEs + window functions (LAG, NTILE, RANK)
written against the cleaned relational database. The CSV files feeding this app
are 1:1 exports of those query results.
"""
    )
    st.caption(f"Source SQL: {SQL_FILE.name}")

# ------------------------------------------------------------------ nav
st.subheader("Explore the analysis")
cols = st.columns(4)
pages = [
    (cols[0], "Executive_Summary", "📊", "Executive Summary",
     "Monthly revenue, AOV, MoM growth, category mix", PRIMARY),
    (cols[1], "Cohort_Retention", "📈", "Cohort Retention",
     "Retention heatmap, average curve, what-if", BLUE),
    (cols[2], "Customer_Segments", "👥", "Customer Segments",
     "RFM segments, revenue shares, campaigns", AMBER),
    (cols[3], "Category_Insights", "🛍️", "Category Insights",
     "Revenue vs volume, delivery impact, sellers", RED),
]
from common import PAGE_URLS  # noqa: E402  (kept close to usage)

for col, slug, icon, label, sub, color in pages:
    with col:
        st.markdown(
            f"""
            <a class="nav-anch" href="{PAGE_URLS[slug]}" target="_self"
               style="border-left: 0">
              <span style="--nav:{color} ; display:block">
              <div class="nav-card" style="border-left-color:{color}">
                <span class="icon">{icon}</span>
                <div class="nav-label">{label}</div>
                <div class="nav-sub">{sub}</div>
              </div>
              </span>
            </a>
            """,
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "Synthetic-free: analysis runs on the public Olist dataset "
    "(CC BY-NC-SA; source credited in README). Snapshot 2018-09-04. "
    "Revenue = item-level GMV (price + freight), R$. "
    f"Key finding teaser: {fmt_pct(at_risk['revenue_share_pct'], 1)} of all revenue sits in the "
    "At-Risk segment — customers who bought well but stopped."
)
