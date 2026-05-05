"""
app.py — Media Tool Pro VIP Pro v8.0
- Auth + Admin Panel + GitHub Sync
- Phân quyền tab theo user
- Studio Scale chỉnh từng ảnh
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

# ── Modes (import an toàn, không sập app nếu thiếu file) ──
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
except Exception:
    run_mode_drive = None

try:
    from mode_local import run_mode_local
except Exception:
    run_mode_local = None


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
    max-width: 1320px;
    padding-top: 0.8rem;
    padding-bottom: 2rem;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#09111f 0%,#0f172a 55%,#131c31 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.14) !important;
}
section[data-testid="stSidebar"] * { color: #dbe7ff !important; }
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
.hero-shell h1 { margin:0; font-size:2rem; font-weight:900; color:#fff; letter-spacing:-.03em; }
.hero-shell p  { margin:8px 0 0; color:#c7d2fe; line-height:1.7; font-size:.95rem; }

.hero-card {
    background: linear-gradient(135deg,#f8fbff 0%,#eef4ff 48%,#f5f3ff 100%);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 18px;
    padding: 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 10px 28px rgba(99,102,241,0.06);
}
.hero-card h2 { margin:0 0 4px; color:#1e1b4b; font-size:1.18rem; font-weight:800; }
.hero-card p  { margin:0; color:#4b5563; line-height:1.75; font-size:.9rem; }

.sec-title {
    font-size: .77rem; font-weight: 800; color: #4338ca;
    text-transform: uppercase; letter-spacing: 1.4px;
    margin: 12px 0 8px; padding: 7px 12px;
    border-left: 4px solid #6366f1;
    background: linear-gradient(90deg, rgba(99,102,241,0.08), transparent);
    border-radius: 0 8px 8px 0;
}

.guide-box {
    background: linear-gradient(135deg,#f5f3ff,#eef2ff,#eff6ff);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 16px;
    padding: 16px 18px; line-height: 1.8;
    font-size: .88rem; color: #334155;
}
.guide-box b { color: #312e81; }

.control-box {
    background: linear-gradient(135deg,#eef2ff,#f8fbff);
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 16px;
    padding: 10px 12px; margin: 8px 0 14px;
}

.log-box {
    background: linear-gradient(180deg,#09111f,#111827);
    color: #80eaff;
    font-family: 'JetBrains Mono', monospace;
    font-size: .74rem; line-height: 1.72;
    padding: 14px 16px; border-radius: 14px;
    max-height: 270px; overflow-y: auto;
    border: 1px solid rgba(99,102,241,0.14);
    white-space: pre-wrap; word-break: break-word;
}

div[data-testid="stTabs"] button {
    font-weight: 800 !important; font-size: .9rem !important;
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
    color: #fff !important; border: none !important;
    box-shadow: 0 10px 24px rgba(99,102,241,0.24) !important;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 16px 32px rgba(99,102,241,0.32) !important;
}

.sb-logo { text-align:center; padding: 14px 0 4px; }
.sb-badge {
    width:52px; height:52px; margin:0 auto 8px; border-radius:16px;
    display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg,#4f46e5,#7c3aed);
    box-shadow: 0 10px 24px rgba(99,102,241,0.28);
    font-size: 1.45rem;
}
.sb-title { font-weight:900; font-size:.98rem; color:#fff !important; }
.sb-sub   { font-size:.72rem; color:#94a3b8 !important; }

.login-shell { max-width: 460px; margin: 3rem auto 0; }
.login-card {
    background: white; border-radius: 24px;
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
.login-title { text-align:center; color:#1e1b4b; font-weight:900; font-size:1.6rem; margin:0; }
.login-sub   { text-align:center; color:#64748b; margin:6px 0 18px; line-height:1.7; font-size:.88rem; }

.cfg-label { font-size:.79rem; font-weight:800; color:#312e81; margin-bottom:5px; }
.tpl-hint  { font-size:.73rem; color:#6b7280; margin-top:4px; line-height:1.7; }

.status-pill {
    display:inline-block;
    padding: 4px 12px; border-radius: 999px;
    font-size:.74rem; font-weight:800;
    margin-right:4px;
}
.status-ok   { background: linear-gradient(135deg,#d1fae5,#a7f3d0); color: #065f46; }
.status-live { background: linear-gradient(135deg,#dbeafe,#bfdbfe); color: #1d4ed8; }
.status-admin{ background: linear-gradient(135deg,#fde68a,#fcd34d); color: #92400e; }

.user-chip {
    background: rgba(99,102,241,0.18);
    border-radius: 12px;
    padding: 10px 12px;
    border: 1px solid rgba(99,102,241,0.25);
    margin-bottom: 8px;
}
.user-chip b { color:#fff !important; font-size:.92rem; }
.user-chip span { color:#94a3b8 !important; font-size:.72rem; }

.lock-card {
    background: linear-gradient(135deg,#fef2f2,#fee2e2);
    border: 1px solid #fecaca;
    border-radius: 16px;
    padding: 22px 24px;
    text-align: center;
    color: #991b1b;
}
.lock-card h3 { margin: 0 0 6px; font-size: 1.1rem; font-weight: 900; }
.lock-card p  { margin: 0; font-size: .88rem; line-height: 1.7; color:#7f1d1d; }
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
        <div class="sb-logo">
            <div class="sb-badge">🖼️</div>
            <div class="sb-title">Media Tool Pro VIP Pro</div>
            <div class="sb-sub">v8.0 · Secure · GitHub Sync</div>
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
    <div class="hero-shell">
        <h1>🖼️ Media Tool Pro VIP Pro — Secure Edition</h1>
        <p>
            Xin chào <b style='color:#fde68a'>{user['username']}</b>!
            Hệ thống bảo mật đa lớp · Phân quyền theo từng tab · Tự sync GitHub chống mất data.
            Tập trung workflow TGDD + Drive + Local + Studio Scale chỉnh từng ảnh.
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
        "scale_pct": int(default_scale_pct),  # alias để tương thích mode_drive/mode_local
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
# TABS — chỉ hiển thị tab user có quyền
# ══════════════════════════════════════════════════════════════
def _locked(tab_label: str):
    st.markdown(
        f"""
        <div class="lock-card">
            <h3>🔒 Bạn chưa có quyền truy cập tab "{tab_label}"</h3>
            <p>Hãy liên hệ Admin <b>ducpro</b> để được cấp quyền sử dụng tính năng này.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
                st.error("Module `mode_web.py` không tải được. Kiểm tra lại file.")
            else:
                run_mode_web(config)

        elif key == "studio":
            if render_adjustment_studio is None:
                st.error("Module `mode_adjust.py` không tải được. Hãy đảm bảo file tồn tại đúng tên `mode_adjust.py` trong cùng thư mục với `app.py`.")
            else:
                render_adjustment_studio()

        elif key == "drive":
            if run_mode_drive is None:
                st.warning("Module `mode_drive.py` chưa sẵn sàng.")
            else:
                drive_service = get_gdrive_service()
                run_mode_drive(config, drive_service)

        elif key == "local":
            if run_mode_local is None:
                st.warning("Module `mode_local.py` chưa sẵn sàng.")
            else:
                run_mode_local(config)

        elif key == "guide":
            st.markdown(
                """
                <div class="guide-box">
                    <div style='font-size:1rem;font-weight:900;color:#1e1b4b;margin-bottom:8px'>
                        📌 Media Tool Pro VIP Pro — vận hành chuẩn
                    </div>
                    <b>1.</b> Đăng ký tài khoản → Admin <b>ducpro</b> duyệt và cấp quyền tab. <br>
                    <b>2.</b> Mỗi tab tương ứng 1 quyền: <code>web</code>, <code>studio</code>, <code>drive</code>, <code>local</code>. <br>
                    <b>3.</b> Tab Web TGDD: dán link → quét → chọn màu → resize. <br>
                    <b>4.</b> Tab Studio Scale: chỉnh từng ảnh sau batch → render lại. <br>
                    <b>5.</b> Tab Drive / Local: xử lý ảnh từ Google Drive hoặc file ZIP. <br>
                    <b>6.</b> Mọi thay đổi user/quyền đều tự sync GitHub → không lo mất data trên Streamlit Cloud.
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander("🔐 Cấu hình GitHub Sync (chống mất tài khoản)", expanded=False):
                st.markdown(
                    """
**Bước 1 — Tạo Personal Access Token GitHub:**
1. Vào https://github.com/settings/tokens?type=beta
2. Generate new token (Fine-grained): chọn repo của bạn, quyền **Contents: Read and write**.
3. Copy token (chỉ xem được 1 lần).

**Bước 2 — Cấu hình Streamlit Secrets:**
Vào *Manage app → Settings → Secrets*, thêm:
```toml
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxx"
GITHUB_REPO  = "username/media-tool-web"
GITHUB_BRANCH = "main"
