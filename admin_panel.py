"""
admin_panel.py — Giao diện Admin v9.0
─────────────────────────────────────────────────────────
Quản trị tài khoản: duyệt, phân quyền, khóa/mở/xóa, reset mật khẩu.
Tự đồng bộ GitHub để chống mất dữ liệu khi Streamlit Cloud reset container.
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
    "studio": "🎚 Studio",
    "drive": "🌐 Drive",
    "local": "💻 Local ZIP",
}

STATUS_LABELS = {
    "approved": ("✅ Đã duyệt", "#22c55e"),
    "pending": ("⏳ Chờ duyệt", "#f59e0b"),
    "banned": ("🚫 Khóa", "#ef4444"),
}


def render_admin_panel():
    st.markdown(
        "<div class='hero-card'>"
        "<h2>👑 Admin Panel</h2>"
        "<p>Duyệt, phân quyền, khóa/mở/xóa tài khoản. Mọi thay đổi tự sync GitHub.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Thanh điều khiển GitHub Sync ──
    sync_col1, sync_col2 = st.columns(2)
    with sync_col1:
        if st.button("🔄 Pull GitHub", use_container_width=True, key="adm_pull"):
            ok = pull_from_github(force=True)
            if ok:
                st.success("Đã pull DB từ GitHub.")
            else:
                st.warning("Không pull được (chưa cấu hình hoặc lỗi mạng).")
            st.rerun()
    with sync_col2:
        if st.button("⬆️ Push GitHub", use_container_width=True, key="adm_push"):
            ok = push_to_github()
            (st.success if ok else st.warning)(
                "Đã push DB lên GitHub." if ok else "Push thất bại — kiểm tra GITHUB_TOKEN."
            )

    st.caption(
        "💡 Cấu hình `GITHUB_TOKEN` + `GITHUB_REPO` (`user/repo`) trong Streamlit Secrets "
        "để bật chế độ chống mất dữ liệu."
    )

    st.divider()

    db = list_users()

    # ── Thống kê ──
    total = len(db)
    approved = sum(1 for u in db.values() if u.get("status") == "approved")
    pending = sum(1 for u in db.values() if u.get("status") == "pending")
    banned = sum(1 for u in db.values() if u.get("status") == "banned")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng", total)
    k2.metric("Duyệt", approved)
    k3.metric("Chờ", pending)
    k4.metric("Khóa", banned)

    # ── Tabs ──
    tab_pending, tab_all = st.tabs([
        f"⏳ Chờ duyệt ({pending})",
        f"📋 Tất cả ({total})",
    ])

    with tab_pending:
        if pending == 0:
            st.info("Không có tài khoản chờ duyệt.")
        else:
            for username, info in db.items():
                if info.get("status") == "pending":
                    _render_user_card(username, info, expanded=True)

    with tab_all:
        search = st.text_input("🔍 Tìm tài khoản", placeholder="Nhập username...", key="adm_search")
        for username, info in sorted(db.items()):
            if search and search.lower() not in username.lower():
                continue
            _render_user_card(username, info, expanded=False)


def _render_user_card(username: str, info: dict, expanded: bool = False):
    status = info.get("status", "pending")
    label, color = STATUS_LABELS.get(status, ("?", "#6b7280"))
    role = info.get("role", "user")
    role_badge = "👑 ADMIN" if role == "admin" else "👤 USER"

    title = f"{role_badge} · {username} · {label}"

    with st.expander(title, expanded=expanded):
        info_col, action_col = st.columns([1.2, 1])

        with info_col:
            perms_text = ', '.join(info.get('permissions', [])) or '— (chưa có)'
            st.markdown(
                f"""
                <div style='font-size:0.74rem;line-height:1.7;color:#cbd5e1'>
                <b style='color:#fff'>👤 {username}</b><br>
                <b>Vai trò:</b> {role}<br>
                <b>Trạng thái:</b> <span style='color:{color};font-weight:700'>{label}</span><br>
                <b>Tạo lúc:</b> {info.get('created_at', '-')}<br>
                <b>Quyền:</b> {perms_text}<br>
                <b>Ghi chú:</b> {info.get('note', '') or '—'}
                </div>
                """,
                unsafe_allow_html=True,
            )

        with action_col:
            if username == "ducpro":
                st.info("🔒 Master admin — không chỉnh sửa.")
                return

            new_status = st.selectbox(
                "Trạng thái",
                ["approved", "pending", "banned"],
                index=["approved", "pending", "banned"].index(status)
                if status in ["approved", "pending", "banned"] else 1,
                key=f"st_{username}",
            )

            current_perms = info.get("permissions", []) or []
            new_perms = st.multiselect(
                "Quyền",
                options=DEFAULT_PERMISSIONS,
                default=[p for p in current_perms if p in DEFAULT_PERMISSIONS],
                format_func=lambda x: PERMISSION_LABELS.get(x, x),
                key=f"pm_{username}",
            )

            new_note = st.text_input(
                "Ghi chú",
                value=info.get("note", ""),
                key=f"nt_{username}",
                placeholder="VD: Đối tác A...",
            )

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("💾 Lưu", key=f"save_{username}",
                             use_container_width=True, type="primary"):
                    update_user_admin(username, new_status, new_perms, new_note)
                    st.success(f"Đã cập nhật {username}")
                    st.rerun()
            with btn_col2:
                if st.button("🗑 Xóa", key=f"del_{username}", use_container_width=True):
                    if delete_user(username):
                        st.success(f"Đã xóa {username}")
                        st.rerun()
                    else:
                        st.error("Không thể xóa.")

            with st.popover("🔑 Reset mật khẩu", use_container_width=True):
                new_pwd = st.text_input(
                    "Mật khẩu mới (≥ 4)",
                    type="password",
                    key=f"rp_{username}",
                )
                if st.button("Xác nhận", key=f"rp_btn_{username}", use_container_width=True):
                    if reset_password(username, new_pwd):
                        st.success(f"Đã reset cho {username}")
                    else:
                        st.error("Mật khẩu không hợp lệ.")
