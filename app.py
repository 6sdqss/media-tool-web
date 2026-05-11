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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ─── RESET & FONT ─── */
#MainMenu, header, footer, .stDeployButton {visibility:hidden!important;display:none!important;}

html, body, [class*="css"] {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif!important;
    font-size:14px!important;
    line-height:1.55!important;
}

/* ─── ROOT BACKGROUND — White workspace ─── */
.stApp {
    background: #f0f2f5 !important;
    color: #1e293b !important;
}

/* ─── MAIN CONTAINER ─── */
.block-container {
    max-width: 1100px !important;
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    padding-left: 1.25rem !important;
    padding-right: 1.25rem !important;
}

@media (max-width: 768px) {
    .block-container {
        max-width:100%!important;
        padding:0.6rem!important;
    }
}

/* ─── SIDEBAR ─── */
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
    box-shadow: 2px 0 8px rgba(0,0,0,0.05) !important;
    width: 260px !important;
}
section[data-testid="stSidebar"] > div {
    padding-top: 0.5rem !important;
}
section[data-testid="stSidebar"] * {
    color: #374151 !important;
    font-size: 13.5px !important;
}
section[data-testid="stSidebar"] .stButton button {
    font-size:13px!important;
    min-height:34px!important;
    padding:4px 10px!important;
}
section[data-testid="stSidebar"] hr {
    border-color:#e2e8f0!important;
    margin:8px 0!important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background:#f8fafc!important;
    border:1px solid #e2e8f0!important;
    border-radius:8px!important;
}

