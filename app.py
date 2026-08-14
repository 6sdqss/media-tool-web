"""
app.py — Media Tool Pro v11.0 — entry point
════════════════════════════════════════════════════════════════
Kiến trúc mới:
    core/   — batch engine, imaging, download, presets, report, ...
    ui/     — theme, components, queue
    modes/  — web / drive / local adapters (dùng chung BatchManager)
    utils.py — compat shim chỉ để mode_adjust (Studio) chạy được

Streamlit rerun-safety: nút START chỉ dispatch khi
    sstate.acquire_batch_lock() == True
Adapter (modes/*) blocking-run BatchManager.start(), rerun trong lúc
đang chạy KHÔNG re-trigger vì state đã chuyển RUNNING.
"""
from __future__ import annotations

import logging
import time

import streamlit as st

# ── Basic logging setup ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ── Page config PHẢI là lệnh Streamlit đầu tiên ──────────────
st.set_page_config(
    page_title="Media Tool Pro v11",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Internal imports ─────────────────────────────────────────
from core import state as sstate
from core.batch import BatchManager, cleanup_old_workspaces
from core.memory import disk_free_mb, available_memory_mb
from ui import components as ui
from ui.theme import inject as inject_theme

# Auth
try:
    from auth import authenticate, register_user, change_own_password
    _AUTH_OK = True
except Exception as _e:
    _AUTH_OK = False
    _AUTH_ERR = str(_e)


# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
def _login_page() -> None:
    st.markdown("<div class='mtp-login-shell'>", unsafe_allow_html=True)
    st.markdown("<div class='mtp-login-card'>", unsafe_allow_html=True)
    st.markdown("<div class='mtp-login-brand'>M</div>", unsafe_allow_html=True)
    st.markdown("<div class='mtp-login-title'>Media Tool Pro</div>", unsafe_allow_html=True)
    st.markdown("<div class='mtp-login-sub'>v11.0 · Batch image processing</div>",
                unsafe_allow_html=True)

    tab_login, tab_reg = st.tabs(["Đăng nhập", "Đăng ký"])
    with tab_login:
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type="password", key="login_p")
        if st.button("Đăng nhập", type="primary", use_container_width=True, key="btn_login"):
            if not _AUTH_OK:
                st.error(f"Auth module lỗi: {_AUTH_ERR}")
            else:
                ok, msg, data = authenticate(u.strip(), p)
                if ok:
                    st.session_state["_user"] = data
                    st.rerun()
                else:
                    st.error(msg)

    with tab_reg:
        ru = st.text_input("Username mới", key="reg_u")
        rp = st.text_input("Password", type="password", key="reg_p")
        rp2 = st.text_input("Nhập lại password", type="password", key="reg_p2")
        if st.button("Tạo tài khoản", use_container_width=True, key="btn_reg"):
            if not _AUTH_OK:
                st.error(f"Auth module lỗi: {_AUTH_ERR}")
            elif rp != rp2:
                st.error("Password không khớp.")
            elif not ru or not rp:
                st.error("Điền đầy đủ.")
            else:
                ok, msg = register_user(ru.strip(), rp)
                if ok:
                    st.success(msg + " — chuyển qua tab Đăng nhập.")
                else:
                    st.error(msg)

    st.markdown("</div></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
def _sidebar(user: dict) -> None:
    with st.sidebar:
        st.markdown(
            f"<div style='padding:4px 0 10px'>"
            f"<div style='font-size:.72rem;color:var(--tx-4);"
            f"text-transform:uppercase;letter-spacing:.5px'>Đăng nhập</div>"
            f"<div style='font-size:1rem;font-weight:700;color:var(--tx-1);"
            f"margin-top:2px'>{user.get('username','')}</div>"
            f"<div style='font-size:.72rem;color:var(--tx-4);margin-top:2px'>"
            f"Role: {user.get('role','user')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<hr>", unsafe_allow_html=True)

        # System status
        st.markdown("<div class='mtp-sec-title'>Hệ thống</div>", unsafe_allow_html=True)
        ui.system_status_sidebar()

        st.markdown("<hr>", unsafe_allow_html=True)

        # Settings
        st.markdown("<div class='mtp-sec-title'>Cài đặt</div>", unsafe_allow_html=True)
        settings = sstate.settings()

        one_click = st.toggle(
            "⚡ One-Click mode",
            value=settings.get("one_click_mode", False),
            key="tog_oneclick",
            help="Không hỏi thêm sau khi bấm START — chạy toàn bộ pipeline auto.",
        )
        sstate.update_setting("one_click_mode", one_click)

        auto_zip = st.toggle(
            "📦 Auto ZIP",
            value=settings.get("auto_zip", True),
            key="tog_zip",
        )
        sstate.update_setting("auto_zip", auto_zip)

        auto_report = st.toggle(
            "📊 Auto Report CSV",
            value=settings.get("auto_report", True),
            key="tog_report",
        )
        sstate.update_setting("auto_report", auto_report)

        st.markdown("<hr>", unsafe_allow_html=True)

        # Cleanup
        st.markdown("<div class='mtp-sec-title'>Bảo trì</div>", unsafe_allow_html=True)
        if st.button("🧹 Dọn workspace cũ", use_container_width=True, key="btn_clean"):
            stats = cleanup_old_workspaces(keep_last=3, max_age_hours=6)
            st.success(
                f"Đã xoá {stats['deleted']} batch cũ · "
                f"giải phóng {stats['freed_mb']} MB"
            )

        st.markdown("<hr>", unsafe_allow_html=True)

        # History
        hist = st.session_state.get("batch_history", [])
        if hist:
            st.markdown("<div class='mtp-sec-title'>Batch gần nhất</div>",
                        unsafe_allow_html=True)
            for h in hist[:5]:
                st.markdown(
                    f"<div style='font-size:.75rem;padding:4px 0;"
                    f"border-bottom:1px solid var(--border)'>"
                    f"<span style='color:var(--tx-1);font-weight:600'>{h.get('mode','?')}</span> "
                    f"· <span style='color:var(--ok)'>{h.get('success',0)}</span>/"
                    f"{h.get('total','?')}"
                    f"<div style='color:var(--tx-4);font-size:.68rem'>"
                    f"{h.get('at','')} · {h.get('duration',0)}s · "
                    f"{h.get('preset', h.get('sizes',''))}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<hr>", unsafe_allow_html=True)

        # Logout
        if st.button("🚪 Đăng xuất", use_container_width=True, key="btn_logout"):
            for k in list(st.session_state.keys()):
                if not k.startswith("_theme"):
                    del st.session_state[k]
            st.rerun()


# ══════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════
def _home_page() -> None:
    ui.hero(
        "Image Resizer Pro",
        "Batch image processing automatic — <b>dán/upload → chọn preset → START</b>. "
        "Hệ thống tự validate, dedup, download, retry, resize, rename, ZIP, report.",
    )

    from core.presets import load_all
    presets = load_all()

    ui.section("Preset có sẵn")
    cols = st.columns(3)
    for i, p in enumerate(presets):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{p.name}**")
                st.caption(p.description or "")
                sizes_txt = " · ".join(s.label() for s in p.sizes)
                st.caption(f"📐 {sizes_txt}")
                st.caption(f"Q={p.quality} · {p.export_format}")

    ui.section("Bắt đầu nhanh")
    c1, c2, c3 = st.columns(3)
    if c1.button("💻 Upload / ZIP", use_container_width=True, key="q_local"):
        st.session_state["_nav"] = "Local"
        st.rerun()
    if c2.button("🌐 Google Drive", use_container_width=True, key="q_drive"):
        st.session_state["_nav"] = "Drive"
        st.rerun()
    if c3.button("🛒 Thegioididong", use_container_width=True, key="q_web"):
        st.session_state["_nav"] = "Web"
        st.rerun()

    hist = st.session_state.get("batch_history", [])
    if hist:
        ui.section("Lịch sử batch")
        for h in hist[:10]:
            st.markdown(
                f"<div style='padding:6px 12px;background:var(--surface);"
                f"border:1px solid var(--border);border-radius:6px;margin-bottom:4px;"
                f"font-size:.82rem'>"
                f"<b>{h.get('mode','?').upper()}</b> · "
                f"<span class='mtp-pill ok'>{h.get('success',0)}</span>/"
                f"<span class='mtp-pill muted'>{h.get('total','?')}</span> · "
                f"{h.get('duration',0)}s · {h.get('at','')} · "
                f"<span style='color:var(--tx-4)'>{h.get('preset', h.get('sizes',''))}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════
# GUIDE
# ══════════════════════════════════════════════════════════════
def _guide_page() -> None:
    ui.hero("📚 Hướng dẫn", "")
    st.markdown("""
### Nguyên tắc
1. **Chọn tab** phù hợp với nguồn ảnh: Local (upload ZIP/ảnh), Drive (link Google Drive), Web (link TGDD).
2. **Chọn preset** — mọi cấu hình (kích thước, chất lượng, format, template tên) đã được gói sẵn.
3. Bấm **START**. Hệ thống chạy tự động: validate → dedup → download → retry (3 lần backoff) → resize → rename → ZIP → CSV report.

### Chế độ One-Click (Sidebar)
Khi bật One-Click mode, bạn không phải điều chỉnh gì thêm giữa các bước — chỉ cần dán/upload rồi START.

### Anti-OOM
- Ảnh > 120 MP hoặc > 60 MB sẽ bị từ chối với lỗi `IMAGE_TOO_LARGE` / `FILE_TOO_LARGE` thay vì làm crash app.
- Số worker resize/download tự điều chỉnh theo RAM còn trống.
- Nếu đĩa còn < 150 MB, batch mới sẽ bị chặn — dùng nút "Dọn workspace cũ" ở sidebar.

### Retry logic
- Timeout / connection error → retry 3 lần (1s, 3.5s, 6s).
- Permission denied, invalid URL, invalid image → KHÔNG retry (retry sẽ luôn fail như nhau).

### Report CSV
Sau mỗi batch có nút "Tải Report CSV" gồm mọi item: status, error_type, error_message, source/output size, thời gian xử lý.
    """)


# ══════════════════════════════════════════════════════════════
# NAV / TAB ROUTER
# ══════════════════════════════════════════════════════════════
TABS = ["🏠 Home", "🛒 Web", "🌐 Drive", "💻 Local", "🎨 Studio", "📚 Guide"]
TAB_KEYS = {"Home", "Web", "Drive", "Local", "Studio", "Guide", "Admin"}


def _resolve_nav_choice(default_label: str = "🏠 Home") -> str:
    """
    Tab được chọn — ưu tiên st.session_state['_nav'] khi user vừa click
    Quick Action ở Home.
    """
    override = st.session_state.pop("_nav", "")
    if override:
        # map "Local" → "💻 Local"
        for t in TABS:
            if t.endswith(override):
                return t
        if override == "Admin":
            return "🔐 Admin"
    return default_label


def _admin_available(user: dict) -> bool:
    return (user or {}).get("role", "user") == "admin"


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main() -> None:
    inject_theme()
    sstate.init()

    user = st.session_state.get("_user")
    if not user:
        _login_page()
        return

    _sidebar(user)

    # Header
    ui.app_header(
        "Media Tool Pro v11",
        "Batch image processing · rerun-safe · anti-OOM · adaptive concurrency",
    )
    ui.one_click_banner()

    # Nav tabs — bằng radio (không phải st.tabs) để rerun-safe với current tab
    nav_options = list(TABS)
    if _admin_available(user):
        nav_options.append("🔐 Admin")

    default_choice = _resolve_nav_choice()
    if default_choice not in nav_options:
        default_choice = nav_options[0]

    st.markdown("<div class='app-tab-nav'>", unsafe_allow_html=True)
    choice = st.radio(
        "Nav", nav_options,
        index=nav_options.index(default_choice),
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Chọn preset dùng chung cho các tab batch — Home / Guide / Studio / Admin không cần
    show_preset = choice in ("🛒 Web", "🌐 Drive", "💻 Local")
    preset = None
    if show_preset:
        ui.section("Preset")
        preset = ui.preset_picker(choice.split(" ")[-1].lower())

    # Route
    if choice == "🏠 Home":
        _home_page()
    elif choice == "🛒 Web":
        from modes import web as mode_web
        mode_web.render(preset)
    elif choice == "🌐 Drive":
        from modes import drive as mode_drive
        mode_drive.render(preset)
    elif choice == "💻 Local":
        from modes import local as mode_local
        mode_local.render(preset)
    elif choice == "🎨 Studio":
        # Studio giữ nguyên từ v10.2 (compat qua utils.py shim)
        try:
            from mode_adjust import render_adjustment_studio
            render_adjustment_studio()
        except Exception as exc:
            st.error(f"Studio module lỗi: {exc}")
            st.caption("Studio đang chạy trên compat shim `utils.py`. "
                       "Nếu Đức muốn refactor Studio hoàn toàn, đây là công việc riêng.")
    elif choice == "📚 Guide":
        _guide_page()
    elif choice == "🔐 Admin" and _admin_available(user):
        try:
            from admin_panel import render_admin_panel
            render_admin_panel()
        except Exception as exc:
            st.error(f"Admin panel lỗi: {exc}")


if __name__ == "__main__" or True:
    main()
