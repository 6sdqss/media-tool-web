# -*- coding: utf-8 -*-
"""
app.py — Media Tool Pro VIP v10.0
─────────────────────────────────────────────────────────
v10.0 UPGRADE: Modern White Professional UI
- Giao diện chuyển sang Light / White Professional (Canva/Figma style)
- Studio CSS hoàn toàn mới: dynamic canvas, realtime preview, no flickering
- Mọi logic backend, auth, routing GIỮ NGUYÊN 100%
"""

from __future__ import annotations

import streamlit as st

from auth import (
    authenticate,
    change_own_password,
    has_permission,
    register_user,
)
from admin_panel import render_admin_panel

from utils import (
    EXPORT_FORMATS,
    SIZE_PRESETS,
    init_app_state,
    render_history_sidebar,
    render_session_stats,
    get_gdrive_service,
)

_err_web = _err_adjust = _err_drive = _err_local = None

try:
    from mode_web import run_mode_web
except Exception as e:
    run_mode_web = None
    _err_web = str(e)

try:
    from mode_adjust import render_adjustment_studio
except Exception as e:
    render_adjustment_studio = None
    _err_adjust = str(e)

try:
    from mode_drive import run_mode_drive
except Exception as e:
    run_mode_drive = None
    _err_drive = str(e)

try:
    from mode_local import run_mode_local
except Exception as e:
    run_mode_local = None
    _err_local = str(e)


# ══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Media Tool Pro VIP",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════
# CSS — v10.0 MODERN WHITE PROFESSIONAL
# ══════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════
   MEDIA TOOL PRO VIP — Design System v10.1
   Inspired by: Linear, Notion, Stripe, Vercel Dashboard
   ══════════════════════════════════════════════════════════════

   COLOR TOKENS
   --color-bg:         #f5f7fb   workspace background
   --color-surface:    #ffffff   cards, panels
   --color-border:     #e4e8ef   default border
   --color-border-2:   #d1d9e6   stronger border
   --color-text-1:     #0f172a   headings
   --color-text-2:     #374151   body
   --color-text-3:     #64748b   secondary
   --color-text-4:     #94a3b8   muted / placeholder
   --color-primary:    #5b5ef4   indigo primary
   --color-primary-h:  #4a4dd4   hover
   --color-primary-bg: #eef0fe   light tint
   --color-success:    #0ea372   green
   --color-warn:       #d97706   amber
   --color-error:      #dc2626   red
   ══════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&display=swap');

/* ─── HIDE STREAMLIT CHROME ─────────────────────────────────── */
#MainMenu, header, footer, .stDeployButton,
[data-testid="stToolbar"] {
    visibility: hidden !important;
    display: none !important;
}

/* ─── ROOT ───────────────────────────────────────────────────── */
:root {
    --c-bg:        #f5f7fb;
    --c-surface:   #ffffff;
    --c-border:    #e4e8ef;
    --c-border2:   #c7d2e2;
    --c-text-1:    #0f172a;
    --c-text-2:    #374151;
    --c-text-3:    #64748b;
    --c-text-4:    #94a3b8;
    --c-primary:   #5b5ef4;
    --c-primary-d: #4a4dd4;
    --c-primary-l: #eef0fe;
    --c-primary-m: #c7c9fc;
    --c-success:   #0ea372;
    --c-success-l: #d1fae5;
    --c-warn:      #d97706;
    --c-warn-l:    #fef3c7;
    --c-error:     #dc2626;
    --c-error-l:   #fee2e2;
    --shadow-xs:   0 1px 2px rgba(15,23,42,.06);
    --shadow-sm:   0 1px 3px rgba(15,23,42,.08), 0 4px 12px rgba(15,23,42,.04);
    --shadow-md:   0 4px 8px rgba(15,23,42,.08), 0 12px 24px rgba(15,23,42,.06);
    --shadow-lg:   0 8px 16px rgba(15,23,42,.10), 0 24px 48px rgba(15,23,42,.08);
    --radius-sm:   6px;
    --radius-md:   10px;
    --radius-lg:   14px;
    --radius-xl:   18px;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    -webkit-font-smoothing: antialiased !important;
    text-rendering: optimizeLegibility !important;
    color: var(--c-text-2) !important;
}

/* ─── WORKSPACE BACKGROUND ───────────────────────────────────── */
.stApp {
    background-color: var(--c-bg) !important;
    background-image:
        radial-gradient(circle at 20% 0%, rgba(91,94,244,.055) 0%, transparent 50%),
        radial-gradient(circle at 80% 100%, rgba(91,94,244,.04) 0%, transparent 45%) !important;
}

/* ─── MAIN CONTAINER ─────────────────────────────────────────── */
.block-container {
    max-width: 1080px !important;
    padding: 1.5rem 1.5rem 3rem !important;
}
@media (max-width: 768px) {
    .block-container { max-width: 100% !important; padding: .75rem .75rem 2rem !important; }
}
@media (min-width: 641px) and (max-width: 1024px) {
    .block-container { max-width: 960px !important; }
}

