"""
app.py — Media Tool Pro VIP Pro v7.0
Bản nâng cấp tập trung Web TGDD + Studio Scale chỉnh riêng từng ảnh.
Giữ tinh thần code cũ, nhưng bỏ Quick Presets và nâng giao diện / độ ổn định.
"""

from __future__ import annotations

import streamlit as st

from utils import (
    EXPORT_FORMATS,
    SIZE_PRESETS,
    init_app_state,
    render_history_sidebar,
    render_session_stats,
)
from mode_web import run_mode_web
from mode_adjust import render_adjustment_studio


# ══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Media Tool Pro VIP Pro",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════
# CSS — VIP PRO
# ══════════════════════════════════════════════════════════════
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

#MainMenu, header, footer {visibility:hidden;}
.stDeployButton {display:none;}
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.block-container {
    max-width: 1280px;
    padding-top: 0.8rem;
    padding-bottom: 2rem;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#09111f 0%,#0f172a 55%,#131c31 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.14) !important;
}
section[data-testid="stSidebar"] * {
    color: #dbe7ff !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(148,163,184,0.18) !important;
    margin: 8px 0 !important;
}

.hero-shell {
    background:
      radial-gradient(circle at top right, rgba(99,102,241,0.32), transparent 28%),
      radial-gradient(circle at left bottom, rgba(14,165,233,0.22), transparent 32%),
      linear-gradient(135deg,#0f172a 0%,#1e1b4b 54%,#312e81 100%);
    color: white;
    border-radius: 24px;
    padding: 24px 28px;
    margin-bottom: 18px;
    box-shadow: 0 18px 50px rgba(15,23,42,0.28);
    border: 1px solid rgba(255,255,255,0.08);
}
.hero-shell h1 {
    margin: 0;
    font-size: 2rem;
    font-weight: 900;
    color: #fff;
    letter-spacing: -.03em;
}
.hero-shell p {
    margin: 8px 0 0;
    color: #c7d2fe;
    line-height: 1.7;
    font-size: .95rem;
}

.hero-card {
    background: linear-gradient(135deg,#f8fbff 0%,#eef4ff 48%,#f5f3ff 100%);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 18px;
    padding: 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 10px 28px rgba(99,102,241,0.06);
}
.hero-card h2 {
    margin: 0 0 4px;
    color: #1e1b4b;
    font-size: 1.18rem;
    font-weight: 800;
}
.hero-card p {
    margin: 0;
    color: #4b5563;
    line-height: 1.75;
    font-size: .9rem;
}

.sec-title {
    font-size: .77rem;
    font-weight: 800;
    color: #4338ca;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    margin: 12px 0 8px;
    padding: 7px 12px;
    border-left: 4px solid #6366f1;
    background: linear-gradient(90deg, rgba(99,102,241,0.08), transparent);
    border-radius: 0 8px 8px 0;
}

.guide-box {
    background: linear-gradient(135deg,#f5f3ff,#eef2ff,#eff6ff);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 16px;
    padding: 16px 18px;
    line-height: 1.8;
    font-size: .88rem;
    color: #334155;
}
.guide-box b { color: #312e81; }

.control-box {
    background: linear-gradient(135deg,#eef2ff,#f8fbff);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 16px;
    padding: 10px 12px;
    margin: 8px 0 14px;
}

.log-box {
    background: linear-gradient(180deg,#09111f,#111827);
    color: #80eaff;
    font-family: 'JetBrains Mono', monospace;
    font-size: .74rem;
    line-height: 1.72;
    padding: 14px 16px;
    border-radius: 14px;
    max-height: 270px;
    overflow-y: auto;
    border: 1px solid rgba(99,102,241,0.14);
    white-space: pre-wrap;
    word-break: break-word;
}

div[data-testid="stTabs"] button {
    font-weight: 800 !important;
    font-size: .9rem !important;
    border-radius: 12px 12px 0 0 !important;
    padding: 10px 18px !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #4338ca !important;
    border-bottom: 3px solid #6366f1 !important;
    background: rgba(99,102,241,0.07) !important;
}

.stButton > button, .stDownloadButton > button {
    border-radius: 14px !important;
    min-height: 46px !important;
    font-weight: 800 !important;
    font-size: .9rem !important;
    transition: all .18s ease !important;
}
.stButton > button[kind="primary"], .stDownloadButton > button {
    background: linear-gradient(135deg,#4f46e5,#7c3aed) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 10px 24px rgba(99,102,241,0.24) !important;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 16px 32px rgba(99,102,241,0.32) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid rgba(99,102,241,0.08) !important;
    box-shadow: 0 6px 18px rgba(15,23,42,0.04), 0 12px 30px rgba(99,102,241,0.04) !important;
}

.sb-logo { text-align:center; padding: 14px 0 4px; }
.sb-badge {
    width:52px; height:52px; margin:0 auto 8px; border-radius:16px;
    display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg,#4f46e5,#7c3aed);
    box-shadow: 0 10px 24px rgba(99,102,241,0.28);
    font-size: 1.45rem;
}
.sb-title { font-weight: 900; font-size: .98rem; color:#fff !important; }
.sb-sub { font-size: .72rem; color:#94a3b8 !important; }
.login-shell {
    max-width: 440px; margin: 4rem auto 0;
}
.login-card {
    background: white;
    border-radius: 24px;
    padding: 24px 22px 18px;
    border: 1px solid rgba(99,102,241,0.12);
    box-shadow: 0 20px 60px rgba(15,23,42,0.12);
}
.login-brand {
    width:72px; height:72px; border-radius:20px;
    margin:0 auto 12px;
    display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg,#4f46e5,#7c3aed);
    color:#fff; font-size:2rem;
    box-shadow: 0 14px 34px rgba(99,102,241,0.26);
}
.login-title {
    text-align:center; color:#1e1b4b; font-weight:900; font-size:1.6rem; margin:0;
}
.login-sub {
    text-align:center; color:#64748b; margin:6px 0 18px; line-height:1.7; font-size:.88rem;
}
.cfg-label {
    font-size: .79rem;
    font-weight: 800;
    color: #312e81;
    margin-bottom: 5px;
}
.tpl-hint {
    font-size: .73rem;
    color: #6b7280;
    margin-top: 4px;
    line-height: 1.7;
}
.status-pill {
    display:inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: .74rem;
    font-weight: 800;
}
.status-ok {
    background: linear-gradient(135deg,#d1fae5,#a7f3d0);
    color: #065f46;
}
.status-live {
    background: linear-gradient(135deg,#dbeafe,#bfdbfe);
    color: #1d4ed8;
}
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════
# SESSION
# ══════════════════════════════════════════════════════════════
init_app_state()


# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("<div class='login-shell'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="login-card">
            <div class="login-brand">🖼️</div>
            <h1 class="login-title">Media Tool Pro VIP Pro</h1>
            <p class="login-sub">
                Bản nâng cấp chuyên cho TGDD: giao diện đẹp hơn, xử lý ảnh lớn tốt hơn,
                có Studio chỉnh riêng từng ảnh sau khi quét batch.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=False):
        username = st.text_input("Tài khoản", placeholder="Nhập tên đăng nhập")
        password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
        if st.button("ĐĂNG NHẬP", type="primary", use_container_width=True):
            if username == "ducpro" and password == "234766":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Sai tài khoản hoặc mật khẩu.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        """
        <div class="sb-logo">
            <div class="sb-badge">🖼️</div>
            <div class="sb-title">Media Tool Pro VIP Pro</div>
            <div class="sb-sub">v7.0 · TGDD Focused · Studio Scale</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown('<span class="status-pill status-ok">✅ TGDD Engine Ready</span>', unsafe_allow_html=True)
    st.markdown('<span class="status-pill status-live">🚀 Scale từng ảnh sau batch</span>', unsafe_allow_html=True)
    st.divider()
    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()
    st.markdown("**📋 Lịch sử xử lý**")
    render_history_sidebar()
    st.divider()
    if st.button("ĐĂNG XUẤT", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown(
    """
    <div class="hero-shell">
        <h1>🖼️ Media Tool Pro VIP Pro — TGDD Edition</h1>
        <p>
            Giao diện đã nâng cấp theo hướng <b>pro / sạch / thực chiến</b>:
            bỏ toàn bộ Quick Presets, tập trung workflow TGDD,
            tối ưu batch lớn, hỗ trợ ảnh nặng hơn, và có <b>Studio Scale</b>
            để chỉnh từng tấm nếu bị zoom lố sau khi chạy batch.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════
# CONFIG PANEL
# ══════════════════════════════════════════════════════════════
def render_config_panel() -> dict:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚙️ CẤU HÌNH XỬ LÝ VIP PRO</div>', unsafe_allow_html=True)

        size_col, opt_col = st.columns([1.25, 1])
        with size_col:
            st.markdown('<div class="cfg-label">📐 Kích thước xuất</div>', unsafe_allow_html=True)
            selected_labels = st.multiselect(
                "Kích thước",
                list(SIZE_PRESETS.keys()),
                default=["1020×680 TGDD chuẩn"],
                label_visibility="collapsed",
                key="cfg_sizes",
            )
            custom_size_on = st.toggle("➕ Thêm kích thước tùy chỉnh", key="cfg_custom_on")
            custom_w, custom_h = 1200, 1200
            if custom_size_on:
                cw, ch = st.columns(2)
                custom_w = cw.number_input("Width", min_value=100, max_value=8000, value=1200, step=10)
                custom_h = ch.number_input("Height", min_value=100, max_value=8000, value=1200, step=10)

        with opt_col:
            st.markdown('<div class="cfg-label">🎛️ Output & hiệu năng</div>', unsafe_allow_html=True)
            quality = st.slider("Chất lượng ảnh", 60, 100, 95, 1, key="cfg_quality")
            default_scale_pct = st.slider("Scale mặc định cho batch (%)", 60, 150, 100, 1, key="cfg_scale")
            export_format = st.selectbox("Định dạng xuất", list(EXPORT_FORMATS.keys()), index=0, key="cfg_format")
            max_workers = st.slider("Số luồng tải / xử lý", 1, 8, 4, 1, key="cfg_workers")

        adv1, adv2 = st.columns([1.25, 1])
        with adv1:
            st.markdown('<div class="cfg-label">✏️ Template đặt tên</div>', unsafe_allow_html=True)
            template = st.text_input(
                "Template",
                value="{name}_{color}_{nn}",
                placeholder="{name}_{color}_{nn}",
                label_visibility="collapsed",
                key="cfg_template",
            )
            rename_enabled = st.toggle("Cho phép sửa tên sản phẩm sau khi quét", value=True, key="cfg_rename")
            st.markdown(
                "<div class='tpl-hint'>"
                "Biến hỗ trợ: <code>{name}</code> · <code>{color}</code> · <code>{nn}</code> · <code>{nnn}</code> · <code>{original}</code>"
                "</div>",
                unsafe_allow_html=True,
            )

        with adv2:
            st.markdown('<div class="cfg-label">🧠 Chế độ batch lớn</div>', unsafe_allow_html=True)
            huge_image_mode = st.toggle("Tối ưu ảnh lớn / batch nặng", value=True, key="cfg_huge")
            zip_compression = st.slider("Nén ZIP", 0, 9, 6, 1, key="cfg_zip_compress")
            st.caption(
                "Bật chế độ này khi bạn xử lý thư viện ảnh rất nặng hoặc file nguồn lớn. "
                "Mặc định app sẽ cố giữ ổn định bộ nhớ tốt hơn."
            )

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
        "quality": int(quality),
        "export_format": export_format,
        "template": template or "{name}_{color}_{nn}",
        "rename": bool(rename_enabled),
        "max_workers": int(max_workers),
        "huge_image_mode": bool(huge_image_mode),
        "zip_compression": int(zip_compression),
    }


# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
config = render_config_panel()

web_tab, studio_tab, guide_tab = st.tabs([
    "🛒 Web TGDD",
    "🎚️ Studio Scale",
    "📖 Hướng dẫn",
])

with web_tab:
    run_mode_web(config)

with studio_tab:
    render_adjustment_studio()

with guide_tab:
    st.markdown(
        """
        <div class="guide-box">
            <div style='font-size:1rem;font-weight:900;color:#1e1b4b;margin-bottom:8px'>
                📌 Media Tool Pro VIP Pro — cách vận hành đúng chuẩn
            </div>
            <b>1.</b> Dán link sản phẩm <b>thegioididong.com</b> rồi quét. <br>
            <b>2.</b> Tick màu cần lấy ảnh. Có thể sửa tên sản phẩm ngay trên giao diện. <br>
            <b>3.</b> Chạy batch resize với scale mặc định. <br>
            <b>4.</b> Nếu có tấm nào bị zoom lố hoặc crop lệch, qua tab <b>Studio Scale</b> để chỉnh riêng từng ảnh rồi render lại. <br>
            <b>5.</b> App ưu tiên workflow ổn định cho batch lớn, và đã bỏ hoàn toàn Quick Presets theo đúng yêu cầu.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("🧩 Điểm nâng cấp chính", expanded=True):
            st.markdown(
                """
- Giao diện VIP Pro sạch hơn, tập trung đúng workflow TGDD.
- Không còn nút áp dụng nhanh / Quick Presets.
- Có Studio chỉnh riêng từng ảnh sau khi batch xong.
- Scale từng ảnh + lệch ngang/dọc để cứu các ảnh bị crop lố.
- Giữ naming template linh hoạt.
- Tối ưu batch lớn bằng chế độ ảnh nặng + nén ZIP tùy chỉnh.
                """
            )

        with st.expander("📐 Cách dùng scale từng ảnh"):
            st.markdown(
                """
- <b>Scale > 100%</b>: phóng to thêm trong khung.
- <b>Lệch ngang</b>: kéo vùng crop sang trái / phải.
- <b>Lệch dọc</b>: kéo vùng crop lên / xuống.
- Khi một vài ảnh bị 'phóng quá tay', bạn chỉ chỉnh đúng các ảnh đó trong tab Studio, không cần chạy lại từ đầu toàn bộ luồng quét TGDD.
                """
            )

    with col2:
        with st.expander("💾 Xử lý ảnh lớn / batch nặng", expanded=True):
            st.markdown(
                """
- App đã thêm chế độ tối ưu cho ảnh lớn hơn bình thường.
- Tăng giới hạn upload / message nên cấu hình thêm file <code>.streamlit/config.toml</code> trong project.
- Với batch lớn, nên bật <b>Tối ưu ảnh lớn / batch nặng</b> và giữ số luồng ở mức vừa phải để ổn định RAM.
- Sau khi có batch, tab Studio cho phép render lại output đã tinh chỉnh mà không cần quét lại toàn bộ nguồn TGDD.
                """
            )

        with st.expander("✏️ Template đặt tên"):
            st.markdown(
                """
| Biến | Ý nghĩa |
|---|---|
| `{name}` | Tên sản phẩm |
| `{color}` | Tên màu |
| `{nn}` | Số thứ tự 2 chữ số |
| `{nnn}` | Số thứ tự 3 chữ số |
| `{original}` | Tên file nguồn |

Ví dụ: <code>{name}_{color}_{nn}</code>
                """
            )

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#94a3b8;font-size:.74rem'>"
        "Media Tool Pro VIP Pro v7.0 · Streamlit · Python · Pillow · TGDD Workflow"
        "</p>",
        unsafe_allow_html=True,
    )
