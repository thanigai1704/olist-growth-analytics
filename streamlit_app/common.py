# -*- coding: utf-8 -*-
"""Common helpers for the GrowthLens Analytics Streamlit app — "Noir Gold" theme.

Every page imports from here so that paths, colors, CSS and data loading
stay consistent. All data comes from data/exports/*.csv — each file is the
direct output of a query in sql/growth_retention_analysis.sql.
"""
import os
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------- paths
APP_DIR = Path(__file__).resolve().parent          # streamlit_app/
REPO_DIR = APP_DIR.parent                          # project root
DATA_DIR = Path(os.environ.get("GROWTHLENS_DATA", REPO_DIR / "data" / "exports"))
SQL_FILE = REPO_DIR / "sql" / "growth_retention_analysis.sql"

# ---------------------------------------------------------------- palette (Noir Gold)
PRIMARY = "#D4AF37"          # gold
PRIMARY_DARK = "#B8860B"     # antique gold
PRIMARY_DEEP = "#1A1206"     # near-black warm brown (hover bg)
BG = "#0D0D10"               # page black
BG_SOFT = "#16161B"          # card black
BG_RAISED = "#1D1D23"        # inputs / raised surfaces
TEXT = "#F1E9D2"             # cream
TEXT_MUTED = "#9C937B"       # muted gold-grey
BORDER = "#2C2A24"           # warm hairline
GOLD_GLOW = "rgba(212, 175, 55, 0.35)"

BLUE = "#6EA8FE"
AMBER = "#F0A93B"
RED = "#F87F7F"
VIOLET = "#B692F0"
SLATE = "#9AA6B4"
TEAL = "#57BFE0"

SEGMENT_META = {
    "Champions": {
        "color": PRIMARY,
        "icon": "🏆",
        "recommendation": (
            "Reward with early access to launches and a referral program. "
            "Ask for reviews within 48h of delivery, and open a members-only "
            "Flash Friday deal. These buyers already convert without "
            "discounts — spend on experience, not price cuts."
        ),
    },
    "Loyal Customers": {
        "color": BLUE,
        "icon": "💙",
        "recommendation": (
            "Upsell complementary categories with product bundles and keep "
            "them subscribed to the best-sellers newsletter. A 3-5% points "
            "reward on the next order is cheaper than acquiring a new customer."
        ),
    },
    "Potential Loyalists": {
        "color": VIOLET,
        "icon": "🌱",
        "recommendation": (
            "Most bought once, recently. Trigger a first-time cross-category "
            "offer within 14 days of delivery (the strongest habit window) "
            "and ask one great review to convert trust into repeat intent."
        ),
    },
    "At-Risk": {
        "color": AMBER,
        "icon": "⚠️",
        "recommendation": (
            "High-value wallets gone quiet for 3+ months. Run a 20% discount "
            "re-engagement campaign limited to their favourite categories, "
            "reach them before the low-promo winter quarter, and cap the "
            "discount at repeat-purchase basket value."
        ),
    },
    "Hibernating": {
        "color": SLATE,
        "icon": "❄️",
        "recommendation": (
            "Inactive for more than a quarter with small baskets. Do not "
            "spend paid media here; use free channels (email/sms) with "
            "wide assortments and entry-level free-shipping thresholds. "
            "Fight only for the profitable ones."
        ),
    },
    "Lost": {
        "color": RED,
        "icon": "🚫",
        "recommendation": (
            "No return signal and low spend. Keep only automated brand "
            "presence (newsletters); otherwise the LTV:CAC math fails on "
            "margin. Reallocate that budget to Potential Loyalists."
        ),
    },
}

SEGMENT_ORDER = ["Champions", "Loyal Customers", "Potential Loyalists",
                 "At-Risk", "Hibernating", "Lost"]

