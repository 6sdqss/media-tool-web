"""
admin_state.py — State cho Admin Panel.

Bọc các hàm quản trị user trong auth.py (repo gốc, KHÔNG đổi logic):
list_users, update_user_admin, delete_user, reset_password,
pull_from_github, push_to_github, DEFAULT_PERMISSIONS.
"""
from __future__ import annotations

import reflex as rx

from . import st_compat  # noqa: F401

import auth


PERMISSION_LABELS = {
    "web": "🛒 Web TGDD",
    "studio": "🎚 Studio",
    "drive": "🌐 Drive",
    "local": "💻 Local ZIP",
}


class AdminState(rx.State):
    users: list[dict] = []
    search: str = ""
    sync_msg: str = ""

    edit_username: str = ""
    edit_status: str = "pending"
    edit_permissions: list[str] = []
    edit_note: str = ""
    edit_new_password: str = ""

    all_permissions: list[str] = list(auth.DEFAULT_PERMISSIONS)

    def load_users(self):
        db = auth.list_users()
        rows = []
        for username, info in sorted(db.items()):
            if self.search and self.search.lower() not in username.lower():
                continue
            perms = info.get("permissions", []) or []
            rows.append({
                "username": username,
                "role": info.get("role", "user"),
                "status": info.get("status", "pending"),
                "permissions_label": ", ".join(perms) or "— (chưa có)",
                "note": info.get("note", "") or "—",
                "created_at": info.get("created_at", "") or "-",
            })
        self.users = rows

    def set_search(self, v: str):
        self.search = v
        self.load_users()

    def start_edit(self, username: str):
        db = auth.list_users()
        info = db.get(username, {})
        self.edit_username = username
        self.edit_status = info.get("status", "pending")
        self.edit_permissions = list(info.get("permissions", []) or [])
        self.edit_note = info.get("note", "")
        self.edit_new_password = ""

    def set_edit_status(self, v: str):
        self.edit_status = v

    def toggle_edit_permission(self, perm: str):
        if perm in self.edit_permissions:
            self.edit_permissions = [p for p in self.edit_permissions if p != perm]
        else:
            self.edit_permissions = self.edit_permissions + [perm]

    def set_edit_note(self, v: str):
        self.edit_note = v

    def set_edit_new_password(self, v: str):
        self.edit_new_password = v

    def save_edit(self):
        if not self.edit_username:
            return
        auth.update_user_admin(
            self.edit_username, self.edit_status, self.edit_permissions, self.edit_note
        )
        self.sync_msg = f"Đã cập nhật {self.edit_username}"
        self.load_users()

    def delete_edit_user(self):
        if not self.edit_username:
            return
        if auth.delete_user(self.edit_username):
            self.sync_msg = f"Đã xoá {self.edit_username}"
            self.edit_username = ""
        else:
            self.sync_msg = "Không thể xoá (admin hoặc không tồn tại)."
        self.load_users()

    def reset_edit_password(self):
        if not self.edit_username:
            return
        if auth.reset_password(self.edit_username, self.edit_new_password):
            self.sync_msg = f"Đã reset mật khẩu cho {self.edit_username}"
            self.edit_new_password = ""
        else:
            self.sync_msg = "Mật khẩu không hợp lệ (>= 4 ký tự)."

    def pull_github(self):
        ok = auth.pull_from_github(force=True)
        self.sync_msg = "Đã pull DB từ GitHub." if ok else "Không pull được (chưa cấu hình / lỗi mạng)."
        self.load_users()

    def push_github(self):
        ok = auth.push_to_github()
        self.sync_msg = "Đã push DB lên GitHub." if ok else "Push thất bại — kiểm tra GITHUB_TOKEN."
