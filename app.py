# -*- coding: utf-8 -*-
"""
app.py - Media Tool Pro VIP Pro v9.3
─────────────────────────────────────────────────────────
- Auth + Admin Panel + GitHub Sync
- Phân quyền tab theo user
- Giao diện COMPACT, ELEGANT, MOBILE-FRIENDLY
- Theme glassmorphism violet/indigo
- v9.3: Studio Live Preview, font cỡ chữ tăng, layout rộng hơn,
        dual-zip download, banner auto-switch sau render.
"""

from __future__ import annotations

import streamlit as st

# ── Auth ──
from auth import (
    authenticate,
    change_own_password,
    has_permission,
    register_user,
)
from admin_panel import render_admin_panel

# ── Engine ──
from utils import (
    EXPORT_FORMATS,
    SIZE_PRESETS,
    init_app_state,
    render_history_sidebar,
    render_session_stats,
    get_gdrive_service,
)

# ── Modes (Import an toàn) ──
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
# CSS — V9.3 (Bigger fonts, Studio live preview, dual zip)
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ─── RESET ─── */
#MainMenu, header, footer, .stDeployButton {visibility: hidden !important; display: none !important;}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 14.5px !important;
    line-height: 1.55 !important;
}

/* ─── BACKGROUND ─── */
.stApp {
    background:
        radial-gradient(circle at 15% 10%, rgba(139, 92, 246, 0.12) 0%, transparent 45%),
        radial-gradient(circle at 85% 90%, rgba(59, 130, 246, 0.10) 0%, transparent 45%),
        #0b0b12 !important;
    color: #e2e8f0 !important;
}

/* ─── CONTAINER ─── */
.block-container {
    max-width: 1040px !important;
    padding-top: 1rem !important;
    padding-bottom: 1.5rem !important;
    padding-left: 1.1rem !important;
    padding-right: 1.1rem !important;
}

@media (max-width: 768px) {
    .block-container {
        max-width: 100% !important;
        padding: 0.55rem !important;
    }
    html, body, [class*="css"] { font-size: 13.8px !important; }
}

/* ─── SIDEBAR ─── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #14141d 0%, #0e0e16 100%) !important;
    border-right: 1px solid rgba(139, 92, 246, 0.15) !important;
    width: 270px !important;
}
section[data-testid="stSidebar"] > div {
    padding-top: 0.5rem !important;
}
section[data-testid="stSidebar"] * {
    color: #cbd5e1 !important;
    font-size: 13.5px !important;
}
section[data-testid="stSidebar"] .stButton button {
    font-size: 13px !important;
    min-height: 34px !important;
    padding: 4px 10px !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(139, 92, 246, 0.15) !important;
    margin: 8px 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(139, 92, 246, 0.04) !important;
    border: 1px solid rgba(139, 92, 246, 0.12) !important;
    border-radius: 8px !important;
}

/* ─── HEADER ─── */
.app-header {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(59, 130, 246, 0.10) 100%);
    border: 1px solid rgba(139, 92, 246, 0.22);
    border-radius: 12px;
    padding: 13px 18px;
    margin-bottom: 12px;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}
.app-header h1 {
    margin: 0;
    font-size: 1.18rem !important;
    font-weight: 800 !important;
    color: #fff !important;
    letter-spacing: -0.3px;
}
.app-header p {
    margin: 2px 0 0;
    color: #a78bfa;
    font-size: 0.82rem;
    font-weight: 500;
}

/* ─── HERO CARD ─── */
.hero-card {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.10), rgba(59, 130, 246, 0.06));
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 12px;
}
.hero-card h2 {
    margin: 0 0 4px;
    color: #fff !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
}
.hero-card p {
    margin: 0;
    color: #94a3b8;
    font-size: 0.85rem;
    line-height: 1.6;
}

