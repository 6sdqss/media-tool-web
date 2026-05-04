import streamlit as st
from utils import get_gdrive_service

st.set_page_config(page_title="Media Tool Pro", layout="wide", page_icon="🖼️",
                   initial_sidebar_state="expanded")

# ══════════════════════════════════════════════════════════════
# CSS PREMIUM v5
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
#MainMenu,header,footer{visibility:hidden}.stDeployButton{display:none}
html,body,[class*="css"]{font-family:'Inter',-apple-system,sans-serif}
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1020px}

/* SIDEBAR */
section[data-testid="stSidebar"]{
  background:linear-gradient(175deg,#0a0e1a 0%,#111827 50%,#1a2332 100%)!important;
  border-right:1px solid rgba(99,102,241,0.1)!important}
section[data-testid="stSidebar"] *{color:#cbd5e1!important}
section[data-testid="stSidebar"] hr{border-color:rgba(99,102,241,0.08)!important;margin:8px 0!important}
section[data-testid="stSidebar"] .stButton>button{
  background:rgba(255,255,255,0.04)!important;color:#e2e8f0!important;
  border:1px solid rgba(255,255,255,0.08)!important;border-radius:10px!important;
  transition:all .2s!important}
section[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(239,68,68,0.8)!important;border-color:rgba(239,68,68,0.5)!important}

/* BUTTONS */
div.stButton>button{border-radius:12px;font-weight:700;font-size:.9rem;
  transition:all .2s cubic-bezier(.4,0,.2,1);height:46px;letter-spacing:.3px;border:1px solid #e5e7eb}
div.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#4f46e5,#7c3aed)!important;
  color:#fff!important;border:none!important;box-shadow:0 2px 12px rgba(99,102,241,0.3)!important}
div.stButton>button[kind="primary"]:hover{
  background:linear-gradient(135deg,#4338ca,#6d28d9)!important;
  transform:translateY(-2px)!important;box-shadow:0 6px 20px rgba(99,102,241,0.45)!important}

/* DOWNLOAD */
div.stDownloadButton>button{
  background:linear-gradient(135deg,#059669,#10b981)!important;
  color:#fff!important;border:none!important;border-radius:12px!important;
  height:50px!important;font-size:.95rem!important;font-weight:800!important;
  box-shadow:0 2px 10px rgba(16,185,129,0.25)!important}
div.stDownloadButton>button:hover{
  background:linear-gradient(135deg,#047857,#059669)!important;
  transform:translateY(-2px)!important;box-shadow:0 6px 20px rgba(16,185,129,0.4)!important}

/* CARDS */
div[data-testid="stVerticalBlockBorderWrapper"]{
  border-radius:14px!important;border:1px solid rgba(99,102,241,0.1)!important;
  box-shadow:0 1px 4px rgba(0,0,0,0.03),0 4px 12px rgba(99,102,241,0.04)!important;
  padding:6px 4px!important}

/* TABS */
div[data-testid="stTabs"] button{font-weight:700!important;font-size:.86rem!important;
  border-radius:10px 10px 0 0!important;padding:8px 16px!important}
div[data-testid="stTabs"] button[aria-selected="true"]{
  color:#6d28d9!important;border-bottom:3px solid #7c3aed!important;
  background:rgba(124,58,237,0.04)!important}

/* SECTION TITLE */
.sec-title{font-size:.75rem;font-weight:800;color:#6d28d9;text-transform:uppercase;
  letter-spacing:1.5px;margin:14px 0 6px;padding:5px 12px;
  border-left:3px solid #7c3aed;
  background:linear-gradient(90deg,rgba(124,58,237,0.06),transparent);border-radius:0 6px 6px 0}

/* CONTROL BOX */
.control-box{background:linear-gradient(135deg,#eef2ff,#ede9fe);
  border:1px solid rgba(124,58,237,0.12);border-radius:12px;padding:12px 16px;margin:8px 0 12px}

/* LOG */
.log-box{background:linear-gradient(180deg,#0a0e1a,#111827);color:#67e8f9;
  font-family:'JetBrains Mono','SF Mono',monospace;font-size:.73rem;line-height:1.75;
  padding:14px 18px;border-radius:12px;max-height:220px;overflow-y:auto;margin-top:8px;
  border:1px solid rgba(99,102,241,0.15);white-space:pre-wrap;word-break:break-word}
.log-box::-webkit-scrollbar{width:5px}
.log-box::-webkit-scrollbar-thumb{background:#334155;border-radius:3px}

/* BADGES */
.badge-ok{background:linear-gradient(135deg,#d1fae5,#a7f3d0);color:#065f46;
  border-radius:20px;padding:3px 12px;font-size:.76rem;font-weight:700;display:inline-block}
.badge-err{background:linear-gradient(135deg,#fee2e2,#fecaca);color:#991b1b;
  border-radius:20px;padding:3px 12px;font-size:.76rem;font-weight:700;display:inline-block}

/* GUIDE */
.guide-box{background:linear-gradient(135deg,#f5f3ff,#ede9fe,#ddd6fe);
  border:1px solid rgba(124,58,237,0.15);border-radius:14px;padding:16px 20px;
  margin-bottom:14px;font-size:.86rem;line-height:1.8}
.guide-box b{color:#5b21b6}

/* HEADER */
.app-header{background:linear-gradient(135deg,#1e1b4b,#312e81,#4c1d95);
  color:#fff;border-radius:16px;padding:18px 26px;margin-bottom:16px;
  box-shadow:0 4px 20px rgba(49,46,129,0.35)}
.app-header h1{color:#fff;margin:0;font-size:1.6rem;font-weight:900}
.app-header p{color:#c4b5fd;margin:3px 0 0;font-size:.85rem}

/* LOGIN */
.login-card{text-align:center;padding:28px 0 14px}
.login-logo{width:60px;height:60px;border-radius:16px;
  background:linear-gradient(135deg,#4f46e5,#7c3aed);
  display:inline-flex;align-items:center;justify-content:center;
  font-size:1.8rem;margin-bottom:10px;box-shadow:0 4px 16px rgba(124,58,237,0.3)}
.login-title{color:#1e1b4b;font-size:1.5rem;font-weight:900;margin:0}
.login-sub{color:#6b7280;font-size:.85rem;margin:4px 0 20px}

/* SIDEBAR LOGO */
.sb-logo{text-align:center;padding:16px 0 4px}
.sb-icon{width:44px;height:44px;border-radius:12px;
  background:linear-gradient(135deg,#4f46e5,#7c3aed);
  display:inline-flex;align-items:center;justify-content:center;
  font-size:1.3rem;margin-bottom:6px;box-shadow:0 2px 10px rgba(124,58,237,0.25)}
.sb-name{font-size:.95rem;font-weight:800;color:#f1f5f9!important}
.sb-ver{font-size:.7rem;color:#6b7280!important}

/* CONFIG PANEL */
.cfg-label{font-size:.78rem;font-weight:700;color:#4c1d95;margin-bottom:4px}
.tpl-hint{font-size:.72rem;color:#9ca3af;margin-top:2px}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════
for k,v in [("download_status","idle"),("logged_in",False)]:
    if k not in st.session_state: st.session_state[k] = v

# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    _,col,_ = st.columns([1,1.3,1])
    with col:
        st.markdown("""<div class="login-card"><div class="login-logo">🖼️</div>
            <h1 class="login-title">Media Tool Pro</h1>
            <p class="login-sub">Xử lý ảnh sản phẩm chuyên nghiệp</p></div>""",
            unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("Tài khoản", placeholder="username")
            p = st.text_input("Mật khẩu", type="password", placeholder="password")
            if st.button("Đăng Nhập", type="primary", use_container_width=True):
                if u == "ducpro" and p == "234766":
                    st.session_state.logged_in = True; st.rerun()
                else: st.error("Sai tài khoản / mật khẩu")
        st.markdown("<p style='text-align:center;color:#94a3b8;font-size:.72rem;margin-top:14px'>v5.0</p>",
                    unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""<div class="sb-logo"><div class="sb-icon">🖼️</div><br>
        <span class="sb-name">Media Tool Pro</span><br>
        <span class="sb-ver">v5.0 · ducpro</span></div>""", unsafe_allow_html=True)
    st.divider()

    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<span class="badge-ok">✅ Drive API</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">⚠️ Drive</span>', unsafe_allow_html=True)
    st.divider()

    from utils import render_session_stats, render_history_sidebar
    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()

    st.markdown("**📋 Lịch sử**")
    render_history_sidebar()
    st.divider()

    if st.button("Đăng Xuất", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# ══════════════════════════════════════════════════════════════
# IMPORTS
# ══════════════════════════════════════════════════════════════
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web   import run_mode_web

# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown("""<div class="app-header">
    <h1>🖼️ Media Tool Pro</h1>
    <p>Xuất nhiều kích thước · Đặt tên template · Chất lượng tùy chỉnh · ZIP tự động</p>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SIZE PRESETS
# ══════════════════════════════════════════════════════════════
SIZE_PRESETS = {
    "1020×680 Ngang chuẩn":     (1020, 680,  "letterbox"),
    "1020×570 Ngang rộng":      (1020, 570,  "letterbox"),
    "1200×1200 Vuông":           (1200, 1200, "letterbox"),
    "1000×1000 PS Crop":         (1000, 1000, "crop_1000"),
    "Giữ gốc":                   (None, None, "letterbox"),
}


def render_config_panel(tab_key: str):
    """Render bảng cấu hình chung, trả về config dict."""
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚙️ CẤU HÌNH XỬ LÝ</div>', unsafe_allow_html=True)

        # ── Chọn nhiều kích thước ──
        c_sizes, c_opts = st.columns([1.4, 1])
        with c_sizes:
            st.markdown("<div class='cfg-label'>📐 Kích thước xuất (chọn nhiều)</div>",
                        unsafe_allow_html=True)
            selected_labels = st.multiselect(
                "Chọn kích thước:",
                list(SIZE_PRESETS.keys()),
                default=["1020×680 Ngang chuẩn"],
                key=f"sizes_{tab_key}",
                label_visibility="collapsed",
            )
            # Kích thước tùy chỉnh
            custom_on = st.toggle("➕ Thêm kích thước tùy chỉnh", key=f"custom_on_{tab_key}")
            if custom_on:
                cc1, cc2 = st.columns(2)
                cw = cc1.number_input("W:", 100, 5000, 800, 10, key=f"cw_{tab_key}")
                ch = cc2.number_input("H:", 100, 5000, 800, 10, key=f"ch_{tab_key}")

        with c_opts:
            st.markdown("<div class='cfg-label'>🎛️ Tùy chọn</div>", unsafe_allow_html=True)
            quality = st.slider("Chất lượng JPEG:", 50, 100, 95, 5, key=f"q_{tab_key}")
            has_letterbox = any(
                SIZE_PRESETS.get(l, (None,None,""))[2] == "letterbox" and SIZE_PRESETS.get(l, (None,None,""))[0] is not None
                for l in selected_labels
            )
            if has_letterbox or custom_on:
                scale = st.slider("Phóng to (%):", 50, 150, 100, 5, key=f"sc_{tab_key}")
            else:
                scale = 100

        # ── Template đặt tên ──
        st.markdown("<div class='cfg-label'>✏️ Template đặt tên ảnh</div>",
                    unsafe_allow_html=True)
        tpl_c1, tpl_c2 = st.columns([2, 1])
        with tpl_c1:
            template = st.text_input(
                "Template:", value="{name}_{nn}",
                placeholder="{name}_{color}_{nn}",
                key=f"tpl_{tab_key}", label_visibility="collapsed")
        with tpl_c2:
            rename = st.toggle("Tên tùy chỉnh", key=f"ren_{tab_key}")
        st.markdown(
            "<div class='tpl-hint'>"
            "Biến: <code>{name}</code> tên SP · <code>{color}</code> màu · "
            "<code>{nn}</code> số 01 · <code>{nnn}</code> số 001 · "
            "<code>{original}</code> tên gốc</div>", unsafe_allow_html=True)

    # Build sizes list
    sizes = []
    for label in selected_labels:
        sizes.append(SIZE_PRESETS[label])
    if custom_on:
        sizes.append((int(cw), int(ch), "letterbox"))
    if not sizes:
        sizes = [(1020, 680, "letterbox")]

    return {
        "sizes": sizes,
        "scale_pct": scale,
        "quality": quality,
        "template": template or "{name}_{nn}",
        "rename": rename,
    }


# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "🌐 Google Drive", "💻 Local (ZIP)", "🛒 Web TGDD/DMX", "📖 Hướng dẫn"])

with tab1:
    cfg1 = render_config_panel("drive")
    run_mode_drive(cfg1, drive_service)

with tab2:
    cfg2 = render_config_panel("local")
    run_mode_local(cfg2)

with tab3:
    cfg3 = render_config_panel("web")
    run_mode_web(cfg3)

with tab4:
    st.markdown("""<div class="guide-box">
        <div style='font-size:1rem;font-weight:800;color:#4c1d95;margin-bottom:8px'>
        📋 Media Tool Pro v5.0 — Xử lý ảnh sản phẩm chuyên nghiệp</div>
        Xuất <b>nhiều kích thước cùng lúc</b> từ 1 nguồn ảnh. Đặt tên bằng template linh hoạt.
        Điều chỉnh chất lượng JPEG. Nhập kích thước tùy chỉnh bất kỳ.
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("🌐 Google Drive", expanded=True):
            st.markdown("""
**1.** Chia sẻ → "Bất kỳ ai có link" · **2.** Dán link
**3.** Bật "Tên tùy chỉnh" → điền tên từng link · **4.** Chọn kích thước → Bắt đầu
ZIP chứa subfolder cho mỗi kích thước nếu chọn nhiều.
""")
        with st.expander("💻 Local (ZIP)"):
            st.markdown("""
**1.** Nén ảnh → `.zip` · **2.** Upload · **3.** Đặt tên folder output · **4.** Bắt đầu
""")
    with c2:
        with st.expander("🛒 Web TGDD / DMX", expanded=True):
            st.markdown("""
**1.** Dán link SP · **2.** Quét → phát hiện màu · **3.** Sửa tên, tick chọn · **4.** Tải
""")
        with st.expander("🔧 Template đặt tên"):
            st.markdown("""
| Biến | Ý nghĩa | Ví dụ |
|---|---|---|
| `{name}` | Tên SP/folder | Samsung_S25 |
| `{color}` | Tên màu | Den |
| `{nn}` | Số thứ tự 01 | 01, 02, 03 |
| `{nnn}` | Số thứ tự 001 | 001, 002 |
| `{original}` | Tên file gốc | IMG_1234 |

**Ví dụ:** `{name}_{color}_{nn}` → `Samsung_S25_Den_01.jpg`
""")

    st.divider()
    st.markdown("<p style='text-align:center;color:#94a3b8;font-size:.74rem'>Media Tool Pro v5.0</p>",
                unsafe_allow_html=True)
