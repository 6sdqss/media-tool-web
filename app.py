"""
app.py — Media Tool Pro VIP Pro v8.0
- Auth + Admin Panel + GitHub Sync
- Phân quyền tab theo user
- Giao diện Premium kết thừa từ v6.0
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
    page_title="Media Tool Pro VIP Pro",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════
# CSS — VIP PRO PREMIUM (Kế thừa phong cách v6.0)
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
    max-width: 1320px;
    padding-top: 1rem;
    padding-bottom: 2rem;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #0a0e1a 0%, #111827 50%, #1a2332 100%) !important;
    border-right: 1px solid rgba(99, 102, 241, 0.1) !important;
}
section[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
section[data-testid="stSidebar"] hr {
    border-color: rgba(99, 102, 241, 0.08) !important;
    margin: 8px 0 !important;
}

/* ── HERO & CARDS ── */
.app-header {
    background: linear-gradient(135deg, #1e1b4b, #312e81, #4c1d95);
    color: #fff;
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(49, 46, 129, 0.25);
    border: 1px solid rgba(255,255,255,0.08);
}
.app-header h1 { margin:0; font-size:1.8rem; font-weight:900; color:#fff; letter-spacing:-.02em; }
.app-header p  { margin:6px 0 0; color:#c4b5fd; line-height:1.6; font-size:.95rem; }

.hero-card {
    background: linear-gradient(135deg,#f8fbff 0%,#eef4ff 48%,#f5f3ff 100%);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 4px 12px rgba(99,102,241,0.04);
}
.hero-card h2 { margin:0 0 4px; color:#1e1b4b; font-size:1.15rem; font-weight:800; }
.hero-card p  { margin:0; color:#4b5563; line-height:1.6; font-size:.9rem; }

/* ── BORDERS & CONTAINERS ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border: 1px solid rgba(99, 102, 241, 0.12) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02) !important;
    padding: 10px 6px !important;
    background: #ffffff;
}

/* ── TITLES & LABELS ── */
.sec-title {
    font-size: 0.78rem; font-weight: 800; color: #6d28d9;
    text-transform: uppercase; letter-spacing: 1.4px;
    margin: 16px 0 10px; padding: 6px 14px;
    border-left: 4px solid #7c3aed;
    background: linear-gradient(90deg, rgba(124, 58, 237, 0.08), transparent);
    border-radius: 0 8px 8px 0;
}
.cfg-label { font-size:.85rem; font-weight:700; color:#4c1d95; margin-bottom:5px; }
.tpl-hint  { font-size:.75rem; color:#6b7280; margin-top:4px; line-height:1.6; }

/* ── GUIDE BOX ── */
.guide-box {
    background: linear-gradient(135deg,#f5f3ff,#ede9fe,#ddd6fe);
    border: 1px solid rgba(124,58,237,0.15);
    border-radius: 12px;
    padding: 16px 20px; line-height: 1.8;
    font-size: .9rem; color: #334155;
    margin-bottom: 14px;
}
.guide-box b { color: #5b21b6; }

/* ── LOG BOX ── */
.log-box {
    background: linear-gradient(180deg,#0a0e1a,#111827);
    color: #67e8f9;
    font-family: 'JetBrains Mono', monospace;
    font-size: .8rem; line-height: 1.7;
    padding: 16px; border-radius: 12px;
    max-height: 280px; overflow-y: auto;
    border: 1px solid rgba(99,102,241,0.2);
    white-space: pre-wrap; word-break: break-word;
}

/* ── TABS ── */
div[data-testid="stTabs"] button {
    font-weight: 700 !important; font-size: .95rem !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 20px !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #6d28d9 !important;
    border-bottom: 3px solid #7c3aed !important;
    background: rgba(124, 58, 237, 0.05) !important;
}

/* ── BUTTONS ── */
.stButton > button, .stDownloadButton > button {
    border-radius: 12px !important;
    min-height: 46px !important;
    font-weight: 700 !important;
    font-size: .95rem !important;
    transition: all .2s ease !important;
    border: 1px solid #e5e7eb !important;
}
.stButton > button[kind="primary"], .stDownloadButton > button {
    background: linear-gradient(135deg,#4f46e5,#7c3aed) !important;
    color: #fff !important; border: none !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.25) !important;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(99,102,241,0.35) !important;
}

/* ── LOGIN ── */
.login-shell { max-width: 480px; margin: 3rem auto 0; }
.login-card {
    background: white; border-radius: 20px;
    padding: 30px 24px;
    border: 1px solid rgba(99,102,241,0.15);
    box-shadow: 0 15px 40px rgba(15,23,42,0.08);
}
.login-brand {
    width:76px; height:76px; border-radius:18px;
    margin:0 auto 16px;
    display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg,#4f46e5,#7c3aed);
    color:#fff; font-size:2.2rem;
    box-shadow: 0 10px 24px rgba(99,102,241,0.3);
}
.login-title { text-align:center; color:#1e1b4b; font-weight:900; font-size:1.6rem; margin:0; }
.login-sub   { text-align:center; color:#64748b; margin:6px 0 20px; line-height:1.6; font-size:.9rem; }

/* ── BADGES & STATUS ── */
.status-pill {
    display:inline-block;
    padding: 5px 12px; border-radius: 999px;
    font-size:.75rem; font-weight:700;
    margin-right:4px;
}
.status-ok   { background: linear-gradient(135deg,#d1fae5,#a7f3d0); color: #065f46; }
.status-live { background: linear-gradient(135deg,#dbeafe,#bfdbfe); color: #1d4ed8; }
.status-admin{ background: linear-gradient(135deg,#fde68a,#fcd34d); color: #92400e; }

.user-chip {
    background: rgba(99,102,241,0.15);
    border-radius: 12px;
    padding: 12px 14px;
    border: 1px solid rgba(99,102,241,0.25);
    margin-bottom: 10px;
}
.user-chip b { color:#fff !important; font-size:.95rem; }
.user-chip span { color:#94a3b8 !important; font-size:.75rem; }

.lock-card {
    background: linear-gradient(135deg,#fef2f2,#fee2e2);
    border: 1px solid #fecaca;
    border-radius: 14px;
    padding: 24px 28px;
    text-align: center;
    color: #991b1b;
}
.lock-card h3 { margin: 0 0 8px; font-size: 1.15rem; font-weight: 800; }
.lock-card p  { margin: 0; font-size: .9rem; line-height: 1.6; color:#7f1d1d; }
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════
# SESSION
# ══════════════════════════════════════════════════════════════
init_app_state()

if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


# ══════════════════════════════════════════════════════════════
# LOGIN / REGISTER UI
# ══════════════════════════════════════════════════════════════
def render_login_screen():
    st.markdown("<div class='login-shell'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="login-card">
            <div class="login-brand">🖼️</div>
            <h1 class="login-title">Media Tool Pro VIP Pro</h1>
            <p class="login-sub">
                Hệ thống tài khoản bảo mật · Phân quyền theo từng tab · 
                Đồng bộ GitHub chống mất dữ liệu trên Streamlit Cloud.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔐 Đăng nhập", "📝 Đăng ký"])

    with tab_login:
        username = st.text_input("Tài khoản", placeholder="Nhập tên đăng nhập", key="login_user")
        password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu", key="login_pwd")
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
        st.caption("Sau khi đăng ký, tài khoản sẽ ở trạng thái **chờ Admin duyệt** trước khi truy cập tool.")
        new_user = st.text_input("Tên tài khoản mới", placeholder="ít nhất 3 ký tự (chữ/số/_/-)", key="reg_user")
        new_pwd = st.text_input("Mật khẩu", type="password", placeholder="ít nhất 4 ký tự", key="reg_pwd")
        new_pwd2 = st.text_input("Nhập lại mật khẩu", type="password", key="reg_pwd2")
        if st.button("ĐĂNG KÝ TÀI KHOẢN", type="primary", use_container_width=True, key="btn_register"):
            if new_pwd != new_pwd2:
                st.error("Hai lần nhập mật khẩu không khớp.")
            else:
                ok, msg = register_user(new_user, new_pwd)
                if ok:
                    st.success(msg)
                    st.info("⏳ Hãy thông báo cho Admin (ducpro) để được duyệt tài khoản.")
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
    st.markdown(
        """
        <div style="text-align:center; padding: 14px 0 4px;">
            <div style="width:56px; height:56px; margin:0 auto 10px; border-radius:14px; background: linear-gradient(135deg,#4f46e5,#7c3aed); display:flex; align-items:center; justify-content:center; font-size: 1.5rem; box-shadow: 0 8px 20px rgba(99,102,241,0.3);">🖼️</div>
            <div style="font-weight:900; font-size:1rem; color:#fff;">Media Tool Pro VIP Pro</div>
            <div style="font-size:.75rem; color:#94a3b8;">v8.0 · Secure · GitHub Sync</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    role_pill = "status-admin" if is_admin else "status-ok"
    role_text = "👑 ADMIN" if is_admin else "👤 USER"
    st.markdown(
        f"""
        <div class="user-chip">
            <b>{user['username']}</b><br>
            <span>{role_text} · {len(user.get('permissions', [])) if not is_admin else 'all'} quyền</span>
        </div>
        <span class="status-pill {role_pill}">{role_text}</span>
        <span class="status-pill status-live">🔒 Authenticated</span>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    with st.expander("🔑 Đổi mật khẩu của tôi"):
        old_p = st.text_input("Mật khẩu cũ", type="password", key="cp_old")
        new_p = st.text_input("Mật khẩu mới", type="password", key="cp_new")
        if st.button("Đổi mật khẩu", use_container_width=True, key="cp_btn"):
            ok, msg = change_own_password(user["username"], old_p, new_p)
            (st.success if ok else st.error)(msg)

    st.markdown("**📊 Phiên làm việc**")
    render_session_stats()
    st.divider()
    st.markdown("**📋 Lịch sử xử lý**")
    render_history_sidebar()
    st.divider()
    if st.button("ĐĂNG XUẤT", use_container_width=True, key="btn_logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown(
    f"""
    <div class="app-header">
        <h1>🖼️ Media Tool Pro VIP Pro — Secure Edition</h1>
        <p>
            Xin chào <b style='color:#fde68a'>{user['username']}</b>! 
            Hệ thống bảo mật đa lớp · Phân quyền theo từng tab · Tự sync GitHub chống mất data.
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
                custom_w = cw.number_input("Width", 100, 8000, 1200, 10)
                custom_h = ch.number_input("Height", 100, 8000, 1200, 10)

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
                "Biến: <code>{name}</code> · <code>{color}</code> · <code>{nn}</code> · <code>{nnn}</code> · <code>{original}</code>"
                "</div>",
                unsafe_allow_html=True,
            )

        with adv2:
            st.markdown('<div class="cfg-label">🧠 Chế độ batch lớn</div>', unsafe_allow_html=True)
            huge_image_mode = st.toggle("Tối ưu ảnh lớn / batch nặng", value=True, key="cfg_huge")
            zip_compression = st.slider("Nén ZIP", 0, 9, 6, 1, key="cfg_zip_compress")
            st.caption("Bật khi xử lý ảnh nặng để giữ ổn định bộ nhớ.")

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
    tab_labels.append("🛒 Web TGDD"); tab_keys.append("web")