/* ─── BORDERED CONTAINERS ─── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px !important;
    border: 1px solid rgba(139, 92, 246, 0.18) !important;
    padding: 12px !important;
    background: rgba(21, 21, 31, 0.6) !important;
    backdrop-filter: blur(8px);
}

/* ─── SECTION TITLES ─── */
.sec-title {
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    color: #c4b5fd !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 12px 0 7px !important;
    padding: 4px 10px;
    border-left: 3px solid #8b5cf6;
    background: rgba(139, 92, 246, 0.08);
    border-radius: 0 4px 4px 0;
}
.cfg-label {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    color: #c4b5fd !important;
    margin-bottom: 5px !important;
}
.tpl-hint {
    font-size: 0.74rem;
    color: #9ca3af;
    margin-top: 3px;
}
.tpl-hint code {
    background: rgba(139, 92, 246, 0.12);
    color: #c4b5fd;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.7rem;
}

/* ─── GUIDE BOX ─── */
.guide-box {
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.18);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.86rem;
    color: #cbd5e1;
    margin-bottom: 10px;
    line-height: 1.65;
}
.guide-box b { color: #fff; }

/* ─── LOG BOX ─── */
.log-box {
    background: #04050a !important;
    color: #4ade80 !important;
    font-family: 'JetBrains Mono', 'Courier New', monospace !important;
    font-size: 0.78rem !important;
    padding: 10px !important;
    border-radius: 8px !important;
    max-height: 220px !important;
    overflow-y: auto !important;
    border: 1px solid rgba(74, 222, 128, 0.18) !important;
    line-height: 1.6 !important;
}

/* ─── SUMMARY CARD ─── */
.summary-card {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(34, 197, 94, 0.06));
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 10px;
    padding: 11px 14px;
    margin: 8px 0;
    font-size: 0.9rem;
    line-height: 1.7;
    color: #d1fae5;
}
.summary-card b { color: #86efac; }

/* ─── PREVIEW META ─── */
.preview-meta {
    text-align: center;
    font-size: 0.78rem;
    color: #94a3b8;
    margin-top: 4px;
}

/* ─── BUTTONS ─── */
.stButton > button, .stDownloadButton > button {
    background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%) !important;
    color: #fff !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    min-height: 36px !important;
    padding: 6px 14px !important;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25) !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4) !important;
    background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%) !important;
}
.stButton > button:active { transform: translateY(0); }

button[kind="secondary"] {
    background: rgba(139, 92, 246, 0.1) !important;
    color: #c4b5fd !important;
    border: 1px solid rgba(139, 92, 246, 0.3) !important;
    box-shadow: none !important;
}

/* ─── INPUTS ─── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {
    background: rgba(30, 30, 40, 0.85) !important;
    border: 1px solid rgba(139, 92, 246, 0.2) !important;
    border-radius: 8px !important;
    color: #f1f5f9 !important;
    font-size: 13.5px !important;
    min-height: 36px !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #8b5cf6 !important;
    box-shadow: 0 0 0 1px rgba(139, 92, 246, 0.3) !important;
}
.stTextArea textarea { min-height: 75px !important; }

/* ─── LABELS ─── */
.stTextInput label, .stTextArea label, .stSelectbox label,
.stNumberInput label, .stSlider label, .stMultiSelect label,
.stRadio label, .stCheckbox label, .stToggle label {
    font-size: 13px !important;
    color: #cbd5e1 !important;
    font-weight: 500 !important;
}

