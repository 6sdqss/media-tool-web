"""
app.py — Media Tool Pro v6.0
Giao diện chính: Login, Sidebar, Config Panel, 4 Tab (Drive / Local / Web / Hướng dẫn).
Tính năng: Multi-size export, Quick presets, Template naming, Quality & Format control.
"""

import streamlit as st
from utils import (
    get_gdrive_service,
    SIZE_PRESETS,
    QUICK_PRESETS,
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
# CSS PREMIUM v6.0
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
    background: linear-gradient(175deg, #0a0e1a 0%, #111827 50%, #1a2332 100%) !important;
    border-right: 1px solid rgba(99, 102, 241, 0.1) !important;
}
section[data-testid="stSidebar"] * {
    color: #cbd5e1 !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(99, 102, 241, 0.08) !important;
    margin: 8px 0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.04) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(239, 68, 68, 0.8) !important;
    border-color: rgba(239, 68, 68, 0.5) !important;
}

/* ══════════ BUTTONS ══════════ */
div.stButton > button {
    border-radius: 12px;
    font-weight: 700;
    font-size: 0.9rem;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    height: 46px;
    letter-spacing: 0.3px;
    border: 1px solid #e5e7eb;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.3) !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4338ca, #6d28d9) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45) !important;
}
div.stButton > button:not([kind="primary"]):hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    border-color: #c7d2fe;
}

/* ══════════ DOWNLOAD BUTTON ══════════ */
div.stDownloadButton > button {
    background: linear-gradient(135deg, #059669, #10b981) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 12px !important;
    height: 50px !important;
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    box-shadow: 0 2px 10px rgba(16, 185, 129, 0.25) !important;
}
div.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #047857, #059669) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4) !important;
}

/* ══════════ CARDS ══════════ */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border: 1px solid rgba(99, 102, 241, 0.1) !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03), 0 4px 12px rgba(99, 102, 241, 0.04) !important;
    padding: 6px 4px !important;
}

/* ══════════ TABS ══════════ */
div[data-testid="stTabs"] button {
    font-weight: 700 !important;
    font-size: 0.86rem !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 8px 16px !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #6d28d9 !important;
    border-bottom: 3px solid #7c3aed !important;
    background: rgba(124, 58, 237, 0.04) !important;
}

/* ══════════ SECTION TITLE ══════════ */
.sec-title {
    font-size: 0.75rem;
    font-weight: 800;
    color: #6d28d9;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 14px 0 6px;
    padding: 5px 12px;
    border-left: 3px solid #7c3aed;
    background: linear-gradient(90deg, rgba(124, 58, 237, 0.06), transparent);
    border-radius: 0 6px 6px 0;
}

