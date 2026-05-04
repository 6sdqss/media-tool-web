import streamlit as st
from utils import get_gdrive_service

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH TRANG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Media Tool Pro",
    layout="wide",
    page_icon="🖼️",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════
# CSS PREMIUM v4.0
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

#MainMenu, header, footer { visibility: hidden; }
.stDeployButton { display: none; }
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.block-container { padding-top:1.2rem; padding-bottom:2rem; max-width:980px; }

/* ═══════ SIDEBAR ═══════ */
section[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #0c1222 0%, #162036 40%, #1a2744 100%) !important;
    border-right: 1px solid rgba(99,130,190,0.15) !important;
}
section[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
section[data-testid="stSidebar"] hr {
    border-color: rgba(99,130,190,0.15) !important;
    margin: 10px 0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    backdrop-filter: blur(8px) !important;
    transition: all .25s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(239,68,68,0.85) !important;
    border-color: rgba(239,68,68,0.6) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(239,68,68,0.25) !important;
}

/* ═══════ BUTTONS ═══════ */
div.stButton > button {
    border-radius: 12px; font-weight: 700; font-size: 0.92rem;
    transition: all .25s cubic-bezier(.4,0,.2,1);
    height: 48px; letter-spacing: .4px;
    border: 1px solid #e2e8f0;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #818cf8 100%) !important;
    color: #fff !important; border: none !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.25) !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4338ca 0%, #4f46e5 50%, #6366f1 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.4) !important;
}
div.stButton > button:not([kind="primary"]):hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    border-color: #c7d2fe;
}

/* ═══════ DOWNLOAD ═══════ */
div.stDownloadButton > button {
    background: linear-gradient(135deg, #059669 0%, #10b981 50%, #34d399 100%) !important;
    color: #fff !important; border: none !important; border-radius: 12px !important;
    height: 52px !important; font-size: 1rem !important;
    font-weight: 800 !important; letter-spacing: .5px !important;
    box-shadow: 0 2px 8px rgba(16,185,129,0.25) !important;
}
div.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #047857 0%, #059669 50%, #10b981 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(16,185,129,0.4) !important;
}

/* ═══════ CARDS ═══════ */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid rgba(99,102,241,0.12) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(99,102,241,0.06) !important;
    padding: 8px 6px !important;
}

/* ═══════ TABS ═══════ */
div[data-testid="stTabs"] button {
    font-weight: 700 !important; font-size: .88rem !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 18px !important;
    transition: all .2s ease !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #4f46e5 !important;
    border-bottom: 3px solid #4f46e5 !important;
    background: rgba(99,102,241,0.05) !important;
}

/* ═══════ SECTION TITLES ═══════ */
.sec-title {
    font-size: .78rem; font-weight: 800; color: #4f46e5;
    text-transform: uppercase; letter-spacing: 1.6px;
    margin: 16px 0 8px; padding: 6px 12px;
    border-left: 3px solid #6366f1;
    background: linear-gradient(90deg, rgba(99,102,241,0.06) 0%, transparent 100%);
    border-radius: 0 6px 6px 0;
}

/* ═══════ CONTROL BOX ═══════ */
.control-box {
    background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 14px; padding: 14px 18px; margin: 10px 0 14px;
}