/* ─── SLIDERS ─── */
.stSlider [data-baseweb="slider"] > div > div {
    background: linear-gradient(90deg, #8b5cf6, #6366f1) !important;
}
.stSlider [role="slider"] {
    background: #fff !important;
    border: 2px solid #8b5cf6 !important;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.4) !important;
}

/* ─── TABS ─── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: rgba(21, 21, 31, 0.5) !important;
    border-radius: 8px !important;
    padding: 4px !important;
    overflow-x: auto;
    flex-wrap: nowrap !important;
}
.stTabs [data-baseweb="tab"] {
    height: 38px !important;
    padding: 0 14px !important;
    border-radius: 6px !important;
    color: #94a3b8 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    background: transparent !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #8b5cf6, #6366f1) !important;
    color: #fff !important;
    box-shadow: 0 2px 6px rgba(139, 92, 246, 0.3);
}

/* ─── EXPANDER ─── */
[data-testid="stExpander"] {
    background: rgba(21, 21, 31, 0.6) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 8px !important;
}
[data-testid="stExpander"] summary {
    font-size: 13.5px !important;
    font-weight: 600 !important;
    padding: 8px 12px !important;
}

/* ─── METRIC ─── */
[data-testid="stMetric"] {
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.15);
    padding: 10px 12px !important;
    border-radius: 8px;
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    color: #94a3b8 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.3rem !important;
    color: #fff !important;
    font-weight: 700 !important;
}

/* ─── ALERT BOXES ─── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
}

/* ─── CAPTION ─── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.8rem !important;
    color: #9ca3af !important;
}

/* ─── PROGRESS BAR ─── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #8b5cf6, #ec4899) !important;
}
.stProgress > div > div { height: 7px !important; border-radius: 3px !important; }

/* ─── LOGIN ─── */
.login-shell { max-width: 360px; margin: 3rem auto 0; }
.login-card {
    background: rgba(21, 21, 31, 0.85);
    border-radius: 16px;
    padding: 22px 24px 14px;
    border: 1px solid rgba(139, 92, 246, 0.2);
    box-shadow:
        0 20px 40px rgba(0, 0, 0, 0.5),
        0 0 60px rgba(139, 92, 246, 0.1);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
}
.login-brand {
    width: 56px; height: 56px;
    border-radius: 14px;
    margin: 0 auto 12px;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #8b5cf6, #6366f1);
    color: #fff;
    font-size: 1.7rem;
    box-shadow: 0 8px 20px rgba(139, 92, 246, 0.4);
}
.login-title {
    text-align: center;
    color: #fff !important;
    font-weight: 800;
    font-size: 1.2rem;
    margin: 0;
    letter-spacing: -0.3px;
}
.login-sub {
    text-align: center;
    color: #94a3b8;
    margin: 4px 0 14px;
    font-size: 0.82rem;
}

/* ─── USER CHIP ─── */
.user-chip {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(99, 102, 241, 0.08));
    border-radius: 10px;
    padding: 11px 13px;
    border: 1px solid rgba(139, 92, 246, 0.22);
    margin-bottom: 8px;
}
.user-chip b {
    color: #fff !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
}
.user-chip span {
    color: #a78bfa !important;
    font-size: 0.74rem !important;
}

/* ─── SIDEBAR LOGO ─── */
.sb-logo-wrap { text-align: center; padding: 4px 0 2px; }
.sb-logo-icon {
    width: 46px; height: 46px;
    margin: 0 auto 7px;
    border-radius: 12px;
    background: linear-gradient(135deg, #8b5cf6, #6366f1);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem;
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.35);
}
.sb-logo-title {
    font-weight: 800 !important;
    font-size: 0.95rem !important;
    color: #fff !important;
    letter-spacing: -0.2px;
}
.sb-logo-sub {
    font-size: 0.72rem !important;
    color: #a78bfa !important;
    margin-top: 2px;
}

