"""
components/bauhaus.py — design tokens & helper cho phong cách Bauhaus
(constructivist modernism): primary colors thuần, viền đen dày, bóng đổ
cứng (hard offset, không blur), bo góc nhị phân (vuông hoặc tròn tuyệt đối),
typography uppercase đậm. Dùng chung cho toàn bộ UI thay vì lặp style rời rạc.
"""
from __future__ import annotations

# ── Màu ──────────────────────────────────────────────────────
BG = "#F0F0F0"
INK = "#121212"
RED = "#D02020"
BLUE = "#1040C0"
YELLOW = "#F0C020"
BORDER = "#121212"
MUTED = "#E0E0E0"
WHITE = "#FFFFFF"

ACCENTS = [RED, BLUE, YELLOW]


def hard_shadow(px: int = 4, color: str = INK) -> str:
    """Bóng đổ cứng kiểu Bauhaus — offset thuần, không blur/spread."""
    return f"{px}px {px}px 0px 0px {color}"


def press_style(shadow_px: int = 4) -> dict:
    """Hiệu ứng 'nhấn xuống' khi active — dịch chuyển theo đúng offset bóng
    rồi bỏ bóng, mô phỏng nút vật lý bị ấn."""
    return {
        "transition": "transform 0.12s ease-out, box-shadow 0.12s ease-out, opacity 0.12s ease-out",
        "_hover": {"opacity": 0.94},
        "_active": {
            "transform": f"translate({shadow_px}px, {shadow_px}px)",
            "box_shadow": "none",
        },
    }


def bauhaus_button(bg: str = RED, color: str = WHITE, shadow_px: int = 4) -> dict:
    """Kwargs style cho 1 nút Bauhaus chuẩn: nền màu nguyên bản, viền đen
    dày, bóng cứng, chữ hoa đậm."""
    return {
        "bg": bg,
        "color": color,
        "border": f"2px solid {INK}",
        "border_radius": "0",
        "box_shadow": hard_shadow(shadow_px),
        "font_weight": "700",
        "text_transform": "uppercase",
        "letter_spacing": "0.03em",
        "style": press_style(shadow_px),
    }


def bauhaus_card(shadow_px: int = 6) -> dict:
    """Kwargs style cho 1 card Bauhaus: nền trắng, viền đen dày, bóng lớn."""
    return {
        "bg": WHITE,
        "border": f"3px solid {INK}",
        "border_radius": "0",
        "box_shadow": hard_shadow(shadow_px),
    }


def corner_shape(color: str, kind: str = "circle", size: str = "14px") -> dict:
    """Style cho 1 hình khối trang trí nhỏ ở góc card (circle/square/triangle)."""
    if kind == "triangle":
        return {
            "width": "0", "height": "0",
            "border_left": f"{size} solid transparent",
            "border_right": f"{size} solid transparent",
            "border_bottom": f"calc({size} * 1.6) solid {color}",
            "bg": "transparent",
        }
    return {
        "width": size, "height": size,
        "bg": color,
        "border_radius": "9999px" if kind == "circle" else "0",
    }