/* ═══════ LOG ═══════ */
.log-box {
    background: linear-gradient(180deg, #0c1222 0%, #131d32 100%);
    color: #7dd3fc;
    font-family: 'JetBrains Mono', 'SF Mono', monospace;
    font-size: .75rem; line-height: 1.8; padding: 16px 20px;
    border-radius: 12px; max-height: 240px; overflow-y: auto;
    margin-top: 10px;
    border: 1px solid rgba(99,130,190,0.2);
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
    white-space: pre-wrap; word-break: break-word;
}
.log-box::-webkit-scrollbar { width: 6px; }
.log-box::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

/* ═══════ BADGES ═══════ */
.badge-ok {
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    color: #065f46; border-radius: 20px;
    padding: 4px 14px; font-size: .78rem; font-weight: 700;
    display: inline-block;
}
.badge-err {
    background: linear-gradient(135deg, #fee2e2, #fecaca);
    color: #991b1b; border-radius: 20px;
    padding: 4px 14px; font-size: .78rem; font-weight: 700;
    display: inline-block;
}

/* ═══════ GUIDE BOX ═══════ */
.guide-box {
    background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 40%, #c7d2fe 100%);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 14px; padding: 18px 22px;
    margin-bottom: 16px; font-size: .87rem; line-height: 1.85;
}
.guide-box b { color: #4338ca; }

/* ═══════ HEADER ═══════ */
.app-header {
    background: linear-gradient(135deg, #312e81 0%, #4338ca 50%, #4f46e5 100%);
    color: #fff; border-radius: 16px; padding: 20px 28px; margin-bottom: 18px;
    box-shadow: 0 4px 20px rgba(67,56,202,0.3);
}
.app-header h1 { color:#fff; margin:0; font-size:1.7rem; font-weight:900; }
.app-header p  { color:#c7d2fe; margin:4px 0 0; font-size:.88rem; }

/* ═══════ LOGIN ═══════ */
.login-card { text-align:center; padding:32px 0 16px; }
.login-logo {
    width:64px; height:64px; border-radius:18px;
    background: linear-gradient(135deg,#4f46e5,#6366f1);
    display:inline-flex; align-items:center; justify-content:center;
    font-size:2rem; margin-bottom:12px;
    box-shadow:0 4px 16px rgba(99,102,241,0.3);
}
.login-title { color:#1e1b4b; font-size:1.6rem; font-weight:900; margin:0; }
.login-sub   { color:#6b7280; font-size:.88rem; margin:6px 0 24px; }

/* ═══════ SIDEBAR LOGO ═══════ */
.sidebar-logo { text-align:center; padding:20px 0 6px; }
.sidebar-logo-icon {
    width:48px; height:48px; border-radius:14px;
    background: linear-gradient(135deg,#4f46e5,#818cf8);
    display:inline-flex; align-items:center; justify-content:center;
    font-size:1.5rem; margin-bottom:8px;
    box-shadow:0 2px 12px rgba(99,102,241,0.3);
}
.sidebar-name { font-size:1rem; font-weight:800; color:#f1f5f9 !important; }
.sidebar-ver  { font-size:.72rem; color:#64748b !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════
for key, val in [("download_status", "idle"), ("logged_in", False)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ══════════════════════════════════════════════════════════════
# ĐĂNG NHẬP
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("""
        <div class="login-card">
            <div class="login-logo">🖼️</div>
            <h1 class="login-title">Media Tool Pro</h1>
            <p class="login-sub">Tải · Resize · Đóng gói — Chuyên nghiệp & Tự động</p>
        </div>""", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            username = st.text_input("Tài khoản", placeholder="Nhập tài khoản...")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu...")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Đăng Nhập", type="primary", use_container_width=True):
                if username == "ducpro" and password == "234766":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Sai tài khoản hoặc mật khẩu")
        st.markdown(
            "<p style='text-align:center;color:#94a3b8;font-size:.74rem;margin-top:16px'>"
            "Media Tool Pro · v4.0</p>", unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <div class="sidebar-logo-icon">🖼️</div><br>
        <span class="sidebar-name">Media Tool Pro</span><br>
        <span class="sidebar-ver">v4.0 · ducpro</span>
    </div>""", unsafe_allow_html=True)
    st.divider()

    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<span class="badge-ok">✅ Drive API OK</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">⚠️ Drive chưa kết nối</span>', unsafe_allow_html=True)
        st.caption("`credentials.json` hoặc Secrets")
    st.divider()

    st.markdown("**📐 Kích thước**")
    st.caption("1020×680 · 1020×570 · 1200²\n1000² Crop · Giữ gốc")
    st.divider()

    st.markdown("**📋 Lịch sử xử lý**")
    from utils import render_history_sidebar
    render_history_sidebar()
    st.divider()

    if st.button("Đăng Xuất", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ══════════════════════════════════════════════════════════════
# IMPORT
# ══════════════════════════════════════════════════════════════
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web   import run_mode_web

# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <h1>🖼️ Media Tool Pro</h1>
    <p>Tải ảnh · Resize thông minh · Đặt tên tùy chỉnh · Đóng gói ZIP tự động</p>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SIZE OPTIONS
# ══════════════════════════════════════════════════════════════
SIZE_OPTIONS = {
    "1020 × 680  —  Ngang chuẩn":     (1020, 680,  "letterbox"),
    "1020 × 570  —  Ngang rộng":      (1020, 570,  "letterbox"),
    "1200 × 1200  —  Vuông":           (1200, 1200, "letterbox"),
    "1000 × 1000  —  Photoshop Crop":  (1000, 1000, "crop_1000"),
    "Giữ hình gốc  —  Không resize":  (None, None, "letterbox"),
}

# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "🌐  Google Drive", "💻  Local (ZIP)",
    "🛒  Web TGDD/DMX", "📖  Hướng dẫn",
])

# ── TAB 1: DRIVE ──────────────────────────────────────────────
with tab1:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚙️ CẤU HÌNH</div>', unsafe_allow_html=True)
        c1a, c1b = st.columns([1.3, 1])
        with c1a:
            sk1 = st.selectbox("Kích thước:", list(SIZE_OPTIONS.keys()), key="sz_drive")
        w1, h1, mode1 = SIZE_OPTIONS[sk1]
        with c1b:
            if mode1 == "letterbox" and w1 is not None:
                scale1 = st.slider("Phóng to (%):", 50, 150, 100, 5, key="scale_drive")
            else:
                scale1 = 100
                st.caption("Scale: không áp dụng")
        rename1 = st.toggle("✏️ Đặt tên tùy chỉnh từng link", value=False, key="rename_drive")
    run_mode_drive(w1, h1, drive_service, scale_pct=scale1, mode=mode1, rename=rename1)

# ── TAB 2: LOCAL ──────────────────────────────────────────────
with tab2:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚙️ CẤU HÌNH</div>', unsafe_allow_html=True)
        c2a, c2b = st.columns([1.3, 1])
        with c2a:
            sk2 = st.selectbox("Kích thước:", list(SIZE_OPTIONS.keys()), key="sz_local")
        w2, h2, mode2 = SIZE_OPTIONS[sk2]
        with c2b:
            if mode2 == "letterbox" and w2 is not None:
                scale2 = st.slider("Phóng to (%):", 50, 150, 100, 5, key="scale_local")
            else:
                scale2 = 100
                st.caption("Scale: không áp dụng")
        rename2 = st.toggle("✏️ Đặt tên tùy chỉnh từng file ZIP", value=False, key="rename_local")
    run_mode_local(w2, h2, scale_pct=scale2, mode=mode2, rename=rename2)

# ── TAB 3: WEB ────────────────────────────────────────────────
with tab3:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚙️ CẤU HÌNH</div>', unsafe_allow_html=True)
        c3a, c3b = st.columns([1.3, 1])
        with c3a:
            sk3 = st.selectbox("Kích thước:", list(SIZE_OPTIONS.keys()), key="sz_web")
        w3, h3, mode3 = SIZE_OPTIONS[sk3]
        with c3b:
            if mode3 == "letterbox" and w3 is not None:
                scale3 = st.slider("Phóng to (%):", 50, 150, 100, 5, key="scale_web")
            else:
                scale3 = 100
                st.caption("Scale: không áp dụng")
        rename3 = st.toggle("✏️ Đặt tên tùy chỉnh sản phẩm", value=False, key="rename_web")
    run_mode_web(w3, h3, scale_pct=scale3, mode=mode3, rename=rename3)

# ── TAB 4: HƯỚNG DẪN ──────────────────────────────────────────
with tab4:
    st.markdown("""
    <div class="guide-box">
        <div style='font-size:1.05rem;font-weight:800;color:#312e81;margin-bottom:10px'>
            📋 Media Tool Pro v4.0
        </div>
        Công cụ xử lý ảnh sản phẩm chuyên nghiệp. Tải ảnh từ nhiều nguồn →
        Resize chuẩn → Đặt tên tùy chỉnh → Đóng gói ZIP tự động.
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("🌐 Google Drive", expanded=True):
            st.markdown("""
**B1.** Chia sẻ → "Bất kỳ ai có link" · **B2.** Dán link (mỗi dòng 1 link)
**B3.** Bật "Đặt tên" → điền tên cho mỗi link · **B4.** Bắt đầu → Tải ZIP
""")
        with st.expander("💻 Local (ZIP)"):
            st.markdown("""
**B1.** Nén ảnh → `.zip` · **B2.** Upload (nhiều file)
**B3.** Bật "Đặt tên" → đổi tên output · **B4.** Bắt đầu → Tải ZIP
""")
    with c2:
        with st.expander("🛒 Web TGDD / DMX", expanded=True):
            st.markdown("""
**B1.** Dán link sản phẩm · **B2.** Quét → phát hiện màu
**B3.** Tick chọn, sửa tên · **B4.** Tải & Resize → ZIP
""")
        with st.expander("🔧 Resize & Crop"):
            st.markdown("""
**Letterbox:** Giữ tỉ lệ → fill trắng → slider % · **Crop 1000:** Center 1:1

| Size | Dùng cho |
|---|---|
| 1020×680 | Banner ngang |
| 1200×1200 | Shopee, Lazada |
| 1000×1000 | Photoshop crop |
""")

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#94a3b8;font-size:.76rem'>"
        "Media Tool Pro v4.0</p>", unsafe_allow_html=True)