/* ─── APP HEADER ─── */
.app-header {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.app-header h1 {
    margin:0;
    font-size:1.1rem!important;
    font-weight:800!important;
    color:#1e293b!important;
    letter-spacing:-0.3px;
}
.app-header p {
    margin:2px 0 0;
    color:#7c3aed;
    font-size:0.8rem;
    font-weight:500;
}

/* ─── HERO CARD ─── */
.hero-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.hero-card h2 {
    margin:0 0 4px;
    color:#1e293b!important;
    font-size:1.05rem!important;
    font-weight:700!important;
}
.hero-card p {
    margin:0;
    color:#64748b;
    font-size:0.85rem;
    line-height:1.65;
}

/* ─── BORDERED CONTAINERS ─── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius:10px!important;
    border:1px solid #e2e8f0!important;
    padding:14px!important;
    background:#ffffff!important;
    box-shadow:0 1px 4px rgba(0,0,0,0.05)!important;
}

/* ─── SECTION TITLES ─── */
.sec-title {
    font-size:0.78rem!important;
    font-weight:700!important;
    color:#7c3aed!important;
    text-transform:uppercase;
    letter-spacing:0.8px;
    margin:14px 0 8px!important;
    padding:4px 10px;
    border-left:3px solid #7c3aed;
    background:#f5f3ff;
    border-radius:0 5px 5px 0;
}
.cfg-label {
    font-size:0.85rem!important;
    font-weight:600!important;
    color:#374151!important;
    margin-bottom:5px!important;
}
.tpl-hint { font-size:0.74rem;color:#9ca3af;margin-top:3px; }
.tpl-hint code {
    background:#f5f3ff;
    color:#7c3aed;
    padding:1px 6px;
    border-radius:4px;
    font-size:0.7rem;
}

/* ─── GUIDE BOX ─── */
.guide-box {
    background:#f8fafc;
    border:1px solid #e2e8f0;
    border-radius:8px;
    padding:10px 14px;
    font-size:0.86rem;
    color:#475569;
    margin-bottom:10px;
    line-height:1.65;
}
.guide-box b { color:#1e293b; }

/* ─── LOG BOX ─── */
.log-box {
    background:#0f172a!important;
    color:#4ade80!important;
    font-family:'JetBrains Mono','Courier New',monospace!important;
    font-size:0.76rem!important;
    padding:10px!important;
    border-radius:8px!important;
    max-height:200px!important;
    overflow-y:auto!important;
    border:1px solid rgba(74,222,128,0.15)!important;
    line-height:1.6!important;
}

/* ─── SUMMARY CARD ─── */
.summary-card {
    background:linear-gradient(135deg,#f0fdf4,#dcfce7);
    border:1px solid #86efac;
    border-radius:10px;
    padding:12px 16px;
    margin:8px 0;
    font-size:0.9rem;
    line-height:1.7;
    color:#166534;
}
.summary-card b { color:#15803d; }

/* ─── PREVIEW META ─── */
.preview-meta {
    text-align:center;
    font-size:0.76rem;
    color:#94a3b8;
    margin-top:4px;
    line-height:1.5;
}

/* ─── BUTTONS ─── */
.stButton>button, .stDownloadButton>button {
    background:linear-gradient(135deg,#7c3aed,#6366f1)!important;
    color:#fff!important;
    border-radius:8px!important;
    border:none!important;
    font-weight:600!important;
    font-size:13.5px!important;
    min-height:36px!important;
    padding:6px 14px!important;
    box-shadow:0 2px 6px rgba(124,58,237,0.2)!important;
    transition:all 0.18s ease!important;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    transform:translateY(-1px);
    box-shadow:0 4px 12px rgba(124,58,237,0.3)!important;
}
.stButton>button:active { transform:translateY(0); }
button[kind="secondary"] {
    background:#f1f5f9!important;
    color:#374151!important;
    border:1px solid #cbd5e1!important;
    box-shadow:none!important;
}
button[kind="secondary"]:hover {
    background:#e2e8f0!important;
}

/* ─── INPUTS ─── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"]>div,
.stMultiSelect div[data-baseweb="select"]>div {
    background:#ffffff!important;
    border:1px solid #d1d5db!important;
    border-radius:8px!important;
    color:#1e293b!important;
    font-size:13.5px!important;
    min-height:36px!important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color:#7c3aed!important;
    box-shadow:0 0 0 2px rgba(124,58,237,0.15)!important;
}
.stTextArea textarea { min-height:72px!important; }

/* ─── LABELS ─── */
.stTextInput label,.stTextArea label,.stSelectbox label,
.stNumberInput label,.stSlider label,.stMultiSelect label,
.stRadio label,.stCheckbox label,.stToggle label {
    font-size:13px!important;
    color:#374151!important;
    font-weight:500!important;
}

/* ─── SLIDERS ─── */
.stSlider [data-baseweb="slider"]>div>div {
    background:linear-gradient(90deg,#7c3aed,#6366f1)!important;
}
.stSlider [role="slider"] {
    background:#fff!important;
    border:2px solid #7c3aed!important;
    box-shadow:0 2px 6px rgba(124,58,237,0.3)!important;
    width:18px!important;
    height:18px!important;
}

/* ─── TABS ─── */
.stTabs [data-baseweb="tab-list"] {
    gap:3px!important;
    background:#f1f5f9!important;
    border-radius:8px!important;
    padding:4px!important;
    overflow-x:auto;
    flex-wrap:nowrap!important;
    border:1px solid #e2e8f0!important;
}
.stTabs [data-baseweb="tab"] {
    height:36px!important;
    padding:0 14px!important;
    border-radius:6px!important;
    color:#64748b!important;
    font-size:13px!important;
    font-weight:600!important;
    white-space:nowrap!important;
    background:transparent!important;
    border:none!important;
}
.stTabs [aria-selected="true"] {
    background:linear-gradient(135deg,#7c3aed,#6366f1)!important;
    color:#fff!important;
    box-shadow:0 2px 6px rgba(124,58,237,0.25);
}

/* ─── EXPANDER ─── */
[data-testid="stExpander"] {
    background:#ffffff!important;
    border:1px solid #e2e8f0!important;
    border-radius:8px!important;
    box-shadow:0 1px 3px rgba(0,0,0,0.04)!important;
}
[data-testid="stExpander"] summary {
    font-size:13.5px!important;
    font-weight:600!important;
    color:#1e293b!important;
    padding:8px 14px!important;
}

/* ─── METRIC ─── */
[data-testid="stMetric"] {
    background:#ffffff;
    border:1px solid #e2e8f0;
    padding:10px 12px!important;
    border-radius:8px;
    box-shadow:0 1px 3px rgba(0,0,0,0.05);
}
[data-testid="stMetricLabel"] { font-size:0.76rem!important;color:#64748b!important; }
[data-testid="stMetricValue"] { font-size:1.25rem!important;color:#1e293b!important;font-weight:700!important; }

/* ─── ALERT BOXES ─── */
[data-testid="stAlert"] { border-radius:8px!important;padding:10px 14px!important;font-size:13px!important; }

/* ─── CAPTION ─── */
.stCaption,[data-testid="stCaptionContainer"] { font-size:0.78rem!important;color:#94a3b8!important; }

/* ─── PROGRESS BAR ─── */
.stProgress>div>div>div>div {
    background:linear-gradient(90deg,#7c3aed,#a855f7)!important;
}
.stProgress>div>div { height:6px!important;border-radius:3px!important; }

/* ─── LOGIN ─── */
.login-shell { max-width:380px;margin:3rem auto 0; }
.login-card {
    background:#ffffff;
    border-radius:16px;
    padding:28px 28px 20px;
    border:1px solid #e2e8f0;
    box-shadow:0 8px 30px rgba(0,0,0,0.1);
}
.login-brand {
    width:56px;height:56px;border-radius:14px;margin:0 auto 14px;
    display:flex;align-items:center;justify-content:center;
    background:linear-gradient(135deg,#7c3aed,#6366f1);
    color:#fff;font-size:1.7rem;
    box-shadow:0 6px 20px rgba(124,58,237,0.3);
}
.login-title { text-align:center;color:#1e293b!important;font-weight:800;font-size:1.2rem;margin:0;letter-spacing:-0.3px; }
.login-sub { text-align:center;color:#94a3b8;margin:4px 0 18px;font-size:0.82rem; }

/* ─── USER CHIP ─── */
.user-chip {
    background:linear-gradient(135deg,#f5f3ff,#ede9fe);
    border-radius:10px;
    padding:11px 13px;
    border:1px solid #ddd6fe;
    margin-bottom:8px;
}
.user-chip b { color:#1e293b!important;font-size:0.95rem!important;font-weight:700!important; }
.user-chip span { color:#7c3aed!important;font-size:0.74rem!important; }

/* ─── SIDEBAR LOGO ─── */
.sb-logo-wrap { text-align:center;padding:4px 0 4px; }
.sb-logo-icon {
    width:46px;height:46px;margin:0 auto 8px;border-radius:12px;
    background:linear-gradient(135deg,#7c3aed,#6366f1);
    display:flex;align-items:center;justify-content:center;
    font-size:1.3rem;box-shadow:0 4px 12px rgba(124,58,237,0.25);
}
.sb-logo-title { font-weight:800!important;font-size:0.92rem!important;color:#1e293b!important;letter-spacing:-0.2px; }
.sb-logo-sub { font-size:0.7rem!important;color:#7c3aed!important;margin-top:2px; }

/* ─── HISTORY ITEM ─── */
.history-item { padding:6px 0;border-bottom:1px solid #f1f5f9; }
.hi-top { font-size:0.8rem!important;color:#374151!important;margin-bottom:1px; }
.hi-top b { color:#1e293b!important; }
.hi-bot { font-size:0.72rem!important;color:#94a3b8!important; }

/* ─── STAT PILLS ─── */
.stat-row { display:flex;gap:5px;margin:4px 0 6px; }
.stat-pill { flex:1;border-radius:8px;padding:7px 4px;text-align:center;border:1px solid #e2e8f0; }
.stat-a { background:#f5f3ff; }
.stat-b { background:#f0fdf4; }
.stat-c { background:#fefce8; }
.sp-num { font-size:1rem!important;font-weight:800!important;color:#1e293b!important; }
.stat-a .sp-num { color:#7c3aed!important; }
.stat-b .sp-num { color:#16a34a!important; }
.stat-c .sp-num { color:#ca8a04!important; }
.sp-lbl { font-size:0.65rem!important;color:#94a3b8!important;text-transform:uppercase;letter-spacing:0.5px; }

/* ─── CONTROL ROW ─── */
.ctrl-row {
    background:#f8fafc;
    border-radius:8px;
    padding:7px;
    margin:6px 0;
    border:1px solid #e2e8f0;
}

/* ─── DIVIDER ─── */
hr { border-color:#e2e8f0!important;margin:12px 0!important; }

/* ─── CHECKBOX & TOGGLE ─── */
.stCheckbox label,.stToggle label { font-size:13.5px!important;color:#374151!important; }

/* ─── SPINNER ─── */
.stSpinner>div { border-top-color:#7c3aed!important; }

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar { width:8px;height:8px; }
::-webkit-scrollbar-track { background:#f1f5f9; }
::-webkit-scrollbar-thumb { background:#cbd5e1;border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:#94a3b8; }

/* ─── MOBILE ─── */
@media (max-width:640px) {
    .app-header h1 { font-size:1rem!important; }
    .stTabs [data-baseweb="tab-list"] {
        position:sticky;top:0;z-index:99;
        background:rgba(240,242,245,0.97)!important;
        backdrop-filter:blur(10px);
    }
    .stTabs [data-baseweb="tab"] { padding:0 11px!important;font-size:12.5px!important;min-height:38px!important; }
    .login-shell { padding:0 12px; }
    .stButton>button { font-size:13px!important;min-height:40px!important; }
    .stDownloadButton>button { min-height:44px!important; }
    section[data-testid="stSidebar"] { width:88vw!important; }
    .block-container { padding:0.5rem!important; }
}

@media (min-width:641px) and (max-width:1024px) {
    .block-container { max-width:940px!important; }
}

/* ─── HIGHLIGHT checked row ─── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(input[type="checkbox"]:checked) {
    border-color:#7c3aed!important;
    box-shadow:0 0 0 2px rgba(124,58,237,0.1);
}

/* ════════════════════════════════════════════════════════════
   STUDIO TAB — Professional Photo Editor Layout
   ════════════════════════════════════════════════════════════ */
.studio-wrap { font-size:14.5px!important; }
.studio-wrap .stTextInput label,
.studio-wrap .stSelectbox label,
.studio-wrap .stNumberInput label,
.studio-wrap .stSlider label,
.studio-wrap .stCheckbox label,
.studio-wrap .stToggle label {
    font-size:13.5px!important;
    font-weight:600!important;
    color:#374151!important;
}
.studio-wrap .sec-title {
    font-size:0.9rem!important;
    padding:6px 12px!important;
    border-left-width:3px!important;
    margin:16px 0 10px!important;
}
.studio-wrap .guide-box {
    font-size:0.9rem!important;
    padding:12px 16px!important;
    line-height:1.7!important;
}
.studio-wrap .preview-meta {
    font-size:0.82rem!important;
    color:#64748b!important;
    margin-top:6px!important;
}
.studio-wrap .stButton>button {
    min-height:40px!important;
    font-size:13.5px!important;
    font-weight:700!important;
}
.studio-wrap div[data-testid="stVerticalBlockBorderWrapper"] {
    padding:16px!important;
    margin-bottom:12px!important;
    border:1px solid #e2e8f0!important;
    background:#ffffff!important;
    box-shadow:0 2px 8px rgba(0,0,0,0.06)!important;
}

/* Studio wide on desktop */
@media (min-width:1025px) {
    body:has(.studio-wrap) .block-container,
    .studio-wide .block-container { max-width:1360px!important; }
}

/* ─── STUDIO CARD ─── */
.sc-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    transition: box-shadow 0.18s, border-color 0.18s;
}
.sc-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.sc-card.sc-adjusted {
    border-color: #7c3aed !important;
    box-shadow: 0 0 0 2px rgba(124,58,237,0.12), 0 4px 12px rgba(0,0,0,0.08) !important;
}
.sc-card.sc-small {
    border-color: #f87171 !important;
}

/* ─── STATUS PILLS ─── */
.spill {
    display:inline-block;
    font-size:0.75rem;
    font-weight:700;
    padding:3px 10px;
    border-radius:999px;
    letter-spacing:0.3px;
    white-space:nowrap;
}
.spill-r { background:#dcfce7;color:#16a34a;border:1px solid #86efac; }
.spill-a { background:#fef9c3;color:#854d0e;border:1px solid #fde68a; }
.spill-s { background:#f1f5f9;color:#64748b;border:1px solid #cbd5e1; }

/* ─── STUDIO IMAGE TITLE ─── */
.studio-img-title {
    font-size:0.95rem!important;
    margin-bottom:8px!important;
    line-height:1.55;
}
.studio-img-title b { color:#1e293b!important;font-size:1rem!important; }
.studio-img-title code {
    font-size:0.82rem!important;
    color:#7c3aed!important;
    background:#f5f3ff;
    padding:2px 7px;
    border-radius:4px;
    word-break:break-all;
}

/* ─── CANVAS WORKSPACE ─── */
.canvas-workspace {
    background: #f8fafc;
    border-radius: 10px;
    padding: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #e2e8f0;
    position: relative;
    min-height: 120px;
}
.canvas-workspace::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 10px;
    /* Checkerboard — biểu thị transparency */
    background-image:
        linear-gradient(45deg,#e2e8f0 25%,transparent 25%),
        linear-gradient(-45deg,#e2e8f0 25%,transparent 25%),
        linear-gradient(45deg,transparent 75%,#e2e8f0 75%),
        linear-gradient(-45deg,transparent 75%,#e2e8f0 75%);
    background-size: 16px 16px;
    background-position: 0 0,0 8px,8px -8px,-8px 0px;
    opacity: 0.5;
    pointer-events: none;
}

/* ─── LIVE PREVIEW FRAME — ĐỘNG THEO ASPECT RATIO ─── */
.live-frame {
    position: relative;
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
    background: #ffffff;
    border: 2px solid #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.08);
    /* aspect-ratio được set inline theo output size thực tế */
}
.live-frame::after {
    /* Corner mark */
    content:'OUTPUT';
    position:absolute;
    bottom:0;right:0;
    font-size:0.6rem;
    font-weight:700;
    color:rgba(100,116,139,0.7);
    background:rgba(248,250,252,0.85);
    padding:2px 6px;
    border-radius:6px 0 0 0;
    letter-spacing:0.8px;
    pointer-events:none;
    z-index:5;
}
.live-frame--empty {
    display:flex;
    align-items:center;
    justify-content:center;
    aspect-ratio:3/2;
    color:#f87171;
    font-size:0.9rem;
    background:#fef2f2;
    border-color:#fca5a5;
}
.live-canvas {
    position:absolute;
    inset:0;
    display:flex;
    align-items:center;
    justify-content:center;
    overflow:hidden;
    background:#ffffff;
}
.live-img {
    width:100%;
    height:100%;
    object-fit:contain;
    object-position:center;
    transform-origin:center center;
    /* Smooth transform — no page rerun needed */
    transition:transform 0.1s cubic-bezier(.4,.7,.2,1);
    will-change:transform;
    user-select:none;
    -webkit-user-drag:none;
    image-rendering:high-quality;
}
/* Overlay bar with scale info */
.live-overlay {
    position:absolute;
    bottom:0;left:0;right:0;
    display:flex;
    flex-wrap:wrap;
    gap:4px 10px;
    padding:5px 10px;
    background:linear-gradient(180deg,rgba(255,255,255,0)0%,rgba(15,23,42,0.45)100%);
    color:#f8fafc;
    font-size:0.76rem!important;
    font-weight:600;
    z-index:2;
    pointer-events:none;
}
.live-overlay span { white-space:nowrap; }

/* ─── RENDERED FRAME ─── */
.rendered-frame {
    background:#ffffff;
    border-radius:10px;
    border:2px solid #86efac;
    overflow:hidden;
    padding:4px;
    box-shadow:0 2px 8px rgba(22,163,74,0.1);
    position:relative;
}
.rendered-frame::before {
    content:'';
    position:absolute;
    inset:0;
    background-image:
        linear-gradient(45deg,#f0fdf4 25%,transparent 25%),
        linear-gradient(-45deg,#f0fdf4 25%,transparent 25%),
        linear-gradient(45deg,transparent 75%,#f0fdf4 75%),
        linear-gradient(-45deg,transparent 75%,#f0fdf4 75%);
    background-size:14px 14px;
    background-position:0 0,0 7px,7px -7px,-7px 0px;
    opacity:0.6;
    pointer-events:none;
}
.rendered-frame img {
    max-width:100%;
    max-height:260px;
    object-fit:contain;
    display:block;
    margin:0 auto;
    position:relative;
    z-index:1;
}

/* ─── SIZE INFO ─── */
.size-info { font-size:0.76rem;color:#94a3b8;margin-top:4px;line-height:1.6; }
.size-info.output { color:#16a34a;font-weight:600; }

/* ─── EXPORT PANEL ─── */
.export-panel {
    background:#ffffff;
    border:1px solid #e2e8f0;
    border-radius:12px;
    padding:20px;
    margin-top:12px;
    box-shadow:0 2px 8px rgba(0,0,0,0.05);
}
.export-panel h2 { margin-top:0;color:#1e293b;font-size:1.2rem; }

/* ─── STUDIO FRESH BANNER ─── */
.studio-fresh-banner {
    background:linear-gradient(135deg,#f0fdf4,#dcfce7);
    border:1px solid #86efac;
    border-radius:10px;
    padding:11px 16px;
    margin:4px 0 12px;
    font-size:0.9rem;
    color:#166534;
    font-weight:600;
}

/* ─── PAGINATION ─── */
.pg-bar {
    display:flex;
    align-items:center;
    gap:6px;
    padding:10px 0;
    flex-wrap:wrap;
    border-top:1px solid #f1f5f9;
    margin-top:8px;
}

/* ─── APP TAB NAV (radio as tabs) ─── */
div[data-testid="stRadio"][aria-label="_app_tab_nav"]>div[role="radiogroup"],
.app-tab-nav div[role="radiogroup"] {
    gap:4px!important;
    background:#f1f5f9!important;
    border-radius:10px!important;
    padding:5px!important;
    flex-wrap:wrap!important;
    border:1px solid #e2e8f0!important;
    margin-bottom:14px!important;
}
.app-tab-nav label {
    background:transparent!important;
    color:#64748b!important;
    padding:8px 16px!important;
    border-radius:7px!important;
    font-weight:600!important;
    font-size:13.5px!important;
    cursor:pointer!important;
    transition:all 0.15s ease!important;
    margin:0!important;
    border:1px solid transparent!important;
}
.app-tab-nav label:hover {
    background:#e2e8f0!important;
    color:#374151!important;
}
.app-tab-nav label>div:first-child { display:none!important; }
.app-tab-nav label:has(input:checked) {
    background:linear-gradient(135deg,#7c3aed,#6366f1)!important;
    color:#fff!important;
    box-shadow:0 2px 8px rgba(124,58,237,0.25)!important;
}

/* ─── DISABLED BUTTONS ─── */
.stButton>button:disabled,.stDownloadButton>button:disabled {
    background:#f1f5f9!important;
    color:#94a3b8!important;
    cursor:not-allowed!important;
    box-shadow:none!important;
    border:1px solid #e2e8f0!important;
    transform:none!important;
}

/* Mobile Studio */
@media (max-width:640px) {
    .live-frame { max-width:100%; }
    .live-overlay { font-size:0.72rem!important;padding:4px 8px; }
    .studio-img-title { font-size:0.9rem!important; }
    .canvas-workspace { padding:8px; }
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
            <div class="sb-logo-icon">&#128444;</div>
            <div class="sb-logo-title">Media Tool Pro VIP</div>
            <div class="sb-logo-sub">v10.0 &middot; White Studio</div>
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
            <h1>&#128444; Workspace &middot; {user['username']}</h1>
            <p>v10.0 · White Studio · Dynamic Canvas · Auto-sync GitHub</p>
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
