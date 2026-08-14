"""
auth_state.py — State đăng nhập / đăng ký / phiên user.

Bọc auth.authenticate / auth.register_user / auth.change_own_password
(repo gốc, KHÔNG đổi logic hash/verify) bằng các event handler Reflex.
"""
from __future__ import annotations

import reflex as rx

from . import st_compat  # noqa: F401 — đăng ký shim streamlit trước

import auth  # repo root auth.py — PBKDF2 hashing, giữ nguyên


class AuthState(rx.State):
    """Trạng thái phiên đăng nhập — 1 instance / browser tab (Reflex chuẩn)."""

    # login form
    login_username: str = ""
    login_password: str = ""
    login_error: str = ""

    # register form
    reg_username: str = ""
    reg_password: str = ""
    reg_password2: str = ""
    reg_error: str = ""
    reg_success: str = ""

    # session
    is_logged_in: bool = False
    user_username: str = ""
    user_role: str = "user"
    user_status: str = ""
    user_permissions: list[str] = []

    change_pwd_old: str = ""
    change_pwd_new: str = ""
    change_pwd_msg: str = ""
    change_pwd_ok: bool = False

    @rx.var
    def is_admin(self) -> bool:
        return self.user_role == "admin"

    def has_permission(self, permission: str) -> bool:
        if self.user_role == "admin":
            return True
        return permission in self.user_permissions

    def set_login_username(self, v: str):
        self.login_username = v

    def set_login_password(self, v: str):
        self.login_password = v

    def do_login(self):
        self.login_error = ""
        u = (self.login_username or "").strip()
        p = self.login_password or ""
        ok, msg, data = auth.authenticate(u, p)
        if not ok:
            self.login_error = msg
            return
        self.is_logged_in = True
        self.user_username = data.get("username", u)
        self.user_role = data.get("role", "user")
        self.user_status = data.get("status", "approved")
        self.user_permissions = list(data.get("permissions", []) or [])
        self.login_password = ""
        self.login_error = ""

    def set_reg_username(self, v: str):
        self.reg_username = v

    def set_reg_password(self, v: str):
        self.reg_password = v

    def set_reg_password2(self, v: str):
        self.reg_password2 = v

    def do_register(self):
        self.reg_error = ""
        self.reg_success = ""
        if self.reg_password != self.reg_password2:
            self.reg_error = "Password không khớp."
            return
        ok, msg = auth.register_user((self.reg_username or "").strip(), self.reg_password)
        if ok:
            self.reg_success = msg + " — chuyển qua tab Đăng nhập."
            self.reg_username = ""
            self.reg_password = ""
            self.reg_password2 = ""
        else:
            self.reg_error = msg

    def do_logout(self):
        self.is_logged_in = False
        self.user_username = ""
        self.user_role = "user"
        self.user_status = ""
        self.user_permissions = []
        self.login_username = ""
        self.login_password = ""

    def set_change_pwd_old(self, v: str):
        self.change_pwd_old = v

    def set_change_pwd_new(self, v: str):
        self.change_pwd_new = v

    def do_change_password(self):
        ok, msg = auth.change_own_password(
            self.user_username, self.change_pwd_old, self.change_pwd_new
        )
        self.change_pwd_ok = ok
        self.change_pwd_msg = msg
        if ok:
            self.change_pwd_old = ""
            self.change_pwd_new = ""
