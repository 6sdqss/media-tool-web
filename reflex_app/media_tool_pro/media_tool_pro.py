"""
media_tool_pro.py — entry point Reflex (thay app.py Streamlit gốc).

Theme: Bauhaus (constructivist modernism) — primary colors, viền đen dày,
bóng đổ cứng (hard offset shadow), bo góc nhị phân (vuông hoặc tròn tuyệt
đối, không có mức trung gian). radius="none" ở theme gốc để mọi component
Radix mặc định vuông vức — chỗ nào cần tròn (logo, avatar...) sẽ tự set
border_radius="9999px" riêng.
"""
from __future__ import annotations

import reflex as rx

from .backend import st_compat  # noqa: F401 — đăng ký shim streamlit TRƯỚC mọi import core/auth
from .pages.index import index

app = rx.App(
    theme=rx.theme(appearance="light", accent_color="red", radius="none"),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;700;900&display=swap",
    ],
    style={"font_family": "'Outfit', sans-serif"},
)
app.add_page(index, route="/", title="Media Tool Pro v11 (Reflex)")