/* ══════════ CONTROL BOX ══════════ */
.control-box {
    background: linear-gradient(135deg, #eef2ff, #ede9fe);
    border: 1px solid rgba(124, 58, 237, 0.12);
    border-radius: 12px;
    padding: 12px 16px;
    margin: 8px 0 12px;
}

/* ══════════ LOG TERMINAL ══════════ */
.log-box {
    background: linear-gradient(180deg, #0a0e1a, #111827);
    color: #67e8f9;
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    font-size: 0.73rem;
    line-height: 1.75;
    padding: 14px 18px;
    border-radius: 12px;
    max-height: 220px;
    overflow-y: auto;
    margin-top: 8px;
    border: 1px solid rgba(99, 102, 241, 0.15);
    white-space: pre-wrap;
    word-break: break-word;
}
.log-box::-webkit-scrollbar { width: 5px; }
.log-box::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

/* ══════════ BADGES ══════════ */
.badge-ok {
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    color: #065f46;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.76rem;
    font-weight: 700;
    display: inline-block;
}
.badge-err {
    background: linear-gradient(135deg, #fee2e2, #fecaca);
    color: #991b1b;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.76rem;
    font-weight: 700;
    display: inline-block;
}

/* ══════════ GUIDE BOX ══════════ */
.guide-box {
    background: linear-gradient(135deg, #f5f3ff, #ede9fe, #ddd6fe);
    border: 1px solid rgba(124, 58, 237, 0.15);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 14px;
    font-size: 0.86rem;
    line-height: 1.8;
}
.guide-box b { color: #5b21b6; }

/* ══════════ APP HEADER ══════════ */
.app-header {
    background: linear-gradient(135deg, #1e1b4b, #312e81, #4c1d95);
    color: #fff;
    border-radius: 16px;
    padding: 18px 26px;
    margin-bottom: 16px;
    box-shadow: 0 4px 20px rgba(49, 46, 129, 0.35);
}
.app-header h1 {
    color: #fff;
    margin: 0;
    font-size: 1.6rem;
    font-weight: 900;
}
.app-header p {
    color: #c4b5fd;
    margin: 3px 0 0;
    font-size: 0.85rem;
}

/* ══════════ LOGIN ══════════ */
.login-card { text-align: center; padding: 28px 0 14px; }
.login-logo {
    width: 60px; height: 60px; border-radius: 16px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.8rem; margin-bottom: 10px;
    box-shadow: 0 4px 16px rgba(124, 58, 237, 0.3);
}
.login-title { color: #1e1b4b; font-size: 1.5rem; font-weight: 900; margin: 0; }
.login-sub { color: #6b7280; font-size: 0.85rem; margin: 4px 0 20px; }

/* ══════════ SIDEBAR LOGO ══════════ */
.sb-logo { text-align: center; padding: 16px 0 4px; }
.sb-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.3rem; margin-bottom: 6px;
    box-shadow: 0 2px 10px rgba(124, 58, 237, 0.25);
}
.sb-name { font-size: 0.95rem; font-weight: 800; color: #f1f5f9 !important; }
.sb-ver { font-size: 0.7rem; color: #6b7280 !important; }

/* ══════════ CONFIG LABELS ══════════ */
.cfg-label {
    font-size: 0.78rem;
    font-weight: 700;
    color: #4c1d95;
    margin-bottom: 4px;
}
.tpl-hint {
    font-size: 0.72rem;
    color: #9ca3af;
    margin-top: 2px;
}

/* ══════════ PRESET PILLS ══════════ */
.preset-row {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin: 6px 0 10px;
}
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
        <div class="login-card">
            <div class="login-logo">🖼️</div>
            <h1 class="login-title">Media Tool Pro</h1>
            <p class="login-sub">Xử lý ảnh sản phẩm chuyên nghiệp</p>
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
            "<p style='text-align:center;color:#94a3b8;font-size:.72rem;"
            "margin-top:14px'>Media Tool Pro v6.0</p>",
            unsafe_allow_html=True,
        )
    st.stop()


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    # Logo
    st.markdown("""
    <div class="sb-logo">
        <div class="sb-icon">🖼️</div><br>
        <span class="sb-name">Media Tool Pro</span><br>
        <span class="sb-ver">v6.0 · ducpro</span>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # Trạng thái Drive API
    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<span class="badge-ok">✅ Drive API OK</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">⚠️ Drive chưa kết nối</span>',
                    unsafe_allow_html=True)
    st.divider()

    # Session Stats
    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()

    # Lịch sử xử lý
    st.markdown("**📋 Lịch sử**")
    render_history_sidebar()
    st.divider()

    # Nút đăng xuất
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
    <h1>🖼️ Media Tool Pro</h1>
    <p>Xuất nhiều kích thước · Quick Presets · Template naming ·
       Chất lượng & Format tùy chỉnh · ZIP tự động</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# CONFIG PANEL (dùng chung cho cả 3 tab)
# ══════════════════════════════════════════════════════════════

def render_config_panel(tab_key: str) -> dict:
    """
    Render bảng cấu hình chung cho mỗi tab.
    Bao gồm: Quick presets, Multi-size, Custom size, Scale, Quality,
              Export format, Naming template.
    Trả về config dict.
    """
    with st.container(border=True):
        st.markdown(
            '<div class="sec-title">⚙️ CẤU HÌNH XỬ LÝ</div>',
            unsafe_allow_html=True,
        )

        # ── QUICK PRESETS ──
        st.markdown(
            "<div class='cfg-label'>⚡ Preset nhanh (click để áp dụng)</div>",
            unsafe_allow_html=True,
        )
        preset_cols = st.columns(len(QUICK_PRESETS))
        active_preset = None
        for idx, (preset_name, _) in enumerate(QUICK_PRESETS.items()):
            with preset_cols[idx]:
                if st.button(preset_name, key=f"preset_{tab_key}_{idx}",
                             use_container_width=True):
                    active_preset = preset_name

        # Nếu có preset được click → lưu vào session state
        preset_state_key = f"active_preset_{tab_key}"
        if active_preset:
            st.session_state[preset_state_key] = active_preset
        current_preset = st.session_state.get(preset_state_key)
        preset_config = QUICK_PRESETS.get(current_preset, {})

        st.write("")  # spacer

        # ── KÍCH THƯỚC & TÙY CHỌN ──
        col_sizes, col_options = st.columns([1.4, 1])

        with col_sizes:
            st.markdown(
                "<div class='cfg-label'>📐 Kích thước xuất (chọn nhiều)</div>",
                unsafe_allow_html=True,
            )
            default_sizes = preset_config.get("sizes", ["1020×680 Ngang chuẩn"])
            selected_labels = st.multiselect(
                "Chọn kích thước:",
                list(SIZE_PRESETS.keys()),
                default=default_sizes,
                key=f"sizes_{tab_key}",
                label_visibility="collapsed",
            )

            # Kích thước tùy chỉnh
            custom_size_on = st.toggle(
                "➕ Thêm kích thước tùy chỉnh",
                key=f"custom_on_{tab_key}",
            )
            custom_w, custom_h = 800, 800
            if custom_size_on:
                col_w, col_h = st.columns(2)
                custom_w = col_w.number_input(
                    "Width:", min_value=100, max_value=5000,
                    value=800, step=10, key=f"cw_{tab_key}")
                custom_h = col_h.number_input(
                    "Height:", min_value=100, max_value=5000,
                    value=800, step=10, key=f"ch_{tab_key}")

        with col_options:
            st.markdown(
                "<div class='cfg-label'>🎛️ Tùy chọn output</div>",
                unsafe_allow_html=True,
            )

            # Chất lượng JPEG
            default_quality = preset_config.get("quality", 95)
            quality = st.slider(
                "Chất lượng ảnh:",
                min_value=50, max_value=100,
                value=default_quality, step=5,
                key=f"quality_{tab_key}",
            )

            # Scale % (chỉ hiện khi có letterbox size)
            has_letterbox = any(
                SIZE_PRESETS.get(label, (None, None, ""))[2] == "letterbox"
                and SIZE_PRESETS.get(label, (None, None, ""))[0] is not None
                for label in selected_labels
            )
            if has_letterbox or custom_size_on:
                default_scale = preset_config.get("scale", 100)
                scale_pct = st.slider(
                    "Phóng to (%):",
                    min_value=50, max_value=150,
                    value=default_scale, step=5,
                    key=f"scale_{tab_key}",
                )
            else:
                scale_pct = 100

            # Định dạng xuất
            default_format = preset_config.get("format", "JPEG (.jpg)")
            export_format = st.selectbox(
                "Định dạng:",
                list(EXPORT_FORMATS.keys()),
                index=list(EXPORT_FORMATS.keys()).index(default_format)
                if default_format in EXPORT_FORMATS else 0,
                key=f"fmt_{tab_key}",
            )

        # ── NAMING TEMPLATE ──
        st.markdown(
            "<div class='cfg-label'>✏️ Template đặt tên ảnh</div>",
            unsafe_allow_html=True,
        )
        col_template, col_rename = st.columns([2.2, 1])
        with col_template:
            default_template = preset_config.get("template", "{name}_{nn}")
            template = st.text_input(
                "Template:",
                value=default_template,
                placeholder="{name}_{color}_{nn}",
                key=f"tpl_{tab_key}",
                label_visibility="collapsed",
            )
        with col_rename:
            rename_enabled = st.toggle(
                "Tên tùy chỉnh",
                key=f"rename_{tab_key}",
            )

        st.markdown(
            "<div class='tpl-hint'>"
            "Biến: <code>{name}</code> tên SP · <code>{color}</code> màu · "
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
    <div class="guide-box">
        <div style='font-size:1rem;font-weight:800;color:#4c1d95;margin-bottom:8px'>
            📋 Media Tool Pro v6.0 — Xử lý ảnh sản phẩm chuyên nghiệp
        </div>
        Xuất <b>nhiều kích thước cùng lúc</b> từ 1 nguồn ảnh.
        Dùng <b>Quick Presets</b> để áp dụng cấu hình nhanh.
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

**Bước 3:** Bật "Tên tùy chỉnh" → điền tên cho từng link

**Bước 4:** Chọn kích thước (nhiều cùng lúc) → Bắt đầu

**Kết quả:** ZIP chứa subfolder cho mỗi kích thước nếu chọn nhiều.

*Folder/file lỗi tự động bỏ qua, không ảnh hưởng link khác.*
            """)

        with st.expander("💻 Local (ZIP) — Hướng dẫn"):
            st.markdown("""
**Bước 1:** Nén ảnh thành file `.zip` (giữ cấu trúc thư mục)

**Bước 2:** Upload lên (hỗ trợ nhiều file cùng lúc)

**Bước 3:** Bật "Tên tùy chỉnh" → đặt tên folder output

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

        with st.expander("⚡ Quick Presets — Mô tả"):
            st.markdown("""
| Preset | Kích thước | Chất lượng | Dùng cho |
|---|---|---|---|
| **TGDD/DMX** | 1020×680 | 95% | Website TGDD, DMX |
| **Shopee/Lazada** | 1200² + 800² | 85% | Sàn TMĐT |
| **TikTok Shop** | 1200×1200 | 90% | TikTok |
| **PS Crop** | 1000×1000 | 95% | Photoshop |
            """)

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#94a3b8;font-size:0.74rem'>"
        "Media Tool Pro v6.0 · Streamlit · Python · Pillow</p>",
        unsafe_allow_html=True,
    )