/* ─── HISTORY ITEM ─── */
.history-item {
    padding: 6px 0;
    border-bottom: 1px solid rgba(139, 92, 246, 0.08);
}
.hi-top { font-size: 0.8rem !important; color: #e2e8f0 !important; margin-bottom: 1px; }
.hi-top b { color: #fff !important; }
.hi-bot { font-size: 0.72rem !important; color: #64748b !important; }

/* ─── STAT PILLS ─── */
.stat-row { display: flex; gap: 5px; margin: 4px 0 6px; }
.stat-pill {
    flex: 1;
    border-radius: 8px;
    padding: 7px 4px;
    text-align: center;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
.stat-a { background: rgba(99, 102, 241, 0.15); }
.stat-b { background: rgba(16, 185, 129, 0.15); }
.stat-c { background: rgba(251, 191, 36, 0.15); }
.sp-num { font-size: 1.05rem !important; font-weight: 800 !important; color: #fff !important; }
.stat-a .sp-num { color: #c7d2fe !important; }
.stat-b .sp-num { color: #a7f3d0 !important; }
.stat-c .sp-num { color: #fde68a !important; }
.sp-lbl {
    font-size: 0.66rem !important;
    color: #94a3b8 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ─── CONTROL ROW ─── */
.ctrl-row {
    background: rgba(21, 21, 31, 0.5);
    border-radius: 8px;
    padding: 7px;
    margin: 6px 0;
    border: 1px solid rgba(139, 92, 246, 0.12);
}

/* ─── DIVIDER ─── */
hr {
    border-color: rgba(139, 92, 246, 0.12) !important;
    margin: 12px 0 !important;
}

/* ─── CHECKBOX & TOGGLE ─── */
.stCheckbox label, .stToggle label { font-size: 13.5px !important; }

/* ─── SPINNER ─── */
.stSpinner > div { border-top-color: #8b5cf6 !important; }

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: #0b0b12; }
::-webkit-scrollbar-thumb {
    background: rgba(139, 92, 246, 0.3);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(139, 92, 246, 0.5); }

/* ─── MOBILE ADJUSTMENTS ─── */
@media (max-width: 640px) {
    .app-header h1 { font-size: 1.05rem !important; }
    .app-header p { font-size: 0.74rem !important; }
    .stTabs [data-baseweb="tab-list"] {
        position: sticky; top: 0; z-index: 99;
        background: rgba(11, 11, 18, 0.95) !important;
        backdrop-filter: blur(12px);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0 12px !important;
        font-size: 12.5px !important;
        min-height: 38px !important;
    }
    .login-shell { padding: 0 12px; }
    .stButton > button { font-size: 13px !important; min-height: 40px !important; }
    .stDownloadButton > button { min-height: 44px !important; font-size: 13.5px !important; }
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    section[data-testid="stSidebar"] { width: 86vw !important; }
    .block-container { padding: 0.45rem !important; }
    .stSlider [role="slider"] { width: 24px !important; height: 24px !important; }
    .stCheckbox label { min-height: 34px !important; align-items: center !important; }
}

/* ─── TABLET ─── */
@media (min-width: 641px) and (max-width: 1024px) {
    .block-container { max-width: 920px !important; }
}

/* ─── HIGHLIGHT BORDER cho ảnh đang chọn ─── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(input[type="checkbox"]:checked) {
    border-color: rgba(251, 191, 36, 0.55) !important;
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.2);
}

/* ════════════════════════════════════════════════════════════ */
/* ─── STUDIO TAB — BỐ CỤC TO RÕ + LIVE PREVIEW ─── */
/* ════════════════════════════════════════════════════════════ */
.studio-wrap, .studio-wrap * { font-size: 15px !important; }

.studio-wrap .stTextInput label,
.studio-wrap .stSelectbox label,
.studio-wrap .stNumberInput label,
.studio-wrap .stSlider label,
.studio-wrap .stCheckbox label,
.studio-wrap .stToggle label {
    font-size: 14.5px !important;
    font-weight: 600 !important;
    color: #e2e8f0 !important;
}
.studio-wrap .sec-title {
    font-size: 1rem !important;
    padding: 8px 14px !important;
    border-left-width: 4px !important;
    margin: 18px 0 11px !important;
    letter-spacing: 0.7px;
}
.studio-wrap .guide-box {
    font-size: 0.98rem !important;
    padding: 13px 17px !important;
    line-height: 1.75 !important;
}
.studio-wrap .preview-meta {
    font-size: 0.92rem !important;
    color: #cbd5e1 !important;
    margin-top: 8px !important;
    line-height: 1.65 !important;
}
.studio-wrap .stButton > button {
    min-height: 44px !important;
    font-size: 14px !important;
    font-weight: 700 !important;
}
.studio-wrap div[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 18px !important;
    margin-bottom: 16px !important;
    border: 1px solid rgba(139, 92, 246, 0.22) !important;
}

/* Studio block-container rộng hơn cho desktop */
@media (min-width: 1025px) {
    /* Tăng max-width khi đang ở Studio tab */
    body:has(.studio-wrap) .block-container,
    .studio-wide .block-container {
        max-width: 1400px !important;
    }
}

/* ─── ẢNH PHỤ TRỢ TRONG STUDIO (st.image fallback) ─── */
.studio-wrap .stImage {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    width: 100% !important;
}
.studio-wrap .stImage > img,
.studio-wrap [data-testid="stImage"] img {
    object-fit: contain !important;
    object-position: center center !important;
    margin: 0 auto !important;
    display: block !important;
    max-height: 500px !important;
    width: auto !important;
    max-width: 100% !important;
    background:
        linear-gradient(45deg, #0f0f17 25%, transparent 25%) 0 0 / 16px 16px,
        linear-gradient(-45deg, #0f0f17 25%, transparent 25%) 0 0 / 16px 16px,
        linear-gradient(45deg, transparent 75%, #0f0f17 75%) 0 0 / 16px 16px,
        linear-gradient(-45deg, transparent 75%, #0f0f17 75%) 0 0 / 16px 16px,
        #0b0b12 !important;
    border-radius: 10px !important;
    border: 1px solid rgba(139, 92, 246, 0.18) !important;
    padding: 6px !important;
}

/* ─── LIVE PREVIEW FRAME (THẾ HỆ MỚI) ─── */
.live-frame {
    position: relative;
    width: 100%;
    max-width: 560px;
    margin: 0 auto;
    background:
        linear-gradient(45deg, #0f0f17 25%, transparent 25%) 0 0 / 18px 18px,
        linear-gradient(-45deg, #0f0f17 25%, transparent 25%) 0 0 / 18px 18px,
        linear-gradient(45deg, transparent 75%, #0f0f17 75%) 0 0 / 18px 18px,
        linear-gradient(-45deg, transparent 75%, #0f0f17 75%) 0 0 / 18px 18px,
        #ffffff;
    border: 1px solid rgba(139, 92, 246, 0.28);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
    /* aspect-ratio đặt inline theo size đầu ra */
}
.live-frame--empty {
    aspect-ratio: 3 / 2;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #f87171;
    font-size: 0.95rem;
    background: rgba(15, 15, 23, 0.85);
}
.live-canvas {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}
.live-canvas .live-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center center;
    transform-origin: center center;
    transition: transform 0.15s cubic-bezier(.4,.7,.2,1);
    will-change: transform;
    user-select: none;
    -webkit-user-drag: none;
}
.live-status {
    position: absolute;
    top: 8px; left: 8px;
    z-index: 3;
}
.live-overlay-info {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px 14px;
    padding: 7px 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.55) 75%);
    color: #e2e8f0;
    font-size: 0.82rem !important;
    font-weight: 600;
    letter-spacing: 0.3px;
    z-index: 2;
}
.live-overlay-info span { white-space: nowrap; }
.live-overlay-status { margin-left: auto; color: #fde68a; }

/* ─── STATUS PILL ─── */
.studio-status-pill {
    display: inline-block;
    font-size: 0.82rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    letter-spacing: 0.4px;
    vertical-align: middle;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(6px);
}
.pill-rendered { background: rgba(34,197,94,0.85); color: #ffffff; border: 1px solid rgba(34,197,94,0.85); }
.pill-adjusted { background: rgba(251,191,36,0.9);  color: #1f2937; border: 1px solid rgba(251,191,36,0.95); }
.pill-source   { background: rgba(148,163,184,0.85); color: #ffffff; border: 1px solid rgba(148,163,184,0.85); }

.studio-img-title {
    font-size: 1.05rem !important;
    margin-bottom: 10px !important;
    line-height: 1.55;
}
.studio-img-title b { color: #fff !important; font-size: 1.1rem !important; }
.studio-img-title code {
    font-size: 0.88rem !important;
    color: #c4b5fd !important;
    background: rgba(139,92,246,0.14);
    padding: 3px 8px;
    border-radius: 5px;
    word-break: break-all;
}

/* ─── BANNER "VỪA RENDER XONG" trên Studio ─── */
.studio-fresh-banner {
    background: linear-gradient(135deg, rgba(34,197,94,0.18), rgba(16,185,129,0.10));
    border: 1px solid rgba(34,197,94,0.45);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 4px 0 12px;
    font-size: 0.95rem;
    color: #d1fae5;
    font-weight: 600;
    animation: fresh-pulse 2s ease-in-out infinite;
}
.studio-fresh-banner b { color: #86efac; }
@keyframes fresh-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.0); }
    50%      { box-shadow: 0 0 0 5px rgba(34,197,94,0.18); }
}

/* ─── RADIO-AS-TABS ─── */
div[data-testid="stRadio"][aria-label="_app_tab_nav"] > div[role="radiogroup"],
.app-tab-nav div[role="radiogroup"] {
    gap: 5px !important;
    background: rgba(21, 21, 31, 0.5) !important;
    border-radius: 10px !important;
    padding: 6px !important;
    flex-wrap: wrap !important;
    border: 1px solid rgba(139,92,246,0.15) !important;
    margin-bottom: 14px !important;
}
.app-tab-nav label {
    background: transparent !important;
    color: #94a3b8 !important;
    padding: 9px 18px !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    margin: 0 !important;
    border: 1px solid transparent !important;
}
.app-tab-nav label:hover {
    background: rgba(139,92,246,0.1) !important;
    color: #c4b5fd !important;
}
.app-tab-nav label > div:first-child { display: none !important; }
.app-tab-nav label:has(input:checked) {
    background: linear-gradient(135deg, #8b5cf6, #6366f1) !important;
    color: #fff !important;
    box-shadow: 0 2px 10px rgba(139,92,246,0.35) !important;
}

/* Mobile Studio: live-frame thu nhỏ vừa khung */
@media (max-width: 640px) {
    .live-frame { max-width: 100%; }
    .live-overlay-info { font-size: 0.78rem !important; padding: 6px 10px; }
    .studio-img-title { font-size: 1rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# SESSION INIT
# ══════════════════════════════════════════════════════════════
init_app_state()


# ══════════════════════════════════════════════════════════════
# LOGIN / REGISTER
# ══════════════════════════════════════════════════════════════
def render_login_screen():
    st.markdown("<div class='login-shell'>", unsafe_allow_html=True)
    st.markdown("""
        <div class="login-card">
            <div class="login-brand">&#128444;</div>
            <h1 class="login-title">Media Tool Pro VIP</h1>
            <p class="login-sub">v9.3 &middot; Secure Workspace</p>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐 Đăng nhập", "📝 Đăng ký"])

    with tab_login:
        username = st.text_input("Tài khoản", placeholder="Tên đăng nhập", key="login_user")
        password = st.text_input("Mật khẩu", type="password", placeholder="••••••••", key="login_pwd")
        if st.button("ĐĂNG NHẬP", type="primary", use_container_width=True, key="btn_login"):
            ok, msg, user_data = authenticate(username, password)
            if ok:
                st.session_state.logged_in = True
                st.session_state.auth_user = user_data
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab_register:
        st.caption("Tài khoản mới sẽ ở trạng thái **chờ Admin duyệt**.")
        new_user = st.text_input("Tài khoản mới", placeholder="≥ 3 ký tự (a-z, 0-9, _, -)", key="reg_user")
        new_pwd = st.text_input("Mật khẩu", type="password", placeholder="≥ 4 ký tự", key="reg_pwd")
        new_pwd2 = st.text_input("Nhập lại mật khẩu", type="password", key="reg_pwd2")
        if st.button("ĐĂNG KÝ", type="primary", use_container_width=True, key="btn_register"):
            if new_pwd != new_pwd2:
                st.error("Hai lần nhập mật khẩu không khớp.")
            else:
                ok, msg = register_user(new_user, new_pwd)
                if ok:
                    st.success(msg)
                    st.info("⏳ Liên hệ Admin (ducpro) để được duyệt.")
                else:
                    st.error(msg)

    st.markdown("</div>", unsafe_allow_html=True)


if not st.session_state.logged_in or not st.session_state.auth_user:
    render_login_screen()
    st.stop()


user = st.session_state.auth_user
is_admin = user.get("role") == "admin"


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
        <div class="sb-logo-wrap">
            <div class="sb-logo-icon">&#128444;</div>
            <div class="sb-logo-title">Media Tool Pro VIP</div>
            <div class="sb-logo-sub">v9.3 &middot; Live Preview</div>
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
        <h1>&#128444; Workspace &middot; {user['username']}</h1>
        <p>v9.3 · Live Preview Studio · Auto-sync GitHub · Mobile-ready</p>
    </div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# CONFIG PANEL
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
            custom_w = cw.number_input("Width", 100, 8000, 1200, 10, key="cfg_cw")
            custom_h = ch.number_input("Height", 100, 8000, 1200, 10, key="cfg_ch")

        st.markdown('<div class="cfg-label">🎛️ Output & hiệu năng</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            quality = st.slider("Chất lượng", 60, 100, 95, 1, key="cfg_quality")
            export_format = st.selectbox("Định dạng", list(EXPORT_FORMATS.keys()), 0, key="cfg_format")
        with c2:
            default_scale_pct = st.slider("Scale (%)", 60, 200, 100, 1, key="cfg_scale")
            max_workers = st.slider("Luồng xử lý", 1, 8, 4, 1, key="cfg_workers")

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
            rename_enabled = st.toggle("Sửa tên sau quét", value=True, key="cfg_rename")
            huge_image_mode = st.toggle("Tối ưu ảnh lớn", value=True, key="cfg_huge")
        with c4:
            zip_compression = st.slider("Nén ZIP", 0, 9, 6, 1, key="cfg_zip_compress")

    sizes_list = []
    for label in selected_labels:
        if label in SIZE_PRESETS:
            sizes_list.append(SIZE_PRESETS[label])
    if custom_size_on:
        sizes_list.append((int(custom_w), int(custom_h), "letterbox"))
    if not sizes_list:
        sizes_list = [SIZE_PRESETS["1020×680 TGDD chuẩn"]]

    return {
        "sizes": sizes_list,
        "default_scale_pct": int(default_scale_pct),
        "scale_pct": int(default_scale_pct),
        "quality": int(quality),
        "export_format": export_format,
        "template": template or "{name}_{color}_{nn}",
        "rename": bool(rename_enabled),
        "max_workers": int(max_workers),
        "huge_image_mode": bool(huge_image_mode),
        "zip_compression": int(zip_compression),
    }


config = render_config_panel()


# ══════════════════════════════════════════════════════════════
# TABS — Phân quyền hiển thị
# ══════════════════════════════════════════════════════════════
tab_labels = []
tab_keys = []

if has_permission(user, "web"):
    tab_labels.append("🛒 Web TGDD")
    tab_keys.append("web")
if has_permission(user, "studio"):
    tab_labels.append("🎚 Studio")
    tab_keys.append("studio")
if has_permission(user, "drive"):
    tab_labels.append("🌐 Drive")
    tab_keys.append("drive")
if has_permission(user, "local"):
    tab_labels.append("💻 Local ZIP")
    tab_keys.append("local")

tab_labels.append("📖 Hướng dẫn")
tab_keys.append("guide")

if is_admin:
    tab_labels.append("👑 Admin")
    tab_keys.append("admin")

if not tab_keys or tab_keys == ["guide"]:
    st.warning("⚠️ Tài khoản chưa được cấp quyền truy cập tab xử lý. Liên hệ Admin để được duyệt.")

# ──────────────────────────────────────────────────────────────
# AUTO-SWITCH SANG STUDIO khi vừa render xong ở tab khác
# ──────────────────────────────────────────────────────────────
if "active_tab_key" not in st.session_state:
    st.session_state.active_tab_key = tab_keys[0] if tab_keys else "guide"

# Nếu mode Web/Drive/Local vừa set cờ _goto_studio → tự chuyển sang tab Studio
if st.session_state.pop("_goto_studio", False) and "studio" in tab_keys:
    st.session_state.active_tab_key = "studio"
    st.session_state["_studio_just_arrived"] = True

if st.session_state.active_tab_key not in tab_keys:
    st.session_state.active_tab_key = tab_keys[0]

# Có batch mới chưa xem ở Studio → highlight tab Studio (badge nháy)
current_batch_id = st.session_state.get("last_batch_meta", {}).get("batch_id")
studio_has_new = bool(current_batch_id) and (
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

# Đánh dấu đã xem batch khi vào Studio (tắt chấm đỏ)
if selected_key == "studio":
    st.session_state["_studio_seen_batch_id"] = current_batch_id

key = selected_key
if key == "web":
    if run_mode_web is None:
        st.error(f"❌ Module mode_web.py lỗi: {_err_web}")
    else:
        run_mode_web(config)

elif key == "studio":
    if render_adjustment_studio is None:
        st.error(f"❌ Module mode_adjust.py lỗi: {_err_adjust}")
    else:
        render_adjustment_studio()

elif key == "drive":
    if run_mode_drive is None:
        st.error(f"❌ Module mode_drive.py lỗi: {_err_drive}")
    else:
        drive_service = get_gdrive_service()
        run_mode_drive(config, drive_service)

elif key == "local":
    if run_mode_local is None:
        st.error(f"❌ Module mode_local.py lỗi: {_err_local}")
    else:
        run_mode_local(config)

elif key == "guide":
    st.markdown("""
        <div class='guide-box'>
        <div style='font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:8px'>
        📌 Media Tool Pro VIP v9.3 — Hướng dẫn nhanh
        </div>
        <b>1.</b> Đăng ký → Admin duyệt và cấp quyền tab.<br>
        <b>2.</b> Mỗi tab tương ứng một quyền riêng.<br>
        <b>3.</b> <b>Web TGDD:</b> dán link → quét → chọn màu → resize.<br>
        <b>4.</b> <b>Studio:</b> chỉnh từng ảnh sau batch → render lại.
            Sau khi render xong ở các tab khác sẽ <b>tự chuyển</b> sang Studio.
            Có <b>Live Preview</b> giãn/dịch ảnh ngay theo slider.<br>
        <b>5.</b> <b>Drive / Local:</b> xử lý ảnh từ Drive hoặc ZIP.<br>
        <b>6.</b> Cấu hình GitHub Sync trong Streamlit Secrets:<br>
        &nbsp;&nbsp;<code>GITHUB_TOKEN</code>, <code>GITHUB_REPO</code>, <code>GITHUB_BRANCH</code>
        </div>
    """, unsafe_allow_html=True)

elif key == "admin":
    try:
        render_admin_panel()
    except Exception as e:
        st.warning(f"Admin Panel lỗi: {e}")
