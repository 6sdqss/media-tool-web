"""
app.py — Media Tool Pro VIP v6.0 (Auth & RBAC Edition)
Giao diện chính tích hợp bảo mật, tạo tài khoản, duyệt và phân quyền Tab động.
Chống mất dữ liệu qua GitHub Auto-sync.
"""

import streamlit as st
import time
import auth  # Module bảo mật chống mất data
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
    page_title="Media Tool VIP",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════
# CSS PREMIUM VIP
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
    max-width: 1050px;
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

/* ══════════ CARDS & ADMIN PANELS ══════════ */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05) !important;
    padding: 10px !important;
    background: #ffffff;
}
.admin-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 15px;
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

.cfg-label { font-size: 0.85rem; font-weight: 700; color: #475569; margin-bottom: 8px; }
.tpl-hint { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SESSION STATE - BẢO MẬT & TRẠNG THÁI
# ══════════════════════════════════════════════════════════════
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "permissions" not in st.session_state:
    st.session_state.permissions = []
if "download_status" not in st.session_state:
    st.session_state.download_status = "idle"

# ══════════════════════════════════════════════════════════════
# GIAO DIỆN ĐĂNG NHẬP / ĐĂNG KÝ TÀI KHOẢN
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    _, center_col, _ = st.columns([1, 1.3, 1])
    with center_col:
        st.markdown("""
        <div style="text-align: center; padding: 40px 0 20px;">
            <div style="width: 70px; height: 70px; border-radius: 18px; background: linear-gradient(135deg, #3b82f6, #2563eb); display: inline-flex; align-items: center; justify-content: center; font-size: 2rem; margin-bottom: 15px; box-shadow: 0 4px 20px rgba(37, 99, 235, 0.4);">💎</div>
            <h1 style="color: #1e293b; font-size: 1.8rem; font-weight: 900; margin: 0;">Media VIP Pro</h1>
            <p style="color: #64748b; font-size: 0.95rem; margin: 8px 0 15px;">Hệ thống xử lý ảnh độc quyền nội bộ</p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["🔐 Đăng Nhập", "📝 Đăng Ký Tài Khoản"])
        
        with tab_login:
            with st.container(border=True):
                user_login = st.text_input("Tài khoản", key="log_user", placeholder="Nhập tên tài khoản")
                pwd_login = st.text_input("Mật khẩu", type="password", key="log_pwd", placeholder="Nhập mật khẩu")
                if st.button("Đăng Nhập", type="primary", use_container_width=True):
                    success, msg, user_data = auth.authenticate(user_login, pwd_login)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = user_login
                        st.session_state.role = user_data["role"]
                        st.session_state.permissions = user_data["permissions"]
                        st.rerun()
                    else:
                        st.error(msg)
                        
        with tab_register:
            with st.container(border=True):
                user_reg = st.text_input("Tên tài khoản mới", key="reg_user")
                pwd_reg = st.text_input("Mật khẩu", type="password", key="reg_pwd")
                pwd_confirm = st.text_input("Xác nhận mật khẩu", type="password", key="reg_confirm")
                if st.button("Đăng Ký Tài Khoản", type="primary", use_container_width=True):
                    if not user_reg or not pwd_reg:
                        st.warning("⚠️ Vui lòng nhập đầy đủ thông tin!")
                    elif pwd_reg != pwd_confirm:
                        st.error("❌ Mật khẩu xác nhận không khớp!")
                    else:
                        success, msg = auth.register_user(user_reg, pwd_reg)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
    st.stop()

# ══════════════════════════════════════════════════════════════
# SIDEBAR (Sau khi đã đăng nhập)
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="text-align: center; padding: 16px 0;">
        <div style="font-size: 2.5rem; margin-bottom: 8px;">👤</div>
        <div style="font-size: 1.1rem; font-weight: 800; color: #fff;">{st.session_state.username.upper()}</div>
        <div style="font-size: 0.8rem; color: #38bdf8; margin-top: 4px;">Vai trò: {st.session_state.role.upper()}</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<div style="text-align:center;"><span style="background:rgba(16,185,129,0.2);color:#34d399;padding:4px 12px;border-radius:20px;font-size:0.8rem;font-weight:700;">✅ API Connected</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align:center;"><span style="background:rgba(239,68,68,0.2);color:#f87171;padding:4px 12px;border-radius:20px;font-size:0.8rem;font-weight:700;">⚠️ API Disconnected</span></div>', unsafe_allow_html=True)
    st.divider()

    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()

    st.markdown("**📋 Lịch sử**")
    render_history_sidebar()
    st.divider()

    if st.button("Đăng Xuất", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ══════════════════════════════════════════════════════════════
# IMPORT CÁC MODULE XỬ LÝ
# ══════════════════════════════════════════════════════════════
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web import run_mode_web

# ══════════════════════════════════════════════════════════════
# HEADER CHÍNH CỦA APP
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <h1>🖼️ Media Tool VIP Pro</h1>
    <p>Hệ thống xử lý ảnh siêu phân giải. Chế độ phân quyền bảo mật cấp cao (RBAC).</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# HÀM RENDER BẢNG CẤU HÌNH DÙNG CHUNG CHO CÁC TAB ĐƯỢC CẤP QUYỀN
# ══════════════════════════════════════════════════════════════
def render_config_panel(tab_key: str) -> dict:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚙️ CẤU HÌNH XỬ LÝ CHUYÊN SÂU</div>', unsafe_allow_html=True)
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
            "<code>{nn}</code> số 01 · <code>{nnn}</code> số 001 · <code>{original}</code> tên gốc"
            "</div>",
            unsafe_allow_html=True,
        )

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
# XÂY DỰNG TABS ĐỘNG DỰA TRÊN QUYỀN (RBAC)
# ══════════════════════════════════════════════════════════════
is_admin = (st.session_state.role == "admin")
perms = st.session_state.permissions

tab_names = []
if is_admin: 
    tab_names.append("🛡️ ADMIN PANEL")
if is_admin or "drive" in perms: 
    tab_names.append("🌐 Google Drive")
if is_admin or "local" in perms: 
    tab_names.append("💻 Local (ZIP)")
if is_admin or "web" in perms: 
    tab_names.append("🛒 Web TGDD/DMX")
tab_names.append("📖 Hướng dẫn")

# Render các Tab được cấp quyền
tabs = st.tabs(tab_names)
tab_idx = 0

# ── TAB 0: ADMIN PANEL (Chỉ Admin mới thấy) ──
if is_admin:
    with tabs[tab_idx]:
        st.markdown('<div class="sec-title">👑 QUẢN LÝ TÀI KHOẢN & PHÂN QUYỀN TRUY CẬP</div>', unsafe_allow_html=True)
        db = auth.load_db()
        
        for u_name, u_data in db.items():
            if u_data["role"] == "admin": 
                continue # Không tự sửa quyền admin
            
            with st.container():
                st.markdown(f'<div class="admin-card">', unsafe_allow_html=True)
                col_info, col_status, col_perms, col_action = st.columns([1.5, 1, 2, 1])
                
                with col_info:
                    st.markdown(f"**👤 {u_name}**")
                    if u_data["status"] == "pending":
                        st.markdown("🔴 *Đang chờ duyệt*")
                    elif u_data["status"] == "approved":
                        st.markdown("🟢 *Đã duyệt*")
                    else:
                        st.markdown("⚫ *Đã khóa*")
                        
                with col_status:
                    new_st = st.selectbox(
                        "Trạng thái", 
                        ["pending", "approved", "banned"], 
                        index=["pending", "approved", "banned"].index(u_data["status"]),
                        key=f"st_{u_name}"
                    )
                with col_perms:
                    new_pm = st.multiselect(
                        "Phân quyền Tab", 
                        ["drive", "local", "web"], 
                        default=u_data["permissions"], 
                        key=f"pm_{u_name}"
                    )
                with col_action:
                    st.write("") # Căn lề cho nút
                    if st.button("Lưu & Đồng bộ", key=f"save_{u_name}", type="primary", use_container_width=True):
                        auth.update_user_admin(u_name, new_st, new_pm)
                        st.success("Đã lưu!")
                        time.sleep(1)
                        st.rerun()
                    if st.button("Xóa User", key=f"del_{u_name}", use_container_width=True):
                        auth.delete_user(u_name)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    tab_idx += 1

# ── TAB: GOOGLE DRIVE ──
if is_admin or "drive" in perms:
    with tabs[tab_idx]:
        config_drive = render_config_panel("drive")
        run_mode_drive(config_drive, drive_service)
    tab_idx += 1

# ── TAB: LOCAL (ZIP) ──
if is_admin or "local" in perms:
    with tabs[tab_idx]:
        config_local = render_config_panel("local")
        run_mode_local(config_local)
    tab_idx += 1

# ── TAB: WEB TGDD/DMX ──
if is_admin or "web" in perms:
    with tabs[tab_idx]:
        config_web = render_config_panel("web")
        run_mode_web(config_web)
    tab_idx += 1

# ── TAB: HƯỚNG DẪN ──
with tabs[tab_idx]:
    st.markdown("""
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:16px 20px; margin-bottom:14px; font-size:0.9rem; line-height:1.8;">
        <div style='font-size:1.05rem;font-weight:800;color:#1e293b;margin-bottom:8px'>
            📋 Hệ thống Media Tool VIP Pro — Phân quyền bảo mật
        </div>
        Hệ thống này hoạt động theo cơ chế <b>RBAC (Role-Based Access Control)</b>. 
        Bạn chỉ nhìn thấy các Tab mà Quản trị viên (Admin) đã phê duyệt và cấp quyền cho bạn.
        Dữ liệu tài khoản của bạn được đồng bộ tự động lên server chống mất phiên làm việc.
    </div>
    """, unsafe_allow_html=True)
    
    col_left, col_right = st.columns(2)
    with col_left:
        with st.expander("Quy trình duyệt tài khoản (Dành cho người mới)", expanded=True):
            st.markdown("""
            1. Đăng ký tài khoản ở màn hình Đăng Nhập.
            2. Báo cho Quản trị viên (`ducpro`).
            3. Quản trị viên vào Admin Panel đổi trạng thái từ Pending -> Approved.
            4. Quản trị viên tick chọn Tab được phép sử dụng (Web, Local, Drive).
            5. Đăng nhập lại để thấy các Tab công cụ.
            """)
    with col_right:
        with st.expander("Tính năng xử lý ảnh VIP", expanded=True):
            st.markdown("""
            - **Mở khóa Max Image Pixels**: Xử lý ảnh > 500MB không bị văng.
            - **Naming Template**: Đổi tên linh hoạt `{name}_{color}_{nn}`.
            - **Multi-size Auto-ZIP**: Xuất nhiều size vào sub-folder tự động.
            """)
