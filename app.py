"""
app.py — Media Tool Pro VIP v6.0
Giao diện chính: Login, Sidebar, Config Panel, 4 Tab (Drive / Local / Web / Hướng dẫn).
Tính năng: Multi-size export, Template naming, Quality & Format control.
Đã nâng cấp giao diện chuẩn SaaS và xóa Quick Presets.
"""

import streamlit as st
from utils import (
    get_gdrive_service,
    SIZE_PRESETS,
    EXPORT_FORMATS,
    render_session_stats,
    render_history_sidebar,
)

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
# CSS PREMIUM v6.0 VIP
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Ẩn menu mặc định ── */
#MainMenu, header, footer { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1020px;
}

/* ══════════ SIDEBAR ══════════ */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
    border-right: 1px solid #334155 !important;
}
section[data-testid="stSidebar"] * {
    color: #f8fafc !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.08) !important;
    margin: 8px 0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.05) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(239, 68, 68, 0.9) !important;
    border-color: rgba(239, 68, 68, 0.6) !important;
}

/* ══════════ BUTTONS ══════════ */
div.stButton > button {
    border-radius: 12px;
    font-weight: 700;
    font-size: 0.95rem;
    transition: all 0.2s ease;
    height: 48px;
    letter-spacing: 0.3px;
    border: 1px solid #e5e7eb;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3) !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4) !important;
}

/* ══════════ DOWNLOAD BUTTON ══════════ */
div.stDownloadButton > button {
    background: linear-gradient(135deg, #10b981, #059669) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    height: 54px !important;
    font-size: 1rem !important;
    font-weight: 800 !important;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3) !important;
}
div.stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.45) !important;
}

/* ══════════ CARDS ══════════ */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05) !important;
    padding: 10px !important;
    background: #ffffff;
}

/* ══════════ TABS ══════════ */
div[data-testid="stTabs"] button {
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 20px !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #2563eb !important;
    border-bottom: 3px solid #2563eb !important;
    background: rgba(37, 99, 235, 0.05) !important;
}

/* ══════════ SECTION TITLE ══════════ */
.sec-title {
    font-size: 0.85rem;
    font-weight: 800;
    color: #1e293b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 10px 0 15px;
    padding-left: 10px;
    border-left: 4px solid #3b82f6;
}

/* ══════════ CONTROL BOX ══════════ */
.control-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px 16px;
    margin: 8px 0 12px;
}

/* ══════════ LOG TERMINAL ══════════ */
.log-box {
    background: #0f172a;
    color: #38bdf8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    line-height: 1.75;
    padding: 16px;
    border-radius: 12px;
    max-height: 250px;
    overflow-y: auto;
    margin-top: 8px;
    border: 1px solid #334155;
    white-space: pre-wrap;
    word-break: break-word;
}
.log-box::-webkit-scrollbar { width: 6px; }
.log-box::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }

/* ══════════ APP HEADER ══════════ */
.app-header {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    color: #fff;
    border-radius: 16px;
    padding: 24px 30px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(15, 23, 42, 0.2);
}
.app-header h1 {
    color: #fff;
    margin: 0;
    font-size: 1.8rem;
    font-weight: 900;
    background: linear-gradient(to right, #60a5fa, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.app-header p {
    color: #94a3b8;
    margin: 5px 0 0;
    font-size: 0.95rem;
}

/* ══════════ SIDEBAR LOGO ══════════ */
.sb-logo { text-align: center; padding: 16px 0 4px; }
.sb-icon {
    width: 48px; height: 48px; border-radius: 14px;
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.5rem; margin-bottom: 8px;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
}
.sb-name { font-size: 1.05rem; font-weight: 800; color: #f8fafc !important; }
.sb-ver { font-size: 0.75rem; color: #94a3b8 !important; }

.cfg-label { font-size: 0.85rem; font-weight: 700; color: #475569; margin-bottom: 8px; }
.tpl-hint { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════
for key, default_value in [("download_status", "idle"), ("logged_in", False)]:
    if key not in st.session_state:
        st.session_state[key] = default_value

# ══════════════════════════════════════════════════════════════
# ĐĂNG NHẬP
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    _, center_col, _ = st.columns([1, 1.3, 1])
    with center_col:
        st.markdown("""
        <div style="text-align: center; padding: 40px 0 20px;">
            <div style="width: 70px; height: 70px; border-radius: 18px; background: linear-gradient(135deg, #3b82f6, #2563eb); display: inline-flex; align-items: center; justify-content: center; font-size: 2rem; margin-bottom: 15px; box-shadow: 0 4px 20px rgba(37, 99, 235, 0.4);">🖼️</div>
            <h1 style="color: #1e293b; font-size: 1.8rem; font-weight: 900; margin: 0;">Media Tool VIP Pro</h1>
            <p style="color: #64748b; font-size: 0.95rem; margin: 8px 0 25px;">Hệ thống xử lý ảnh siêu phân giải</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            username = st.text_input("Tài khoản", placeholder="Nhập tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
            if st.button("Đăng Nhập", type="primary", use_container_width=True):
                if username == "ducpro" and password == "234766":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Sai tài khoản hoặc mật khẩu")

        st.markdown(
            "<p style='text-align:center;color:#94a3b8;font-size:.75rem;"
            "margin-top:20px'>Media Tool Pro VIP v6.0</p>",
            unsafe_allow_html=True,
        )
    st.stop()

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="sb-logo">
        <div class="sb-icon">🖼️</div><br>
        <span class="sb-name">Media Tool VIP</span><br>
        <span class="sb-ver">v6.0 · ducpro</span>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<span style="background:rgba(16,185,129,0.2);color:#34d399;padding:4px 12px;border-radius:20px;font-size:0.8rem;font-weight:700;">✅ Drive API OK</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="background:rgba(239,68,68,0.2);color:#f87171;padding:4px 12px;border-radius:20px;font-size:0.8rem;font-weight:700;">⚠️ Drive chưa kết nối</span>', unsafe_allow_html=True)
    st.divider()

    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()

    st.markdown("**📋 Lịch sử**")
    render_history_sidebar()
    st.divider()

    if st.button("Đăng Xuất", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ══════════════════════════════════════════════════════════════
# IMPORT MODE MODULES
# ══════════════════════════════════════════════════════════════
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web import run_mode_web

# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <h1>🖼️ Media Tool VIP Pro</h1>
    <p>Xuất đa kích thước · Template naming · Mở khóa xử lý ảnh > 500MB · ZIP tự động</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CONFIG PANEL (dùng chung cho cả 3 tab, đã bỏ preset nhanh)
# ══════════════════════════════════════════════════════════════
def render_config_panel(tab_key: str) -> dict:
    with st.container(border=True):
        st.markdown(
            '<div class="sec-title">⚙️ CẤU HÌNH XỬ LÝ CHUYÊN SÂU</div>',
            unsafe_allow_html=True,
        )
        
        # ── KÍCH THƯỚC & TÙY CHỌN ──
        col_sizes, col_options = st.columns([1.5, 1])

        with col_sizes:
            st.markdown("<div class='cfg-label'>📐 Kích thước xuất (Hỗ trợ chọn đa size)</div>", unsafe_allow_html=True)
            default_sizes = ["1020×680 Ngang chuẩn"]
            selected_labels = st.multiselect(
                "Chọn kích thước:",
                list(SIZE_PRESETS.keys()),
                default=default_sizes,
                key=f"sizes_{tab_key}",
                label_visibility="collapsed",
            )

            custom_size_on = st.toggle("➕ Thêm kích thước tùy chỉnh", key=f"custom_on_{tab_key}")
            custom_w, custom_h = 800, 800
            if custom_size_on:
                col_w, col_h = st.columns(2)
                custom_w = col_w.number_input("Rộng (px):", min_value=100, max_value=10000, value=800, step=10, key=f"cw_{tab_key}")
                custom_h = col_h.number_input("Cao (px):", min_value=100, max_value=10000, value=800, step=10, key=f"ch_{tab_key}")

        with col_options:
            st.markdown("<div class='cfg-label'>🎛️ Thông số tối ưu</div>", unsafe_allow_html=True)

            quality = st.slider("Chất lượng nén (%):", min_value=50, max_value=100, value=95, step=5, key=f"quality_{tab_key}")

            has_letterbox = any(
                SIZE_PRESETS.get(label, (None, None, ""))[2] == "letterbox"
                and SIZE_PRESETS.get(label, (None, None, ""))[0] is not None
                for label in selected_labels
            )
            if has_letterbox or custom_size_on:
                scale_pct = st.slider("Phóng to chi tiết (%):", min_value=50, max_value=150, value=100, step=5, key=f"scale_{tab_key}")
            else:
                scale_pct = 100

            export_format = st.selectbox(
                "Định dạng file:",
                list(EXPORT_FORMATS.keys()),
                index=0,
                key=f"fmt_{tab_key}",
            )

        # ── NAMING TEMPLATE ──
        st.markdown("<div class='cfg-label' style='margin-top: 15px;'>✏️ Cấu trúc đặt tên (Naming Template)</div>", unsafe_allow_html=True)
        col_template, col_rename = st.columns([2.5, 1])
        with col_template:
            template = st.text_input(
                "Template:",
                value="{name}_{color}_{nn}",
                placeholder="{name}_{color}_{nn}",
                key=f"tpl_{tab_key}",
                label_visibility="collapsed",
            )
        with col_rename:
            rename_enabled = st.toggle("Cho phép sửa tên SP", value=True, key=f"rename_{tab_key}")

        st.markdown(
            "<div class='tpl-hint'>"
            "Biến hỗ trợ: <code>{name}</code> tên SP · <code>{color}</code> màu · "
            "<code>{nn}</code> số 01 · <code>{nnn}</code> số 001 · "
            "<code>{original}</code> tên file gốc"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── BUILD CONFIG DICT ──
    sizes_list = []
    for label in selected_labels:
        if label in SIZE_PRESETS:
            sizes_list.append(SIZE_PRESETS[label])
    if custom_size_on:
        sizes_list.append((int(custom_w), int(custom_h), "letterbox"))
    if not sizes_list:
        sizes_list = [(1020, 680, "letterbox")]

    return {
        "sizes": sizes_list,
        "scale_pct": scale_pct,
        "quality": quality,
        "export_format": export_format,
        "template": template or "{name}_{nn}",
        "rename": rename_enabled,
    }

# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
tab_drive, tab_local, tab_web, tab_guide = st.tabs([
    "🌐 Google Drive",
    "💻 Local (ZIP)",
    "🛒 Web TGDD/DMX",
    "📖 Hướng dẫn",
])

# ── TAB 1: GOOGLE DRIVE ──
with tab_drive:
    config_drive = render_config_panel("drive")
    run_mode_drive(config_drive, drive_service)

# ── TAB 2: LOCAL (ZIP) ──
with tab_local:
    config_local = render_config_panel("local")
    run_mode_local(config_local)

# ── TAB 3: WEB TGDD / DMX ──
with tab_web:
    config_web = render_config_panel("web")
    run_mode_web(config_web)

# ── TAB 4: HƯỚNG DẪN ──
with tab_guide:
    st.markdown("""
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:16px 20px; margin-bottom:14px; font-size:0.9rem; line-height:1.8;">
        <div style='font-size:1.05rem;font-weight:800;color:#1e293b;margin-bottom:8px'>
            📋 Media Tool VIP Pro v6.0 — Hệ thống xử lý ảnh chuyên nghiệp
        </div>
        Xuất <b>đa kích thước cùng lúc</b> từ 1 nguồn ảnh.
        Đã <b>mở khóa giới hạn dung lượng ảnh</b> (cho phép xử lý file lên đến 500MB+).
        Đặt tên bằng <b>template linh hoạt</b> ({name}_{color}_{nn}).
        Chọn <b>format xuất</b> (JPEG / PNG / WebP) và chất lượng tùy chỉnh.
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
        with st.expander("🌐 Google Drive — Hướng dẫn", expanded=True):
            st.markdown("""
**Bước 1:** Chia sẻ file/folder → "Bất kỳ ai có link"

**Bước 2:** Dán link vào ô (mỗi dòng 1 link)

**Bước 3:** Bật "Cho phép sửa tên SP" → điền tên cho từng link

**Bước 4:** Chọn kích thước (nhiều cùng lúc) → Bắt đầu

**Kết quả:** ZIP chứa subfolder cho mỗi kích thước nếu chọn nhiều.

*Folder/file lỗi tự động bỏ qua, không ảnh hưởng link khác.*
            """)

        with st.expander("💻 Local (ZIP) — Hướng dẫn"):
            st.markdown("""
**Bước 1:** Nén ảnh thành file `.zip` (giữ cấu trúc thư mục)

**Bước 2:** Upload lên (hỗ trợ nhiều file cùng lúc)

**Bước 3:** Bật "Cho phép sửa tên SP" → đặt tên folder output

**Bước 4:** Chọn cấu hình → Bắt đầu → Tải ZIP kết quả

*Hỗ trợ: jpg, png, webp, bmp. Tự động bỏ qua __MACOSX, .DS_Store.*
            """)

    with col_right:
        with st.expander("🛒 Web TGDD / DMX — Hướng dẫn", expanded=True):
            st.markdown("""
**Bước 1:** Dán link sản phẩm TGDD / DMX

**Bước 2:** Bấm "Quét" → hệ thống phát hiện màu sắc

**Bước 3:** Tick chọn màu cần tải, sửa tên nếu muốn

**Bước 4:** Bắt đầu → Tải ZIP

*Cấu trúc: `tên_sp/tên_màu/ảnh.jpg`. Ảnh lỗi tự động bỏ qua.*
            """)

        with st.expander("🔧 Template đặt tên — Chi tiết"):
            st.markdown("""
| Biến | Ý nghĩa | Ví dụ output |
|---|---|---|
| `{name}` | Tên sản phẩm / folder | Samsung_S25 |
| `{color}` | Tên màu sắc | Den, Trang |
| `{nn}` | Số thứ tự 2 chữ số | 01, 02, 03 |
| `{nnn}` | Số thứ tự 3 chữ số | 001, 002 |
| `{original}` | Tên file gốc | IMG_1234 |

**Ví dụ template:**
- `{name}_{nn}` → `Samsung_S25_01.jpg`
- `{name}_{color}_{nn}` → `Samsung_S25_Den_01.jpg`
- `SP_{original}` → `SP_IMG_1234.jpg`
            """)

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#94a3b8;font-size:0.8rem'>"
        "Media Tool VIP Pro v6.0 · Streamlit · Python · Pillow</p>",
        unsafe_allow_html=True,
    )
