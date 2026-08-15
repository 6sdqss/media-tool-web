"""
pages/index.py — trang duy nhất: Login (chưa đăng nhập) hoặc Dashboard
(đã đăng nhập, có sidebar nav + nội dung theo active_mode).
Tương đương app.py gốc (_login_page + main layout + nav router) nhưng
dùng rx.cond thay cho `if not user: ... else: ...` của Streamlit.
Theme: Bauhaus (constructivist) — xem media_tool_pro/components/bauhaus.py.
"""
from __future__ import annotations

import reflex as rx

from ..backend.auth_state import AuthState
from ..backend.batch_state import BatchState
from ..components.ui import top_header, sidebar_nav
from ..components import modes as m
from ..components import bauhaus as bh


def _bg_shape(size: str, color: str, top=None, left=None, right=None, bottom=None,
              kind: str = "circle", rotate: str = "0deg") -> rx.Component:
    style = {"width": size, "height": size, "bg": color, "opacity": "0.9",
             "position": "absolute", "transform": f"rotate({rotate})",
             "border": f"3px solid {bh.INK}"}
    if kind == "circle":
        style["border_radius"] = "9999px"
    if top is not None:
        style["top"] = top
    if left is not None:
        style["left"] = left
    if right is not None:
        style["right"] = right
    if bottom is not None:
        style["bottom"] = bottom
    return rx.box(**style)


def _geo_mark() -> rx.Component:
    """Logo hình học Bauhaus cho trang login: tròn đỏ + vuông vàng chồng
    vuông xanh."""
    return rx.box(
        rx.box(position="absolute", top="0", left="0", width="100%", height="100%",
               bg=bh.BLUE, border=f"3px solid {bh.INK}"),
        rx.box(position="absolute", bottom="-8px", right="-8px", width="52%", height="52%",
               bg=bh.YELLOW, border=f"3px solid {bh.INK}"),
        rx.box(position="absolute", top="-8px", left="-8px", width="46%", height="46%",
               bg=bh.RED, border=f"3px solid {bh.INK}", border_radius="9999px"),
        position="relative", width="60px", height="60px", margin="6px",
    )


def _login_page() -> rx.Component:
    return rx.center(
        # Bố cục hình học trang trí nền — vòng tròn, vuông xoay, tam giác
        _bg_shape("140px", bh.YELLOW, top="8%", left="10%", kind="circle"),
        _bg_shape("90px", bh.BLUE, bottom="12%", left="16%", kind="square", rotate="20deg"),
        _bg_shape("110px", bh.RED, top="14%", right="12%", kind="square", rotate="12deg"),
        _bg_shape("70px", bh.INK, bottom="10%", right="18%", kind="circle"),
        rx.box(
            rx.vstack(
                _geo_mark(),
                rx.heading(
                    "MEDIA TOOL PRO", size="6", color=bh.INK, font_weight="900",
                    text_transform="uppercase", letter_spacing="-0.01em",
                ),
                rx.text("V11 · BATCH IMAGE PROCESSING", size="1", color=bh.INK,
                         font_weight="700", letter_spacing="0.08em"),
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("ĐĂNG NHẬP", value="login"),
                        rx.tabs.trigger("ĐĂNG KÝ", value="register"),
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.input(placeholder="Username", value=AuthState.login_username,
                                      on_change=AuthState.set_login_username, width="100%",
                                      radius="none", variant="classic",
                                      style={"border": f"2px solid {bh.INK}"}),
                            rx.input(placeholder="Password", type="password",
                                      value=AuthState.login_password,
                                      on_change=AuthState.set_login_password, width="100%",
                                      radius="none", variant="classic",
                                      style={"border": f"2px solid {bh.INK}"}),
                            rx.button("ĐĂNG NHẬP", on_click=AuthState.do_login,
                                      width="100%", size="3",
                                      **bh.bauhaus_button(bg=bh.RED, shadow_px=4)),
                            rx.cond(AuthState.login_error != "",
                                    rx.box(
                                        rx.text(AuthState.login_error, size="2", font_weight="700"),
                                        bg=bh.RED, color=bh.WHITE, border=f"2px solid {bh.INK}",
                                        padding="0.5em 0.8em", width="100%",
                                    )),
                            spacing="3", width="100%", padding_top="1em",
                        ),
                        value="login",
                    ),
                    rx.tabs.content(
                        rx.vstack(
                            rx.input(placeholder="Username mới", value=AuthState.reg_username,
                                      on_change=AuthState.set_reg_username, width="100%",
                                      radius="none", style={"border": f"2px solid {bh.INK}"}),
                            rx.input(placeholder="Password", type="password",
                                      value=AuthState.reg_password,
                                      on_change=AuthState.set_reg_password, width="100%",
                                      radius="none", style={"border": f"2px solid {bh.INK}"}),
                            rx.input(placeholder="Nhập lại password", type="password",
                                      value=AuthState.reg_password2,
                                      on_change=AuthState.set_reg_password2, width="100%",
                                      radius="none", style={"border": f"2px solid {bh.INK}"}),
                            rx.button("TẠO TÀI KHOẢN", on_click=AuthState.do_register,
                                      width="100%", size="3",
                                      **bh.bauhaus_button(bg=bh.BLUE, shadow_px=4)),
                            rx.cond(AuthState.reg_error != "",
                                    rx.box(
                                        rx.text(AuthState.reg_error, size="2", font_weight="700"),
                                        bg=bh.RED, color=bh.WHITE, border=f"2px solid {bh.INK}",
                                        padding="0.5em 0.8em", width="100%",
                                    )),
                            rx.cond(AuthState.reg_success != "",
                                    rx.box(
                                        rx.text(AuthState.reg_success, size="2", font_weight="700"),
                                        bg="#2E8B3D", color=bh.WHITE, border=f"2px solid {bh.INK}",
                                        padding="0.5em 0.8em", width="100%",
                                    )),
                            spacing="3", width="100%", padding_top="1em",
                        ),
                        value="register",
                    ),
                    default_value="login", width="100%",
                ),
                spacing="4", align_items="center", width="340px",
            ),
            padding="2.6em",
            bg=bh.WHITE,
            border=f"4px solid {bh.INK}",
            box_shadow=bh.hard_shadow(10),
            position="relative", z_index="1",
        ),
        min_height="100vh", width="100%", position="relative", overflow="hidden",
        bg=bh.BG,
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
            rx.box(body, flex="1", overflow_y="auto", height="calc(100vh - 70px)",
                    bg=bh.BG),
            width="100%", align_items="start", spacing="0",
        ),
        spacing="0", width="100%", min_height="100vh",
        on_mount=BatchState.load_presets,
    )


def index() -> rx.Component:
    return rx.cond(AuthState.is_logged_in, _dashboard(), _login_page())
