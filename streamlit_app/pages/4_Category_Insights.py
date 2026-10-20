# -*- coding: utf-8 -*-
"""Page 4 — Category Insights: ranking toggles, delivery-vs-rating scatter, table."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (
    AMBER, BLUE, PRIMARY, RED, VIOLET,
    fmt_money, inject_css, kpi_card, load_csv, render_nav_tabs,
)

st.set_page_config(page_title="Category Insights · GrowthLens", page_icon="🛍️", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div class="sidebar-logo"><span class="logo-mark">🛍️</span>'
                '<span class="logo-text">GrowthLens</span></div>'
                '<div class="sidebar-dim">Category Insights</div>',
                unsafe_allow_html=True)

st.title("🛍️ Category Insights")
st.markdown(render_nav_tabs("Category_Insights"), unsafe_allow_html=True)
st.caption("Category performance from `mv_category_performance` and delivery-vs-review from "
           "`mv_delivery_review` — same SQL file, same rules.")

cats = load_csv("category_performance.csv")
delivery = load_csv("delivery_vs_review.csv")
sellers = load_csv("seller_ranking.csv")

# ------------------------------------------------------------------ headline
most_volume = cats.sort_values("order_volume", ascending=False).iloc[0]
highest_aov = cats.sort_values("aov", ascending=False).iloc[0]
rank_gap = (cats["rank_revenue"] - cats["rank_volume"]).abs().max()
c1, c2, c3 = st.columns(3)
c1.markdown(kpi_card("Revenue leader", str(cats.iloc[0]["category"]).replace("_", " ").title(),
                     fmt_money(cats.iloc[0]["revenue"]), PRIMARY), unsafe_allow_html=True)
c2.markdown(kpi_card("Volume leader (≈ revenue leader?)",
                     str(most_volume["category"]).replace("_", " ").title(),
                     f"#{int(most_volume['rank_volume'])} by volume vs #{int(most_volume['rank_revenue'])} by revenue",
                     BLUE), unsafe_allow_html=True)
c3.markdown(kpi_card("Highest AOV category", str(highest_aov["category"]).replace("_", " ").title(),
                     f"{fmt_money(highest_aov['aov'])} per order · only #{int(highest_aov['rank_volume'])} by volume",
                     VIOLET), unsafe_allow_html=True)
st.info(
    f"**Why the leaders differ:** the top revenue position went to *{cats.iloc[0]['category']}*, but "
    f"*{most_volume['category']}* wins order volume — cheap, repeatable products buy reach, while "
    f"higher baskets buy revenue. The two rankings differ by up to **{int(rank_gap)} positions**; "
    "marketing budget should follow the goal, not the leaderboard.",
    icon="⚖️",
)

st.divider()

# ------------------------------------------------------------------ bar ranking
st.subheader("Category ranking")
sort_mode = st.radio("Sort by", ["Revenue", "Order volume", "Rating", "AOV"],
                     horizontal=True, label_visibility="collapsed")
sort_col = {"Revenue": "revenue", "Order volume": "order_volume",
            "Rating": "avg_rating", "AOV": "aov"}[sort_mode]
top_n = st.slider("How many categories", 5, 30, 12)
sel = cats.sort_values(sort_col, ascending=False).head(top_n).copy()
sel["label"] = sel["category"].str.replace("_", " ").str.title()
sel["revenue_fmt"] = sel["revenue"].apply(fmt_money)

if sort_mode in ("Revenue", "AOV"):
    hover = ("<b>%{y}</b><br>revenue: %{customdata[0]}<br>AOV: R$ %{customdata[1]:,.2f}"
             "<extra></extra>")
else:
    hover = "<b>%{y}</b><br>orders: %{x:,}<extra></extra>"

sel_sorted = sel.sort_values(sort_col)
fig = px.bar(sel_sorted, y="label", x=sort_col, orientation="h",
             color_discrete_sequence=[PRIMARY])
fig.update_traces(
    marker=dict(line=dict(color="#0D0D10", width=0.5)),
    customdata=np.stack([sel_sorted["revenue_fmt"], sel_sorted["aov"]], axis=-1),
    hovertemplate=hover,
)
fig.update_layout(height=min(640, 80 + 34 * len(sel)), margin=dict(t=10), showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ scatter
st.divider()
st.subheader("Delivery time vs rating — does lateness break promise?")

min_orders = st.slider("Keep categories with at least N orders", 50, 3000, 300)
scatter_df = cats[cats["order_volume"] >= min_orders].copy()
scatter_df["label"] = scatter_df["category"].str.replace("_", " ").str.title()
scatter_df["size"] = scatter_df["order_volume"] ** 0.5

fig = px.scatter(
    scatter_df,
    x="avg_delivery_days", y="avg_rating",
    size="size", color="aov",
    hover_name="label",
    color_continuous_scale="Viridis",
    labels={"avg_delivery_days": "Avg delivery delay vs estimate (days)",
            "avg_rating": "Avg review score (1-5)"},
)
fig.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>delay: %{x:+.2f} days vs estimate<br>"
                  "rating: %{y:.2f}<extra></extra>",
)
fig.add_hrect(y0=1.0, y1=3.5, fillcolor="#FEE2E2", opacity=0.35,
              annotation_text="danger zone < 3.5 stars",
              annotation_font=dict(size=11, color="#B91C1C"))
fig.update_layout(height=460, template="plotly_dark",
                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)
st.caption("Note: category aggregates hover around the pack average, so the scatter looks 'tight'. The real "
           "signal lives in the delivery performance bridge below — late orders crater ratings "
           "regardless of category.")

# ------------------------------------------------------------------ delivery bridge
st.subheader("The delivery × review bridge")
d = delivery.copy()
d["delay_label"] = (d["delay_bucket"]
                    .str.replace("^a_", "on time / early", regex=True)
                    .str.replace("^b_", "up to 3d late", regex=True)
                    .str.replace("^c_", "4-7d late", regex=True)
                    .str.replace("^d_", "8-15d late", regex=True)
                    .str.replace("^e_", "16-30d late", regex=True)
                    .str.replace("^f_", "30d+ late", regex=True))
d = d.groupby("delay_label", as_index=False).agg(
    orders=("orders", "sum"),
    avg_review_score=("avg_review_score", "mean"),
    bad_review_pct=("bad_review_pct", "mean"),
)
d["ranko"] = d["delay_label"].map({m: i for i, m in enumerate(
    ["on time / early", "up to 3d late", "4-7d late", "8-15d late", "16-30d late", "30d+ late"])})
d = d.sort_values("ranko")

fig = go.Figure()
fig.add_trace(go.Bar(
    x=d["delay_label"], y=d["avg_review_score"],
    marker_color=[PRIMARY if s > 4.0 else AMBER if s > 3.0 else RED for s in d["avg_review_score"]],
    customdata=d[["orders", "bad_review_pct"]],
    hovertemplate=("<b>%{x}</b><br>score: %{y:.2f} ★<br>"
                   "orders: %{customdata[0]:,} (avg across transit buckets)<br>"
                   "bad-review share: %{customdata[1]:.1f}%<extra></extra>"),
))
fig.update_layout(height=400, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                  yaxis_title="Avg review score", xaxis_title="Delivery lateness vs promise",
                  showlegend=False)
st.plotly_chart(fig, use_container_width=True)
st.caption("Averaged across transit-time buckets. Orders arriving even a few days past the promised date "
           "lose more than a full star; a month+ late means a ~1.6★ order and ~80% bad reviews.")

# ------------------------------------------------------------------ table
st.divider()
st.subheader("Category table")
q = st.text_input("Search category", value="", placeholder="e.g. health, toys, gift")
view = cats.copy()
if q.strip():
    view = view[view["category"].str.contains(q.strip(), case=False, na=False)]
view = view.copy()
view["label"] = view["category"].str.replace("_", " ").str.title()
view["revenue_fmt"] = view["revenue"].apply(fmt_money)
view["aov_fmt"] = view["aov"].apply(fmt_money)

st.dataframe(
    view[["label", "revenue_fmt", "order_volume", "aov_fmt", "avg_rating",
          "avg_delivery_days", "rank_revenue", "rank_volume"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "label": "Category",
        "revenue_fmt": st.column_config.TextColumn("Revenue"),
        "order_volume": st.column_config.NumberColumn("Orders", format="localized"),
        "aov_fmt": st.column_config.TextColumn("AOV"),
        "avg_rating": st.column_config.NumberColumn("Avg ★", format="%.2f"),
        "avg_delivery_days": st.column_config.NumberColumn("Avg delay (d)"),
        "rank_revenue": st.column_config.NumberColumn("Rank $"),
        "rank_volume": st.column_config.NumberColumn("Rank vol"),
    },
)
st.caption("Use the search box + column sort. `Rank $` vs `Rank vol` side by side is the "
           "cheap-popular-vs-expensive-niche story in numbers.")

# ------------------------------------------------------------------ sellers
st.divider()
st.subheader("Seller leaderboard (RANK by revenue)")
top_sellers = sellers.sort_values("revenue_rank").head(10).copy()
top_sellers["seller_short"] = top_sellers["seller_id"].str[:8] + "…"
fig = px.bar(
    top_sellers.sort_values("revenue"),
    y="seller_short", x="revenue", orientation="h",
    color="avg_review", color_continuous_scale="RdYlGn",
    range_color=(3.0, 4.6),
    labels={"seller_short": "Seller", "revenue": "Revenue (R$)", "avg_review": "Avg ★"},
)
fig.update_traces(
    customdata=top_sellers.sort_values("revenue")[["ontime_pct", "orders"]],
    hovertemplate=("<b>%{y}</b><br>revenue: R$ %{x:,.0f}<br>"
                   "avg ★: %{marker.color:.2f}<extra></extra>"))
fig.update_layout(height=420, template="plotly_dark",
                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)
st.caption("Colour = average review score. Two of the top-5 sellers by revenue deliver distinctly "
           "mediocre reviews — scale is not yet quality on this marketplace. "
           "Full 100-row list: data/exports/seller_ranking.csv.")
