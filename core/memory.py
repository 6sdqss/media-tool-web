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

# Render free/starter chỉ có 512MB RAM cho CẢ container (Reflex + Caddy +
# Python + libs đã chiếm ~250-300MB baseline) → siết concurrency mặc định
# thấp hơn nhiều so với trước (từng để 4/3, gây OOM-kill status 137 dù đã
# có throttle theo cgroup). An toàn > tốc độ trên gói RAM nhỏ.
DOWNLOAD_WORKERS_DEFAULT = 2
DOWNLOAD_WORKERS_MAX = 3

# Resize là CPU + RAM heavy → worker thấp hơn download nhiều
RESIZE_WORKERS_DEFAULT = 2
RESIZE_WORKERS_MAX = 2


# ══════════════════════════════════════════════════════════════
# RAM
# ══════════════════════════════════════════════════════════════
def _host_available_mb() -> float:
    """RAM còn trống theo /proc/meminfo — đây là RAM của HOST, không phải
    của container. Trong Docker (Render...) con số này thường lớn hơn nhiều
    so với giới hạn thật (cgroup), vì kernel host có nhiều RAM hơn container
    được cấp."""
    try:
        with open("/proc/meminfo", "r") as f:
            info = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    info[parts[0].strip()] = parts[1].strip()
        avail_kb = info.get("MemAvailable", "").split()
        if avail_kb:
            return int(avail_kb[0]) / 1024.0
    except Exception:
        pass
    try:
        import psutil  # type: ignore
        return psutil.virtual_memory().available / (1024 * 1024)
    except Exception:
        return -1.0


def _cgroup_available_mb() -> float:
    """RAM còn trống THEO GIỚI HẠN CONTAINER (cgroup) — con số đúng khi chạy
    trên Render/Docker. Nếu không đọc được (dev máy thường, không phải
    container) → trả -1 để caller bỏ qua.

    Hỗ trợ cả cgroup v2 (memory.max/memory.current) và v1
    (memory.limit_in_bytes/memory.usage_in_bytes). Nếu limit là "max"
    (không giới hạn) hoặc lớn bất thường (>16GB, rõ ràng không phải giới
    hạn container thật) → coi như không có cgroup limit, trả -1.
    """
    HUGE = 16 * 1024 * 1024 * 1024  # 16GB — ngưỡng coi là "unlimited"
    try:
        # cgroup v2
        max_p = Path("/sys/fs/cgroup/memory.max")
        cur_p = Path("/sys/fs/cgroup/memory.current")
        if max_p.exists() and cur_p.exists():
            raw_max = max_p.read_text().strip()
            if raw_max != "max":
                limit = int(raw_max)
                if 0 < limit < HUGE:
                    used = int(cur_p.read_text().strip())
                    return max(0.0, (limit - used) / (1024 * 1024))
    except Exception:
        pass
    try:
        # cgroup v1
        lim_p = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        use_p = Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")
        if lim_p.exists() and use_p.exists():
            limit = int(lim_p.read_text().strip())
            if 0 < limit < HUGE:
                used = int(use_p.read_text().strip())
                return max(0.0, (limit - used) / (1024 * 1024))
    except Exception:
        pass
    return -1.0


def available_memory_mb() -> float:
    """
    Lấy RAM còn trống (MB) — LẤY MIN giữa host (/proc/meminfo) và giới hạn
    container thật (cgroup), vì trong Docker (Render free = 512MB) host
    thường báo RAM dư dả trong khi container sắp OOM. Trả -1 nếu không đọc
    được cả hai (ví dụ Windows dev).
    """
    host_mb = _host_available_mb()
    cgroup_mb = _cgroup_available_mb()
    if cgroup_mb >= 0 and host_mb >= 0:
        return min(host_mb, cgroup_mb)
    if cgroup_mb >= 0:
        return cgroup_mb
    return host_mb


def memory_pressure_high() -> bool:
    """True nếu RAM còn ≤ 350MB — phải giảm concurrency xuống mức tối thiểu.
    Ngưỡng nâng dần 250→300→350MB: baseline riêng Reflex+Caddy+Python trên
    Render free/starter (512MB container) đã chiếm phần lớn RAM, nên biên an
    toàn phải rộng để không bị OOM-kill (status 137) giữa batch."""
    mb = available_memory_mb()
    return 0 <= mb <= 350


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


MIN_FREE_RAM_MB_TO_START = 180  # RAM tối thiểu để CHO PHÉP bắt đầu batch mới


def memory_ok_for_batch() -> tuple[bool, str]:
    """Kiểm tra RAM TRƯỚC khi cho phép bắt đầu batch mới — tránh việc bắt
    đầu rồi giữa chừng bị Render OOM-kill (mất cả batch + session).
    Trả (ok, message cảnh báo cho user nếu not ok)."""
    mb = available_memory_mb()
    if mb < 0:
        return True, ""  # không đo được → không chặn (ví dụ máy dev)
    if mb < MIN_FREE_RAM_MB_TO_START:
        return False, (
            f"RAM server chỉ còn ~{mb:.0f}MB — chưa đủ an toàn để bắt đầu "
            f"batch mới (cần ≥{MIN_FREE_RAM_MB_TO_START}MB). Server free-tier "
            f"512MB dễ bị quá tải khi có nhiều ảnh nặng cùng lúc. Vui lòng đợi "
            f"~30-60s cho batch/RAM trước giải phóng rồi thử lại, hoặc giảm số "
            f"lượng link/ảnh mỗi lần chạy."
        )
    return True, ""


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
