# -*- coding: utf-8 -*-
"""Page 2 — Cohort Retention: heatmap, average curve, cohort drill-down, what-if."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import (
    AMBER, BLUE, PRIMARY, RED, fmt_money, fmt_num, inject_css,
    kpi_card, load_csv, render_nav_tabs,
)

st.set_page_config(page_title="Cohort Retention · GrowthLens", page_icon="📈", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div class="sidebar-logo"><span class="logo-mark">📈</span>'
                '<span class="logo-text">GrowthLens</span></div>'
                '<div class="sidebar-dim">Cohort Retention</div>',
                unsafe_allow_html=True)

st.title("📈 Cohort Retention")
st.markdown(render_nav_tabs("Cohort_Retention"), unsafe_allow_html=True)
st.caption("Retention matrix from `mv_retention_matrix` — each row is an acquisition "
           "cohort (month of a customer's first delivered order); each column is months "
           "since that first purchase.")

matrix = load_csv("cohort_retention_matrix.csv")
curve = load_csv("retention_curve.csv")
mrr = load_csv("monthly_revenue_metrics.csv")

matrix["cohort_label"] = pd.to_datetime(matrix["cohort_month"]).dt.strftime("%b %Y")
matrix["size_label"] = matrix["cohort_size"].map(fmt_num)

# ------------------------------------------------------------------ headline KPI
m1 = curve[curve["months_since"] == 1].iloc[0]
m2 = curve[curve["months_since"] == 2].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("Month-1 Retention (pooled)", f"{m1['pooled_retention_pct']:.2f}%",
                     f"avg of {m1['cohorts']:.0f} cohorts of 100+ customers", BLUE),
            unsafe_allow_html=True)
c2.markdown(kpi_card("Month-2 Retention (pooled)", f"{m2['pooled_retention_pct']:.2f}%",
                     "of cohort active", BLUE), unsafe_allow_html=True)
cohort_total = int(matrix[matrix["months_since_first_purchase"] == 0]["cohort_size"].sum())
c3.markdown(kpi_card("Cohorted customers", fmt_num(cohort_total),
                     "acquired 2016-09 → 2018-08", PRIMARY), unsafe_allow_html=True)
aov_avg = float(mrr["aov"].mean())
c4.markdown(kpi_card("AOV used in what-if", fmt_money(aov_avg),
                     "monthly AOV average", AMBER), unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ controls
f1, f2, f3 = st.columns([2.0, 1.4, 1.0])
with f1:
    horizon = st.selectbox("Show stage window (months since first purchase)",
                           options=[6, 12, 24], index=0)
with f2:
    focus_cohort = st.selectbox(
        "Highlight a specific cohort (drives the curve below)",
        options=sorted(matrix["cohort_label"].unique(), reverse=True),
        index=4,
    )
with f3:
    run_whatif = st.button("⚡ Run What-If: +10% Retention")

horizon_matrix = matrix[matrix["months_since_first_purchase"] <= horizon]

# ------------------------------------------------------------------ heatmap
pivot = horizon_matrix.pivot_table(
    index="cohort_label", columns="months_since_first_purchase",
    values="retention_pct", aggfunc="first",
)
pivot = pivot.sort_index(ascending=False)
sizes = (horizon_matrix[horizon_matrix["months_since_first_purchase"] == 0]
         .set_index("cohort_label")["cohort_size"])
hover_text = pivot.copy().astype(object)
for cohort in pivot.index:
    for col in pivot.columns:
        v = pivot.loc[cohort, col]
        if pd.isna(v):
            hover_text.loc[cohort, col] = "no purchases recorded"
        else:
            c_n = int(round(v / 100 * sizes.get(cohort, 0)))
            hover_text.loc[cohort, col] = (
                f"{cohort} · {fmt_num(sizes.get(cohort, 0))} customers<br>"
                f"month {int(col)}: {v:.2f}% active ({fmt_num(c_n)} customers)"
            )

COHORT_STACK = [[0, "#17171A"], [0.35, "#4E3F10"], [0.7, "#B8860B"], [1, "#F4D969"]]
fig = go.Figure(go.Heatmap(
    z=pivot.values,
    x=[f"M{int(c)}" for c in pivot.columns],
    y=pivot.index,
    zmin=0, zmax=30,
    colorscale=COHORT_STACK,
    xgap=2, ygap=2,
    text=hover_text.values,
    hovertemplate="%{text}<extra></extra>",
    colorbar=dict(title="Active %", thickness=12),
))
fig.update_layout(
    title="Cohort Retention Heatmap — % of acquisition cohort active in each later month",
    height=max(420, 26 * len(pivot.index) + 80),
    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    yaxis_title="Acquisition cohort",
    xaxis_title="Months since first purchase",
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ how to read
st.info(
    "**How to read this heatmap** — every row is a group of customers ('cohort') defined by the month of "
    "their FIRST order. A cell = the share of that group still buying in a later month: M0 is always "
    "100% by definition; M1 is survival to the next month. Darker green = healthier cohort. The far "
    "right columns empty out because later cohorts simply haven't aged that far. One caution cell: "
    "the Dec 2016 cohort had just 1 customer, so its 100% at M1 is one repeat buyer, not a pattern — "
    "the pooled average curve below excludes cohorts < 100 customers for exactly this reason.",
    icon="🧭",
)

# ------------------------------------------------------------------ cohort curve
st.subheader(f"Cohort curve — {focus_cohort} vs the pool")
sel_curve = matrix[matrix["cohort_label"] == focus_cohort].sort_values("months_since_first_purchase")
pool_curve = curve[curve["months_since"] <= max(int(sel_curve["months_since_first_purchase"].max()), 6)]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=pool_curve["months_since"], y=pool_curve["pooled_retention_pct"],
    mode="lines", name="Pooled average (cohorts of 100+)",
    line=dict(color="#9CA3AF", width=2, dash="dash"),
    hovertemplate="pool · M%{x}: %{y:.2f}%<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=sel_curve["months_since_first_purchase"], y=sel_curve["retention_pct"],
    mode="lines+markers", name=focus_cohort,
    line=dict(color=RED, width=2.6),
    marker=dict(size=8),
    customdata=sel_curve["customer_count"],
    hovertemplate="%{x} months after first order<br>%{y:.2f}% active "
                  "(%{customdata:,} customers)<extra></extra>",
))
fig.update_layout(height=390, template="plotly_dark",
                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                  xaxis_title="Months since first purchase",
                  yaxis_title="% of cohort active",
                  legend=dict(orientation="h", y=1.12))
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ what-if
st.divider()
st.subheader("What-if: +10% month-1..6 retention")

st.markdown(
    "Small retention lifts compound into orders. The model: a **+10% relative lift on the number of "
    "active customers at each stage M1..M6** (across all cohorts) adds incremental repeat orders, "
    "valued at the blended AOV."
)

if run_whatif:
    lift = 0.10
    rows = curve[(curve["months_since"] >= 1) & (curve["months_since"] <= 6)]
    base_orders = int(rows["active_customers"].sum())
    incremental_orders = int(round(base_orders * lift))
    incremental_revenue = incremental_orders * aov_avg
    incremental_annual = incremental_revenue * 12

    w1, w2, w3 = st.columns(3)
    w1.markdown(kpi_card("Base repeat orders (M1-M6)", fmt_num(base_orders),
                         "all cohorts pooled", BLUE), unsafe_allow_html=True)
    w2.markdown(kpi_card("Incremental orders", f"+{fmt_num(incremental_orders)}",
                         f"{lift:.0%} relative lift on actives", PRIMARY), unsafe_allow_html=True)
    w3.markdown(kpi_card("Incremental revenue", f"+{fmt_money(incremental_revenue)}",
                         f"≈ {fmt_money(incremental_annual)} if sustained for a year", AMBER),
                unsafe_allow_html=True)
    st.caption(
        f"math: Σ(active customers, M1..M6) = {base_orders:,} → +10% = +{incremental_orders:,} orders "
        f"× AOV {fmt_money(aov_avg)} ≈ +{fmt_money(incremental_revenue)}. Retention quality is the compounding "
        "lever here — even a 10% relative lift on such a small repeat base."
    )
