"""
pages/index.py — trang duy nhất: Login (chưa đăng nhập) hoặc Dashboard
(đã đăng nhập, có sidebar nav + nội dung theo active_mode).
Tương đương app.py gốc (_login_page + main layout + nav router) nhưng
dùng rx.cond thay cho `if not user: ... else: ...` của Streamlit.
"""
from __future__ import annotations

import reflex as rx

from ..backend.auth_state import AuthState
from ..backend.batch_state import BatchState
from ..components.ui import top_header, sidebar_nav
from ..components import modes as m


def _login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.box(
                    rx.text("M", weight="bold", size="7", color="white"),
                    bg="linear-gradient(135deg,#7c3aed,#ec4899)",
                    border_radius="14px", width="56px", height="56px",
                    display="flex", align_items="center", justify_content="center",
                ),
                rx.heading("Media Tool Pro", size="6"),
                rx.text("v11 · Batch image processing (Reflex UI)", size="2", color="gray"),
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("Đăng nhập", value="login"),
                        rx.tabs.trigger("Đăng ký", value="register"),
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.input(placeholder="Username", value=AuthState.login_username,
                                      on_change=AuthState.set_login_username, width="100%"),
                            rx.input(placeholder="Password", type="password",
                                      value=AuthState.login_password,
                                      on_change=AuthState.set_login_password, width="100%"),
                            rx.button("Đăng nhập", on_click=AuthState.do_login,
                                      color_scheme="violet", width="100%", size="3"),
                            rx.cond(AuthState.login_error != "",
                                    rx.callout(AuthState.login_error, color_scheme="red")),
                            spacing="3", width="100%", padding_top="1em",
                        ),
                        value="login",
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.input(placeholder="Username mới", value=AuthState.reg_username,
                                      on_change=AuthState.set_reg_username, width="100%"),
                            rx.input(placeholder="Password", type="password",
                                      value=AuthState.reg_password,
                                      on_change=AuthState.set_reg_password, width="100%"),
                            rx.input(placeholder="Nhập lại password", type="password",
                                      value=AuthState.reg_password2,
                                      on_change=AuthState.set_reg_password2, width="100%"),
                            rx.button("Tạo tài khoản", on_click=AuthState.do_register,
                                      width="100%", size="3"),
                            rx.cond(AuthState.reg_error != "",
                                    rx.callout(AuthState.reg_error, color_scheme="red")),
                            rx.cond(AuthState.reg_success != "",
                                    rx.callout(AuthState.reg_success, color_scheme="green")),
                            spacing="3", width="100%", padding_top="1em",
                        ),
                        value="register",
                    ),
                    default_value="login", width="100%",
                ),
                spacing="4", align_items="center", width="340px",
            ),
            padding="2.5em",
        ),
        min_height="100vh", width="100%",
    )


def _dashboard() -> rx.Component:
    body = rx.match(
        BatchState.active_mode,
        ("home", m.render_home()),
        ("web", m.render_web()),
        ("drive", m.render_drive()),
        ("local", m.render_local()),
        ("studio", m.render_studio()),
        ("guide", m.render_guide()),
        ("admin", m.render_admin()),
        m.render_home(),
    )
    return rx.vstack(
        top_header(),
        rx.hstack(
            sidebar_nav(),
            rx.box(body, flex="1", overflow_y="auto", height="calc(100vh - 70px)"),
            width="100%", align_items="start", spacing="0",
        ),
        spacing="0", width="100%", min_height="100vh",
        on_mount=BatchState.load_presets,
    )


def index() -> rx.Component:
    return rx.cond(AuthState.is_logged_in, _dashboard(), _login_page())