/* ─── SIDEBAR ────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: var(--c-surface) !important;
    border-right: 1px solid var(--c-border) !important;
    box-shadow: 2px 0 12px rgba(15,23,42,.05) !important;
    width: 256px !important;
}
section[data-testid="stSidebar"] > div { padding-top: .75rem !important; }
section[data-testid="stSidebar"] * {
    color: var(--c-text-2) !important;
    font-size: 13.5px !important;
}
section[data-testid="stSidebar"] hr {
    border-color: var(--c-border) !important;
    margin: 10px 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: var(--c-bg) !important;
    border: 1px solid var(--c-border) !important;
    border-radius: var(--radius-md) !important;
}
section[data-testid="stSidebar"] .stButton button {
    font-size: 13px !important;
    min-height: 34px !important;
    padding: 4px 10px !important;
}

/* ─── APP HEADER ─────────────────────────────────────────────── */
.app-header {
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-lg);
    padding: 18px 24px;
    margin-bottom: 20px;
    box-shadow: var(--shadow-sm);
    display: flex;
    align-items: center;
    gap: 16px;
}
.app-header-icon {
    flex-shrink: 0;
    width: 44px; height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #5b5ef4 0%, #818cf8 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem;
    box-shadow: 0 4px 12px rgba(91,94,244,.3);
}
.app-header-body { flex: 1; min-width: 0; }
.app-header h1 {
    margin: 0 0 2px;
    font-size: 1.15rem !important;
    font-weight: 800 !important;
    color: var(--c-text-1) !important;
    letter-spacing: -.3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.app-header p {
    margin: 0;
    font-size: .78rem;
    color: var(--c-text-4);
    font-weight: 400;
    display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.app-header-badge {
    display: inline-flex; align-items: center;
    background: var(--c-primary-l);
    color: var(--c-primary);
    font-size: .68rem; font-weight: 700;
    padding: 1px 7px; border-radius: 999px;
    border: 1px solid var(--c-primary-m);
    letter-spacing: .2px;
}

/* ─── HERO CARD ──────────────────────────────────────────────── */
.hero-card {
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-md);
    padding: 16px 20px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-xs);
    border-left: 4px solid var(--c-primary);
}
.hero-card h2 {
    margin: 0 0 5px;
    color: var(--c-text-1) !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    letter-spacing: -.2px;
}
.hero-card p { margin: 0; color: var(--c-text-3); font-size: .88rem; line-height: 1.7; }
.hero-card b { color: var(--c-text-2); font-weight: 600; }

/* ─── CARDS / BORDERED CONTAINERS ───────────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--c-border) !important;
    padding: 16px !important;
    background: var(--c-surface) !important;
    box-shadow: var(--shadow-xs) !important;
    transition: box-shadow .18s, border-color .18s !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: var(--shadow-sm) !important;
}

/* ─── SECTION TITLES ─────────────────────────────────────────── */
.sec-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: .72rem !important;
    font-weight: 700 !important;
    color: var(--c-text-3) !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 20px 0 10px !important;
    padding: 0;
}
.sec-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--c-border);
}
.cfg-label {
    font-size: .82rem !important;
    font-weight: 600 !important;
    color: var(--c-text-2) !important;
    margin-bottom: 6px !important;
    margin-top: 4px !important;
}
.tpl-hint { font-size: .74rem; color: var(--c-text-4); margin-top: 4px; }
.tpl-hint code {
    background: var(--c-primary-l);
    color: var(--c-primary);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-size: .7rem;
    font-weight: 600;
}

/* ─── GUIDE BOX ──────────────────────────────────────────────── */
.guide-box {
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    font-size: .86rem;
    color: var(--c-text-3);
    margin-bottom: 12px;
    line-height: 1.7;
}
.guide-box b { color: var(--c-text-2); font-weight: 600; }

/* ─── LOG BOX ────────────────────────────────────────────────── */
.log-box {
    background: #0d1117 !important;
    color: #4ade80 !important;
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace !important;
    font-size: .75rem !important;
    padding: 12px !important;
    border-radius: var(--radius-md) !important;
    max-height: 200px !important;
    overflow-y: auto !important;
    border: 1px solid rgba(74,222,128,.12) !important;
    line-height: 1.65 !important;
}

