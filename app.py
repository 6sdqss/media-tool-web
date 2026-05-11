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
   MEDIA TOOL PRO — Premium Design System v10.2
   Primary purple sampled from reference UI: #6238e5
   ══════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ─── HIDE CHROME ── */
#MainMenu,header,footer,.stDeployButton,[data-testid="stToolbar"]{
    visibility:hidden!important;display:none!important;
}

/* ─── DESIGN TOKENS ── */
:root {
    --p:         #6238e5;   /* Primary purple — exact from UI */
    --p-dark:    #4f28c9;   /* Hover/pressed */
    --p-deep:    #3a1da8;   /* Active/focused */
    --p-10:      #f0ebff;   /* 10% tint — active nav bg */
    --p-15:      #e8dffd;   /* 15% tint */
    --p-20:      #ddd4fc;   /* 20% tint */
    --p-40:      #b9a8f7;   /* 40% — borders on purple */
    --p-text:    #5030cc;   /* Purple text on white — readable */

    --bg:        #f5f7fb;   /* Workspace bg */
    --surface:   #ffffff;   /* Cards */
    --border:    #e2e6ed;   /* Default border */
    --border-2:  #c9d0dc;   /* Stronger border */

    --tx-1:      #0d1117;   /* Heading — near black */
    --tx-2:      #1e293b;   /* Body primary */
    --tx-3:      #475569;   /* Secondary */
    --tx-4:      #7c8b9e;   /* Muted */
    --tx-5:      #a0aec0;   /* Placeholder */

    --ok:        #0d9e6e;
    --ok-bg:     #d1fae5;
    --ok-bd:     #6ee7b7;
    --warn:      #c2830a;
    --warn-bg:   #fef3c7;
    --warn-bd:   #fcd34d;
    --err:       #c8192e;
    --err-bg:    #fee2e2;
    --err-bd:    #fca5a5;

    --sh-xs: 0 1px 2px rgba(13,17,23,.06);
    --sh-sm: 0 1px 4px rgba(13,17,23,.08), 0 4px 16px rgba(13,17,23,.04);
    --sh-md: 0 4px 12px rgba(13,17,23,.1), 0 12px 32px rgba(13,17,23,.07);
    --sh-lg: 0 8px 24px rgba(13,17,23,.12), 0 24px 48px rgba(13,17,23,.09);

    --r-xs: 5px;
    --r-sm: 8px;
    --r-md: 12px;
    --r-lg: 16px;
}

/* ─── BASE ── */
html,body,[class*="css"]{
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
    font-size:14px!important;
    line-height:1.6!important;
    -webkit-font-smoothing:antialiased!important;
    color:var(--tx-2)!important;
}

/* ─── APP BACKGROUND ── */
.stApp{
    background:var(--bg)!important;
    background-image:
        radial-gradient(ellipse 60% 40% at 10% -5%,rgba(98,56,229,.07) 0%,transparent 60%),
        radial-gradient(ellipse 50% 35% at 95% 105%,rgba(98,56,229,.05) 0%,transparent 55%)!important;
}

/* ─── MAIN CONTAINER ── */
.block-container{
    max-width:1100px!important;
    padding:1.5rem 1.75rem 3rem!important;
}
@media(max-width:768px){
    .block-container{max-width:100%!important;padding:.75rem .75rem 2rem!important;}
}
@media(min-width:641px)and(max-width:1024px){
    .block-container{max-width:980px!important;}
}

/* ─── SIDEBAR ── */
section[data-testid="stSidebar"]{
    background:var(--surface)!important;
    border-right:1.5px solid var(--border)!important;
    box-shadow:3px 0 16px rgba(13,17,23,.06)!important;
    width:260px!important;
}
section[data-testid="stSidebar"]>div{padding-top:.75rem!important;}
section[data-testid="stSidebar"] *{
    font-size:13.5px!important;
    color:var(--tx-3)!important;
}
section[data-testid="stSidebar"] hr{
    border:none!important;
    border-top:1px solid var(--border)!important;
    margin:10px 0!important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]{
    background:var(--bg)!important;
    border:1px solid var(--border)!important;
    border-radius:var(--r-sm)!important;
}
section[data-testid="stSidebar"] .stButton button{
    font-size:13px!important;min-height:34px!important;padding:4px 12px!important;
}

