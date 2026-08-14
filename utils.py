"""
utils.py — Compat shim v11.0
════════════════════════════════════════════════════════════════
Toàn bộ logic mới đã được refactor sang các package:
    core.*  — batch engine, imaging, download, presets, report, ...
    ui.*    — components, theme
    modes.* — web / drive / local adapters

File utils.py này CHỈ tồn tại để giữ tương thích cho `mode_adjust.py`
(Studio Scale) — module còn giữ nguyên từ v10 vì phần Studio là workflow
độc lập, không thuộc pipeline batch chính.

Không dùng file này cho code mới. Các file mới import trực tiếp từ core.*
"""
from __future__ import annotations

import base64
import io
import logging
import shutil
import time
from pathlib import Path
from typing import Iterable, Optional

import streamlit as st
from PIL import Image, ImageOps

# ── Re-export từ core ───────────────────────────────────────────
from core.imaging import (
    EXPORT_FORMATS,
    IMAGE_EXTENSIONS,
    apply_size as _core_apply_size,
    build_preview_thumb as _core_build_preview_thumb,
    is_real_image_file,
    open_prepared as _core_open_prepared,
    probe_meta,
)
from core.archive import (
    make_zip_stream as _core_make_zip_stream,
    open_zip_for_download,
    readable_size as _core_readable_size,
)
from core.naming import render as _core_render_name, unique_path
from core.validation import clean_name


_log = logging.getLogger("utils_shim")


# ══════════════════════════════════════════════════════════════
# COMPAT: readable_file_size
# ══════════════════════════════════════════════════════════════
def readable_file_size(num_bytes) -> str:
    """Giữ tương thích tên hàm cũ."""
    try:
        return _core_readable_size(int(num_bytes or 0))
    except Exception:
        return "0 B"


# ══════════════════════════════════════════════════════════════
# COMPAT: get_size_label
# ══════════════════════════════════════════════════════════════
def get_size_label(w: int, h: int, mode: str = "letterbox") -> str:
    """Nhãn thư mục output theo size + mode."""
    try:
        if mode == "crop_1000":
            return "1000x1000_crop"
        if mode == "keep":
            return "keep_ratio"
        return f"{int(w)}x{int(h)}"
    except Exception:
        return "unknown"


# ══════════════════════════════════════════════════════════════
# COMPAT: apply_name_template
# ══════════════════════════════════════════════════════════════
def apply_name_template(
    template: str,
    name: str = "",
    color: str = "",
    index: int = 1,
    original: str = "",
    width: int = 0,
    height: int = 0,
    fmt: str = "jpg",
) -> str:
    """Wrapper cho core.naming.render — giữ kwargs signature cũ."""
    return _core_render_name(
        template or "{name}_{nn}",
        name=name, original=original or name, color=color,
        index=index, width=width, height=height, fmt=fmt,
    )


# ══════════════════════════════════════════════════════════════
# COMPAT: estimate_default_scale_for_size
# ══════════════════════════════════════════════════════════════
def estimate_default_scale_for_size(
    source_path: str | Path,
    target_w: int,
    target_h: int,
    default: int = 100,
) -> int:
    """
    Ước lượng scale% mặc định để ảnh sản phẩm nhỏ (thumbnail) fit đẹp
    trong canvas target — dựa theo tỉ lệ target/source.

    Trả giá trị int trong [50, 100]:
      • Ảnh source lớn hơn hoặc bằng target → 100
      • Ảnh nhỏ hơn nhiều → giảm scale để không phóng quá mức
    """
    try:
        p = Path(source_path)
        if not p.exists():
            return int(default)
        with Image.open(p) as im:
            sw, sh = im.size
        if sw <= 0 or sh <= 0:
            return int(default)
        # tỉ lệ nhỏ nhất giữa source và target — quyết định bao nhiêu ảnh phóng lên
        ratio = min(target_w / sw, target_h / sh)
        if ratio >= 1.0:
            return 100
        # Ảnh nhỏ hơn → suggest scale trong khoảng 60–95
        val = int(round(min(100, max(50, ratio * 100 + 20))))
        return val
    except Exception:
        return int(default)


