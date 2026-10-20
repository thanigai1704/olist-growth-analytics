# -*- coding: utf-8 -*-
"""Page 1 — Executive Summary: revenue trend, growth, category mix."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import (
    AMBER, BLUE, PRIMARY, RED, fmt_money, fmt_num, inject_css,
    kpi_card, load_csv, render_nav_tabs,
)

st.set_page_config(page_title="Executive Summary · GrowthLens", page_icon="📊",
                   layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div class="sidebar-logo"><span class="logo-mark">📊</span>'
                '<span class="logo-text">GrowthLens</span></div>'
                '<div class="sidebar-dim">Executive Summary</div>',
                unsafe_allow_html=True)

st.title("📊 Executive Summary")
st.markdown(render_nav_tabs("Executive_Summary"), unsafe_allow_html=True)
st.caption("Monthly booked revenue (MRR), MoM growth, AOV — sourced from "
           "`mv_mrr_monthly` / `mv_daily_revenue` in growth_retention_analysis.sql")

monthly = load_csv("monthly_revenue_metrics.csv")
daily = load_csv("revenue_daily.csv")
cat_split = load_csv("revenue_by_category.csv")

daily["day"] = pd.to_datetime(daily["day"])
monthly["month_dt"] = pd.to_datetime(monthly["month"])

# the dataset has a dead month (2016-11, zero orders) and a stub tail after
# Aug 2018; both are real and kept in the data.
MIN_DAY, MAX_DAY = daily["day"].min().date(), daily["day"].max().date()

# ------------------------------------------------------------------ filters
f1, f2, f3 = st.columns([3.4, 1.6, 1.6])
with f1:
    date_range = st.date_input(
        "Date range",
        value=(pd.Timestamp("2017-01-01").date(), MAX_DAY),
        min_value=MIN_DAY,
        max_value=MAX_DAY,
    )
with f2:
    view = st.toggle("Weekly view", value=False,
                     help="Switches monthly totals to weekly totals resampled from daily revenue")
with f3:
    @st.cache_data
    def _report_csv() -> bytes:
        mo = load_csv("monthly_revenue_metrics.csv")
        return mo.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇️ Download report",
        data=_report_csv(),
        file_name="growthlens_monthly_metrics_report.csv",
        mime="text/csv",
        help="CSV of monthly metrics: month, MRR, MoM growth %, AOV, orders, new customers",
    )
st.divider()

start, end = (date_range if isinstance(date_range, (tuple, list)) else (MIN_DAY, MAX_DAY))
start, end = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)

# ------------------------------------------------------------------ KPIs
mask = (daily["day"] >= start) & (daily["day"] < end)
rev_sel = daily[mask]
rev_in_range = rev_sel["revenue"].sum()
orders_in_range = rev_sel["orders"].sum()
aov_in_range = rev_in_range / orders_in_range

mo_in_range_all = monthly[(monthly["month_dt"] >= start) & (monthly["month_dt"] < end)]
growth_latest = mo_in_range_all.iloc[-1]["growth_pct"] if len(mo_in_range_all) else None
new_cust_in_range = mo_in_range_all["new_customers"].sum() if len(mo_in_range_all) else 0

c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("Revenue in range", fmt_money(rev_in_range),
                     f"{fmt_num(orders_in_range)} orders", PRIMARY), unsafe_allow_html=True)
c3.markdown(kpi_card("Avg Order Value", fmt_money(aov_in_range),
                     "revenue / orders", BLUE), unsafe_allow_html=True)
c4.markdown(kpi_card("Total Customers", fmt_num(new_cust_in_range),
                     "first-time buyers in range", AMBER), unsafe_allow_html=True)
if growth_latest is not None and pd.notna(growth_latest):
    c2.markdown(kpi_card("Latest MoM Growth", f"{growth_latest * 100:+.1f}%",
                         "vs previous month", RED if growth_latest < 0 else PRIMARY,
                         delta_positive=growth_latest > 0), unsafe_allow_html=True)
else:
    c2.markdown(kpi_card("Latest MoM Growth", "—", "extend the range", BLUE),
                unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ revenue line
if view:
    weekly = (rev_sel.set_index("day")["revenue"]
              .resample("W").sum().reset_index())
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weekly["day"], y=weekly["revenue"], mode="lines",
        line=dict(color=PRIMARY, width=2.5, shape="spline"),
        fill="tozeroy", fillcolor="rgba(212,175,55,0.14)",
        name="Weekly revenue",
        hovertemplate="%{x|%d %b %Y}<br>R$ %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(title="Weekly Revenue", height=420,
                      template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False,
                      yaxis_title="Revenue (R$)", xaxis_title=None)
else:
    mo_view = monthly[(monthly["month_dt"] >= start) & (monthly["month_dt"] < end)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mo_view["month_dt"], y=mo_view["mrr"],
        mode="lines+markers", line=dict(color=PRIMARY, width=2.8),
        marker=dict(size=7),
        fill="tozeroy", fillcolor="rgba(212,175,55,0.14)",
        name="MRR",
        customdata=mo_view[["order_count", "aov", "growth_pct"]],
        hovertemplate=("%{x|%b %Y}<br>MRR: R$ %{y:,.0f}<br>"
                       "orders: %{customdata[0]:,} · AOV: R$ %{customdata[1]:,.2f}<br>"
                       "MoM: %{customdata[2]:+.1%}<extra></extra>"),
    ))
    fig.update_layout(title="Monthly Revenue (MRR)", height=420,
                      template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False,
                      yaxis_title="Revenue (R$)", xaxis_title=None)

st.plotly_chart(fig, use_container_width=True)
st.caption("Note the real data edges: **Nov 2016 = zero orders** (dead month from the soft-launch era) "
           "and the Black Friday jump in Nov 2017. Nothing has been smoothed away.")

# ------------------------------------------------------------------ category donut
col_chart, col_table = st.columns([1.15, 1])
with col_chart:
    st.subheader("Revenue by category")
    colors = ["#D4AF37", "#B692F0", "#6EA8FE", "#F0A93B", "#57BFE0", "#8C8455"]
    figd = go.Figure(go.Pie(
        labels=cat_split["category"],
        values=cat_split["revenue"],
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="#0D0D10", width=2)),
        textinfo="label+percent", textposition="outside",
        hovertemplate="%{label}<br>R$ %{value:,.0f}<extra></extra>",
    ))
    figd.update_layout(height=430, template="plotly_dark",
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       legend=dict(orientation="h", y=-0.12))
    figd.update_traces(pull=[0.03] * len(cat_split))
    st.plotly_chart(figd, use_container_width=True)
with col_table:
    st.subheader("Top-5 vs the rest")
    cat_split = cat_split.copy()
    cat_split["share"] = 100 * cat_split["revenue"] / cat_split["revenue"].sum()
    cat_split["revenue_fmt"] = cat_split["revenue"].apply(fmt_money)
    st.dataframe(cat_split[["category", "revenue_fmt", "share"]],
                 use_container_width=True, hide_index=True,
                 column_config={
                     "category": st.column_config.TextColumn("Category"),
                     "revenue_fmt": st.column_config.TextColumn("Revenue"),
                     "share": st.column_config.NumberColumn("Share", format="%.1f%%"),
                 })
    st.caption('"Others" pools the remaining categories (74 total) — '
               "the long tail single-handedly exceeds the best category.")

st.caption("The report CSV (⬇️ button above) contains month, MRR, MoM growth %, "
           "AOV, order count and new-customer count — the exact columns used by "
           "the charts above.")
