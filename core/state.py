"""
core/state.py — schema cho st.session_state.
Đưa toàn bộ key rải rác về một chỗ có tên rõ ràng, tránh dùng
key ngẫu nhiên hoặc trùng lặp gây stale data giữa các tab.
"""
from __future__ import annotations

import streamlit as st

from .types import BatchInfo, BatchState


# Danh sách key đã "khai báo" — dùng để cleanup an toàn khi cần
_STATE_KEYS = {
    "app_ready",
    "batch_info",       # BatchInfo (single active batch per session)
    "batch_items",      # list[TaskItem]
    "batch_lock",       # threading-like guard: True = có batch chưa idle
    "batch_history",    # list[dict] — batch đã xong
    "presets_cache",    # list[Preset]
    "current_preset",   # str
    "recent_inputs",    # dict[mode -> str]
    "user_settings",    # dict {show_advanced, autorun_zip, ...}
    "goto_studio",      # bool — chuyển tab sau batch xong
    # UI ephemerals
    "last_error_toast",
    "last_success_toast",
}


def init() -> None:
    """Khởi tạo state schema. An toàn khi gọi nhiều lần."""
    ss = st.session_state
    ss.setdefault("app_ready", True)
    if "batch_info" not in ss:
        ss["batch_info"] = BatchInfo()
    ss.setdefault("batch_items", [])
    ss.setdefault("batch_lock", False)
    ss.setdefault("batch_history", [])
    ss.setdefault("presets_cache", None)
    ss.setdefault("current_preset", "TGDD Product 1020x680")
    ss.setdefault("recent_inputs", {})
    ss.setdefault("user_settings", {
        "show_advanced": False,
        "auto_zip": True,
        "auto_report": True,
        "one_click_mode": False,
    })
    ss.setdefault("goto_studio", False)


def batch() -> BatchInfo:
    return st.session_state["batch_info"]


def set_batch(info: BatchInfo) -> None:
    st.session_state["batch_info"] = info


def items() -> list:
    return st.session_state["batch_items"]


def set_items(new_items: list) -> None:
    st.session_state["batch_items"] = new_items


def is_batch_active() -> bool:
    """True khi có batch đang preparing/running/paused/cancelling."""
    bi = batch()
    return bi.state not in (BatchState.IDLE, BatchState.DONE, BatchState.FAILED)


def acquire_batch_lock() -> bool:
    """
    Trả True nếu vừa acquire được lock (batch chưa chạy).
    Trả False nếu batch đã đang chạy — chống double-click và Streamlit rerun spam.
    """
    if is_batch_active():
        return False
    st.session_state["batch_lock"] = True
    return True


def release_batch_lock() -> None:
    st.session_state["batch_lock"] = False


def reset_batch() -> None:
    """Đưa batch về IDLE để chuẩn bị batch mới."""
    st.session_state["batch_info"] = BatchInfo()
    st.session_state["batch_items"] = []
    release_batch_lock()


def push_history(entry: dict) -> None:
    hist = st.session_state.setdefault("batch_history", [])
    hist.insert(0, entry)
    del hist[20:]  # giữ 20 gần nhất


def settings() -> dict:
    return st.session_state["user_settings"]


def update_setting(key: str, value) -> None:
    settings()[key] = value
