"""
media_tool_pro.py — entry point Reflex (thay app.py Streamlit gốc).
"""
from __future__ import annotations

import reflex as rx

from .backend import st_compat  # noqa: F401 — đăng ký shim streamlit TRƯỚC mọi import core/auth
from .pages.index import index

app = rx.App(
    theme=rx.theme(appearance="light", accent_color="violet", radius="large"),
)
app.add_page(index, route="/", title="Media Tool Pro v11 (Reflex)")
