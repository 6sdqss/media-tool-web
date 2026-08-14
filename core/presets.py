"""
core/presets.py — kho preset (built-in + user-defined).
User chỉ cần chọn 1 preset là xong toàn bộ config resize/format/naming.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .types import Preset, SizeSpec


_log = logging.getLogger("core.presets")
_USER_STORE = Path("user_presets.json")


# ══════════════════════════════════════════════════════════════
# BUILT-IN PRESETS
# ══════════════════════════════════════════════════════════════
def _builtin() -> list[Preset]:
    return [
        Preset(
            name="TGDD Product 1020x680",
            sizes=[SizeSpec(1020, 680, "letterbox")],
            quality=92, export_format="JPEG (.jpg)",
            template="{name}_{nn}", is_builtin=True,
            description="Chuẩn hero-image sản phẩm Thegioididong.com",
        ),
        Preset(
            name="TGDD Multi (1020 + 600)",
            sizes=[
                SizeSpec(1020, 680, "letterbox"),
                SizeSpec(600, 600, "letterbox"),
            ],
            quality=92, export_format="JPEG (.jpg)",
            template="{name}_{nn}", is_builtin=True,
            description="Xuất 2 kích thước cho hero + thumb.",
        ),
        Preset(
            name="Square 1000",
            sizes=[SizeSpec(1000, 1000, "crop_1000")],
            quality=92, export_format="JPEG (.jpg)",
            template="{name}_{nn}", is_builtin=True,
            description="Crop giữa thành ảnh vuông 1000×1000.",
        ),
        Preset(
            name="E-commerce 1200",
            sizes=[SizeSpec(1200, 1200, "letterbox")],
            quality=90, export_format="JPEG (.jpg)",
            template="{name}_{nn}", is_builtin=True,
            description="Ảnh sản phẩm chuẩn TMĐT chung.",
        ),
        Preset(
            name="Social 1080",
            sizes=[SizeSpec(1080, 1080, "letterbox")],
            quality=88, export_format="JPEG (.jpg)",
            template="{name}_{nn}", is_builtin=True,
            description="Post vuông cho social media.",
        ),
        Preset(
            name="Keep original",
            sizes=[SizeSpec(0, 0, "keep")],
            quality=95, export_format="JPEG (.jpg)",
            template="{original}", is_builtin=True,
            description="Không resize — copy y nguyên (dùng để đóng gói ZIP).",
        ),
    ]


# ══════════════════════════════════════════════════════════════
# LOAD / SAVE
# ══════════════════════════════════════════════════════════════
def load_all() -> list[Preset]:
    """Trả built-in + user preset (user override cùng tên nếu có)."""
    presets: dict[str, Preset] = {p.name: p for p in _builtin()}
    if _USER_STORE.exists():
        try:
            raw = json.loads(_USER_STORE.read_text(encoding="utf-8"))
            for d in raw:
                try:
                    p = Preset.from_json(d)
                    p.is_builtin = False
                    presets[p.name] = p
                except Exception as exc:
                    _log.warning("Bỏ qua preset lỗi: %s", exc)
        except Exception as exc:
            _log.warning("Không đọc được %s: %s", _USER_STORE, exc)
    return list(presets.values())


def get(name: str) -> Preset | None:
    for p in load_all():
        if p.name == name:
            return p
    return None


def save_user_preset(preset: Preset) -> bool:
    """Ghi 1 user preset (override nếu trùng tên). Không ghi được built-in."""
    if preset.is_builtin:
        return False
    existing = []
    if _USER_STORE.exists():
        try:
            existing = json.loads(_USER_STORE.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    # Loại preset cùng tên
    existing = [d for d in existing if d.get("name") != preset.name]
    existing.append(preset.to_json())
    try:
        _USER_STORE.write_text(json.dumps(existing, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        return True
    except Exception as exc:
        _log.error("Không lưu được preset: %s", exc)
        return False


def delete_user_preset(name: str) -> bool:
    if not _USER_STORE.exists():
        return False
    try:
        existing = json.loads(_USER_STORE.read_text(encoding="utf-8"))
    except Exception:
        return False
    new_list = [d for d in existing if d.get("name") != name]
    if len(new_list) == len(existing):
        return False
    _USER_STORE.write_text(json.dumps(new_list, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    return True