/* ─── APP HEADER ── */
.app-header{
    background:var(--surface);
    border:1.5px solid var(--border);
    border-radius:var(--r-md);
    padding:18px 24px;
    margin-bottom:20px;
    box-shadow:var(--sh-sm);
    display:flex;align-items:center;gap:16px;
}
.app-header-icon{
    flex-shrink:0;
    width:46px;height:46px;border-radius:14px;
    background:linear-gradient(135deg,var(--p) 0%,#8b6ff4 100%);
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 4px 14px rgba(98,56,229,.35);
    position:relative;overflow:hidden;
}
.app-header-icon::before{
    content:'';position:absolute;top:-10px;left:-10px;
    width:30px;height:30px;border-radius:50%;
    background:rgba(255,255,255,.15);
}
.app-header-body{flex:1;min-width:0;}
.app-header h1{
    margin:0 0 4px;
    font-size:1.2rem!important;
    font-weight:800!important;
    color:var(--tx-1)!important;
    letter-spacing:-.4px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.app-header p{
    margin:0;font-size:.78rem;color:var(--tx-4);
    display:flex;align-items:center;gap:6px;flex-wrap:wrap;
}
/* Feature badges like screenshot */
.hdr-badge{
    display:inline-flex;align-items:center;
    font-size:.68rem;font-weight:700;padding:2px 9px;
    border-radius:999px;letter-spacing:.2px;
    border:1.5px solid;white-space:nowrap;
}
.hdr-badge.v{ background:var(--p);color:#fff;border-color:var(--p); }
.hdr-badge.w{ background:var(--surface);color:var(--tx-3);border-color:var(--border-2); }
.hdr-badge.ok{ background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd); }

/* ─── HERO CARD ── */
.hero-card{
    background:var(--surface);
    border:1.5px solid var(--border);
    border-left:4px solid var(--p);
    border-radius:var(--r-md);
    padding:16px 20px;margin-bottom:16px;
    box-shadow:var(--sh-xs);
}
.hero-card h2{
    margin:0 0 5px;
    color:var(--tx-1)!important;
    font-size:1.05rem!important;font-weight:700!important;
    letter-spacing:-.2px;
}
.hero-card p{margin:0;color:var(--tx-3);font-size:.88rem;line-height:1.7;}
.hero-card b{color:var(--tx-2);font-weight:600;}

/* ─── CARDS / BORDERED CONTAINERS ── */
div[data-testid="stVerticalBlockBorderWrapper"]{
    border-radius:var(--r-md)!important;
    border:1.5px solid var(--border)!important;
    padding:18px!important;
    background:var(--surface)!important;
    box-shadow:var(--sh-xs)!important;
    transition:box-shadow .18s,border-color .18s!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover{
    box-shadow:var(--sh-sm)!important;
}

/* ─── SECTION TITLES — match screenshot style ── */
.sec-title{
    display:inline-flex;align-items:center;gap:8px;
    font-size:.72rem!important;font-weight:700!important;
    color:var(--p-text)!important;
    text-transform:uppercase;letter-spacing:1px;
    margin:20px 0 10px!important;padding:0;
}
/* Horizontal rule after (Figma/Linear style) */
.sec-title-row{
    display:flex;align-items:center;gap:10px;
    margin:20px 0 10px;
}
.sec-title-row .sec-title{margin:0!important;}
.sec-title-row::after{
    content:'';flex:1;height:1px;background:var(--border);
}
.cfg-label{
    font-size:.82rem!important;font-weight:600!important;
    color:var(--tx-2)!important;
    margin-bottom:6px!important;margin-top:4px!important;
}
.tpl-hint{font-size:.74rem;color:var(--tx-4);margin-top:4px;}
.tpl-hint code{
    background:var(--p-10);color:var(--p);
    padding:1px 7px;border-radius:var(--r-xs);
    font-size:.7rem;font-weight:700;
}

/* ─── GUIDE BOX ── */
.guide-box{
    background:var(--surface);border:1.5px solid var(--border);
    border-radius:var(--r-sm);padding:12px 16px;
    font-size:.86rem;color:var(--tx-3);
    margin-bottom:12px;line-height:1.75;
}
.guide-box b{color:var(--tx-2);font-weight:600;}

/* ─── LOG BOX ── */
.log-box{
    background:#0d1117!important;color:#4ade80!important;
    font-family:'JetBrains Mono','Fira Code',monospace!important;
    font-size:.74rem!important;padding:12px!important;
    border-radius:var(--r-sm)!important;
    max-height:200px!important;overflow-y:auto!important;
    border:1px solid rgba(74,222,128,.12)!important;
    line-height:1.65!important;
}

/* ─── SUMMARY CARD ── */
.summary-card{
    background:linear-gradient(135deg,#f0fdf8,#d1fae5);
    border:1.5px solid var(--ok-bd);
    border-radius:var(--r-sm);padding:14px 18px;margin:10px 0;
    font-size:.9rem;line-height:1.75;color:#064e3b;
}
.summary-card b{color:#047857;}

/* ─── PREVIEW META ── */
.preview-meta{text-align:center;font-size:.75rem;color:var(--tx-4);margin-top:5px;}

/* ─── BUTTONS — Rich purple like screenshot ── */
.stButton>button,.stDownloadButton>button{
    background:linear-gradient(160deg,var(--p) 0%,#7b52f5 100%)!important;
    color:#fff!important;
    border-radius:var(--r-sm)!important;
    border:none!important;
    font-weight:700!important;
    font-size:13.5px!important;
    min-height:38px!important;
    padding:7px 18px!important;
    box-shadow:0 2px 8px rgba(98,56,229,.32),inset 0 1px 0 rgba(255,255,255,.12)!important;
    transition:all .14s cubic-bezier(.4,.7,.2,1)!important;
    letter-spacing:.1px;
}
.stButton>button:hover,.stDownloadButton>button:hover{
    background:linear-gradient(160deg,var(--p-dark) 0%,#6640e8 100%)!important;
    box-shadow:0 5px 16px rgba(98,56,229,.42)!important;
    transform:translateY(-1px)!important;
}
.stButton>button:active{transform:translateY(0)!important;box-shadow:0 1px 4px rgba(98,56,229,.25)!important;}
.stButton>button:focus-visible{outline:2px solid var(--p)!important;outline-offset:2px!important;}
button[kind="secondary"]{
    background:var(--surface)!important;color:var(--tx-2)!important;
    border:1.5px solid var(--border-2)!important;
    box-shadow:var(--sh-xs)!important;font-weight:500!important;
}
button[kind="secondary"]:hover{background:var(--bg)!important;border-color:var(--tx-4)!important;}
.stButton>button:disabled,.stDownloadButton>button:disabled{
    background:var(--bg)!important;color:var(--tx-5)!important;
    border:1.5px solid var(--border)!important;
    box-shadow:none!important;cursor:not-allowed!important;transform:none!important;
}

/* ─── INPUTS ── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input{
    background:var(--surface)!important;
    border:1.5px solid var(--border-2)!important;
    border-radius:var(--r-sm)!important;
    color:var(--tx-1)!important;
    font-size:14px!important;
    min-height:40px!important;
    padding:9px 14px!important;
    transition:border-color .14s,box-shadow .14s!important;
}
.stTextInput input:focus,.stTextArea textarea:focus,.stNumberInput input:focus{
    border-color:var(--p)!important;
    box-shadow:0 0 0 3px rgba(98,56,229,.14)!important;
}
.stTextInput input::placeholder,.stTextArea textarea::placeholder{
    color:var(--tx-5)!important;font-weight:400!important;
}
.stTextArea textarea{min-height:90px!important;}
.stSelectbox div[data-baseweb="select"]>div,
.stMultiSelect div[data-baseweb="select"]>div{
    background:var(--surface)!important;
    border:1.5px solid var(--border-2)!important;
    border-radius:var(--r-sm)!important;
    color:var(--tx-1)!important;font-size:13.5px!important;
    min-height:40px!important;
}

/* ─── LABELS ── */
.stTextInput label,.stTextArea label,.stSelectbox label,
.stNumberInput label,.stSlider label,.stMultiSelect label,
.stRadio label,.stCheckbox label,.stToggle label{
    font-size:13px!important;font-weight:600!important;
    color:var(--tx-2)!important;letter-spacing:.05px;
}

/* ─── SLIDERS — rich purple ── */
.stSlider [data-baseweb="slider"]>div>div{
    background:linear-gradient(90deg,var(--p),#8b6ff4)!important;
    height:4px!important;border-radius:2px!important;
}
.stSlider [data-baseweb="slider"]>div>div:first-child{
    background:var(--border)!important;
}
.stSlider [role="slider"]{
    background:var(--surface)!important;
    border:2.5px solid var(--p)!important;
    box-shadow:0 2px 6px rgba(98,56,229,.35)!important;
    width:18px!important;height:18px!important;
    transition:transform .1s,box-shadow .1s!important;
}
.stSlider [role="slider"]:hover{
    transform:scale(1.25)!important;
    box-shadow:0 3px 10px rgba(98,56,229,.45)!important;
}

/* ─── TABS ── */
.stTabs [data-baseweb="tab-list"]{
    gap:2px!important;background:var(--bg)!important;
    border-radius:var(--r-sm)!important;padding:4px!important;
    overflow-x:auto;flex-wrap:nowrap!important;
    border:1.5px solid var(--border)!important;
}
.stTabs [data-baseweb="tab"]{
    height:36px!important;padding:0 16px!important;
    border-radius:var(--r-xs)!important;
    color:var(--tx-3)!important;font-size:13px!important;
    font-weight:500!important;white-space:nowrap!important;
    background:transparent!important;border:none!important;
    transition:all .14s!important;
}
.stTabs [data-baseweb="tab"]:hover{
    color:var(--tx-1)!important;background:var(--surface)!important;
}
.stTabs [aria-selected="true"]{
    background:var(--surface)!important;color:var(--p)!important;
    box-shadow:var(--sh-xs)!important;font-weight:700!important;
}

/* ─── EXPANDER ── */
[data-testid="stExpander"]{
    background:var(--surface)!important;
    border:1.5px solid var(--border)!important;
    border-radius:var(--r-md)!important;
    box-shadow:var(--sh-xs)!important;overflow:hidden!important;
}
[data-testid="stExpander"] summary{
    font-size:13.5px!important;font-weight:600!important;
    color:var(--tx-2)!important;padding:12px 18px!important;
}
[data-testid="stExpander"] summary:hover{background:var(--bg)!important;}

/* ─── METRICS ── */
[data-testid="stMetric"]{
    background:var(--surface);border:1.5px solid var(--border);
    padding:14px 16px!important;border-radius:var(--r-md);
    box-shadow:var(--sh-xs);transition:box-shadow .15s!important;
}
[data-testid="stMetric"]:hover{box-shadow:var(--sh-sm)!important;}
[data-testid="stMetricLabel"]{
    font-size:.72rem!important;font-weight:600!important;
    color:var(--tx-4)!important;text-transform:uppercase;letter-spacing:.7px;
}
[data-testid="stMetricValue"]{
    font-size:1.45rem!important;font-weight:900!important;
    color:var(--tx-1)!important;letter-spacing:-.4px;
}

/* ─── ALERTS ── */
[data-testid="stAlert"]{
    border-radius:var(--r-sm)!important;
    padding:12px 16px!important;
    font-size:13.5px!important;
    border-width:1.5px!important;
}

/* ─── CAPTION ── */
.stCaption,[data-testid="stCaptionContainer"]{
    font-size:.78rem!important;color:var(--tx-4)!important;line-height:1.5!important;
}

/* ─── PROGRESS BAR ── */
.stProgress>div>div>div>div{
    background:linear-gradient(90deg,var(--p) 0%,#9b7ff7 100%)!important;
    border-radius:2px!important;
}
.stProgress>div>div{height:5px!important;background:var(--border)!important;border-radius:2px!important;}

/* ─── CHECKBOX & TOGGLE ── */
.stCheckbox label,.stToggle label{font-size:13.5px!important;color:var(--tx-2)!important;}

/* ─── SPINNER ── */
.stSpinner>div{border-top-color:var(--p)!important;}

/* ─── SCROLLBAR ── */
::-webkit-scrollbar{width:7px;height:7px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--border-2);border-radius:10px;}
::-webkit-scrollbar-thumb:hover{background:var(--tx-4);}

/* ─── DIVIDER ── */
hr{border:none!important;border-top:1.5px solid var(--border)!important;margin:16px 0!important;}

/* ─── MOBILE ── */
@media(max-width:640px){
    .app-header h1{font-size:1rem!important;}
    .stTabs [data-baseweb="tab-list"]{
        position:sticky;top:0;z-index:99;
        background:rgba(245,247,251,.97)!important;
        backdrop-filter:blur(12px);
    }
    .stTabs [data-baseweb="tab"]{padding:0 11px!important;font-size:12.5px!important;}
    .login-shell{padding:0 12px;}
    section[data-testid="stSidebar"]{width:88vw!important;}
    .block-container{padding:.5rem!important;}
    .stButton>button,.stDownloadButton>button{min-height:44px!important;}
}

/* ─── LOGIN ── */
.login-shell{max-width:400px;margin:3.5rem auto 0;}
.login-card{
    background:var(--surface);border-radius:var(--r-lg);
    padding:34px 32px 26px;
    border:1.5px solid var(--border);
    box-shadow:var(--sh-lg);
}
.login-brand{
    width:58px;height:58px;border-radius:16px;margin:0 auto 18px;
    display:flex;align-items:center;justify-content:center;
    background:linear-gradient(135deg,var(--p) 0%,#8b6ff4 100%);
    color:#fff;box-shadow:0 8px 24px rgba(98,56,229,.32);
    position:relative;overflow:hidden;
}
.login-brand::before{
    content:'';position:absolute;top:-8px;left:-8px;
    width:26px;height:26px;border-radius:50%;
    background:rgba(255,255,255,.18);
}
.login-title{text-align:center;color:var(--tx-1)!important;font-weight:900;font-size:1.3rem;margin:0;letter-spacing:-.4px;}
.login-sub{text-align:center;color:var(--tx-4);margin:5px 0 22px;font-size:.82rem;}

/* ─── USER CHIP ── */
.user-chip{
    background:var(--p-10);border-radius:var(--r-sm);
    padding:12px 14px;border:1.5px solid var(--p-20);margin-bottom:8px;
}
.user-chip b{color:var(--tx-1)!important;font-size:.95rem!important;font-weight:800!important;}
.user-chip span{color:var(--p-text)!important;font-size:.74rem!important;font-weight:600!important;}

/* ─── SIDEBAR LOGO — Modern grid icon matching screenshot ── */
.sb-logo-wrap{text-align:center;padding:10px 0 6px;}
.sb-logo-icon{
    width:44px;height:44px;margin:0 auto 10px;
    border-radius:13px;
    background:linear-gradient(135deg,var(--p) 0%,#9b7ff7 100%);
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 5px 18px rgba(98,56,229,.3);
    position:relative;overflow:hidden;
}
.sb-logo-icon::after{
    content:'';position:absolute;top:-12px;left:-12px;
    width:32px;height:32px;border-radius:50%;
    background:rgba(255,255,255,.16);pointer-events:none;
}
.sb-logo-title{font-weight:800!important;font-size:.9rem!important;color:var(--tx-1)!important;letter-spacing:-.2px;}
.sb-logo-sub{font-size:.68rem!important;color:var(--p-text)!important;margin-top:2px;font-weight:600!important;}

/* ─── HISTORY ── */
.history-item{padding:7px 0;border-bottom:1px solid var(--bg);}
.hi-top{font-size:.8rem!important;color:var(--tx-2)!important;margin-bottom:1px;font-weight:500;}
.hi-top b{color:var(--tx-1)!important;}
.hi-bot{font-size:.72rem!important;color:var(--tx-4)!important;}

/* ─── STAT PILLS ── */
.stat-row{display:flex;gap:5px;margin:5px 0 8px;}
.stat-pill{flex:1;border-radius:var(--r-xs);padding:9px 4px;text-align:center;border:1.5px solid;}
.stat-a{background:var(--p-10);border-color:var(--p-20);}
.stat-b{background:var(--ok-bg);border-color:var(--ok-bd);}
.stat-c{background:var(--warn-bg);border-color:var(--warn-bd);}
.sp-num{font-size:.95rem!important;font-weight:900!important;display:block;}
.stat-a .sp-num{color:var(--p)!important;}
.stat-b .sp-num{color:var(--ok)!important;}
.stat-c .sp-num{color:var(--warn)!important;}
.sp-lbl{font-size:.6rem!important;color:var(--tx-4)!important;text-transform:uppercase;letter-spacing:.6px;margin-top:1px;display:block;}

/* ─── CTRL ROW ── */
.ctrl-row{background:var(--bg);border-radius:var(--r-sm);padding:8px;margin:8px 0;border:1.5px solid var(--border);}

/* ─── APP NAV TABS (radio-as-tabs) — match sidebar nav style ── */
div[data-testid="stRadio"][aria-label="_app_tab_nav"]>div[role="radiogroup"],
.app-tab-nav div[role="radiogroup"]{
    gap:2px!important;background:var(--bg)!important;
    border-radius:var(--r-md)!important;padding:5px!important;
    flex-wrap:wrap!important;
    border:1.5px solid var(--border)!important;
    margin-bottom:18px!important;
}
.app-tab-nav label{
    background:transparent!important;color:var(--tx-3)!important;
    padding:8px 16px!important;border-radius:var(--r-xs)!important;
    font-weight:500!important;font-size:13.5px!important;
    cursor:pointer!important;transition:all .14s ease!important;
    margin:0!important;border:1.5px solid transparent!important;
}
.app-tab-nav label:hover{background:var(--surface)!important;color:var(--tx-2)!important;}
.app-tab-nav label>div:first-child{display:none!important;}
/* Active tab — matches screenshot purple pill */
.app-tab-nav label:has(input:checked){
    background:var(--p-10)!important;
    color:var(--p)!important;
    border-color:var(--p-20)!important;
    font-weight:700!important;
    box-shadow:none!important;
}

/* ─── CHECKED ROW HIGHLIGHT ── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(input[type="checkbox"]:checked){
    border-color:var(--p)!important;
    box-shadow:0 0 0 2px rgba(98,56,229,.1),var(--sh-sm)!important;
}

/* ══════════════════════════════════════════════════════════════
   STUDIO TAB
   ══════════════════════════════════════════════════════════════ */
.studio-wrap{font-size:14px!important;}
.studio-wrap .stTextInput label,.studio-wrap .stSelectbox label,
.studio-wrap .stNumberInput label,.studio-wrap .stSlider label,
.studio-wrap .stCheckbox label{
    font-size:13px!important;font-weight:600!important;color:var(--tx-2)!important;
}
.studio-wrap .stButton>button{min-height:40px!important;font-size:13.5px!important;}
.studio-wrap div[data-testid="stVerticalBlockBorderWrapper"]{padding:18px!important;margin-bottom:14px!important;}
@media(min-width:1200px){
    .studio-wrap .block-container{max-width:1420px!important;}
}

/* ─── LIVE PREVIEW FRAME ── */
.live-frame{
    position:relative;width:100%;max-width:520px;margin:0 auto;
    background:#fff;border:2px solid var(--border-2);
    border-radius:var(--r-sm);overflow:hidden;
    box-shadow:var(--sh-md);
}
.live-frame::after{
    content:'PREVIEW';position:absolute;bottom:0;right:0;
    font-size:.58rem;font-weight:700;color:var(--tx-4);
    background:rgba(245,247,251,.9);padding:2px 7px;
    border-radius:var(--r-xs) 0 0 0;letter-spacing:.8px;
    pointer-events:none;z-index:5;
}
.live-frame--empty{
    display:flex;align-items:center;justify-content:center;
    aspect-ratio:3/2;color:var(--err);font-size:.9rem;
    background:var(--err-bg);border-color:var(--err-bd);
}
.live-canvas{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#fff;}
.live-img{
    width:100%;height:100%;object-fit:contain;object-position:center;
    transform-origin:center center;
    transition:transform .1s cubic-bezier(.4,.7,.2,1);
    will-change:transform;user-select:none;-webkit-user-drag:none;
}
.live-overlay{
    position:absolute;bottom:0;left:0;right:0;
    display:flex;flex-wrap:wrap;gap:4px 10px;padding:5px 10px;
    background:linear-gradient(180deg,rgba(255,255,255,0) 0%,rgba(13,17,23,.35) 100%);
    color:#f8fafc;font-size:.72rem!important;font-weight:600;z-index:2;pointer-events:none;
}
.live-overlay span{white-space:nowrap;}

/* ─── RENDERED FRAME ── */
.rendered-frame{
    background:#fff;border-radius:var(--r-sm);
    border:2px solid var(--ok-bd);overflow:hidden;padding:4px;
    box-shadow:0 2px 8px rgba(13,163,114,.1);position:relative;
}
.rendered-frame::after{
    content:'✓ OUTPUT';position:absolute;top:0;right:0;
    font-size:.56rem;font-weight:700;color:var(--ok);
    background:var(--ok-bg);padding:2px 7px;
    border-radius:0 0 0 var(--r-xs);letter-spacing:.5px;pointer-events:none;z-index:5;
}
.rendered-frame img{max-width:100%;max-height:260px;object-fit:contain;display:block;margin:0 auto;position:relative;z-index:1;}

/* ─── STATUS PILLS ── */
.spill{display:inline-flex;align-items:center;gap:4px;font-size:.72rem;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap;border:1.5px solid;}
.spill-r{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd);}
.spill-a{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd);}
.spill-s{background:var(--bg);color:var(--tx-3);border-color:var(--border-2);}

/* ─── INFO PILLS ── */
.info-pills{display:flex;flex-wrap:wrap;gap:4px;margin:5px 0;}
.info-pill{font-size:.72rem;color:var(--tx-3);background:var(--bg);border:1.5px solid var(--border);border-radius:var(--r-xs);padding:2px 9px;white-space:nowrap;}
.info-pill b{color:var(--tx-2);font-weight:700;}
.size-info{font-size:.74rem;color:var(--tx-4);margin-top:4px;line-height:1.6;}
.size-info.output{color:var(--ok);font-weight:700;}

/* ─── EXPORT PANEL ── */
.export-panel{background:var(--surface);border:1.5px solid var(--border);border-radius:var(--r-lg);padding:22px 26px;margin-top:16px;box-shadow:var(--sh-sm);}
.export-panel h2{margin:0 0 6px;color:var(--tx-1);font-size:1.1rem;font-weight:800;}
.export-panel p{color:var(--tx-3);font-size:.88rem;margin:0;}

/* ─── STUDIO IMG TITLE ── */
.studio-img-title{font-size:.95rem!important;margin-bottom:8px!important;line-height:1.55;}
.studio-img-title b{color:var(--tx-1)!important;font-size:.95rem!important;font-weight:700!important;}
.studio-img-title code{font-size:.8rem!important;color:var(--p)!important;background:var(--p-10);padding:2px 7px;border-radius:var(--r-xs);word-break:break-all;}

/* ─── STUDIO FRESH BANNER ── */
.studio-fresh-banner{background:var(--ok-bg);border:1.5px solid var(--ok-bd);border-radius:var(--r-sm);padding:12px 18px;margin:6px 0 14px;font-size:.9rem;color:#064e3b;font-weight:600;}

/* ─── WORKFLOW SIDEBAR WIDGET ── */
.wf-block{
    background:var(--bg);border:1.5px solid var(--border);
    border-radius:var(--r-sm);padding:12px 14px;margin-top:8px;
}
.wf-title{
    font-size:.72rem;font-weight:700;color:var(--p-text);
    text-transform:uppercase;letter-spacing:.8px;
    margin-bottom:10px;display:flex;align-items:center;gap:6px;
}
.wf-item{
    display:flex;align-items:flex-start;gap:10px;
    padding:6px 0;border-bottom:1px solid var(--border);
    font-size:.82rem;color:var(--tx-3);line-height:1.45;
}
.wf-item:last-child{border-bottom:none;padding-bottom:0;}
.wf-num{
    flex-shrink:0;
    width:20px;height:20px;border-radius:50%;
    background:var(--p);color:#fff;
    font-size:.68rem;font-weight:800;
    display:flex;align-items:center;justify-content:center;
    margin-top:1px;
}

@media(max-width:640px){
    .live-frame{max-width:100%;}
    .live-overlay{font-size:.68rem!important;padding:4px 8px;}
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
            <div class="sb-logo-sub">v10.2 &middot; Premium Studio</div>
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
    st.markdown("""
        <div class="wf-block">
            <div class="wf-title">⚡ Workflow TGDD</div>
            <div class="wf-item"><div class="wf-num">1</div><span>Nạp cookie</span></div>
            <div class="wf-item"><div class="wf-num">2</div><span>Dán link sản phẩm</span></div>
            <div class="wf-item"><div class="wf-num">3</div><span>Quét dữ liệu</span></div>
            <div class="wf-item"><div class="wf-num">4</div><span>Chọn màu sắc</span></div>
            <div class="wf-item"><div class="wf-num">5</div><span>Resize ảnh</span></div>
            <div class="wf-item"><div class="wf-num">6</div><span>Sang Studio chỉnh sửa</span></div>
        </div>
    """, unsafe_allow_html=True)
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
