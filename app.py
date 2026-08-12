# -*- coding: utf-8 -*-
"""
app.py — Media Tool Pro VIP v10.2
─────────────────────────────────────────────────────────
CHANGELOG v10.2:
[FIX] CSS injection: st.markdown(<style>) chuyển hoàn toàn vào hàm _inject_global_css()
      được gọi SAU init_app_state() — tránh lỗi module-level side effects khi
      Streamlit hot-reload, tránh nhân đôi <style> block gây DOM phình to.
[FIX] Session guard '_global_css_v102': CSS chỉ inject 1 lần per session.
[UI]  Design system giữ nguyên 100%: Modern White Professional, token --p:#6238e5.
[COMPAT] Toàn bộ logic routing, sidebar, auth, config panel GIỮ NGUYÊN HOÀN TOÀN.
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
# PAGE CONFIG — phải là lệnh Streamlit đầu tiên
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Media Tool Pro VIP",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════
# CSS — Modern White Professional v10.2
# [FIX v10.2] Toàn bộ CSS nằm trong hàm _inject_global_css()
# KHÔNG inject ở module level. Gọi SAU init_app_state().
# ══════════════════════════════════════════════════════════════
def _inject_global_css():
    """
    Inject toàn bộ Design System CSS vào trang.

    [v10.2 KEY FIX] Hàm này PHẢI được gọi sau init_app_state() vì:
    1. Session guard dùng st.session_state — cần init trước.
    2. CSS ở module level gây st.markdown() trước set_page_config()
       → lỗi "StreamlitAPIException: set_page_config() can only be called once"
       khi file được import lại sau hot-reload.
    3. Session guard '_global_css_v102' đảm bảo CSS không bị inject nhiều lần
       trong cùng một phiên → tránh DOM phình to với nhiều <style> block.
    """
    if st.session_state.get("_global_css_v102"):
        return
    st.session_state["_global_css_v102"] = True

    st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════════
   MEDIA TOOL PRO — Maximalism / Dopamine Design System v11.0
   Dark cosmic base + 5-accent rotation (magenta/cyan/yellow/orange/purple)
   ══════════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;700;800;900&family=DM+Sans:wght@400;500;600;700;800&display=swap');

/* ─── HIDE CHROME ─── */
#MainMenu,header,footer,.stDeployButton,[data-testid="stToolbar"]{
    visibility:hidden!important;display:none!important;
}

/* ─── DESIGN TOKENS ─── */
:root {
    /* 5 accents kept under the same --p names used across every .py file
       so no other file needs to change — only the palette shifts. */
    --p:         #FF3AF2;   /* Accent — magenta */
    --p-dark:    #E020D6;
    --p-deep:    #A812A0;
    --p-10:      rgba(255,58,242,.10);
    --p-15:      rgba(255,58,242,.16);
    --p-20:      rgba(255,58,242,.22);
    --p-40:      rgba(255,58,242,.45);
    --p-text:    #FF7CF5;

    --acc-1:     #FF3AF2;   /* magenta */
    --acc-2:     #00F5D4;   /* cyan */
    --acc-3:     #FFE600;   /* yellow */
    --acc-4:     #FF6B35;   /* orange */
    --acc-5:     #7B2FFF;   /* purple */

    --bg:        #0D0D1A;
    --surface:   #1A1330;
    --muted:     #2D1B4E;
    --border:    #7B2FFF;
    --border-2:  #FF3AF2;

    --tx-1:      #FFFFFF;
    --tx-2:      #F3EEFF;
    --tx-3:      #C9BEEA;
    --tx-4:      #9C8FC4;
    --tx-5:      #6E6396;

    --ok:        #00F5D4;
    --ok-bg:     rgba(0,245,212,.12);
    --ok-bd:     #00F5D4;
    --warn:      #FFE600;
    --warn-bg:   rgba(255,230,0,.12);
    --warn-bd:   #FFE600;
    --err:       #FF3AF2;
    --err-bg:    rgba(255,58,242,.14);
    --err-bd:    #FF3AF2;

    --sh-xs: 0 0 0 1.5px rgba(255,58,242,.25);
    --sh-sm: 4px 4px 0 #7B2FFF, 8px 8px 0 rgba(255,58,242,.35);
    --sh-md: 6px 6px 0 #FFE600, 12px 12px 0 #FF3AF2;
    --sh-lg: 0 0 40px rgba(255,58,242,.35), 8px 8px 0 #00F5D4, 16px 16px 0 #7B2FFF;

    --r-xs: 8px;
    --r-sm: 12px;
    --r-md: 18px;
    --r-lg: 24px;
}

/* ─── BASE ─── */
html,body,[class*="css"]{
    font-family:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
    font-size:14px!important;
    line-height:1.6!important;
    -webkit-font-smoothing:antialiased!important;
    color:var(--tx-2)!important;
}
h1,h2,h3,.app-header h1,.hero-card h2,.login-title{
    font-family:'Outfit',sans-serif!important;
}

/* ─── APP BACKGROUND (layered pattern-on-pattern, per design system) ─── */
.stApp{
    background:var(--bg)!important;
    background-image:
        radial-gradient(ellipse at 15% 20%, rgba(255,58,242,.16) 0%, transparent 45%),
        radial-gradient(ellipse at 85% 15%, rgba(0,245,212,.13) 0%, transparent 45%),
        radial-gradient(ellipse at 50% 90%, rgba(123,47,255,.15) 0%, transparent 55%),
        radial-gradient(circle, rgba(255,255,255,.06) 1px, transparent 1px)!important;
    background-size:100% 100%,100% 100%,100% 100%,22px 22px!important;
}

/* ─── MAIN CONTAINER ─── */
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

/* ─── SIDEBAR ─── */
section[data-testid="stSidebar"]{
    background:var(--surface)!important;
    border-right:3px solid var(--acc-1)!important;
    box-shadow:6px 0 0 rgba(123,47,255,.25)!important;
    width:270px!important;
}
section[data-testid="stSidebar"]>div{padding-top:.75rem!important;}
section[data-testid="stSidebar"] *{font-size:13.5px!important;color:var(--tx-3)!important;}
section[data-testid="stSidebar"] hr{
    border:none!important;border-top:2px dashed var(--acc-5)!important;margin:10px 0!important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]{
    background:var(--muted)!important;border:2px solid var(--acc-2)!important;
    border-radius:var(--r-sm)!important;
}
section[data-testid="stSidebar"] .stButton button{
    font-size:13px!important;min-height:34px!important;padding:4px 12px!important;
}

/* ─── APP HEADER ─── */
.app-header{
    background:linear-gradient(120deg,var(--muted),var(--surface));
    border:3px solid var(--acc-2);
    border-radius:var(--r-md);padding:18px 24px;margin-bottom:20px;
    box-shadow:var(--sh-sm);display:flex;align-items:center;gap:16px;
    position:relative;overflow:hidden;
}
.app-header h1{
    margin:0 0 4px;font-size:1.35rem!important;font-weight:900!important;
    color:var(--tx-1)!important;letter-spacing:-.4px;text-transform:uppercase;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    text-shadow:2px 2px 0 var(--acc-5),4px 4px 0 var(--acc-1);
}
.app-header p{margin:0;font-size:.78rem;color:var(--tx-3);display:flex;align-items:center;gap:6px;flex-wrap:wrap;}

/* ─── HERO CARD ─── */
.hero-card{
    background:var(--surface);border:3px solid var(--acc-1);
    border-left:8px solid var(--acc-3);border-radius:var(--r-md);
    padding:16px 20px;margin-bottom:16px;box-shadow:var(--sh-sm);
}
.hero-card h2{
    margin:0 0 5px;color:var(--tx-1)!important;
    font-size:1.15rem!important;font-weight:800!important;letter-spacing:-.2px;
    text-shadow:2px 2px 0 var(--acc-5);
}
.hero-card p{margin:0;color:var(--tx-3);font-size:.88rem;line-height:1.7;}
.hero-card b{color:var(--tx-1);font-weight:700;}

/* ─── CARDS / BORDERED CONTAINERS ─── */
div[data-testid="stVerticalBlockBorderWrapper"]{
    border-radius:var(--r-md)!important;border:3px solid var(--acc-5)!important;
    padding:18px!important;background:var(--surface)!important;
    box-shadow:4px 4px 0 var(--acc-1)!important;
    transition:transform .18s,box-shadow .18s,border-color .18s!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover{
    box-shadow:6px 6px 0 var(--acc-2)!important;transform:translate(-2px,-2px)!important;
}

/* ─── SECTION TITLES ─── */
.sec-title{
    display:inline-flex;align-items:center;gap:8px;
    font-size:.76rem!important;font-weight:800!important;color:var(--acc-3)!important;
    text-transform:uppercase;letter-spacing:1.4px;margin:20px 0 10px!important;padding:0;
}
.cfg-label{
    font-size:.82rem!important;font-weight:700!important;
    color:var(--tx-2)!important;margin-bottom:6px!important;margin-top:4px!important;
}
.tpl-hint{font-size:.74rem;color:var(--tx-4);margin-top:4px;}
.tpl-hint code{
    background:var(--p-10);color:var(--acc-2);padding:1px 7px;
    border-radius:var(--r-xs);font-size:.7rem;font-weight:700;
}

/* ─── GUIDE BOX ─── */
.guide-box{
    background:var(--muted);border:2px dashed var(--acc-4);
    border-radius:var(--r-sm);padding:12px 16px;font-size:.86rem;
    color:var(--tx-3);margin-bottom:12px;line-height:1.75;
}
.guide-box b{color:var(--tx-1);font-weight:700;}

/* ─── LOG BOX ─── */
.log-box{
    background:#050510!important;color:#00F5D4!important;
    font-family:'JetBrains Mono','Fira Code',monospace!important;
    font-size:.74rem!important;padding:12px!important;
    border-radius:var(--r-sm)!important;max-height:200px!important;
    overflow-y:auto!important;border:2px solid var(--acc-2)!important;
    line-height:1.65!important;
}

/* ─── SUMMARY CARD ─── */
.summary-card{
    background:linear-gradient(135deg,var(--muted),rgba(0,245,212,.14));border:2px solid var(--ok-bd);
    border-radius:var(--r-sm);padding:14px 18px;margin:10px 0;
    font-size:.9rem;line-height:1.75;color:var(--tx-1);
}
.summary-card b{color:var(--ok);}

/* ─── PREVIEW META ─── */
.preview-meta{text-align:center;font-size:.75rem;color:var(--tx-4);margin-top:5px;}

/* ─── INPUTS ─── */
.stTextInput input,.stTextArea textarea,.stNumberInput input{
    background:var(--muted)!important;border:2.5px solid var(--acc-5)!important;
    border-radius:var(--r-sm)!important;color:var(--tx-1)!important;
    font-size:14px!important;min-height:40px!important;padding:9px 14px!important;
    transition:border-color .14s,box-shadow .14s!important;font-weight:600!important;
}
.stTextInput input:focus,.stTextArea textarea:focus,.stNumberInput input:focus{
    border-color:var(--acc-2)!important;box-shadow:0 0 16px rgba(0,245,212,.4)!important;
}
.stTextInput input::placeholder,.stTextArea textarea::placeholder{
    color:var(--tx-5)!important;font-weight:400!important;
}
.stTextArea textarea{min-height:90px!important;}
.stSelectbox div[data-baseweb="select"]>div,.stMultiSelect div[data-baseweb="select"]>div{
    background:var(--muted)!important;border:2.5px solid var(--acc-1)!important;
    border-radius:var(--r-sm)!important;color:var(--tx-1)!important;
    font-size:13.5px!important;min-height:40px!important;
}

/* ─── LABELS ─── */
.stTextInput label,.stTextArea label,.stSelectbox label,
.stNumberInput label,.stSlider label,.stMultiSelect label,
.stRadio label,.stCheckbox label,.stToggle label{
    font-size:13px!important;font-weight:700!important;
    color:var(--tx-2)!important;letter-spacing:.05px;
}

/* ─── BUTTONS ─── */
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-secondary"],
div[data-testid="stButton"] > button {
    background:linear-gradient(90deg,var(--acc-1) 0%,var(--acc-5) 50%,var(--acc-2) 100%)!important;
    background-size:220% 100%!important;
    color:white!important;border:3px solid var(--acc-3)!important;
    border-radius:999px!important;font-weight:800!important;text-transform:uppercase;
    letter-spacing:.5px;
    font-size:13px!important;min-height:42px!important;
    box-shadow:4px 4px 0 var(--acc-3),0 0 20px rgba(255,58,242,.25)!important;
    transition:transform .16s,box-shadow .16s,background-position .4s!important;
}
button[data-testid="baseButton-primary"]:hover,
button[data-testid="baseButton-secondary"]:hover,
div[data-testid="stButton"] > button:hover {
    transform:scale(1.04) translate(-2px,-2px)!important;
    box-shadow:6px 6px 0 var(--acc-3),0 0 28px rgba(255,58,242,.4)!important;
    background-position:100% 0!important;
}
button[data-testid="baseButton-primary"]:active,
div[data-testid="stButton"] > button:active{
    transform:scale(.97) translate(0,0)!important;box-shadow:2px 2px 0 var(--acc-3)!important;
}
div[data-testid="stDownloadButton"] > button {
    background:linear-gradient(90deg,var(--acc-2) 0%,#00c9ae 100%)!important;
    border:3px solid var(--acc-3)!important;
    border-radius:999px!important;min-height:42px!important;font-weight:800!important;
    text-transform:uppercase;letter-spacing:.5px;color:#062a24!important;
    box-shadow:4px 4px 0 var(--acc-1)!important;
}
div[data-testid="stDownloadButton"] > button:hover{
    box-shadow:6px 6px 0 var(--acc-1)!important;transform:scale(1.03) translate(-2px,-2px)!important;
}

/* ─── SLIDERS ─── */
.stSlider [data-baseweb="slider"]>div>div{
    background:linear-gradient(90deg,var(--acc-1),var(--acc-2))!important;
    height:6px!important;border-radius:3px!important;
}
.stSlider [data-baseweb="slider"]>div>div:first-child{background:var(--muted)!important;}
.stSlider [role="slider"]{
    background:var(--acc-3)!important;border:3px solid var(--acc-1)!important;
    box-shadow:0 0 14px rgba(255,58,242,.5)!important;
    width:20px!important;height:20px!important;
    transition:transform .1s,box-shadow .1s!important;
}
.stSlider [role="slider"]:hover{
    transform:scale(1.3)!important;box-shadow:0 0 20px rgba(255,230,0,.6)!important;
}

/* ─── TABS ─── */
.stTabs [data-baseweb="tab-list"]{
    gap:4px!important;background:var(--muted)!important;
    border-radius:var(--r-md)!important;padding:5px!important;
    overflow-x:auto;flex-wrap:nowrap!important;border:2.5px solid var(--acc-5)!important;
}
.stTabs [data-baseweb="tab"]{
    height:38px!important;padding:0 18px!important;border-radius:999px!important;
    color:var(--tx-3)!important;font-size:13px!important;font-weight:700!important;
    white-space:nowrap!important;background:transparent!important;border:none!important;
    transition:all .14s!important;text-transform:uppercase;letter-spacing:.3px;
}
.stTabs [data-baseweb="tab"]:hover{color:var(--tx-1)!important;background:rgba(255,255,255,.06)!important;}
.stTabs [aria-selected="true"]{
    background:linear-gradient(90deg,var(--acc-1),var(--acc-5))!important;color:#fff!important;
    box-shadow:0 0 16px rgba(255,58,242,.45)!important;font-weight:800!important;
}

/* ─── EXPANDER ─── */
[data-testid="stExpander"]{
    background:var(--surface)!important;border:2.5px dashed var(--acc-4)!important;
    border-radius:var(--r-md)!important;box-shadow:3px 3px 0 rgba(123,47,255,.3)!important;overflow:hidden!important;
}
[data-testid="stExpander"] summary{
    font-size:13.5px!important;font-weight:700!important;
    color:var(--tx-1)!important;padding:12px 18px!important;
}
[data-testid="stExpander"] summary:hover{background:var(--muted)!important;}

/* ─── METRICS ─── */
[data-testid="stMetric"]{
    background:var(--surface);border:2.5px solid var(--acc-2);
    padding:14px 16px!important;border-radius:var(--r-md);
    box-shadow:4px 4px 0 var(--acc-1);transition:transform .15s,box-shadow .15s!important;
}
[data-testid="stMetric"]:hover{
    box-shadow:6px 6px 0 var(--acc-1)!important;transform:translate(-2px,-2px)!important;
}
[data-testid="stMetricLabel"]{
    font-size:.72rem!important;font-weight:700!important;
    color:var(--tx-4)!important;text-transform:uppercase;letter-spacing:.7px;
}
[data-testid="stMetricValue"]{
    font-size:1.55rem!important;font-weight:900!important;
    color:var(--tx-1)!important;letter-spacing:-.4px;
    text-shadow:2px 2px 0 var(--acc-5);
}

/* ─── ALERTS ─── */
[data-testid="stAlert"]{
    border-radius:var(--r-sm)!important;padding:12px 16px!important;
    font-size:13.5px!important;border-width:2.5px!important;font-weight:600!important;
}

/* ─── CAPTION ─── */
.stCaption,[data-testid="stCaptionContainer"]{
    font-size:.78rem!important;color:var(--tx-4)!important;line-height:1.5!important;
}

/* ─── PROGRESS BAR ─── */
.stProgress>div>div>div>div{
    background:linear-gradient(90deg,var(--acc-1) 0%,var(--acc-2) 100%)!important;border-radius:3px!important;
    box-shadow:0 0 10px rgba(255,58,242,.5)!important;
}
.stProgress>div>div{height:7px!important;background:var(--muted)!important;border-radius:3px!important;}

/* ─── CHECKBOX & TOGGLE ─── */
.stCheckbox label,.stToggle label{font-size:13.5px!important;color:var(--tx-2)!important;}

/* ─── SPINNER ─── */
.stSpinner>div{border-top-color:var(--acc-1)!important;}

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar{width:8px;height:8px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--acc-5);border-radius:10px;}
::-webkit-scrollbar-thumb:hover{background:var(--acc-1);}

/* ─── DIVIDER ─── */
hr{border:none!important;border-top:2px dashed var(--acc-5)!important;margin:16px 0!important;}

/* ─── MOBILE (chaos stays, just stacks) ─── */
@media(max-width:640px){
    .app-header h1{font-size:1.05rem!important;}
    .stTabs [data-baseweb="tab-list"]{
        position:sticky;top:0;z-index:99;
        background:rgba(13,13,26,.96)!important;backdrop-filter:blur(12px);
    }
    .stTabs [data-baseweb="tab"]{padding:0 12px!important;font-size:12px!important;}
    .login-shell{padding:0 12px;}
    section[data-testid="stSidebar"]{width:88vw!important;}
    .block-container{padding:.5rem!important;}
    .stButton>button,.stDownloadButton>button{min-height:46px!important;}
}

/* ─── LOGIN ─── */
.login-shell{max-width:420px;margin:3.5rem auto 0;position:relative;}
.login-card{
    background:var(--surface);border-radius:var(--r-lg);
    padding:36px 32px 28px;border:3px solid var(--acc-1);box-shadow:var(--sh-lg);
    position:relative;overflow:hidden;
}
.login-card::before{
    content:'✨';position:absolute;top:-10px;right:14px;font-size:2.4rem;opacity:.5;
    animation:mtp-float 6s ease-in-out infinite;pointer-events:none;
}
.login-brand{
    width:64px;height:64px;border-radius:20px;margin:0 auto 18px;
    display:flex;align-items:center;justify-content:center;
    background:linear-gradient(135deg,var(--acc-1) 0%,var(--acc-5) 55%,var(--acc-2) 100%);
    color:#fff;box-shadow:0 0 30px rgba(255,58,242,.45),4px 4px 0 var(--acc-3);
    position:relative;overflow:hidden;border:2px solid var(--acc-3);
}
.login-brand::before{
    content:'';position:absolute;top:-8px;left:-8px;
    width:26px;height:26px;border-radius:50%;background:rgba(255,255,255,.25);
}
.login-title{
    text-align:center;color:var(--tx-1)!important;font-weight:900;font-size:1.5rem;margin:0;
    letter-spacing:-.4px;text-transform:uppercase;
    text-shadow:2px 2px 0 var(--acc-5),4px 4px 0 var(--acc-1);
}
.login-sub{text-align:center;color:var(--tx-3);margin:6px 0 24px;font-size:.84rem;}

/* ─── USER CHIP ─── */
.user-chip{
    background:linear-gradient(120deg,var(--p-10),transparent);border-radius:var(--r-sm);
    padding:12px 14px;border:2px solid var(--acc-1);margin-bottom:8px;
}
.user-chip b{color:var(--tx-1)!important;font-size:.95rem!important;font-weight:800!important;}
.user-chip span{color:var(--acc-2)!important;font-size:.74rem!important;font-weight:700!important;}

/* ─── SIDEBAR LOGO ─── */
.sb-logo-wrap{text-align:center;padding:10px 0 6px;}
.sb-logo-icon{
    width:48px;height:48px;margin:0 auto 10px;border-radius:15px;
    background:linear-gradient(135deg,var(--acc-1) 0%,var(--acc-5) 100%);
    display:flex;align-items:center;justify-content:center;
    box-shadow:0 0 18px rgba(255,58,242,.4),3px 3px 0 var(--acc-3);
    position:relative;overflow:hidden;border:2px solid var(--acc-3);
    animation:mtp-wiggle 4s ease-in-out infinite;
}
.sb-logo-icon::after{
    content:'';position:absolute;top:-12px;left:-12px;
    width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.2);pointer-events:none;
}
.sb-logo-title{font-weight:900!important;font-size:.92rem!important;color:var(--tx-1)!important;letter-spacing:-.2px;text-transform:uppercase;}
.sb-logo-sub{font-size:.68rem!important;color:var(--acc-2)!important;margin-top:2px;font-weight:700!important;}

/* ─── HISTORY ─── */
.history-item{padding:7px 0;border-bottom:1px dashed var(--muted);}
.hi-top{font-size:.8rem!important;color:var(--tx-2)!important;margin-bottom:1px;font-weight:600;}
.hi-top b{color:var(--tx-1)!important;}
.hi-bot{font-size:.72rem!important;color:var(--tx-4)!important;}

/* ─── STAT PILLS ─── */
.stat-row{display:flex;gap:6px;margin:5px 0 8px;}
.stat-pill{flex:1;border-radius:var(--r-xs);padding:9px 4px;text-align:center;border:2px solid;}
.stat-a{background:var(--p-10);border-color:var(--acc-1);}
.stat-b{background:var(--ok-bg);border-color:var(--ok-bd);}
.stat-c{background:var(--warn-bg);border-color:var(--warn-bd);}
.sp-num{font-size:.98rem!important;font-weight:900!important;display:block;}
.stat-a .sp-num{color:var(--acc-1)!important;}
.stat-b .sp-num{color:var(--ok)!important;}
.stat-c .sp-num{color:var(--warn)!important;}
.sp-lbl{font-size:.6rem!important;color:var(--tx-4)!important;text-transform:uppercase;letter-spacing:.6px;margin-top:1px;display:block;}

/* ─── CTRL ROW ─── */
.ctrl-row{background:var(--muted);border-radius:var(--r-sm);padding:8px;margin:8px 0;border:2px solid var(--acc-5);}

/* ─── APP NAV TABS (radio-as-tabs) ─── */
div[data-testid="stRadio"][aria-label="_app_tab_nav"]>div[role="radiogroup"],
.app-tab-nav div[role="radiogroup"]{
    gap:4px!important;background:var(--muted)!important;
    border-radius:var(--r-md)!important;padding:5px!important;
    flex-wrap:wrap!important;border:2.5px solid var(--acc-5)!important;margin-bottom:18px!important;
}
.app-tab-nav label{
    background:transparent!important;color:var(--tx-3)!important;
    padding:8px 16px!important;border-radius:999px!important;
    font-weight:700!important;font-size:13.5px!important;cursor:pointer!important;
    transition:all .14s ease!important;margin:0!important;border:1.5px solid transparent!important;
    text-transform:uppercase;letter-spacing:.3px;
}
.app-tab-nav label:hover{background:rgba(255,255,255,.06)!important;color:var(--tx-1)!important;}
.app-tab-nav label>div:first-child{display:none!important;}
.app-tab-nav label:has(input:checked){
    background:linear-gradient(90deg,var(--acc-1),var(--acc-5))!important;color:#fff!important;
    border-color:var(--acc-3)!important;font-weight:800!important;
    box-shadow:0 0 14px rgba(255,58,242,.4)!important;
}

/* ─── CHECKED ROW HIGHLIGHT ─── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(input[type="checkbox"]:checked){
    border-color:var(--acc-3)!important;
    box-shadow:4px 4px 0 var(--acc-1),0 0 18px rgba(255,230,0,.25)!important;
}

/* ─── SIGNATURE ANIMATIONS ─── */
@keyframes mtp-float{0%,100%{transform:translateY(0) rotate(0deg);}50%{transform:translateY(-8px) rotate(4deg);}}
@keyframes mtp-wiggle{0%,100%{transform:rotate(-2deg);}50%{transform:rotate(2deg);}}
@media(prefers-reduced-motion:reduce){
    .login-card::before,.sb-logo-icon{animation:none!important;}
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

/* ─── LIVE PREVIEW FRAME ─── */
/* [KEPT WHITE ON PURPOSE] Đây là khung xem trước ảnh sản phẩm thật —
   nền phải trung tính (trắng) để Đức đánh giá đúng màu ảnh gốc,
   không bị ám màu theme tối. Sự "maximalist" nằm ở khung viền/shadow xung quanh. */
.live-frame{
    position:relative;width:100%;max-width:520px;margin:0 auto;
    background:#fff;border:3px solid var(--acc-2);
    border-radius:var(--r-sm);overflow:hidden;box-shadow:4px 4px 0 var(--acc-1),8px 8px 0 var(--acc-5);
}
.live-frame::after{
    content:'PREVIEW';position:absolute;bottom:0;right:0;
    font-size:.58rem;font-weight:800;color:#0D0D1A;
    background:var(--acc-3);padding:2px 8px;
    border-radius:var(--r-xs) 0 0 0;letter-spacing:.8px;pointer-events:none;z-index:5;
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
    background:linear-gradient(180deg,rgba(255,255,255,0) 0%,rgba(13,13,26,.55) 100%);
    color:#f8fafc;font-size:.72rem!important;font-weight:700;z-index:2;pointer-events:none;
}
.live-overlay span{white-space:nowrap;}

/* ─── RENDERED FRAME ─── */
.rendered-frame{
    background:#fff;border-radius:var(--r-sm);border:3px solid var(--ok-bd);
    overflow:hidden;padding:4px;box-shadow:4px 4px 0 var(--acc-3);position:relative;
}
.rendered-frame::after{
    content:'✓ OUTPUT';position:absolute;top:0;right:0;
    font-size:.56rem;font-weight:800;color:#062a24;background:var(--ok);
    padding:2px 8px;border-radius:0 0 0 var(--r-xs);letter-spacing:.5px;pointer-events:none;z-index:5;
}
.rendered-frame img{max-width:100%;max-height:260px;object-fit:contain;display:block;margin:0 auto;position:relative;z-index:1;}

/* ─── STATUS PILLS ─── */
.spill{display:inline-flex;align-items:center;gap:4px;font-size:.72rem;font-weight:800;padding:3px 11px;border-radius:999px;white-space:nowrap;border:2px solid;}
.spill-r{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd);}
.spill-a{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd);}
.spill-s{background:var(--muted);color:var(--tx-3);border-color:var(--acc-5);}

/* ─── INFO PILLS ─── */
.info-pills{display:flex;flex-wrap:wrap;gap:5px;margin:5px 0;}
.info-pill{font-size:.72rem;color:var(--tx-2);background:var(--muted);border:1.5px solid var(--acc-5);border-radius:var(--r-xs);padding:2px 9px;white-space:nowrap;}
.info-pill b{color:var(--tx-1);font-weight:800;}
.size-info{font-size:.74rem;color:var(--tx-4);margin-top:4px;line-height:1.6;}
.size-info.output{color:var(--ok);font-weight:700;}

/* ─── EXPORT PANEL ─── */
.export-panel{background:var(--surface);border:3px solid var(--acc-1);border-radius:var(--r-lg);padding:22px 26px;margin-top:16px;box-shadow:6px 6px 0 var(--acc-5);}
.export-panel h2{margin:0 0 6px;color:var(--tx-1);font-size:1.2rem;font-weight:900;text-shadow:2px 2px 0 var(--acc-5);}
.export-panel p{color:var(--tx-3);font-size:.88rem;margin:0;}

/* ─── STUDIO IMG TITLE ─── */
.studio-img-title{font-size:.95rem!important;margin-bottom:8px!important;line-height:1.55;}
.studio-img-title b{color:var(--tx-1)!important;font-size:.95rem!important;font-weight:800!important;}
.studio-img-title code{font-size:.8rem!important;color:var(--acc-2)!important;background:var(--muted);padding:2px 7px;border-radius:var(--r-xs);word-break:break-all;}

/* ─── STUDIO FRESH BANNER ─── */
.studio-fresh-banner{background:var(--ok-bg);border:2px solid var(--ok-bd);border-radius:var(--r-sm);padding:12px 18px;margin:6px 0 14px;font-size:.9rem;color:var(--tx-1);font-weight:700;}

/* ─── WORKFLOW SIDEBAR WIDGET ─── */
.wf-block{background:var(--muted);border:2px solid var(--acc-5);border-radius:var(--r-sm);padding:12px 14px;margin-top:8px;}
.wf-title{font-size:.72rem;font-weight:800;color:var(--acc-3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px;display:flex;align-items:center;gap:6px;}
.wf-item{display:flex;align-items:flex-start;gap:10px;padding:6px 0;border-bottom:1px dashed var(--acc-5);font-size:.82rem;color:var(--tx-3);line-height:1.45;}
.wf-item:last-child{border-bottom:none;padding-bottom:0;}
.wf-num{flex-shrink:0;width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,var(--acc-1),var(--acc-5));color:#fff;font-size:.68rem;font-weight:800;display:flex;align-items:center;justify-content:center;margin-top:1px;}

@media(max-width:640px){
    .live-frame{max-width:100%;}
    .live-overlay{font-size:.68rem!important;padding:4px 8px;}
}

/* ─── STREAMLIT NATIVE OVERRIDES ─── */
[data-testid="stAppViewContainer"]{background-color:var(--bg)!important;}
[data-testid="stSidebar"]{background-color:var(--surface)!important;}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] > div > div {
    border-radius:var(--r-sm)!important;border:2.5px solid var(--acc-5)!important;
    background-color:var(--muted)!important;
}
[data-testid="stTextInput"] input:focus,[data-testid="stNumberInput"] input:focus {
    border-color:var(--acc-2)!important;box-shadow:0 0 16px rgba(0,245,212,.4)!important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# SESSION INIT + CSS
# ══════════════════════════════════════════════════════════════
init_app_state()
_inject_global_css()   # [v10.2 FIX] Gọi SAU init_app_state()


# ══════════════════════════════════════════════════════════════
# LOGIN / REGISTER
# ══════════════════════════════════════════════════════════════
def render_login_screen():
    st.markdown("<div class='login-shell'>", unsafe_allow_html=True)
    st.markdown("""
        <div class="login-card">
            <div class="login-brand">&#128444;</div>
            <h1 class="login-title">Media Tool Pro VIP</h1>
            <p class="login-sub">v10.2 &middot; Secure Workspace</p>
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
# SIDEBAR
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
            <p>v10.2 · Premium SaaS UI · Dynamic Canvas · Auto-sync GitHub</p>
        </div>
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
        <div style='font-size:1.05rem;font-weight:900;color:#FFFFFF;margin-bottom:8px;text-shadow:2px 2px 0 #7B2FFF'>
        📌 Media Tool Pro VIP v10.2 — Hướng dẫn nhanh
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