/* ─── SUMMARY CARD ───────────────────────────────────────────── */
.summary-card {
    background: linear-gradient(135deg, #f0fdf8 0%, #d1fae5 100%);
    border: 1px solid #6ee7b7;
    border-radius: var(--radius-md);
    padding: 14px 18px;
    margin: 10px 0;
    font-size: .9rem;
    line-height: 1.7;
    color: #065f46;
}
.summary-card b { color: #047857; }

/* ─── PREVIEW META ───────────────────────────────────────────── */
.preview-meta {
    text-align: center;
    font-size: .75rem;
    color: var(--c-text-4);
    margin-top: 5px;
    line-height: 1.5;
}

/* ─── BUTTONS ────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button {
    background: linear-gradient(135deg, #5b5ef4 0%, #818cf8 100%) !important;
    color: #fff !important;
    border-radius: var(--radius-sm) !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    min-height: 36px !important;
    padding: 6px 16px !important;
    box-shadow: 0 1px 3px rgba(91,94,244,.3), inset 0 1px 0 rgba(255,255,255,.1) !important;
    transition: all .15s cubic-bezier(.4,.7,.2,1) !important;
    letter-spacing: .1px;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: linear-gradient(135deg, #4a4dd4 0%, #6366f1 100%) !important;
    box-shadow: 0 4px 12px rgba(91,94,244,.35) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) !important; }
.stButton > button:focus-visible {
    outline: 2px solid var(--c-primary) !important;
    outline-offset: 2px !important;
}
button[kind="secondary"] {
    background: var(--c-surface) !important;
    color: var(--c-text-2) !important;
    border: 1px solid var(--c-border2) !important;
    box-shadow: var(--shadow-xs) !important;
    font-weight: 500 !important;
}
button[kind="secondary"]:hover {
    background: var(--c-bg) !important;
    border-color: var(--c-text-4) !important;
}
.stButton > button:disabled, .stDownloadButton > button:disabled {
    background: var(--c-bg) !important;
    color: var(--c-text-4) !important;
    border: 1px solid var(--c-border) !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
    transform: none !important;
}

/* ─── INPUTS ─────────────────────────────────────────────────── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
    background: var(--c-surface) !important;
    border: 1.5px solid var(--c-border2) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--c-text-1) !important;
    font-size: 14px !important;
    min-height: 38px !important;
    padding: 8px 12px !important;
    transition: border-color .15s, box-shadow .15s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    border-color: var(--c-primary) !important;
    box-shadow: 0 0 0 3px rgba(91,94,244,.12) !important;
    outline: none !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
    color: var(--c-text-4) !important;
    font-weight: 400 !important;
}
.stTextArea textarea { min-height: 80px !important; }
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {
    background: var(--c-surface) !important;
    border: 1.5px solid var(--c-border2) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--c-text-1) !important;
    font-size: 13.5px !important;
    min-height: 38px !important;
}

/* ─── LABELS ─────────────────────────────────────────────────── */
.stTextInput label, .stTextArea label, .stSelectbox label,
.stNumberInput label, .stSlider label, .stMultiSelect label,
.stRadio label, .stCheckbox label, .stToggle label {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--c-text-2) !important;
    letter-spacing: .1px;
}

/* ─── SLIDERS ────────────────────────────────────────────────── */
.stSlider [data-baseweb="slider"] > div > div {
    background: linear-gradient(90deg, var(--c-primary), #818cf8) !important;
    height: 4px !important;
    border-radius: 2px !important;
}
.stSlider [role="slider"] {
    background: var(--c-surface) !important;
    border: 2px solid var(--c-primary) !important;
    box-shadow: 0 1px 4px rgba(91,94,244,.35) !important;
    width: 16px !important; height: 16px !important;
    transition: transform .1s, box-shadow .1s !important;
}
.stSlider [role="slider"]:hover {
    transform: scale(1.2) !important;
    box-shadow: 0 2px 8px rgba(91,94,244,.4) !important;
}
.stSlider [data-testid="stTickBarMin"],
.stSlider [data-testid="stTickBarMax"] {
    font-size: .72rem !important;
    color: var(--c-text-4) !important;
}

/* ─── TABS ───────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px !important;
    background: var(--c-bg) !important;
    border-radius: var(--radius-md) !important;
    padding: 4px !important;
    overflow-x: auto;
    flex-wrap: nowrap !important;
    border: 1px solid var(--c-border) !important;
}
.stTabs [data-baseweb="tab"] {
    height: 34px !important;
    padding: 0 14px !important;
    border-radius: var(--radius-sm) !important;
    color: var(--c-text-3) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    white-space: nowrap !important;
    background: transparent !important;
    border: none !important;
    transition: all .15s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--c-text-2) !important; background: var(--c-surface) !important; }
.stTabs [aria-selected="true"] {
    background: var(--c-surface) !important;
    color: var(--c-primary) !important;
    box-shadow: var(--shadow-xs) !important;
    font-weight: 600 !important;
}

/* ─── EXPANDER ───────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--c-surface) !important;
    border: 1px solid var(--c-border) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-xs) !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-size: 13.5px !important;
    font-weight: 600 !important;
    color: var(--c-text-2) !important;
    padding: 10px 16px !important;
}
[data-testid="stExpander"] summary:hover { background: var(--c-bg) !important; }

/* ─── METRICS ────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    padding: 12px 14px !important;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-xs);
    transition: box-shadow .15s !important;
}
[data-testid="stMetric"]:hover { box-shadow: var(--shadow-sm) !important; }
[data-testid="stMetricLabel"] {
    font-size: .74rem !important;
    font-weight: 500 !important;
    color: var(--c-text-4) !important;
    text-transform: uppercase;
    letter-spacing: .6px;
}
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 800 !important;
    color: var(--c-text-1) !important;
    letter-spacing: -.3px;
}

/* ─── ALERTS ─────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius-md) !important;
    padding: 12px 16px !important;
    font-size: 13.5px !important;
    border-width: 1px !important;
}

/* ─── CAPTION ────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: .78rem !important;
    color: var(--c-text-4) !important;
    line-height: 1.5 !important;
}

/* ─── PROGRESS BAR ───────────────────────────────────────────── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, var(--c-primary) 0%, #818cf8 100%) !important;
    border-radius: 2px !important;
}
.stProgress > div > div { height: 5px !important; background: var(--c-border) !important; border-radius: 2px !important; }

/* ─── CHECKBOX & TOGGLE ──────────────────────────────────────── */
.stCheckbox label, .stToggle label { font-size: 13.5px !important; color: var(--c-text-2) !important; }
.stCheckbox [data-testid="stCheckbox"] span {
    border-color: var(--c-border2) !important;
    border-radius: 4px !important;
}

/* ─── SPINNER ────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: var(--c-primary) !important; }

/* ─── SCROLLBAR ──────────────────────────────────────────────── */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--c-border2); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--c-text-4); }

