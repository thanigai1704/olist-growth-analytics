# -*- coding: utf-8 -*-
"""Page 3 — Customer Segments (RFM): treemap, drill-down, campaign drafts."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import (
    SEGMENT_META,
    SEGMENT_ORDER,
    AMBER,
    PRIMARY,
    fmt_money,
    fmt_num,
    fmt_pct,
    inject_css,
    kpi_card,
    load_csv,
    render_nav_tabs,
)

st.set_page_config(page_title="Customer Segments · GrowthLens", page_icon="👥", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div class="sidebar-logo"><span class="logo-mark">👥</span>'
                '<span class="logo-text">GrowthLens</span></div>'
                '<div class="sidebar-dim">Customer Segments</div>',
                unsafe_allow_html=True)

st.title("👥 Customer Segments (RFM)")
st.markdown(render_nav_tabs("Customer_Segments"), unsafe_allow_html=True)
st.caption("Per-customer Recency · Frequency · Monetary scored with NTILE(4) and combined into named "
           "segments — `mv_rfm_segments` / `mv_rfm_segment_summary` in growth_retention_analysis.sql")

rfm = load_csv("rfm_segments.csv")
summary = load_csv("rfm_segment_summary.csv")

summary = summary.set_index("segment").reindex(SEGMENT_ORDER).reset_index()

# ------------------------------------------------------------------ headline
c1, c2, c3 = st.columns(3)
champ = summary[summary["segment"] == "Champions"].iloc[0]
risk = summary[summary["segment"] == "At-Risk"].iloc[0]
c1.markdown(kpi_card("Customers analysed", fmt_num(summary["customers"].sum()),
                     "one row per customer, frozen snapshot", PRIMARY), unsafe_allow_html=True)
c2.markdown(kpi_card("Champions revenue share", f"{champ['revenue_share_pct']:.1f}%",
                     f"{champ['customer_share_pct']:.1f}% of customers", "#3B82F6"),
            unsafe_allow_html=True)
c3.markdown(kpi_card("At-Risk revenue share", f"{risk['revenue_share_pct']:.1f}%",
                     f"{risk['customer_share_pct']:.1f}% of customers", AMBER),
            unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ treemap
st.subheader("Segment map — size = customers, colour = share of total revenue")
fig = go.Figure(go.Treemap(
    labels=summary["segment"],
    values=summary["customers"],
    parents=[""] * len(summary),
    marker=dict(
        colors=summary["revenue_share_pct"],
        colorscale=[[0, "#E5E7EB"], [0.5, "#6EE7B7"], [1, "#059669"]],
        line=dict(width=1.5, color="#FFFFFF"),
    ),
    texttemplate=("<b>%{label}</b><br>%{value:,} customers<br>"
                  "<span style='font-size:12px'>%{customdata[0]:.1f}% revenue share</span>"),
    customdata=summary[["revenue_share_pct"]].values,
    textinfo="text",
    hovertemplate=("%{label}<br>%{value:,} customers (%{percentRoot:.1%} of base)<br>"
                   "revenue share %{customdata[0]:.1f}%<extra></extra>"),
))
fig.update_layout(height=430, margin=dict(t=10, l=10, r=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ segment table
st.subheader("Segment scorecard")
tbl = summary.copy()
tbl["revenue_fmt"] = tbl["revenue"].apply(fmt_money)
tbl["avg_frequency"] = tbl["avg_frequency"].round(2)
tbl["avg_recency_days"] = tbl["avg_recency_days"].round(0).astype(int)
st.dataframe(
    tbl[["segment", "customers", "customer_share_pct", "revenue_fmt",
         "revenue_share_pct", "avg_recency_days", "avg_frequency"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "segment": st.column_config.TextColumn("Segment"),
        "customers": st.column_config.NumberColumn("Customers", format="localized"),
        "customer_share_pct": st.column_config.NumberColumn("% Customers", format="%.1f%%"),
        "revenue_fmt": st.column_config.TextColumn("Revenue"),
        "revenue_share_pct": st.column_config.NumberColumn("% Revenue", format="%.1f%%"),
        "avg_recency_days": st.column_config.NumberColumn("Avg recency (d)"),
        "avg_frequency": st.column_config.NumberColumn("Avg orders"),
    },
)
st.caption("With a 3.0% lifetime repeat rate, the Frequency quartile is nearly degenerate (almost everyone "
           "has exactly 1 order) — segments lean on Recency × Monetary. That is an honest property of real "
           "marketplace data, and it is exactly why At-Risk dwarfs Loyal Customers.")

st.divider()

# ------------------------------------------------------------------ drill-down
st.subheader("Drill into one segment")
current = st.radio(
    "Segment",
    SEGMENT_ORDER,
    horizontal=True,
    format_func=lambda s: f"{SEGMENT_META[s]['icon']} {s}",
)
srow = summary[summary["segment"] == current].iloc[0]
s = (rfm[rfm["rfm_segment"] == current]
     .sort_values("monetary", ascending=False)
     .head(10)
     .copy())
s["monetary_fmt"] = s["monetary"].apply(fmt_money)

t1, t2 = st.columns([1.4, 0.6])
with t1:
    st.markdown(f"Sample customers — top 10 by lifetime spend (of {fmt_num(int(srow['customers']))}):")
    st.dataframe(
        s[["customer_id", "recency", "frequency", "monetary_fmt"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "customer_id": st.column_config.TextColumn("Customer"),
            "recency": st.column_config.NumberColumn("Days since last order"),
            "frequency": st.column_config.NumberColumn("Orders"),
            "monetary_fmt": st.column_config.TextColumn("Lifetime spend"),
        },
    )
    st.caption("Full 93,358-row per-customer file: data/exports/rfm_segments.csv "
               "(Power BI page 3 uses exactly this file).")
with t2:
    st.markdown("RFM tiles of the same sample:")
    st.dataframe(
        s[["r_score", "f_score", "m_score"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "r_score": st.column_config.NumberColumn("R (1-4)"),
            "f_score": st.column_config.NumberColumn("F (1-4)"),
            "m_score": st.column_config.NumberColumn("M (1-4)"),
        },
    )

# ------------------------------------------------------------------ recommendation cards
st.divider()
st.subheader("Recommended actions")


def campaign_email_draft(segment: str, avg_lifetime: str) -> str:
    """Rule-based re-engagement email template (deterministic, offline).

    If an LLM key is available this is the exact hook point: pass
    `segment` + the same stats into an API call and stream the result.
    """
    copy = {
        "Champions": (
            "Olá [first name],\n\n"
            "You are one of our most valuable customers — thank you. As a Champion, "
            "you get early access to the next product launch before anyone else.\n\n"
            "Tap below to reserve your spot (we ship in order of sign-up).\n"
        ),
        "Loyal Customers": (
            "Olá [first name],\n\n"
            "You keep coming back — let's make your next order stronger. Bundle "
            "complementary products and earn double points on this week's picks.\n\n"
        ),
        "Potential Loyalists": (
            "Olá [first name],\n\n"
            "Your first order arrived exactly as promised. Here is a 10% welcome-back "
            "coupon valid for the next 14 days — pick anything.\n\n"
        ),
        "At-Risk": (
            "Olá [first name],\n\n"
            "It has been over 3 months since your last order, and we still have your "
            "favourite categories in stock. Here is 20% OFF, limited to what you loved — "
            "valid for 10 days.\n\n"
        ),
        "Hibernating": (
            "Olá [first name],\n\n"
            "Lots changed since your last visit: faster deliveries, more categories, "
            "and free shipping on small orders. Take a look — no discount needed.\n\n"
        ),
        "Lost": (
            "Olá [first name],\n\n"
            "If your first experience fell short, we are sorry. Here is 10% and "
            "priority support on your next order — no strings attached.\n\n"
        ),
    }
    footer = (
        "\nEquipe Olist\n\n"
        f"[Campaign: {segment}] · [Offer owner: CRM]\n"
        "[A/B split: 50/50 · success metric: repeat purchase within 30 days]\n"
        f"[Audience value: avg lifetime {avg_lifetime}]"
    )
    return copy[segment] + footer


half = (len(SEGMENT_ORDER) + 1) // 2
left_col, right_col = st.columns(2)
for i, seg_name in enumerate(SEGMENT_ORDER):
    col = left_col if i < half else right_col
    m = SEGMENT_META[seg_name]
    row = summary[summary["segment"] == seg_name].iloc[0]
    avg_lifetime = fmt_money(row["revenue"] / max(row["customers"], 1))
    with col:
        st.markdown(
            f"""
            <div class="seg-card" style="--seg:{m['color']}">
                <div class="seg-head">{m['icon']} {seg_name}</div>
                <div class="seg-stat">
                    {fmt_pct(row['customer_share_pct'], 1)} of customers ·
                    <b>{fmt_pct(row['revenue_share_pct'], 1)} of revenue</b> ·
                    avg {avg_lifetime} lifetime
                </div>
                <div class="seg-body">{m['recommendation']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"✉️ Generate campaign email draft — {seg_name}", key=f"email_{seg_name}"):
            st.text_area("Draft", value=campaign_email_draft(seg_name, avg_lifetime),
                         height=320, key=f"draft_{seg_name}")

st.info("Adapter note: these drafts are rule-based templates seeded with each segment's real stats. "
        "With an LLM key in the environment this generator is the natural place to stream a "
        "personalised subject line + body per segment.", icon="🧪")
