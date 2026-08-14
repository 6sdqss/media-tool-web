"""
modes/local.py — Upload files (ZIP hoặc ảnh trực tiếp) → BatchManager.
"""
from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path
from typing import Iterable

import streamlit as st

from core import state as sstate
from core.batch import BatchManager, DownloadResult, Workspace
from core.imaging import IMAGE_EXTENSIONS
from core.memory import disk_ok_for_batch
from core.types import BatchState, ErrorType, TaskItem, new_id
from core.validation import clean_name, fingerprint
from ui import components as ui


def _download_upload_item(item: TaskItem, ws: Workspace) -> DownloadResult:
    """
    Với mode local, "download" thực chất là copy binary từ payload
    (đã đọc từ file_uploader) ra disk trong ws.raw.
    """
    data: bytes = item.payload.get("data", b"")
    if not data:
        return DownloadResult(False, None, ErrorType.INVALID_IMAGE, "Không có dữ liệu")

    ext = Path(item.display_name).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        ext = ".jpg"
    dest = ws.raw / (item.group_name or "default") / f"{clean_name(item.display_name)[:60]}_{item.item_id[-6:]}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(data)
    except OSError as exc:
        msg = str(exc).lower()
        if "no space" in msg:
            return DownloadResult(False, None, ErrorType.DISK_FULL, str(exc)[:120])
        return DownloadResult(False, None, ErrorType.SAVE_FAILED, str(exc)[:120])
    # Giải phóng RAM ngay
    item.payload["data"] = b""
    return DownloadResult(True, dest)


def _extract_zip_to_items(uf, group_hint: str) -> list[tuple[str, bytes, str]]:
    """
    Trích các ảnh trong 1 ZIP → list (filename, bytes, group).
    Bỏ qua system files và file 0 byte.
    """
    out: list[tuple[str, bytes, str]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(uf.getvalue())) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if any(part.startswith(".") or part == "__MACOSX" for part in Path(name).parts):
                    continue
                ext = Path(name).suffix.lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                if info.file_size <= 0:
                    continue
                # group = folder cấp 1 trong ZIP, nếu không có thì dùng group_hint
                parts = Path(name).parts
                group = parts[0] if len(parts) > 1 else group_hint
                try:
                    data = zf.read(info)
                except Exception:
                    continue
                out.append((Path(name).name, data, group))
    except zipfile.BadZipFile:
        return []
    except Exception:
        return []
    return out


def render(preset) -> None:
    """UI cho mode Local."""
    ui.hero(
        "💻 Local — Upload ZIP hoặc ảnh",
        "Kéo/chọn file (nhiều file cùng lúc) → hệ thống tự giải nén nếu là ZIP → "
        "resize theo preset → xuất ZIP kết quả.",
    )

    ui.section("Chọn file")
    uploaded = st.file_uploader(
        "Files",
        type=["zip", "jpg", "jpeg", "png", "webp", "bmp", "gif"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="local_up",
    )

    if not uploaded:
        st.caption("Chấp nhận ZIP chứa ảnh, hoặc ảnh rời (mọi kích thước).")
        return

    # Preview counts
    n_zip = sum(1 for u in uploaded if u.name.lower().endswith(".zip"))
    n_img = len(uploaded) - n_zip
    ui.input_report_bar(len(uploaded), n_zip + n_img, 0, 0)

    ui.section("Chạy")
    col_start, col_cancel = st.columns([3, 1])
    with col_start:
        clicked = ui.start_button("🚀 START — xử lý & tải kết quả", key="btn_local_start")
    with col_cancel:
        if sstate.is_batch_active():
            if st.button("⏹ Huỷ", use_container_width=True, key="btn_local_cancel"):
                BatchManager.request_cancel()

    if clicked:
        _handle_start(uploaded, preset)

    # Realtime panels
    ui.batch_progress_panel()
    ui.batch_queue_view()
    ui.batch_result_panel()

    # Auto-poll khi batch đang chạy (background thread)
    ui.auto_refresh_if_active(1.0)


def _handle_start(uploaded, preset) -> None:
    if not sstate.acquire_batch_lock():
        st.warning("Batch khác đang chạy — chờ xong rồi thử lại.")
        return

    ok, msg = disk_ok_for_batch()
    if not ok:
        sstate.release_batch_lock()
        st.error(f"⚠️ {msg}")
        return

    # Build items
    items: list[TaskItem] = []
    seen_fps: set[str] = set()
    bid = f"local_{int(time.time())}"

    for uf in uploaded:
        if uf.name.lower().endswith(".zip"):
            group_hint = clean_name(Path(uf.name).stem)
            for fname, data, group in _extract_zip_to_items(uf, group_hint):
                fp = fingerprint(f"{uf.name}|{fname}|{len(data)}", "upload")
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                items.append(TaskItem(
                    item_id=new_id("it"),
                    batch_id=bid,
                    source=f"{uf.name}/{fname}",
                    source_kind="upload",
                    group_name=clean_name(group),
                    display_name=Path(fname).stem,
                    fingerprint=fp,
                    payload={"data": data},
                ))
        else:
            data = uf.getvalue()
            fp = fingerprint(f"{uf.name}|{len(data)}", "upload")
            if fp in seen_fps:
                continue
            seen_fps.add(fp)
            items.append(TaskItem(
                item_id=new_id("it"),
                batch_id=bid,
                source=uf.name,
                source_kind="upload",
                group_name="uploads",
                display_name=Path(uf.name).stem,
                fingerprint=fp,
                payload={"data": data},
            ))

    if not items:
        sstate.release_batch_lock()
        st.error("Không tìm thấy ảnh hợp lệ trong file upload.")
        return

    # Non-blocking start — pipeline chạy trong background thread
    BatchManager.start_background("local", preset, items, _download_upload_item)
    st.rerun()
