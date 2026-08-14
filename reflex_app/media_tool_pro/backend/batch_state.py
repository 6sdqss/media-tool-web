"""
batch_state.py — State cho 3 mode batch (Web/TGDD, Drive, Local) + queue/progress.

Toàn bộ logic "build TaskItem" ở đây được port 1:1 từ modes/web.py,
modes/drive.py, modes/local.py (repo gốc) — chỉ bỏ phần st.* UI, thay
bằng Reflex event handler. Lời gọi vào core.batch.BatchManager và
core.download / core.validation / core.presets GIỮ NGUYÊN không đổi.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import reflex as rx

from . import st_compat  # noqa: F401 — đăng ký shim streamlit trước
from .st_compat import GLOBAL_SESSION_STATE

from core import state as sstate
from core import presets as presets_mod
from core.batch import BatchManager, DownloadResult, Workspace
from core.download import (
    download_drive_file, drive_name_scrape, list_drive_folder,
)
from core.memory import disk_ok_for_batch
from core.types import BatchState as CoreBatchState, ErrorType, TaskItem, new_id
from core.validation import (
    classify_url, clean_name, extract_drive_id, fingerprint,
    split_input_lines, validate_url_batch,
)
from core.imaging import IMAGE_EXTENSIONS

_log = logging.getLogger("reflex.batch_state")

sstate.init()  # khởi tạo schema dùng chung (session_state giả — 1 lần / process)


# ══════════════════════════════════════════════════════════════
# DOWNLOAD ADAPTERS (port từ modes/web.py, modes/drive.py, modes/local.py)
# ══════════════════════════════════════════════════════════════
def _download_image_url(item: TaskItem, ws: Workspace) -> DownloadResult:
    from core.download import download_http
    img_url = item.payload.get("image_url", item.source)
    ext = Path(img_url.split("?")[0]).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
        ext = ".jpg"
    dest_dir = ws.raw / (item.group_name or "web")
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = clean_name(item.display_name)[:50] or "img"
    dest = dest_dir / f"{base}_{item.item_id[-6:]}{ext}"
    ok, err, msg = download_http(
        img_url, dest, timeout=(10, 30),
        headers={"Referer": "https://www.thegioididong.com/"},
    )
    if ok:
        return DownloadResult(True, dest)
    return DownloadResult(False, None, err or ErrorType.DOWNLOAD_FAILED, msg)


def _download_drive_item(item: TaskItem, ws: Workspace) -> DownloadResult:
    service = GLOBAL_SESSION_STATE.get("_drive_service_v11")
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


def _download_upload_item(item: TaskItem, ws: Workspace) -> DownloadResult:
    data: bytes = item.payload.get("data", b"")
    if not data:
        return DownloadResult(False, None, ErrorType.INVALID_IMAGE, "Không có dữ liệu")
    ext = Path(item.display_name).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        ext = ".jpg"
    dest = ws.raw / (item.group_name or "default") / (
        f"{clean_name(item.display_name)[:60]}_{item.item_id[-6:]}{ext}"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(data)
    except OSError as exc:
        msg = str(exc).lower()
        if "no space" in msg:
            return DownloadResult(False, None, ErrorType.DISK_FULL, str(exc)[:120])
        return DownloadResult(False, None, ErrorType.SAVE_FAILED, str(exc)[:120])
    item.payload["data"] = b""
    return DownloadResult(True, dest)


def _get_drive_service():
    """Khởi tạo Google Drive service từ service account (biến môi trường)."""
    if "_drive_service_v11" in GLOBAL_SESSION_STATE:
        return GLOBAL_SESSION_STATE["_drive_service_v11"]
    svc = None
    try:
        import json as _json
        import os
        creds_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_raw:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_info(
                _json.loads(creds_raw),
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Drive service init failed: %s", exc)
    GLOBAL_SESSION_STATE["_drive_service_v11"] = svc
    return svc


def _get_tgdd_scraper():
    from modes.tgdd_scraper import TGDDScraper
    sc = GLOBAL_SESSION_STATE.get("_tgdd_scraper_v11")
    if sc is None:
        sc = TGDDScraper()
        GLOBAL_SESSION_STATE["_tgdd_scraper_v11"] = sc
    return sc


# ══════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════
class BatchState(rx.State):
    # ── mode & preset ──
    active_mode: str = "web"          # "web" | "drive" | "local" | "studio" | "admin" | "guide" | "home"
    preset_options: list[dict] = []
    selected_preset: str = "TGDD Product 1020x680"

    # ── inputs ──
    web_links: str = ""
    web_cookie_text: str = ""
    web_cookie_status: str = ""
    web_scrape_log: list[str] = []

    drive_links: str = ""

    local_upload_names: list[str] = []
    local_upload_ready: bool = False

    input_report: dict = {"raw": 0, "valid": 0, "dup": 0, "invalid": 0}
    input_invalid_lines: list[list[str]] = []

    # ── settings ──
    one_click_mode: bool = False
    auto_zip: bool = True
    auto_report: bool = True

    # ── batch progress (mirror BatchInfo) ──
    is_batch_running: bool = False
    batch_state_label: str = "IDLE"
    batch_total: int = 0
    batch_queued: int = 0
    batch_running_n: int = 0
    batch_success: int = 0
    batch_failed: int = 0
    batch_retrying: int = 0
    batch_cancelled: int = 0
    batch_skipped: int = 0
    batch_progress_pct: int = 0
    batch_current_item: str = ""
    batch_current_op: str = ""
    batch_log_tail: list[str] = []
    batch_duration_s: float = 0.0
    batch_zip_ready: bool = False
    batch_report_ready: bool = False
    batch_error_msg: str = ""

    queue_rows: list[dict] = []

    history: list[dict] = []

    cleanup_msg: str = ""

    # local upload staging: bytes held server-side (not in Var) via dict
    _local_pending: list = []  # instance attr, populated by upload handler

    @rx.var
    def preset_names(self) -> list[str]:
        return [p["name"] for p in self.preset_options]

    def load_presets(self):
        plist = presets_mod.load_all()
        self.preset_options = [
            {
                "name": p.name,
                "description": p.description,
                "sizes": " · ".join(s.label() for s in p.sizes),
                "quality": p.quality,
                "format": p.export_format,
            }
            for p in plist
        ]
        if plist and self.selected_preset not in [p.name for p in plist]:
            self.selected_preset = plist[0].name

    def set_active_mode(self, mode: str):
        self.active_mode = mode

    def set_selected_preset(self, name: str):
        self.selected_preset = name

    def set_web_links(self, v: str):
        self.web_links = v
        self._refresh_report(allowed={"tgdd"})

    def set_drive_links(self, v: str):
        self.drive_links = v
        self._refresh_report(allowed={"drive_file", "drive_folder"})

    def set_web_cookie_text(self, v: str):
        self.web_cookie_text = v

    def load_cookie(self):
        sc = _get_tgdd_scraper()
        n, msg = sc.set_cookies(self.web_cookie_text)
        self.web_cookie_status = ("✔ " if n > 0 else "⚠ ") + msg

    def set_one_click_mode(self, v: bool):
        self.one_click_mode = v

    def set_auto_zip(self, v: bool):
        self.auto_zip = v

    def set_auto_report(self, v: bool):
        self.auto_report = v

    def _refresh_report(self, allowed: set[str]):
        text = self.web_links if "tgdd" in allowed else self.drive_links
        lines = split_input_lines(text)
        rep = validate_url_batch(lines, allowed_kinds=allowed)
        self.input_report = {
            "raw": rep.raw_count, "valid": rep.valid_count,
            "dup": rep.dup_count, "invalid": rep.invalid_count,
        }
        self.input_invalid_lines = [[raw, reason] for raw, reason in rep.invalid[:20]]

    def _current_preset_obj(self):
        p = presets_mod.get(self.selected_preset)
        if p is None:
            plist = presets_mod.load_all()
            p = plist[0] if plist else None
        return p

    # ── WEB / TGDD ────────────────────────────────────────────
    @rx.event(background=True)
    async def start_web_batch(self):
        async with self:
            if self.is_batch_running:
                self.batch_error_msg = "Batch khác đang chạy."
                return
            lines = split_input_lines(self.web_links)
            report = validate_url_batch(lines, allowed_kinds={"tgdd"})
            if not report.valid:
                self.batch_error_msg = "Không có link TGDD hợp lệ."
                return
            if not sstate.acquire_batch_lock():
                self.batch_error_msg = "Batch khác đang chạy."
                return
            ok, msg = disk_ok_for_batch()
            if not ok:
                sstate.release_batch_lock()
                self.batch_error_msg = msg
                return
            preset = self._current_preset_obj()
            self.batch_error_msg = ""
            self.web_scrape_log = []
            self.is_batch_running = True

        scraper = _get_tgdd_scraper()
        items: list[TaskItem] = []
        seen_fps: set[str] = set()
        bid = f"web_{int(time.time())}"
        log_lines: list[str] = []

        for norm_url, _kind in report.valid:
            try:
                prod = scraper.scrape(norm_url)
            except Exception as exc:  # noqa: BLE001
                log_lines.append(f"❌ {norm_url[:60]} — {exc}")
                continue
            product_name = clean_name(prod.get("name", "product"))[:40] or "product"
            colors = prod.get("colors", [])
            if not colors:
                log_lines.append(f"⚠ {product_name} — không tìm thấy ảnh")
                continue
            for color in colors:
                color_name = clean_name(color.get("name", "default"))[:30] or "default"
                imgs = color.get("images", [])
                if not imgs:
                    continue
                group = (
                    f"{product_name}/{color_name}"
                    if color_name and color_name != "Mac_dinh" else product_name
                )
                for i, img_url in enumerate(imgs, 1):
                    fp = fingerprint(img_url, "image_url")
                    if fp in seen_fps:
                        continue
                    seen_fps.add(fp)
                    from modes.tgdd_scraper import derive_filename
                    fname = derive_filename(img_url, i) or f"{color_name}_{i:02d}"
                    items.append(TaskItem(
                        item_id=new_id("it"), batch_id=bid, source=img_url,
                        source_kind="image_url", group_name=group, display_name=fname,
                        fingerprint=fp,
                        payload={"image_url": img_url, "product_url": norm_url,
                                 "product_name": product_name, "color_name": color_name},
                    ))
            log_lines.append(
                f"✔ {product_name} — {len(colors)} màu, "
                f"{sum(len(c.get('images', [])) for c in colors)} ảnh"
            )

        async with self:
            self.web_scrape_log = log_lines[:40]
            if not items:
                sstate.release_batch_lock()
                self.is_batch_running = False
                self.batch_error_msg = "Không scrape được ảnh nào (cần cookie, hoặc link sai/hết hàng)."
                return

        BatchManager.start_background("web", preset, items, _download_image_url)
        async for _ in self._poll_loop():
            yield

    # ── DRIVE ────────────────────────────────────────────────
    @rx.event(background=True)
    async def start_drive_batch(self):
        async with self:
            if self.is_batch_running:
                self.batch_error_msg = "Batch khác đang chạy."
                return
            lines = split_input_lines(self.drive_links)
            report = validate_url_batch(lines, allowed_kinds={"drive_file", "drive_folder"})
            if not report.valid:
                self.batch_error_msg = "Không có link Drive hợp lệ."
                return
            if not sstate.acquire_batch_lock():
                self.batch_error_msg = "Batch khác đang chạy."
                return
            ok, msg = disk_ok_for_batch()
            if not ok:
                sstate.release_batch_lock()
                self.batch_error_msg = msg
                return
            preset = self._current_preset_obj()
            self.batch_error_msg = ""
            self.is_batch_running = True

        service = _get_drive_service()
        items: list[TaskItem] = []
        seen_fps: set[str] = set()
        bid = f"drive_{int(time.time())}"
        warnings: list[str] = []

        for norm_url, kind in report.valid:
            file_id = extract_drive_id(norm_url)
            if not file_id:
                continue
            if kind == "drive_folder":
                if not service:
                    warnings.append(f"Bỏ qua folder {norm_url[:60]} — cần Service Account.")
                    continue
                files = list_drive_folder(service, file_id)
                if not files:
                    warnings.append(f"Folder rỗng/không truy cập: {norm_url[:60]}")
                    continue
                folder_name = clean_name(drive_name_scrape(file_id, "drive_folder"))
                for f in files:
                    fp = fingerprint(f["id"], "drive_file")
                    if fp in seen_fps:
                        continue
                    seen_fps.add(fp)
                    items.append(TaskItem(
                        item_id=new_id("it"), batch_id=bid, source=norm_url,
                        source_kind="drive_file", group_name=folder_name,
                        display_name=Path(f.get("name", "")).stem or f["id"][:8],
                        fingerprint=fp, payload={"file_id": f["id"]},
                    ))
            else:
                fp = fingerprint(file_id, "drive_file")
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                name = clean_name(drive_name_scrape(file_id, "drive_file"))
                items.append(TaskItem(
                    item_id=new_id("it"), batch_id=bid, source=norm_url,
                    source_kind="drive_file", group_name="drive_files",
                    display_name=name, fingerprint=fp, payload={"file_id": file_id},
                ))

        async with self:
            if not items:
                sstate.release_batch_lock()
                self.is_batch_running = False
                self.batch_error_msg = "Không expand được item nào từ link Drive." + (
                    " " + " / ".join(warnings) if warnings else ""
                )
                return

        BatchManager.start_background("drive", preset, items, _download_drive_item)
        async for _ in self._poll_loop():
            yield

    # ── LOCAL ────────────────────────────────────────────────
    async def handle_local_upload(self, files: list[rx.UploadFile]):
        self._local_pending = []
        names = []
        for f in files:
            data = await f.read()
            self._local_pending.append((f.filename or f.name, data))
            names.append(f.filename or f.name)
        self.local_upload_names = names
        self.local_upload_ready = bool(names)

    @rx.event(background=True)
    async def start_local_batch(self):
        async with self:
            if self.is_batch_running:
                self.batch_error_msg = "Batch khác đang chạy."
                return
            if not self._local_pending:
                self.batch_error_msg = "Chưa chọn file."
                return
            if not sstate.acquire_batch_lock():
                self.batch_error_msg = "Batch khác đang chạy."
                return
            ok, msg = disk_ok_for_batch()
            if not ok:
                sstate.release_batch_lock()
                self.batch_error_msg = msg
                return
            preset = self._current_preset_obj()
            pending = list(self._local_pending)
            self.batch_error_msg = ""
            self.is_batch_running = True

        import io
        import zipfile

        items: list[TaskItem] = []
        seen_fps: set[str] = set()
        bid = f"local_{int(time.time())}"

        for fname, data in pending:
            if fname.lower().endswith(".zip"):
                group_hint = clean_name(Path(fname).stem)
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            name = info.filename
                            if any(part.startswith(".") or part == "__MACOSX"
                                   for part in Path(name).parts):
                                continue
                            ext = Path(name).suffix.lower()
                            if ext not in IMAGE_EXTENSIONS or info.file_size <= 0:
                                continue
                            parts = Path(name).parts
                            group = parts[0] if len(parts) > 1 else group_hint
                            try:
                                idata = zf.read(info)
                            except Exception:  # noqa: BLE001
                                continue
                            fp = fingerprint(f"{fname}|{name}|{len(idata)}", "upload")
                            if fp in seen_fps:
                                continue
                            seen_fps.add(fp)
                            items.append(TaskItem(
                                item_id=new_id("it"), batch_id=bid,
                                source=f"{fname}/{Path(name).name}", source_kind="upload",
                                group_name=clean_name(group),
                                display_name=Path(name).name, fingerprint=fp,
                                payload={"data": idata},
                            ))
                except zipfile.BadZipFile:
                    continue
            else:
                fp = fingerprint(f"{fname}|{len(data)}", "upload")
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                items.append(TaskItem(
                    item_id=new_id("it"), batch_id=bid, source=fname,
                    source_kind="upload", group_name="uploads",
                    display_name=Path(fname).stem, fingerprint=fp,
                    payload={"data": data},
                ))

        async with self:
            self._local_pending = []
            self.local_upload_names = []
            self.local_upload_ready = False
            if not items:
                sstate.release_batch_lock()
                self.is_batch_running = False
                self.batch_error_msg = "Không tìm thấy ảnh hợp lệ trong file đã upload."
                return

        BatchManager.start_background("local", preset, items, _download_upload_item)
        async for _ in self._poll_loop():
            yield

    # ── CONTROL ──────────────────────────────────────────────
    def cancel_batch(self):
        BatchManager.request_cancel()

    def cleanup_workspace(self):
        from core.batch import cleanup_old_workspaces
        stats = cleanup_old_workspaces(keep_last=3, max_age_hours=6)
        self.cleanup_msg = f"Đã xoá {stats['deleted']} batch cũ · giải phóng {stats['freed_mb']} MB"

    # ── POLL LOOP (background task → cập nhật UI mỗi 0.8s) ────
    async def _poll_loop(self):
        """
        Generator dùng trong background event handler — thay thế cho
        `time.sleep(0.8) + st.rerun()` của bản Streamlit gốc.
        BatchManager chạy trong 1 daemon thread riêng (core/batch.py không
        đổi); handler này CHỈ đọc state dùng chung (sstate.batch()/items())
        và đẩy dữ liệu vào Reflex Var để browser tự cập nhật qua websocket.
        """
        while True:
            await asyncio.sleep(0.8)
            async with self:
                bi = sstate.batch()
                items = sstate.items()
                self.batch_state_label = bi.state.value
                self.batch_total = bi.total
                self.batch_queued = bi.queued
                self.batch_running_n = bi.running
                self.batch_success = bi.success
                self.batch_failed = bi.failed
                self.batch_retrying = bi.retrying
                self.batch_cancelled = bi.cancelled
                self.batch_skipped = bi.skipped
                self.batch_progress_pct = int(bi.progress_ratio * 100)
                self.batch_current_item = bi.current_item_name
                self.batch_current_op = bi.current_operation
                self.batch_log_tail = list(bi.log_tail[-15:])
                self.batch_duration_s = round(bi.duration, 1)
                self.batch_zip_ready = bool(bi.zip_path)
                self.batch_report_ready = bool(bi.report_path)

                self.queue_rows = [
                    {
                        "name": it.display_name or it.source[:40],
                        "group": it.group_name,
                        "status": it.status.value,
                        "error": it.error_type.value,
                    }
                    for it in items[:300]
                ]

                finished = bi.state in (CoreBatchState.DONE, CoreBatchState.FAILED)
                if finished:
                    self.is_batch_running = False
                    hist = GLOBAL_SESSION_STATE.get("batch_history", [])
                    self.history = list(hist[:10])
                    yield
                    return
            yield

    def download_zip(self):
        bi = sstate.batch()
        if bi.zip_path and Path(bi.zip_path).exists():
            return rx.download(data=Path(bi.zip_path).read_bytes(),
                                filename=Path(bi.zip_path).name)

    def download_report(self):
        bi = sstate.batch()
        if bi.report_path and Path(bi.report_path).exists():
            return rx.download(data=Path(bi.report_path).read_bytes(),
                                filename=Path(bi.report_path).name)