# ══════════════════════════════════════════════════════════════
# COMPAT: build_live_preview_b64
# ══════════════════════════════════════════════════════════════
def build_live_preview_b64(source_path: str | Path, max_size: int = 480) -> str:
    """Tạo data URL base64 dùng nhúng HTML preview trong Studio."""
    try:
        p = Path(source_path)
        if not p.exists():
            return ""
        with _core_open_prepared(p, (max_size, max_size), True) as im:
            im.thumbnail((max_size, max_size), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=82, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:
        _log.warning("build_live_preview_b64 failed: %s", exc)
        return ""


# ══════════════════════════════════════════════════════════════
# COMPAT: resize_to_multi_sizes
# ══════════════════════════════════════════════════════════════
def resize_to_multi_sizes(
    source_path: str | Path,
    out_dir: str | Path,
    base_name: str,
    sizes: Iterable[tuple],
    quality: int = 92,
    export_format: str = "JPEG (.jpg)",
    scale_pct: int = 100,
    no_upscale: bool = True,
    **_ignored,
) -> list[str]:
    """
    Resize 1 ảnh nguồn ra nhiều size — dùng cho Studio khi apply lại thay đổi.
    Trả list path đã xuất.
    """
    from core.types import SizeSpec

    src = Path(source_path)
    if not src.exists():
        return []

    out_paths: list[str] = []
    info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
    ext = info["ext"]

    for sz in sizes:
        try:
            spec = SizeSpec.from_tuple(sz) if not hasattr(sz, "width") else sz
        except Exception:
            continue
        sub = Path(out_dir) / get_size_label(spec.width, spec.height, spec.mode)
        sub.mkdir(parents=True, exist_ok=True)
        out_path = unique_path(sub, clean_name(base_name), ext)

        ok, _err, _msg = _core_apply_size(
            src, out_path, spec,
            quality=quality, export_format=export_format,
            scale_pct=scale_pct, no_upscale=no_upscale, huge_mode=True,
        )
        if ok:
            out_paths.append(str(out_path))
    return out_paths


# ══════════════════════════════════════════════════════════════
# COMPAT: make_zip / open_zip_for_download
# ══════════════════════════════════════════════════════════════
def make_zip(source_dir, zip_path, compresslevel: int = 6, **_ignored):
    """Alias cho core.archive.make_zip_stream."""
    return _core_make_zip_stream(source_dir, zip_path, compresslevel=int(compresslevel))


# open_zip_for_download đã re-export ở trên


# ══════════════════════════════════════════════════════════════
# COMPAT: merge_final_with_adjusted
# ══════════════════════════════════════════════════════════════
def merge_final_with_adjusted(
    final_dir: str | Path,
    adjusted_dir: str | Path,
    merged_dir: str | Path,
) -> dict:
    """
    Trộn final/ (ảnh đã render trong batch) với adjusted/ (ảnh Studio đã chỉnh):
      • copy toàn bộ ảnh từ final/
      • ghi đè bằng phiên bản trong adjusted/ nếu có (theo relative path)
    Trả stats {copied, overridden}.
    """
    fdir = Path(final_dir)
    adir = Path(adjusted_dir)
    mdir = Path(merged_dir)
    mdir.mkdir(parents=True, exist_ok=True)
    stats = {"copied": 0, "overridden": 0}

    if not fdir.exists():
        return stats

    for src in fdir.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(fdir)
        dest = mdir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Có bản Studio ghi đè không?
            adj = adir / rel
            if adj.exists() and adj.is_file():
                shutil.copy2(adj, dest)
                stats["overridden"] += 1
            else:
                shutil.copy2(src, dest)
                stats["copied"] += 1
        except Exception as exc:
            _log.warning("merge copy failed [%s]: %s", src, exc)
    return stats


# ══════════════════════════════════════════════════════════════
# COMPAT: add_to_history
# ══════════════════════════════════════════════════════════════
def add_to_history(mode: str, sizes_label: str, duration: float, **extras) -> None:
    """
    Ghi vào session_state.batch_history — tương thích chữ ký cũ mà mode_adjust dùng.
    Cấu trúc entry: {mode, sizes, duration, at, ...}
    """
    hist = st.session_state.setdefault("batch_history", [])
    entry = {
        "mode": mode,
        "sizes": sizes_label,
        "duration": round(float(duration or 0), 1),
        "at": time.strftime("%H:%M:%S"),
    }
    entry.update(extras)
    hist.insert(0, entry)
    del hist[20:]


# ══════════════════════════════════════════════════════════════
# COMPAT: render_batch_kpis
# ══════════════════════════════════════════════════════════════
def render_batch_kpis(meta: dict) -> None:
    """
    Render 4-column KPI cho batch trong Studio.
    meta có thể chứa: total, success, failed, duration, ...
    """
    if not isinstance(meta, dict):
        return
    total = int(meta.get("total", 0) or 0)
    ok = int(meta.get("success", 0) or 0)
    failed = int(meta.get("failed", 0) or 0)
    dur = float(meta.get("duration", 0) or 0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Success", ok)
    c3.metric("Failed", failed)
    c4.metric("Time (s)", f"{dur:.1f}")


# ══════════════════════════════════════════════════════════════
# COMPAT: các helper legacy Studio còn dùng nội bộ
# (Studio v10.2 chỉ cần các hàm trên — các helper khác đã inline sẵn)
# ══════════════════════════════════════════════════════════════

# Alias tên biến hằng để tương thích
IMAGE_EXTENSIONS = IMAGE_EXTENSIONS
EXPORT_FORMATS = EXPORT_FORMATS