/* ─── DIVIDER ────────────────────────────────────────────────── */
hr { border: none !important; border-top: 1px solid var(--c-border) !important; margin: 14px 0 !important; }

/* ─── MOBILE ─────────────────────────────────────────────────── */
@media (max-width: 640px) {
    .app-header h1 { font-size: 1rem !important; }
    .stTabs [data-baseweb="tab-list"] {
        position: sticky; top: 0; z-index: 99;
        background: rgba(245,247,251,.97) !important;
        backdrop-filter: blur(12px);
    }
    .stTabs [data-baseweb="tab"] { padding: 0 11px !important; font-size: 12.5px !important; }
    .login-shell { padding: 0 12px; }
    section[data-testid="stSidebar"] { width: 88vw !important; }
    .block-container { padding: .5rem !important; }
}

/* ─── LOGIN ──────────────────────────────────────────────────── */
.login-shell { max-width: 400px; margin: 3.5rem auto 0; }
.login-card {
    background: var(--c-surface);
    border-radius: var(--radius-xl);
    padding: 32px 32px 24px;
    border: 1px solid var(--c-border);
    box-shadow: var(--shadow-lg);
}
.login-brand {
    width: 56px; height: 56px;
    border-radius: var(--radius-lg);
    margin: 0 auto 16px;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #5b5ef4 0%, #818cf8 100%);
    color: #fff; font-size: 1.5rem;
    box-shadow: 0 8px 24px rgba(91,94,244,.3);
}
.login-title { text-align: center; color: var(--c-text-1) !important; font-weight: 800; font-size: 1.25rem; margin: 0; }
.login-sub { text-align: center; color: var(--c-text-4); margin: 5px 0 20px; font-size: .82rem; }

/* ─── USER CHIP ──────────────────────────────────────────────── */
.user-chip {
    background: var(--c-primary-l);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    border: 1px solid var(--c-primary-m);
    margin-bottom: 8px;
}
.user-chip b { color: var(--c-text-1) !important; font-size: .95rem !important; font-weight: 700 !important; }
.user-chip span { color: var(--c-primary) !important; font-size: .75rem !important; font-weight: 500 !important; }

