"""
core/archive.py — ZIP streaming từ disk.
Không load toàn bộ file vào RAM — ghi trực tiếp qua ZipFile với compresslevel
phù hợp. Tránh OOM khi batch xuất hàng trăm ảnh.
"""
from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import Iterable, Optional


_log = logging.getLogger("core.archive")


def make_zip_stream(
    source_dir: Path,
    zip_path: Path,
    compresslevel: int = 6,
    skip_names: Iterable[str] = (".DS_Store", "Thumbs.db"),
    progress_cb: Optional[callable] = None,
) -> Path:
    """
    Tạo ZIP từ 1 thư mục. Ghi trực tiếp từng file (không đọc toàn bộ vào RAM).
    Trả đường dẫn ZIP đã tạo. Raise nếu thất bại.
    """
    source_dir = Path(source_dir)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    # Đếm trước để có progress
    files = [
        f for f in source_dir.rglob("*")
        if f.is_file() and f.name not in skip_names and f.stat().st_size > 0
    ]
    total = len(files)

    tmp_zip = zip_path.with_suffix(zip_path.suffix + ".tmp")
    try:
        with zipfile.ZipFile(
            tmp_zip, "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=compresslevel,
            allowZip64=True,
        ) as zf:
            for idx, f in enumerate(files, 1):
                arcname = f.relative_to(source_dir).as_posix()
                zf.write(f, arcname)
                if progress_cb and (idx % 8 == 0 or idx == total):
                    try:
                        progress_cb(idx, total)
                    except Exception:
                        pass
        os.replace(tmp_zip, zip_path)
        return zip_path
    except Exception:
        try:
            tmp_zip.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def open_zip_for_download(zip_path: str):
    """
    Trả file handle open('rb') để streamlit dùng làm data cho st.download_button.
    Streamlit đọc streaming — không load full vào RAM.
    Trả None nếu path không hợp lệ.
    """
    if not zip_path:
        return None
    p = Path(zip_path)
    if not p.exists() or p.stat().st_size < 22:  # ZIP header ≥ 22 bytes
        return None
    return open(p, "rb")


def readable_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