if has_permission(user, "studio"):
    tab_labels.append("🎚️ Studio Scale"); tab_keys.append("studio")
if has_permission(user, "drive"):
    tab_labels.append("🌐 Google Drive"); tab_keys.append("drive")
if has_permission(user, "local"):
    tab_labels.append("💻 Local ZIP"); tab_keys.append("local")

tab_labels.append("📖 Hướng dẫn"); tab_keys.append("guide")
if is_admin:
    tab_labels.append("👑 Admin Panel"); tab_keys.append("admin")

if not tab_keys or tab_keys == ["guide"]:
    st.warning("⚠️ Tài khoản của bạn chưa được cấp quyền truy cập tab xử lý nào. Vui lòng liên hệ Admin để được duyệt.")

tabs = st.tabs(tab_labels)

for tab, key in zip(tabs, tab_keys):
    with tab:
        if key == "web":
            if run_mode_web is None:
                st.error(f"❌ Module `mode_web.py` lỗi: {_err_web}")
            else:
                run_mode_web(config)

        elif key == "studio":
            if render_adjustment_studio is None:
                st.error(f"❌ Module `mode_adjust.py` không tải được. \n\n**Lỗi:** `{_err_adjust}`\n\n💡 Vui lòng đảm bảo file tồn tại với tên chuẩn xác là `mode_adjust.py` trong thư mục gốc.")
            else:
                render_adjustment_studio()

        elif key == "drive":
            if run_mode_drive is None:
                st.error(f"❌ Module `mode_drive.py` lỗi: {_err_drive}")
            else:
                drive_service = get_gdrive_service()
                run_mode_drive(config, drive_service)

        elif key == "local":
            if run_mode_local is None:
                st.error(f"❌ Module `mode_local.py` lỗi: {_err_local}")
            else:
                run_mode_local(config)

        elif key == "guide":
            st.markdown(
                "<div class='guide-box'>"
                "<div style='font-size:1.05rem;font-weight:900;color:#1e1b4b;margin-bottom:8px'>"
                "📌 Media Tool Pro VIP Pro — Hướng dẫn Vận hành"
                "</div>"
                "<b>1.</b> Đăng ký tài khoản → Admin <b>ducpro</b> duyệt và cấp quyền tab. <br>"
                "<b>2.</b> Mỗi tab tương ứng 1 quyền riêng biệt. <br>"
                "<b>3.</b> Tab Web TGDD: dán link → quét → chọn màu → resize. <br>"
                "<b>4.</b> Tab Studio Scale: chỉnh riêng từng ảnh sau batch → render lại. <br>"
                "<b>5.</b> Tab Drive / Local: xử lý ảnh từ Google Drive hoặc file ZIP. <br>"
                "</div>",
                unsafe_allow_html=True
            )

        elif key == "admin":
            try:
                render_admin_panel()
            except Exception as e:
                st.warning(f"Module Admin chưa tải được: {e}")