/* ─── SIDEBAR LOGO — New Modern Branding ─────────────────────── */
.sb-logo-wrap { text-align: center; padding: 8px 0 4px; }
.sb-logo-icon {
    width: 48px; height: 48px;
    margin: 0 auto 10px;
    border-radius: 14px;
    background: linear-gradient(135deg, #5b5ef4 0%, #818cf8 100%);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 16px rgba(91,94,244,.28);
    position: relative; overflow: hidden;
}
.sb-logo-icon::before {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(circle at 30% 30%, rgba(255,255,255,.2) 0%, transparent 60%);
}
.sb-logo-icon svg { position: relative; z-index: 1; }
.sb-logo-title {
    font-weight: 800 !important;
    font-size: .92rem !important;
    color: var(--c-text-1) !important;
    letter-spacing: -.2px;
}
.sb-logo-sub { font-size: .7rem !important; color: var(--c-primary) !important; margin-top: 2px; font-weight: 500 !important; }

/* ─── HISTORY ITEM ───────────────────────────────────────────── */
.history-item { padding: 7px 0; border-bottom: 1px solid var(--c-bg); }
.hi-top { font-size: .8rem !important; color: var(--c-text-2) !important; margin-bottom: 1px; font-weight: 500; }
.hi-top b { color: var(--c-text-1) !important; }
.hi-bot { font-size: .72rem !important; color: var(--c-text-4) !important; }

/* ─── STAT PILLS ─────────────────────────────────────────────── */
.stat-row { display: flex; gap: 5px; margin: 5px 0 7px; }
.stat-pill { flex: 1; border-radius: var(--radius-sm); padding: 8px 4px; text-align: center; border: 1px solid var(--c-border); }
.stat-a { background: var(--c-primary-l); border-color: var(--c-primary-m); }
.stat-b { background: #d1fae5; border-color: #6ee7b7; }
.stat-c { background: #fef3c7; border-color: #fcd34d; }
.sp-num { font-size: .95rem !important; font-weight: 800 !important; }
.stat-a .sp-num { color: var(--c-primary) !important; }
.stat-b .sp-num { color: var(--c-success) !important; }
.stat-c .sp-num { color: var(--c-warn) !important; }
.sp-lbl { font-size: .62rem !important; color: var(--c-text-4) !important; text-transform: uppercase; letter-spacing: .5px; margin-top: 1px; display: block; }

/* ─── CTRL ROW ───────────────────────────────────────────────── */
.ctrl-row {
    background: var(--c-bg); border-radius: var(--radius-md);
    padding: 8px; margin: 8px 0; border: 1px solid var(--c-border);
}

/* ─── APP TAB NAV (radio-as-tabs) ────────────────────────────── */
div[data-testid="stRadio"][aria-label="_app_tab_nav"] > div[role="radiogroup"],
.app-tab-nav div[role="radiogroup"] {
    gap: 3px !important;
    background: var(--c-bg) !important;
    border-radius: var(--radius-md) !important;
    padding: 5px !important;
    flex-wrap: wrap !important;
    border: 1px solid var(--c-border) !important;
    margin-bottom: 16px !important;
}
.app-tab-nav label {
    background: transparent !important;
    color: var(--c-text-3) !important;
    padding: 8px 16px !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-size: 13.5px !important;
    cursor: pointer !important;
    transition: all .15s ease !important;
    margin: 0 !important;
    border: 1px solid transparent !important;
}
.app-tab-nav label:hover { background: var(--c-surface) !important; color: var(--c-text-2) !important; }
.app-tab-nav label > div:first-child { display: none !important; }
.app-tab-nav label:has(input:checked) {
    background: var(--c-surface) !important;
    color: var(--c-primary) !important;
    border-color: var(--c-border) !important;
    box-shadow: var(--shadow-xs) !important;
    font-weight: 600 !important;
}

/* ─── CHECKBOX SELECTED CARD HIGHLIGHT ───────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(input[type="checkbox"]:checked) {
    border-color: var(--c-primary) !important;
    box-shadow: 0 0 0 2px rgba(91,94,244,.1), var(--shadow-sm) !important;
}

/* ══════════════════════════════════════════════════════════════
   STUDIO TAB — Professional Editor UI
   ══════════════════════════════════════════════════════════════ */
.studio-wrap { font-size: 14px !important; }
.studio-wrap .stTextInput label,
.studio-wrap .stSelectbox label,
.studio-wrap .stNumberInput label,
.studio-wrap .stSlider label,
.studio-wrap .stCheckbox label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--c-text-2) !important;
}
.studio-wrap .stButton > button { min-height: 38px !important; font-size: 13.5px !important; }
.studio-wrap div[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 18px !important;
    margin-bottom: 14px !important;
}
@media (min-width: 1200px) {
    .studio-wrap .block-container { max-width: 1400px !important; }
}

/* ─── CANVAS WORKSPACE ───────────────────────────────────────── */
.canvas-workspace {
    background: #f8fafc;
    border-radius: var(--radius-md);
    padding: 12px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--c-border);
    position: relative;
    min-height: 100px;
}

/* ─── LIVE PREVIEW FRAME — Dynamic aspect ratio ──────────────── */
.live-frame {
    position: relative;
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
    background: #ffffff;
    border: 1.5px solid var(--c-border2);
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-md);
    /* aspect-ratio set inline per output size */
}
.live-frame::after {
    content: 'PREVIEW';
    position: absolute; bottom: 0; right: 0;
    font-size: .58rem; font-weight: 700;
    color: var(--c-text-4); background: rgba(245,247,251,.9);
    padding: 2px 7px; border-radius: var(--radius-sm) 0 0 0;
    letter-spacing: .8px; pointer-events: none; z-index: 5;
}
.live-frame--empty {
    display: flex; align-items: center; justify-content: center;
    aspect-ratio: 3/2; color: var(--c-error); font-size: .9rem;
    background: var(--c-error-l); border-color: #fca5a5;
}
.live-canvas {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden; background: #ffffff;
}
.live-img {
    width: 100%; height: 100%;
    object-fit: contain; object-position: center;
    transform-origin: center center;
    transition: transform .1s cubic-bezier(.4,.7,.2,1);
    will-change: transform;
    user-select: none; -webkit-user-drag: none;
    image-rendering: -webkit-optimize-contrast;
}
.live-overlay {
    position: absolute; bottom: 0; left: 0; right: 0;
    display: flex; flex-wrap: wrap; gap: 4px 10px;
    padding: 5px 10px;
    background: linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(15,23,42,.38) 100%);
    color: #f8fafc; font-size: .72rem !important; font-weight: 600;
    z-index: 2; pointer-events: none;
}
.live-overlay span { white-space: nowrap; }

/* ─── RENDERED FRAME ─────────────────────────────────────────── */
.rendered-frame {
    background: #ffffff; border-radius: var(--radius-md);
    border: 1.5px solid #6ee7b7; overflow: hidden; padding: 4px;
    box-shadow: 0 2px 8px rgba(14,163,114,.1);
    position: relative;
}
.rendered-frame::after {
    content: '✓ RENDERED';
    position: absolute; top: 0; right: 0;
    font-size: .56rem; font-weight: 700;
    color: var(--c-success); background: #d1fae5;
    padding: 2px 7px; border-radius: 0 0 0 var(--radius-sm);
    letter-spacing: .5px; pointer-events: none; z-index: 5;
}
.rendered-frame img {
    max-width: 100%; max-height: 260px;
    object-fit: contain; display: block; margin: 0 auto;
    position: relative; z-index: 1;
}

