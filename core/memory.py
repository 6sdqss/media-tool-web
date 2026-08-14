"""
core/memory.py — theo dõi RAM / disk, cấp phát worker động.
Streamlit Cloud giới hạn ~1GB RAM và ~1GB disk. Module này quyết định:
- Có nên bắt đầu batch mới không (disk còn đủ?)
- Bao nhiêu worker resize/download an toàn?
- Có phải giảm concurrency giữa batch không?
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


# ══════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════
MAX_IMAGE_PIXELS_SAFE = 120_000_000     # ~120 MP — chặn "bomb image"
MAX_SOURCE_FILE_BYTES = 60 * 1024 * 1024  # 60MB / file input
MIN_FREE_DISK_MB = 150                  # Không bắt đầu batch nếu còn < 150MB
DISK_WARNING_MB = 300                   # Cảnh báo user ở mức này

DOWNLOAD_WORKERS_DEFAULT = 4
DOWNLOAD_WORKERS_MAX = 6

# Resize là CPU + RAM heavy → worker thấp hơn download nhiều
RESIZE_WORKERS_DEFAULT = 3
RESIZE_WORKERS_MAX = 4


# ══════════════════════════════════════════════════════════════
# RAM
# ══════════════════════════════════════════════════════════════
def available_memory_mb() -> float:
    """
    Lấy RAM còn trống (MB). Trả -1 nếu không đọc được (ví dụ Windows dev).
    Ưu tiên /proc/meminfo (Linux/Streamlit Cloud), fallback psutil nếu có.
    """
    # Linux: /proc/meminfo
    try:
        with open("/proc/meminfo", "r") as f:
            info = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    info[parts[0].strip()] = parts[1].strip()
        # MemAvailable là số kB thực dụng nhất
        avail_kb = info.get("MemAvailable", "").split()
        if avail_kb:
            return int(avail_kb[0]) / 1024.0
    except Exception:
        pass

    # psutil fallback
    try:
        import psutil  # type: ignore
        return psutil.virtual_memory().available / (1024 * 1024)
    except Exception:
        return -1.0


def memory_pressure_high() -> bool:
    """True nếu RAM còn ≤ 250MB — phải giảm concurrency."""
    mb = available_memory_mb()
    return 0 <= mb <= 250


# ══════════════════════════════════════════════════════════════
# DISK
# ══════════════════════════════════════════════════════════════
def disk_free_mb(path: Path | str = "/tmp") -> float:
    try:
        p = Path(str(path))
        while not p.exists():
            p = p.parent
        stats = shutil.disk_usage(str(p))
        return stats.free / (1024 * 1024)
    except Exception:
        return -1.0


def disk_ok_for_batch(workspace: Path | str = "/tmp") -> tuple[bool, str]:
    """Trả (ok, message). Nếu không ok, message giải thích cho user."""
    free = disk_free_mb(workspace)
    if free < 0:
        return True, ""  # không đo được → giả định ok
    if free < MIN_FREE_DISK_MB:
        return False, (
            f"Đĩa chỉ còn {free:.0f}MB — cần ít nhất {MIN_FREE_DISK_MB}MB "
            f"để bắt đầu batch mới. Bấm nút 🧹 để dọn workspace cũ."
        )
    return True, ""


# ══════════════════════════════════════════════════════════════
# ADAPTIVE WORKER COUNT
# ══════════════════════════════════════════════════════════════
def suggest_download_workers(total_items: int) -> int:
    """Số worker download hợp lý theo tổng items và RAM."""
    if memory_pressure_high():
        return 2
    if total_items <= 3:
        return min(DOWNLOAD_WORKERS_DEFAULT, total_items)
    return DOWNLOAD_WORKERS_DEFAULT


def suggest_resize_workers(sample_size_mb: float = 0.0) -> int:
    """
    Số worker resize hợp lý.
    File càng lớn → càng ít worker để tránh OOM.
    """
    if memory_pressure_high():
        return 1
    if sample_size_mb >= 15:      # ảnh nặng — 1 luồng
        return 1
    if sample_size_mb >= 5:       # ảnh vừa
        return 2
    return RESIZE_WORKERS_DEFAULT


def clamp_workers(requested: int, kind: str = "resize") -> int:
    """Ép giá trị user request vào khoảng an toàn."""
    try:
        v = int(requested)
    except Exception:
        v = 1
    if kind == "download":
        return max(1, min(DOWNLOAD_WORKERS_MAX, v))
    return max(1, min(RESIZE_WORKERS_MAX, v))