# ---------------------------------------------------------------- CSS
CUSTOM_CSS = f"""
<style>
    html, body {{ background: {BG}; }}

    /* ---- app surfaces ---- */
    .stApp {{ background: {BG}; }}
    section.main > div.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1240px; }}
    .stApp header {{ background: transparent; }}

    /* ---- base typography ---- */
    html, body, [class*="css"], .stMarkdown {{
        color: {TEXT};
        font-family: "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    }}
    h1, h2, h3 {{ font-family: Georgia, "Times New Roman", serif; letter-spacing: .01em; }}
    .stApp a {{ color: {PRIMARY}; }}

    /* ---- gold hairline dividers ---- */
    .stApp hr, .stApp .stDivider {{
        border: none; height: 1px;
        background: linear-gradient(90deg, transparent, {PRIMARY_DARK}66, transparent);
    }}

    /* ---- KPI cards ---- */
    .kpi-card {{
        background: linear-gradient(160deg, {BG_RAISED} 0%, {BG_SOFT} 70%);
        border: 1px solid {BORDER};
        border-top: 2px solid {PRIMARY};
        border-radius: 12px;
        padding: 16px 20px 13px 20px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.45);
        height: 100%;
    }}
    .kpi-title {{
        font-size: 0.74rem; letter-spacing: 0.14em; text-transform: uppercase;
        color: {TEXT_MUTED}; font-weight: 600; margin-bottom: 5px;
    }}
    .kpi-value {{
        font-family: Georgia, "Times New Roman", serif;
        font-size: 1.8rem; font-weight: 700; line-height: 1.12;
    }}
    .kpi-delta {{ font-size: 0.82rem; margin-top: 6px; color: {TEXT_MUTED}; }}
    .kpi-up    {{ color: {PRIMARY}; font-weight: 700; }}
    .kpi-down  {{ color: {RED}; font-weight: 700; }}

    /* ---- hero banner ---- */
    .hero {{
        background:
            radial-gradient(1200px 240px at -10% -80%, {GOLD_GLOW}22, transparent),
            linear-gradient(135deg, {BG_RAISED} 0%, {BG} 60%, {PRIMARY_DEEP} 160%);
        border: 1px solid {PRIMARY_DARK};
        border-left: 5px solid {PRIMARY};
        border-radius: 14px;
        padding: 26px 30px; margin-bottom: 20px;
        box-shadow: 0 6px 28px rgba(0,0,0,0.5);
    }}
    .hero h1 {{
        font-size: 2.25rem; font-weight: 700; margin: 0 0 8px 0; color: {TEXT};
        font-family: Georgia, "Times New Roman", serif;
    }}
    .hero p  {{ color: {TEXT_MUTED}; margin: 0; font-size: 1.02rem; }}
    .kicker {{
        font-size: 0.7rem; letter-spacing: 0.22em; text-transform: uppercase;
        color: {PRIMARY}; font-weight: 700; margin-bottom: 4px;
    }}

    /* ---- top nav tabs (moved out of the sidebar) ---- */
    .navtabs {{
        display: flex; flex-wrap: wrap; gap: 8px;
        margin: 2px 0 16px 0; padding: 5px;
        background: {BG_SOFT}; border: 1px solid {BORDER}; border-radius: 12px;
        width: fit-content;
    }}
    a.navtab {{
        display: inline-block; text-decoration: none;
        font-size: 0.86rem; font-weight: 600; letter-spacing: .02em;
        color: {TEXT}; background: transparent;
        border: 1px solid transparent; border-radius: 9px;
        padding: 7px 15px; transition: all .15s ease;
    }}
    a.navtab:hover {{ border-color: {PRIMARY_DARK}; color: {PRIMARY}; }}
    a.navtab.active {{
        background: linear-gradient(180deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        color: {BG}; font-weight: 700;
        box-shadow: 0 2px 10px {GOLD_GLOW};
    }}

    /* ---- buttons ---- */
    div[data-testid="stButton"] > button {{
        border-radius: 9px;
        border: 1px solid {PRIMARY_DARK};
        background: linear-gradient(180deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        color: {BG}; font-weight: 700;
        margin-top: 24px;
        transition: all .15s ease;
        box-shadow: 0 2px 12px {GOLD_GLOW};
    }}
    div[data-testid="stButton"] > button:hover {{
        background: {PRIMARY_DEEP}; border-color: {PRIMARY}; color: {PRIMARY};
        box-shadow: 0 2px 16px {GOLD_GLOW};
    }}
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: {BG_RAISED}; color: {TEXT}; border-color: {BORDER}; box-shadow: none;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        border-color: {PRIMARY_DARK}; color: {PRIMARY}; background: {BG_RAISED};
    }}

    /* ---- nav cards on home ---- */
    a.nav-anch {{ text-decoration: none; display: block; margin-bottom: 12px; }}
    .nav-card {{
        border: 1px solid {BORDER};
        border-top: 3px solid var(--nav);
        border-radius: 12px;
        background: linear-gradient(160deg, {BG_RAISED} 0%, {BG_SOFT} 70%);
        padding: 18px;
        height: 100%;
        transition: all .15s ease;
    }}
    a.nav-anch:hover .nav-card {{
        background: {PRIMARY_DEEP}; border-color: {PRIMARY_DARK};
        transform: translateY(-2px);
        box-shadow: 0 6px 22px rgba(0,0,0,0.55);
    }}
    .nav-card .icon {{ font-size: 1.6rem; }}
    .nav-card .nav-label {{
        font-family: Georgia, "Times New Roman", serif;
        font-weight: 700; font-size: 1.05rem; color: {TEXT}; margin-top: 5px;
    }}
    a.nav-anch:hover .nav-label {{ color: {PRIMARY}; }}
    .nav-card .nav-sub {{ font-size: 0.83rem; color: {TEXT_MUTED}; margin-top: 3px; }}

    /* ---- segment recommendation cards ---- */
    .seg-card {{
        border: 1px solid {BORDER}; border-left: 5px solid var(--seg);
        border-radius: 12px; padding: 14px 16px;
        background: linear-gradient(160deg, {BG_RAISED} 0%, {BG_SOFT} 70%);
        height: 100%;
    }}
    .seg-head {{ font-weight: 700; font-size: 1rem; color: {TEXT}; }}
    .seg-stat {{ color: {TEXT_MUTED}; font-size: 0.86rem; margin: 2px 0 8px 0; }}
    .seg-body {{ font-size: 0.92rem; }}

    /* ---- sidebar ---- */
    section[data-testid="stSidebar"] {{
        background: {BG_SOFT};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] .sidebar-logo {{
        padding: 18px 10px 4px 10px;
    }}
    section[data-testid="stSidebar"] .sidebar-logo .logo-mark {{
        display: inline-flex; align-items: center; justify-content: center;
        width: 36px; height: 36px; border-radius: 9px;
        background: linear-gradient(180deg, {PRIMARY}, {PRIMARY_DARK});
        color: {BG}; font-weight: 800; font-size: 1.05rem; margin-right: 8px;
        box-shadow: 0 2px 10px {GOLD_GLOW};
    }}
    section[data-testid="stSidebar"] .sidebar-logo .logo-text {{
        font-family: Georgia, "Times New Roman", serif;
        font-weight: 700; font-size: 1.16rem; color: {PRIMARY};
    }}
    section[data-testid="stSidebar"] .sidebar-dim {{
        color: {TEXT_MUTED}; font-size: 0.8rem; padding: 6px 12px;
    }}

    /* ---- widgets ---- */
    .stApp [data-testid="stExpander"] {{
        background: {BG_SOFT}; border: 1px solid {BORDER} !important; border-radius: 12px;
    }}
    .stApp [data-testid="stExpander"] details {{ background: transparent; }}
    .stApp [data-testid="stToggle"] span[data-testid="stMarkdownContainer"] {{ color: {TEXT}; }}
    .stApp label, .stApp [data-testid="stWidgetLabel"] p {{ color: {TEXT_MUTED} !important; }}
    .stApp .stCaption, .stApp [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED}; }}
    .stApp .stCaption b {{ color: {PRIMARY}; }}
    .stApp [data-testid="stAlert"] {{
        background: {BG_RAISED}; border: 1px solid {BORDER}; border-left: 4px solid {PRIMARY};
        border-radius: 10px; color: {TEXT};
    }}
    .stApp [data-testid="stDownloadButton"] > button {{
        border-radius: 9px; border: 1px dashed {PRIMARY_DARK};
        background: {BG_RAISED}; color: {PRIMARY}; font-weight: 600; margin-top: 24px;
    }}
    .stApp [data-testid="stDownloadButton"] > button:hover {{
        background: {PRIMARY_DEEP}; border-color: {PRIMARY}; color: {PRIMARY};
    }}
    .stApp [data-testid="stDateInput"], .stApp [data-testid="stSelectbox"],
    .stApp [data-testid="stTextInput"] {{
        color: {TEXT};
    }}
    .stApp input, .stApp [data-baseweb="input"] {{
        background-color: {BG_RAISED} !important;
        border-color: {BORDER} !important; color: {TEXT} !important;
    }}
    .stPlotlyChart {{ border-radius: 12px; }}

    /* ---- tables ---- */
    .stApp [data-testid="stDataFrame"] {{
        border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden;
    }}
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# static URL slugs for the multipage app (robust to page-registry quirks)
PAGE_URLS = {
    "home": "/",
    "Executive_Summary": "/Executive_Summary",
    "Cohort_Retention": "/Cohort_Retention",
    "Customer_Segments": "/Customer_Segments",
    "Category_Insights": "/Category_Insights",
}

NAV_TABS = [
    ("home", "🏠", "Home"),
    ("Executive_Summary", "📊", "Executive Summary"),
    ("Cohort_Retention", "📈", "Cohort Retention"),
    ("Customer_Segments", "👥", "Customer Segments"),
    ("Category_Insights", "🛍️", "Category Insights"),
]


def render_nav_tabs(active: str = "home") -> str:
    """Horizontal gold/black tab strip rendered at the top of the main area."""
    tabs = []
    for slug, icon, label in NAV_TABS:
        cls = "navtab active" if slug == active else "navtab"
        tabs.append(f'<a class="{cls}" href="{PAGE_URLS[slug]}" target="_self">{icon} {label}</a>')
    return '<div class="navtabs">' + "".join(tabs) + "</div>"


# kept for backward compatibility (no longer used by pages)
HOME_BTN = ('<a class="page-btn" href="/" target="_self">🏠 Home</a>')


def page_button(slug: str, label: str, icon: str = "🏠", secondary: bool = False) -> str:
    """A styled HTML anchor that navigates between app pages."""
    cls = "navtab active" if slug == "home" else "navtab"
    return f'<a class="{cls}" href="{PAGE_URLS[slug]}" target="_self">{icon} {label}</a>'


# ---------------------------------------------------------------- KPI card
def kpi_card(title, value, delta_note="", color=PRIMARY, delta_positive=None):
    """A styled KPI card. delta_positive=None renders the note neutral."""
    if delta_note and delta_positive is not None:
        cls = "kpi-up" if delta_positive else "kpi-down"
        arrow = "▲" if delta_positive else "▼"
        note = f'<div class="kpi-delta"><span class="{cls}">{arrow} {delta_note}</span></div>'
    elif delta_note:
        note = f'<div class="kpi-delta">{delta_note}</div>'
    else:
        note = ""
    return (
        f'<div class="kpi-card" style="border-top-color:{color}">'
        f'<div class="kpi-title">{title}</div>'
        f'<div class="kpi-value" style="color:{color}">{value}</div>'
        f"{note}</div>"
    )


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading analysis exports ...")
def load_csv(name) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name)


def fmt_money(v, compact=True):
    """Brazilian-real-first, human-first formatting."""
    sign = "-" if v < 0 else ""
    v = abs(float(v))
    if compact and v >= 1_000_000_000:
        return f"{sign}R${v / 1e9:.2f}B"
    if compact and v >= 1_000_000:
        return f"{sign}R${v / 1e6:.2f}M"
    if compact and v >= 10_000:
        return f"{sign}R${v / 1e3:.1f}k"
    return f"{sign}R${v:,.2f}"


def fmt_num(v):
    return f"{int(v):,}".replace(",", ".")


def fmt_pct(v, decimals=1):
    return f"{float(v):,.{decimals}f}%"
