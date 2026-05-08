"""
cleanup.py — Batch Workspace Cleanup Utility v1.0
─────────────────────────────────────────────────────────
Giải quyết vấn đề: BATCH_ROOT (~/.tmp/media_tool_pro_vip_batches) không bao giờ được dọn dẹp
→ Đĩa Streamlit Cloud (1GB) bị đầy sau vài chục batch.

Cơ chế:
- Chạy cleanup() tự động khi app khởi động (qua init_app_state).
- Xóa các workspace cũ hơn MAX_AGE_HOURS.
- Giữ lại tối đa MAX_KEEP_BATCHES batch gần nhất.
- Không xóa batch đang được tham chiếu bởi session_state hiện tại.
"""
from __future__ import annotations

import time
import shutil
from pathlib import Path

import streamlit as st


# ── Cấu hình ──
MAX_AGE_HOURS = 4       # Xóa workspace cũ hơn 4h
MAX_KEEP_BATCHES = 8    # Giữ tối đa 8 batch gần nhất (dù chưa đủ tuổi)
MIN_FREE_MB = 200       # Nếu còn ít hơn 200MB, xóa tích cực hơn

_CLEANUP_TS_KEY = "_last_cleanup_ts"
_CLEANUP_INTERVAL = 600  # Chỉ chạy cleanup tối đa mỗi 10 phút


def _get_active_roots() -> set[str]:
    """Lấy danh sách root path của batch đang dùng trong session hiện tại."""
    active = set()
    for meta_key in ["last_batch_meta"]:
        meta = st.session_state.get(meta_key, {})
        if isinstance(meta, dict):
            root = meta.get("root", "")
            if root:
                active.add(root)
    # Các zip path đang hiển thị download button
    for zip_key in ["web_zip_path", "drive_zip_path", "local_zip_path", "adjust_zip_path"]:
        val = st.session_state.get(zip_key, "")
        if val:
            active.add(str(Path(val).parent.parent))  # workspace root
    return active


def cleanup(force: bool = False) -> dict:
    """
    Dọn dẹp BATCH_ROOT.
    Trả về stats: {"deleted": N, "kept": M, "freed_mb": F}
    """
    from utils import BATCH_ROOT  # import late để tránh circular

    now = time.time()

    # Rate limit cleanup (không chạy quá thường xuyên)
    if not force:
        last = st.session_state.get(_CLEANUP_TS_KEY, 0)
        if now - last < _CLEANUP_INTERVAL:
            return {"deleted": 0, "kept": 0, "freed_mb": 0}

    st.session_state[_CLEANUP_TS_KEY] = now

    if not BATCH_ROOT.exists():
        return {"deleted": 0, "kept": 0, "freed_mb": 0}

    active_roots = _get_active_roots()
    max_age_seconds = MAX_AGE_HOURS * 3600

    # Lấy tất cả workspace, sắp xếp theo thời gian tạo (mới nhất trước)
    all_workspaces = sorted(
        [d for d in BATCH_ROOT.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    deleted = 0
    freed_bytes = 0
    kept = 0

    for idx, ws in enumerate(all_workspaces):
        ws_str = str(ws)

        # Luôn giữ nếu đang dùng trong session
        if ws_str in active_roots:
            kept += 1
            continue

        age_seconds = now - ws.stat().st_mtime
        should_delete = (
            age_seconds > max_age_seconds     # Quá tuổi
            or idx >= MAX_KEEP_BATCHES        # Quá số lượng giữ
        )

        if should_delete:
            try:
                ws_size = sum(
                    f.stat().st_size
                    for f in ws.rglob("*")
                    if f.is_file()
                )
                shutil.rmtree(ws, ignore_errors=True)
                deleted += 1
                freed_bytes += ws_size
            except Exception:
                pass
        else:
            kept += 1

    return {
        "deleted": deleted,
        "kept": kept,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1),
    }


def get_disk_usage_mb() -> float:
    """Lấy tổng dung lượng BATCH_ROOT (MB)."""
    from utils import BATCH_ROOT
    if not BATCH_ROOT.exists():
        return 0.0
    total = sum(f.stat().st_size for f in BATCH_ROOT.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 1)