/* ─── STATUS PILLS ───────────────────────────────────────────── */
.spill {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: .72rem; font-weight: 600;
    padding: 3px 9px; border-radius: 999px; white-space: nowrap;
}
.spill-r { background: var(--c-success-l); color: var(--c-success); border: 1px solid #6ee7b7; }
.spill-a { background: var(--c-warn-l); color: var(--c-warn); border: 1px solid #fcd34d; }
.spill-s { background: var(--c-bg); color: var(--c-text-3); border: 1px solid var(--c-border); }

/* ─── SIZE INFO PILLS ────────────────────────────────────────── */
.info-pills { display: flex; flex-wrap: wrap; gap: 4px; margin: 5px 0; }
.info-pill {
    font-size: .72rem; color: var(--c-text-3);
    background: var(--c-bg); border: 1px solid var(--c-border);
    border-radius: var(--radius-sm); padding: 2px 8px; white-space: nowrap;
}
.info-pill b { color: var(--c-text-2); font-weight: 600; }
.size-info { font-size: .74rem; color: var(--c-text-4); margin-top: 4px; line-height: 1.6; }
.size-info.output { color: var(--c-success); font-weight: 600; }

/* ─── EXPORT PANEL ───────────────────────────────────────────── */
.export-panel {
    background: var(--c-surface); border: 1px solid var(--c-border);
    border-radius: var(--radius-lg); padding: 20px 24px;
    margin-top: 14px; box-shadow: var(--shadow-sm);
}
.export-panel h2 { margin: 0 0 6px; color: var(--c-text-1); font-size: 1.1rem; font-weight: 700; }
.export-panel p { color: var(--c-text-3); font-size: .88rem; margin: 0; }

/* ─── STUDIO IMG TITLE ───────────────────────────────────────── */
.studio-img-title { font-size: .95rem !important; margin-bottom: 8px !important; line-height: 1.55; }
.studio-img-title b { color: var(--c-text-1) !important; font-size: .95rem !important; font-weight: 700 !important; }
.studio-img-title code {
    font-size: .8rem !important; color: var(--c-primary) !important;
    background: var(--c-primary-l); padding: 2px 7px;
    border-radius: var(--radius-sm); word-break: break-all;
}

/* ─── STUDIO FRESH BANNER ────────────────────────────────────── */
.studio-fresh-banner {
    background: var(--c-success-l); border: 1px solid #6ee7b7;
    border-radius: var(--radius-md); padding: 12px 16px;
    margin: 6px 0 14px; font-size: .9rem; color: #065f46; font-weight: 600;
}

@media (max-width: 640px) {
    .live-frame { max-width: 100%; }
    .live-overlay { font-size: .68rem !important; padding: 4px 8px; }
}
</style>
""", unsafe_allow_html=True)




# ══════════════════════════════════════════════════════════════
# SESSION INIT
# ══════════════════════════════════════════════════════════════
init_app_state()


# ══════════════════════════════════════════════════════════════
# LOGIN / REGISTER — Logic giữ nguyên
# ══════════════════════════════════════════════════════════════
def render_login_screen():
    st.markdown("<div class='login-shell'>", unsafe_allow_html=True)
    st.markdown("""
        <div class="login-card">
            <div class="login-brand">&#128444;</div>
            <h1 class="login-title">Media Tool Pro VIP</h1>
            <p class="login-sub">v10.0 &middot; Secure Workspace</p>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐 Đăng nhập", "📝 Đăng ký"])

    with tab_login:
        username = st.text_input("Tài khoản", placeholder="Tên đăng nhập", key="login_user")
        password = st.text_input("Mật khẩu", type="password", placeholder="••••••••", key="login_pwd")
        if st.button("ĐĂNG NHẬP", type="primary", use_container_width=True, key="btn_login"):
            ok, msg, user_data = authenticate(username, password)
            if ok:
                st.session_state.logged_in  = True
                st.session_state.auth_user  = user_data
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab_register:
        st.caption("Tài khoản mới sẽ ở trạng thái **chờ Admin duyệt**.")
        new_user = st.text_input("Tài khoản mới", placeholder="≥ 3 ký tự (a-z, 0-9, _, -)", key="reg_user")
        new_pwd  = st.text_input("Mật khẩu", type="password", placeholder="≥ 4 ký tự", key="reg_pwd")
        new_pwd2 = st.text_input("Nhập lại mật khẩu", type="password", key="reg_pwd2")
        if st.button("ĐĂNG KÝ", type="primary", use_container_width=True, key="btn_register"):
            if new_pwd != new_pwd2:
                st.error("Hai lần nhập mật khẩu không khớp.")
            else:
                ok, msg = register_user(new_user, new_pwd)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.info("⏳ Liên hệ Admin (ducpro) để được duyệt.")

    st.markdown("</div>", unsafe_allow_html=True)


if not st.session_state.logged_in or not st.session_state.auth_user:
    render_login_screen()
    st.stop()


user     = st.session_state.auth_user
is_admin = user.get("role") == "admin"


# ══════════════════════════════════════════════════════════════
# SIDEBAR — Giữ nguyên logic
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
        <div class="sb-logo-wrap">
            <div class="sb-logo-icon">
                <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
                    <rect x="3" y="3" width="9" height="9" rx="2.5" fill="rgba(255,255,255,0.9)"/>
                    <rect x="14" y="3" width="9" height="9" rx="2.5" fill="rgba(255,255,255,0.6)"/>
                    <rect x="3" y="14" width="9" height="9" rx="2.5" fill="rgba(255,255,255,0.6)"/>
                    <rect x="14" y="14" width="9" height="9" rx="2.5" fill="rgba(255,255,255,0.35)"/>
                </svg>
            </div>
            <div class="sb-logo-title">Media Tool Pro VIP</div>
            <div class="sb-logo-sub">v10.1 &middot; Premium Studio</div>
        </div>
    """, unsafe_allow_html=True)
    st.divider()

    role_text = "👑 ADMIN" if is_admin else "👤 USER"
    perm_text = "all" if is_admin else f"{len(user.get('permissions', []))} quyền"
    st.markdown(f"""
        <div class="user-chip">
            <b>{user['username']}</b><br>
            <span>{role_text} &middot; {perm_text}</span>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("🔑 Đổi mật khẩu"):
        old_p = st.text_input("Mật khẩu cũ", type="password", key="cp_old")
        new_p = st.text_input("Mật khẩu mới", type="password", key="cp_new")
        if st.button("Đổi", use_container_width=True, key="cp_btn"):
            ok, msg = change_own_password(user["username"], old_p, new_p)
            (st.success if ok else st.error)(msg)

    st.divider()
    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()
    st.markdown("**📋 Lịch sử**")
    render_history_sidebar()
    st.divider()

    if st.button("🚪 ĐĂNG XUẤT", use_container_width=True, key="btn_logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown(f"""
    <div class="app-header">
        <div>
            <h1>Workspace &middot; {user['username']}</h1>
            <p>v10.1 · Premium SaaS UI · Dynamic Canvas · Auto-sync</p>
        </div>
    </div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# CONFIG PANEL — Logic giữ nguyên, UI làm sạch hơn
# ══════════════════════════════════════════════════════════════
def render_config_panel() -> dict:
    with st.expander("⚙️ CẤU HÌNH XỬ LÝ", expanded=False):
        st.markdown('<div class="cfg-label">📐 Kích thước xuất</div>', unsafe_allow_html=True)
        selected_labels = st.multiselect(
            "Sizes",
            list(SIZE_PRESETS.keys()),
            default=["1020×680 TGDD chuẩn"],
            label_visibility="collapsed",
            key="cfg_sizes",
        )

        custom_size_on = st.toggle("➕ Thêm kích thước tùy chỉnh", key="cfg_custom_on")
        custom_w, custom_h = 1200, 1200
        if custom_size_on:
            cw, ch = st.columns(2)
            custom_w = cw.number_input("Width",  100, 8000, 1200, 10, key="cfg_cw")
            custom_h = ch.number_input("Height", 100, 8000, 1200, 10, key="cfg_ch")

        st.markdown('<div class="cfg-label">🎛️ Output & hiệu năng</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            quality       = st.slider("Chất lượng", 60, 100, 95, 1, key="cfg_quality")
            export_format = st.selectbox("Định dạng", list(EXPORT_FORMATS.keys()), 0, key="cfg_format")
        with c2:
            default_scale_pct = st.slider("Scale (%)", 60, 200, 100, 1, key="cfg_scale")
            max_workers       = st.slider("Luồng xử lý", 1, 8, 4, 1, key="cfg_workers")

        st.markdown('<div class="cfg-label">✏️ Template tên & nén</div>', unsafe_allow_html=True)
        template = st.text_input(
            "Template",
            value="{name}_{color}_{nn}",
            placeholder="{name}_{color}_{nn}",
            label_visibility="collapsed",
            key="cfg_template",
        )
        st.markdown(
            "<div class='tpl-hint'>Biến: <code>{name}</code> <code>{color}</code> "
            "<code>{nn}</code> <code>{nnn}</code> <code>{original}</code></div>",
            unsafe_allow_html=True,
        )

        c3, c4 = st.columns(2)
        with c3:
            rename_enabled  = st.toggle("Sửa tên sau quét",  value=True, key="cfg_rename")
            huge_image_mode = st.toggle("Tối ưu ảnh lớn",    value=True, key="cfg_huge")
        with c4:
            zip_compression = st.slider("Nén ZIP", 0, 9, 6, 1, key="cfg_zip_compress")

    sizes_list = [SIZE_PRESETS[l] for l in selected_labels if l in SIZE_PRESETS]
    if custom_size_on:
        sizes_list.append((int(custom_w), int(custom_h), "letterbox"))
    if not sizes_list:
        sizes_list = [SIZE_PRESETS["1020×680 TGDD chuẩn"]]

    return {
        "sizes":              sizes_list,
        "default_scale_pct":  int(default_scale_pct),
        "scale_pct":          int(default_scale_pct),
        "quality":            int(quality),
        "export_format":      export_format,
        "template":           template or "{name}_{color}_{nn}",
        "rename":             bool(rename_enabled),
        "max_workers":        int(max_workers),
        "huge_image_mode":    bool(huge_image_mode),
        "zip_compression":    int(zip_compression),
    }


config = render_config_panel()


# ══════════════════════════════════════════════════════════════
# TABS — Routing giữ nguyên 100%
# ══════════════════════════════════════════════════════════════
tab_labels = []
tab_keys   = []

if has_permission(user, "web"):
    tab_labels.append("🛒 Web TGDD"); tab_keys.append("web")
if has_permission(user, "studio"):
    tab_labels.append("🎚 Studio");   tab_keys.append("studio")
if has_permission(user, "drive"):
    tab_labels.append("🌐 Drive");    tab_keys.append("drive")
if has_permission(user, "local"):
    tab_labels.append("💻 Local ZIP"); tab_keys.append("local")

tab_labels.append("📖 Hướng dẫn"); tab_keys.append("guide")
if is_admin:
    tab_labels.append("👑 Admin");    tab_keys.append("admin")

if not tab_keys or tab_keys == ["guide"]:
    st.warning("⚠️ Tài khoản chưa được cấp quyền. Liên hệ Admin để được duyệt.")

if "active_tab_key" not in st.session_state:
    st.session_state.active_tab_key = tab_keys[0] if tab_keys else "guide"

if st.session_state.pop("_goto_studio", False) and "studio" in tab_keys:
    st.session_state.active_tab_key  = "studio"
    st.session_state["_studio_just_arrived"] = True

if st.session_state.active_tab_key not in tab_keys:
    st.session_state.active_tab_key = tab_keys[0]

current_batch_id = st.session_state.get("last_batch_meta", {}).get("batch_id")
studio_has_new   = bool(current_batch_id) and (
    st.session_state.get("_studio_seen_batch_id") != current_batch_id
)

label_for_key = dict(zip(tab_keys, tab_labels))
if studio_has_new and "studio" in label_for_key and st.session_state.active_tab_key != "studio":
    label_for_key["studio"] = label_for_key["studio"] + " 🔴"

display_options = [label_for_key[k] for k in tab_keys]
try:
    current_index = tab_keys.index(st.session_state.active_tab_key)
except ValueError:
    current_index = 0

st.markdown("<div class='app-tab-nav'>", unsafe_allow_html=True)
selected_label = st.radio(
    "_app_tab_nav",
    options=display_options,
    index=current_index,
    horizontal=True,
    label_visibility="collapsed",
    key="_active_tab_radio",
)
st.markdown("</div>", unsafe_allow_html=True)

selected_key = tab_keys[display_options.index(selected_label)]
if selected_key != st.session_state.active_tab_key:
    st.session_state.active_tab_key = selected_key
    st.rerun()

if selected_key == "studio":
    st.session_state["_studio_seen_batch_id"] = current_batch_id

key = selected_key

if key == "web":
    if run_mode_web is None:
        st.error(f"❌ mode_web.py lỗi: {_err_web}")
    else:
        run_mode_web(config)

elif key == "studio":
    if render_adjustment_studio is None:
        st.error(f"❌ mode_adjust.py lỗi: {_err_adjust}")
    else:
        render_adjustment_studio()

elif key == "drive":
    if run_mode_drive is None:
        st.error(f"❌ mode_drive.py lỗi: {_err_drive}")
    else:
        run_mode_drive(config, get_gdrive_service())

elif key == "local":
    if run_mode_local is None:
        st.error(f"❌ mode_local.py lỗi: {_err_local}")
    else:
        run_mode_local(config)

elif key == "guide":
    st.markdown("""
        <div class='guide-box'>
        <div style='font-size:1rem;font-weight:800;color:#1e293b;margin-bottom:8px'>
        📌 Media Tool Pro VIP v10.0 — Hướng dẫn nhanh
        </div>
        <b>1.</b> Đăng ký → Admin duyệt và cấp quyền tab.<br>
        <b>2.</b> <b>Web TGDD:</b> dán link → quét → chọn màu → resize.<br>
        <b>3.</b> <b>Studio:</b> chỉnh từng ảnh sau batch. Live Preview CSS theo slider.
            Canvas preview <b>động theo aspect ratio</b> output thực tế.<br>
        <b>4.</b> <b>Drive / Local:</b> xử lý ảnh từ Drive hoặc ZIP.<br>
        <b>5.</b> Cấu hình GitHub Sync trong Streamlit Secrets:<br>
        &nbsp;&nbsp;<code>GITHUB_TOKEN</code>, <code>GITHUB_REPO</code>, <code>GITHUB_BRANCH</code>
        </div>
    """, unsafe_allow_html=True)

elif key == "admin":
    try:
        render_admin_panel()
    except Exception as e:
        st.warning(f"Admin Panel lỗi: {e}")
