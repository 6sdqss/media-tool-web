"""
core/naming.py — engine template tên file xuất.
Placeholders: {name} {original} {color} {nn} {nnn} {index}
              {width} {height} {format} {date}
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from .validation import clean_name


_PLACEHOLDER = re.compile(r"\{([a-zA-Z_]+)\}")


def render(
    template: str,
    *,
    name: str = "",
    original: str = "",
    color: str = "",
    index: int = 1,
    width: int = 0,
    height: int = 0,
    fmt: str = "jpg",
) -> str:
    """Thay placeholder trong template. Trả tên file (không kèm extension)."""
    tpl = template or "{name}_{nn}"

    values = {
        "name": clean_name(name or original or "img"),
        "original": clean_name(original or name or "img"),
        "color": clean_name(color) if color else "",
        "nn": f"{index:02d}",
        "nnn": f"{index:03d}",
        "index": str(index),
        "width": str(width),
        "height": str(height),
        "format": fmt,
        "date": time.strftime("%Y%m%d"),
    }

    def _sub(m: re.Match) -> str:
        key = m.group(1).lower()
        return values.get(key, "")

    result = _PLACEHOLDER.sub(_sub, tpl)
    # Dọn dấu ngăn thừa nếu placeholder trả rỗng
    result = re.sub(r"_+", "_", result).strip("_-. ")
    return clean_name(result or "img")


def unique_path(out_dir: Path, base_name: str, ext: str) -> Path:
    """
    Trả đường dẫn KHÔNG trùng với file đã có: name.jpg → name_01.jpg → name_02.jpg
    Tránh ghi đè lẫn nhau khi 2 item trùng tên.
    """
    ext = ext if ext.startswith(".") else f".{ext}"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate = out_dir / f"{base_name}{ext}"
    if not candidate.exists():
        return candidate
    for i in range(1, 999):
        candidate = out_dir / f"{base_name}_{i:02d}{ext}"
        if not candidate.exists():
            return candidate
    # Cuối cùng — ép suffix theo timestamp
    return out_dir / f"{base_name}_{int(time.time())}{ext}"
