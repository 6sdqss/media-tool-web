"""
ui/theme.py — Design system CSS.
Nguyên tắc: dark, clean, professional, high information density.
Không lạm dụng gradient/animation. Contrast AAA cho text chính.
Guard session key '_theme_v11' để không inject nhiều lần.
"""
from __future__ import annotations

import streamlit as st


_GUARD_KEY = "_theme_v11"


def inject() -> None:
    if st.session_state.get(_GUARD_KEY):
        return
    st.session_state[_GUARD_KEY] = True
    st.markdown(_CSS, unsafe_allow_html=True)


_CSS = """
<style>
/* ═════════════════════════════════════════════════════════
   Media Tool Pro v11 — Dark Professional
   Tokens ═════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --bg:        #0B0F1A;
  --surface:   #131A2A;
  --surface-2: #1B2338;
  --muted:     #232D48;
  --border:    #2B3654;
  --border-2:  #3A4869;

  --primary:      #3B82F6;
  --primary-hi:   #60A5FA;
  --primary-dark: #1E5BC5;
  --primary-10:   rgba(59,130,246,.12);
  --primary-20:   rgba(59,130,246,.22);

  --tx-1: #F5F7FB;
  --tx-2: #D6DBE7;
  --tx-3: #A0AAC0;
  --tx-4: #7A849C;
  --tx-5: #556072;

  --ok:      #22C55E;
  --ok-bg:   rgba(34,197,94,.12);
  --warn:    #F59E0B;
  --warn-bg: rgba(245,158,11,.12);
  --err:     #EF4444;
  --err-bg:  rgba(239,68,68,.12);
  --info:    #38BDF8;
  --info-bg: rgba(56,189,248,.12);

  --r-sm: 6px;
  --r-md: 10px;
  --r-lg: 14px;

  --sh-1: 0 1px 2px rgba(0,0,0,.4);
  --sh-2: 0 4px 12px rgba(0,0,0,.35);
}

/* Hide Streamlit chrome */
#MainMenu, header, footer, .stDeployButton, [data-testid="stToolbar"] {
  visibility: hidden !important; display: none !important;
}

html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, sans-serif !important;
  font-size: 14px !important;
  line-height: 1.55 !important;
  color: var(--tx-2) !important;
  -webkit-font-smoothing: antialiased !important;
}

.stApp {
  background: var(--bg) !important;
}

.block-container {
  max-width: 1280px !important;
  padding: 1.25rem 1.5rem 2.5rem !important;
}
@media (max-width: 900px) {
  .block-container { padding: .75rem !important; }
}

/* ─── SIDEBAR ─── */
section[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
  width: 280px !important;
}
section[data-testid="stSidebar"] * {
  font-size: 13px !important;
  color: var(--tx-3) !important;
}
section[data-testid="stSidebar"] hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 10px 0 !important;
}

/* ─── HEADINGS ─── */
h1, h2, h3, h4 { color: var(--tx-1) !important; font-weight: 700 !important; }
h1 { font-size: 1.4rem !important; letter-spacing: -.3px; }
h2 { font-size: 1.15rem !important; }
h3 { font-size: 1.0rem !important; }

/* ─── APP HEADER ─── */
.mtp-header {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 14px 18px;
  margin-bottom: 16px;
  display: flex; align-items: center; gap: 14px;
}
.mtp-header .brand {
  width: 40px; height: 40px; border-radius: 10px;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; color: #fff; font-size: 1.1rem;
  box-shadow: var(--sh-1);
}
.mtp-header h1 { margin: 0; font-size: 1.05rem !important; }
.mtp-header p  { margin: 2px 0 0; color: var(--tx-4); font-size: .78rem; }

/* ─── HERO / SECTION HEADER ─── */
.mtp-hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--primary);
  border-radius: var(--r-md);
  padding: 14px 18px;
  margin-bottom: 14px;
}
.mtp-hero h2 { margin: 0 0 4px; font-size: 1.0rem !important; }
.mtp-hero p  { margin: 0; color: var(--tx-3); font-size: .85rem; line-height: 1.65; }
.mtp-hero b  { color: var(--tx-1); font-weight: 600; }

.mtp-sec-title {
  display: inline-block;
  font-size: .72rem !important;
  font-weight: 700 !important;
  color: var(--tx-3) !important;
  text-transform: uppercase;
  letter-spacing: .8px;
  margin: 14px 0 8px !important;
}

/* ─── CARDS / CONTAINERS ─── */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 14px !important;
  box-shadow: var(--sh-1) !important;
}

/* ─── FORM CONTROLS ─── */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {
  background: var(--surface-2) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--r-sm) !important;
  color: var(--tx-1) !important;
  font-size: 13.5px !important;
  min-height: 38px !important;
  padding: 8px 12px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px var(--primary-10) !important;
  outline: none !important;
}
.stTextArea textarea { min-height: 88px !important; }
.stTextInput label, .stTextArea label, .stSelectbox label,
.stNumberInput label, .stSlider label, .stMultiSelect label,
.stRadio label, .stCheckbox label, .stToggle label {
  font-size: 12.5px !important;
  font-weight: 600 !important;
  color: var(--tx-3) !important;
}

/* ─── BUTTONS ─── */
div[data-testid="stButton"] > button {
  background: var(--surface-2) !important;
  color: var(--tx-1) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--r-sm) !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  min-height: 38px !important;
  padding: 6px 16px !important;
  box-shadow: none !important;
  transition: background .12s, border-color .12s !important;
}
div[data-testid="stButton"] > button:hover {
  background: var(--muted) !important;
  border-color: var(--primary) !important;
}
button[data-testid="baseButton-primary"] {
  background: var(--primary) !important;
  color: #fff !important;
  border-color: var(--primary) !important;
}
button[data-testid="baseButton-primary"]:hover {
  background: var(--primary-hi) !important;
}
button:disabled {
  opacity: .55 !important; cursor: not-allowed !important;
}
div[data-testid="stDownloadButton"] > button {
  background: var(--ok) !important;
  color: #052E1A !important;
  border: 1px solid var(--ok) !important;
  font-weight: 700 !important;
}

/* ─── TABS / RADIO-AS-NAV ─── */
.stTabs [data-baseweb="tab-list"] {
  gap: 2px !important;
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 4px !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--tx-3) !important;
  border-radius: var(--r-sm) !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  height: 34px !important;
  padding: 0 14px !important;
}
.stTabs [aria-selected="true"] {
  background: var(--primary) !important;
  color: #fff !important;
}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
  background: var(--muted) !important;
  color: var(--tx-1) !important;
}

.app-tab-nav div[role="radiogroup"] {
  gap: 2px !important;
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 4px !important;
  flex-wrap: wrap !important;
  margin-bottom: 14px !important;
}
.app-tab-nav label {
  background: transparent !important;
  color: var(--tx-3) !important;
  padding: 7px 14px !important;
  border-radius: var(--r-sm) !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  cursor: pointer !important;
  border: none !important;
  margin: 0 !important;
}
.app-tab-nav label:hover { background: var(--muted) !important; color: var(--tx-1) !important; }
.app-tab-nav label > div:first-child { display: none !important; }
.app-tab-nav label:has(input:checked) {
  background: var(--primary) !important;
  color: #fff !important;
}

/* ─── EXPANDER ─── */
[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
}
[data-testid="stExpander"] summary {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--tx-2) !important;
  padding: 10px 14px !important;
}
[data-testid="stExpander"] summary:hover { background: var(--muted) !important; }

/* ─── METRICS ─── */
[data-testid="stMetric"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 10px 14px !important;
}
[data-testid="stMetricLabel"] {
  font-size: .68rem !important;
  font-weight: 600 !important;
  color: var(--tx-4) !important;
  text-transform: uppercase;
  letter-spacing: .5px;
}
[data-testid="stMetricValue"] {
  font-size: 1.4rem !important;
  font-weight: 800 !important;
  color: var(--tx-1) !important;
}

/* ─── PROGRESS ─── */
.stProgress > div > div > div > div {
  background: linear-gradient(90deg, var(--primary), var(--primary-hi)) !important;
  border-radius: 3px !important;
}
.stProgress > div > div { height: 6px !important; background: var(--muted) !important; border-radius: 3px !important; }

/* ─── ALERTS ─── */
[data-testid="stAlert"] {
  border-radius: var(--r-md) !important;
  border: 1px solid var(--border) !important;
  font-size: 13px !important;
}

/* ─── DIVIDER ─── */
hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 14px 0 !important;
}

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--tx-5); }

/* ─── SLIDER ─── */
.stSlider [data-baseweb="slider"] > div > div {
  background: var(--primary) !important; height: 4px !important; border-radius: 2px !important;
}
.stSlider [data-baseweb="slider"] > div > div:first-child { background: var(--muted) !important; }
.stSlider [role="slider"] {
  background: var(--primary-hi) !important;
  border: 2px solid var(--primary) !important;
  width: 16px !important; height: 16px !important;
}

/* ─── LOG BOX ─── */
.mtp-log {
  background: #050810 !important;
  color: #7EE8B4 !important;
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace !important;
  font-size: 12px !important;
  padding: 10px 12px !important;
  border-radius: var(--r-sm) !important;
  border: 1px solid var(--border) !important;
  max-height: 220px !important;
  overflow-y: auto !important;
  line-height: 1.55 !important;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ─── STATUS PILLS ─── */
.mtp-pill {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: .72rem; font-weight: 700;
  padding: 3px 10px; border-radius: 999px;
  border: 1px solid; white-space: nowrap;
}
.mtp-pill.ok  { background: var(--ok-bg);  color: var(--ok);  border-color: var(--ok); }
.mtp-pill.warn{ background: var(--warn-bg);color: var(--warn);border-color: var(--warn); }
.mtp-pill.err { background: var(--err-bg); color: var(--err); border-color: var(--err); }
.mtp-pill.info{ background: var(--info-bg);color: var(--info);border-color: var(--info); }
.mtp-pill.muted{background: var(--muted);  color: var(--tx-3);border-color: var(--border-2); }

/* ─── INPUT REPORT (validation bar) ─── */
.mtp-input-report {
  display: flex; flex-wrap: wrap; gap: 6px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 8px 12px;
  margin: 8px 0;
  font-size: .78rem;
  color: var(--tx-3);
}

/* ─── QUEUE ROW ─── */
.mtp-queue {
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  overflow: hidden;
  background: var(--surface);
}
.mtp-queue-row {
  display: grid;
  grid-template-columns: 30px 1fr 100px 90px 60px;
  gap: 8px;
  padding: 8px 12px;
  align-items: center;
  border-bottom: 1px solid var(--border);
  font-size: .82rem;
}
.mtp-queue-row:last-child { border-bottom: none; }
.mtp-queue-row.head {
  background: var(--surface-2);
  font-size: .68rem;
  color: var(--tx-4);
  text-transform: uppercase;
  letter-spacing: .5px;
  font-weight: 700;
}
.mtp-queue-name {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--tx-1);
}
.mtp-queue-err { font-size: .72rem; color: var(--err); margin-top: 2px; }

/* ─── LOGIN ─── */
.mtp-login-shell { max-width: 380px; margin: 3rem auto 0; }
.mtp-login-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 28px 26px;
  box-shadow: var(--sh-2);
}
.mtp-login-title {
  text-align: center; color: var(--tx-1);
  font-size: 1.2rem; font-weight: 800;
  margin: 12px 0 4px;
}
.mtp-login-sub {
  text-align: center; color: var(--tx-4);
  font-size: .8rem; margin: 0 0 18px;
}
.mtp-login-brand {
  width: 52px; height: 52px; margin: 0 auto;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 1.4rem; font-weight: 800;
  box-shadow: var(--sh-2);
}

/* ─── ONE-CLICK BANNER ─── */
.mtp-oneclick {
  background: linear-gradient(90deg, var(--primary-10), transparent);
  border: 1px solid var(--primary);
  border-radius: var(--r-md);
  padding: 10px 14px;
  margin-bottom: 12px;
  font-size: .82rem;
  color: var(--tx-2);
}

/* ─── CAPTION ─── */
.stCaption, [data-testid="stCaptionContainer"] {
  font-size: .76rem !important; color: var(--tx-4) !important;
}

/* ─── STREAMLIT NATIVE OVERRIDES ─── */
[data-testid="stAppViewContainer"] { background: var(--bg) !important; }
[data-testid="stSidebar"] { background: var(--surface) !important; }

/* ─── STUDIO frames (kept white bg to judge product color) ─── */
.live-frame {
  position: relative; width: 100%; max-width: 520px; margin: 0 auto;
  background: #fff; border: 1px solid var(--border-2);
  border-radius: var(--r-sm); overflow: hidden;
  box-shadow: var(--sh-2);
}
.live-frame::after {
  content: 'PREVIEW'; position: absolute; bottom: 0; right: 0;
  font-size: .58rem; font-weight: 700; color: #0B0F1A;
  background: #fff; padding: 2px 8px;
  border-radius: var(--r-sm) 0 0 0; letter-spacing: .5px;
  pointer-events: none; z-index: 5;
}
.live-frame--empty {
  display: flex; align-items: center; justify-content: center;
  aspect-ratio: 3/2; color: var(--err); font-size: .9rem;
  background: var(--err-bg); border-color: var(--err);
}
.live-canvas { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #fff; }
.live-img { width: 100%; height: 100%; object-fit: contain; transform-origin: center; transition: transform .1s; will-change: transform; }
.live-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  display: flex; flex-wrap: wrap; gap: 4px 10px; padding: 4px 10px;
  background: linear-gradient(180deg, transparent, rgba(0,0,0,.45));
  color: #fff; font-size: .72rem !important; font-weight: 600; z-index: 2;
  pointer-events: none;
}
.rendered-frame {
  background: #fff; border: 1px solid var(--ok);
  border-radius: var(--r-sm); overflow: hidden; padding: 4px;
  position: relative;
}
.rendered-frame::after {
  content: '✓ OUTPUT'; position: absolute; top: 0; right: 0;
  font-size: .56rem; font-weight: 700; color: #052E1A;
  background: var(--ok); padding: 2px 8px;
  border-radius: 0 0 0 var(--r-sm); pointer-events: none; z-index: 5;
}
.rendered-frame img {
  max-width: 100%; max-height: 260px; object-fit: contain;
  display: block; margin: 0 auto;
}

/* Studio pills / small labels — kept dark theme */
.spill { display: inline-flex; align-items: center; gap: 4px;
         font-size: .72rem; font-weight: 700;
         padding: 3px 10px; border-radius: 999px;
         white-space: nowrap; border: 1px solid; }
.spill-r { background: var(--ok-bg); color: var(--ok); border-color: var(--ok); }
.spill-a { background: var(--warn-bg); color: var(--warn); border-color: var(--warn); }
.spill-s { background: var(--muted); color: var(--tx-3); border-color: var(--border-2); }

.info-pills { display: flex; flex-wrap: wrap; gap: 5px; margin: 4px 0; }
.info-pill {
  font-size: .72rem; color: var(--tx-2);
  background: var(--muted); border: 1px solid var(--border-2);
  border-radius: var(--r-sm); padding: 2px 9px; white-space: nowrap;
}
.info-pill b { color: var(--tx-1); font-weight: 700; }

.slider-val {
  display: inline-block;
  background: var(--primary-10); color: var(--primary-hi);
  font-size: .78rem; font-weight: 700;
  padding: 1px 8px; border-radius: 999px;
  border: 1px solid var(--primary);
  min-width: 38px; text-align: center;
}

.wf-block { background: var(--muted); border: 1px solid var(--border); border-radius: var(--r-sm); padding: 12px 14px; margin-top: 8px; }
.wf-title { font-size: .72rem; font-weight: 700; color: var(--primary-hi); text-transform: uppercase; letter-spacing: .8px; margin-bottom: 10px; }
.wf-item { display: flex; align-items: flex-start; gap: 10px; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: .8rem; color: var(--tx-3); }
.wf-item:last-child { border-bottom: none; }
.wf-num { flex-shrink: 0; width: 20px; height: 20px; border-radius: 50%; background: var(--primary); color: #fff; font-size: .68rem; font-weight: 700; display: flex; align-items: center; justify-content: center; }

/* Studio wrap max width */
@media (min-width: 1200px) {
  .studio-wrap .block-container { max-width: 1420px !important; }
}
</style>
"""
