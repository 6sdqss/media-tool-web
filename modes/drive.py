"""
modes/drive.py — Google Drive files/folders → BatchManager.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import streamlit as st

from core import state as sstate
from core.batch import BatchManager, DownloadResult, Workspace
from core.download import (
    download_drive_file, drive_name_scrape, list_drive_folder,
)
from core.memory import disk_ok_for_batch
from core.types import ErrorType, TaskItem, new_id
from core.validation import (
    classify_url, clean_name, extract_drive_id, fingerprint,
    split_input_lines, validate_url_batch,
)
from ui import components as ui


_log = logging.getLogger("modes.drive")

# Bộ nhớ đệm ngắn hạn cho service (khởi tạo 1 lần / session)
_SERVICE_KEY = "_drive_service_v11"


def _get_service():
    """Lấy Google Drive service từ service account trong secrets."""
    if _SERVICE_KEY in st.session_state:
        return st.session_state[_SERVICE_KEY]
    svc = None
    try:
        creds_info = st.secrets.get("google_service_account", None)
        if creds_info:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_info(
                dict(creds_info),
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        _log.warning("Drive service init failed: %s", exc)
    st.session_state[_SERVICE_KEY] = svc
    return svc


def _download_drive_item(item: TaskItem, ws: Workspace) -> DownloadResult:
    """Adapter download cho item Drive."""
    service = st.session_state.get(_SERVICE_KEY)
    file_id = item.payload.get("file_id", "")
    if not file_id:
        return DownloadResult(False, None, ErrorType.INVALID_URL, "Không có file_id")

    dest_dir = ws.raw / (item.group_name or "drive")
    dest_dir.mkdir(parents=True, exist_ok=True)

    path, err, msg = download_drive_file(
        file_id, dest_dir, name_hint=item.display_name or f"drive_{file_id[:8]}",
        service=service, max_retries=2,
    )
    if path and err is None:
        return DownloadResult(True, path)
    return DownloadResult(False, None, err or ErrorType.DOWNLOAD_FAILED, msg)


def render(preset) -> None:
    ui.hero(
        "🌐 Google Drive — Folder & File",
        "Dán link Drive (folder chia sẻ hoặc file đơn) → tải song song → resize → ZIP. "
        "Ưu tiên Service Account (nếu có config trong Secrets); "
        "fallback về link chia sẻ công khai.",
    )

    service = _get_service()
    if not service:
        st.caption("ℹ️ Chưa có Service Account — chỉ dùng được link chia sẻ **public**.")

    ui.section("Dán link Drive")
    text = st.text_area(
        "Links",
        height=110,
        placeholder=(
            "https://drive.google.com/drive/folders/ABC123\n"
            "https://drive.google.com/file/d/XYZ789"
        ),
        label_visibility="collapsed",
        key="drive_links",
    )

    # Validate
    lines = split_input_lines(text)
    report = validate_url_batch(lines, allowed_kinds={"drive_file", "drive_folder"})
    if lines:
        ui.input_report_bar(
            report.raw_count, report.valid_count, report.dup_count, report.invalid_count,
        )
        if report.invalid:
            with st.expander(f"Xem {len(report.invalid)} link không hỗ trợ"):
                for raw, reason in report.invalid[:20]:
                    st.caption(f"❌ {raw} — {reason}")

    ui.section("Chạy")
    col1, col2 = st.columns([3, 1])
    with col1:
        clicked = ui.start_button("🚀 START — tải & xử lý", key="btn_drive_start")
    with col2:
        if sstate.is_batch_active():
            if st.button("⏹ Huỷ", use_container_width=True, key="btn_drive_cancel"):
                BatchManager.request_cancel()

    if clicked:
        _handle_start(report, preset, service)

    ui.batch_progress_panel()
    ui.batch_queue_view()
    ui.batch_result_panel()

    ui.auto_refresh_if_active(1.0)


def _handle_start(report, preset, service) -> None:
    if not report.valid:
        st.error("Không có link Drive hợp lệ.")
        return
    if not sstate.acquire_batch_lock():
        st.warning("Batch khác đang chạy.")
        return

    ok, msg = disk_ok_for_batch()
    if not ok:
        sstate.release_batch_lock()
        st.error(f"⚠️ {msg}")
        return

    # Expand: mỗi folder → nhiều file
    items: list[TaskItem] = []
    seen_fps: set[str] = set()
    bid = f"drive_{int(time.time())}"

    with st.spinner("Đang liệt kê nội dung Drive..."):
        for norm_url, kind in report.valid:
            file_id = extract_drive_id(norm_url)
            if not file_id:
                continue

            if kind == "drive_folder":
                # Cần Service Account để list folder
                if not service:
                    st.warning(f"Bỏ qua folder {norm_url[:60]} — cần Service Account để liệt kê.")
                    continue
                files = list_drive_folder(service, file_id)
                if not files:
                    st.warning(f"Folder rỗng hoặc không truy cập được: {norm_url[:60]}")
                    continue
                folder_name = clean_name(drive_name_scrape(file_id, "drive_folder"))
                for f in files:
                    fp = fingerprint(f["id"], "drive_file")
                    if fp in seen_fps:
                        continue
                    seen_fps.add(fp)
                    items.append(TaskItem(
                        item_id=new_id("it"),
                        batch_id=bid,
                        source=norm_url,
                        source_kind="drive_file",
                        group_name=folder_name,
                        display_name=Path(f.get("name", "")).stem or f["id"][:8],
                        fingerprint=fp,
                        payload={"file_id": f["id"]},
                    ))
            else:
                # File đơn
                fp = fingerprint(file_id, "drive_file")
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                name = clean_name(drive_name_scrape(file_id, "drive_file"))
                items.append(TaskItem(
                    item_id=new_id("it"),
                    batch_id=bid,
                    source=norm_url,
                    source_kind="drive_file",
                    group_name="drive_files",
                    display_name=name,
                    fingerprint=fp,
                    payload={"file_id": file_id},
                ))

    if not items:
        sstate.release_batch_lock()
        st.error("Không expand được item nào từ link Drive đã cho.")
        return

    BatchManager.start_background("drive", preset, items, _download_drive_item)
    st.rerun()
