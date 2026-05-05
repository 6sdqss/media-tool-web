"""
admin_panel.py — Giao diện Admin để duyệt và phân quyền user.
Chỉ hiển thị cho user có role='admin'.
"""

from __future__ import annotations

import streamlit as st

from auth import (
    DEFAULT_PERMISSIONS,
    delete_user,
    list_users,
    pull_from_github,
    push_to_github,
    reset_password,
    update_user_admin,
)


PERMISSION_LABELS = {
    "web": "🛒 Web TGDD",
    "studio": "🎚️ Studio Scale",
    "drive": "🌐 Google Drive",
    "local": "💻 Local ZIP",
}

STATUS_LABELS = {
    "approved": ("✅ Đã duyệt", "#16a34a"),
    "pending": ("⏳ Chờ duyệt", "#d97706"),
    "banned": ("🚫 Đã khóa", "#dc2626"),
}


def render_admin_panel():
    st.markdown(
        "<div class='hero-card'>"
        "<h2>👑 Admin Panel — Quản trị tài khoản</h2>"
        "<p>Duyệt tài khoản đăng ký mới, phân quyền truy cập từng tab, khóa/mở/xóa tài khoản. "
        "Mọi thay đổi sẽ được tự động đồng bộ lên GitHub để không mất dữ liệu khi Streamlit Cloud reset container.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Thanh điều khiển GitHub Sync ──
    sync_col1, sync_col2, sync_col3 = st.columns([1, 1, 2])
    with sync_col1:
        if st.button("🔄 Pull từ GitHub", use_container_width=True):
            ok = pull_from_github(force=True)
            if ok:
                st.success("Đã đồng bộ DB từ GitHub.")
            else:
                st.warning("Không pull được (chưa cấu hình hoặc lỗi mạng).")
            st.rerun()
    with sync_col2:
        if st.button("⬆️ Push lên GitHub", use_container_width=True):
            ok = push_to_github()
            st.success("Đã push DB lên GitHub.") if ok else st.warning("Push thất bại — kiểm tra GITHUB_TOKEN.")
    with sync_col3:
        st.caption(
            "💡 Cấu hình `GITHUB_TOKEN` và `GITHUB_REPO` (định dạng `user/repo`) "
            "trong **Streamlit Secrets** để bật chế độ chống mất dữ liệu."
        )

    st.divider()

    db = list_users()

    # ── Thống kê tổng quan ──
    total = len(db)
    approved = sum(1 for u in db.values() if u.get("status") == "approved")
    pending = sum(1 for u in db.values() if u.get("status") == "pending")
    banned = sum(1 for u in db.values() if u.get("status") == "banned")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng user", total)
    k2.metric("Đã duyệt", approved)
    k3.metric("Chờ duyệt", pending)
    k4.metric("Đã khóa", banned)

    # ── Tab pending / approved / banned ──
    tab_pending, tab_all = st.tabs([
        f"⏳ Chờ duyệt ({pending})",
        f"📋 Tất cả tài khoản ({total})",
    ])

    with tab_pending:
        if pending == 0:
            st.info("Không có tài khoản nào đang chờ duyệt.")
        else:
            for username, info in db.items():
                if info.get("status") == "pending":
                    _render_user_card(username, info, expanded=True)

    with tab_all:
        search = st.text_input("🔍 Tìm tài khoản", placeholder="Nhập tên user...")
        for username, info in sorted(db.items()):
            if search and search.lower() not in username.lower():
                continue
            _render_user_card(username, info, expanded=False)


def _render_user_card(username: str, info: dict, expanded: bool = False):
    status = info.get("status", "pending")
    label, color = STATUS_LABELS.get(status, ("?", "#6b7280"))
    role = info.get("role", "user")
    role_badge = "👑 ADMIN" if role == "admin" else "👤 USER"

    title = f"{role_badge} · `{username}` · {label}"

    with st.expander(title, expanded=expanded):
        info_col, action_col = st.columns([1.3, 1])

        with info_col:
            st.markdown(
                f"""
                - **Username:** `{username}`
                - **Vai trò:** {role}
                - **Trạng thái:** <span style='color:{color};font-weight:700'>{label}</span>
                - **Tạo lúc:** {info.get('created_at', '-')}
                - **Quyền hiện tại:** {', '.join(info.get('permissions', [])) or '— (chưa có)'}
                - **Ghi chú:** {info.get('note', '') or '—'}
                """,
                unsafe_allow_html=True,
            )

        with action_col:
            if username == "ducpro":
                st.info("🔒 Master admin — không thể chỉnh sửa.")
                return

            new_status = st.selectbox(
                "Trạng thái",
                ["approved", "pending", "banned"],
                index=["approved", "pending", "banned"].index(status) if status in ["approved", "pending", "banned"] else 1,
                key=f"st_{username}",
            )

            current_perms = info.get("permissions", []) or []
            new_perms = st.multiselect(
                "Quyền truy cập tab",
                options=DEFAULT_PERMISSIONS,
                default=[p for p in current_perms if p in DEFAULT_PERMISSIONS],
                format_func=lambda x: PERMISSION_LABELS.get(x, x),
                key=f"pm_{username}",
            )

            new_note = st.text_input(
                "Ghi chú",
                value=info.get("note", ""),
                key=f"nt_{username}",
                placeholder="VD: Đối tác A, hết hạn 30/12...",
            )

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("💾 Lưu", key=f"save_{username}", use_container_width=True, type="primary"):
                    update_user_admin(username, new_status, new_perms, new_note)
                    st.success(f"Đã cập nhật `{username}`")
                    st.rerun()
            with btn_col2:
                if st.button("🗑️ Xóa", key=f"del_{username}", use_container_width=True):
                    if delete_user(username):
                        st.success(f"Đã xóa `{username}`")
                        st.rerun()
                    else:
                        st.error("Không thể xóa user này.")

            with st.popover("🔑 Reset mật khẩu", use_container_width=True):
                new_pwd = st.text_input(
                    "Mật khẩu mới (≥ 4 ký tự)",
                    type="password",
                    key=f"rp_{username}",
                )
                if st.button("Xác nhận reset", key=f"rp_btn_{username}", use_container_width=True):
                    if reset_password(username, new_pwd):
                        st.success(f"Đã reset mật khẩu cho `{username}`")
                    else:
                        st.error("Mật khẩu không hợp lệ.")
