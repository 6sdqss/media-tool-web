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
from core.memory import disk_ok_for_batch, memory_ok_for_batch
from core.types import (
    BatchState as CoreBatchState, ErrorType, ItemState, Preset, SizeSpec, TaskItem, new_id,
)
from core.validation import (
    classify_url, clean_name, extract_drive_id, fingerprint,
    split_input_lines, validate_url_batch,
)
from core.imaging import IMAGE_EXTENSIONS
import dataclasses

_log = logging.getLogger("reflex.batch_state")

# Số file Drive xử lý mỗi "đợt" trong 1 lượt chạy — hạn chế gọi Drive API
# dồn dập, tránh bị Google tạm khoá quyền truy cập khi paste rất nhiều link.
# Giảm 20→10: mỗi đợt xử lý ít file hơn để đỉnh RAM thấp hơn khi có nhiều
# ảnh nặng cùng lúc (Render free/starter chỉ 512MB). Bù lại bằng nghỉ ngắn
# hơn giữa đợt (3→2s) để tổng thời gian không tăng nhiều.
DRIVE_CHUNK_SIZE = 10
DRIVE_CHUNK_DELAY_S = 2.0


def _build_local_items(pending: list[tuple[str, bytes]]) -> list[TaskItem]:
    """Build lại TaskItem cho local upload TỪ ĐẦU (từ bytes gốc còn giữ trong
    `pending`) — dùng làm items_factory cho _run_all_presets khi chạy nhiều
    preset, vì payload["data"] bị xoá rỗng ngay sau khi ghi file lần đầu."""
    import io
    import zipfile

    items: list[TaskItem] = []
    seen_fps: set[str] = set()
    bid = f"local_{int(time.time() * 1000)}"

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
    return items


def _clone_items(items: list[TaskItem]) -> list[TaskItem]:
    """Nhân bản items cho 1 lượt chạy preset mới — reset status/payload
    riêng (không share dict payload giữa các bản clone) để chạy nhiều
    preset trên cùng 1 tập nguồn (web/drive) không bị ảnh hưởng lẫn nhau
    (vd item bị đánh dấu SKIPPED do trùng fingerprint ở preset trước không
    được lây sang preset sau)."""
    return [
        dataclasses.replace(
            it,
            status=ItemState.QUEUED,
            attempt=0, error_type=ErrorType.NONE, error_message="",
            downloaded_path="", output_paths=[], payload=dict(it.payload),
        )
        for it in items
    ]

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
    selected_preset: str = "TGDD Product 1020x680"   # giữ để tương thích ngược (preset hiển thị mô tả)
    selected_presets: list[str] = ["TGDD Product 1020x680"]   # multi-select — chạy tuần tự từng preset

    # ── custom size (tự thêm preset mới) ──
    custom_name: str = ""
    custom_width: str = ""
    custom_height: str = ""
    custom_mode: str = "letterbox"    # "letterbox" | "crop_1000" | "keep"
    custom_msg: str = ""

    # ── scale % thủ công (giống slider "Scale %" 60-200 ở bản Streamlit cũ) ──
    # Override scale_pct của TẤT CẢ preset đã chọn cho lượt chạy này — dùng
    # khi muốn phóng to/thu nhỏ chủ động thêm ngoài phần auto-upscale trong
    # core/imaging.py. 100 = giữ nguyên như preset gốc.
    run_scale_pct: int = 100


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

    # Danh sách zip/report đã xong trong LƯỢT CHẠY hiện tại (1 dòng / preset
    # hoặc / đợt-chunk drive) — cho phép tải từng file riêng khi chạy multi-preset.
    run_outputs: list[dict] = []

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
        names = [p.name for p in plist]
        if plist and self.selected_preset not in names:
            self.selected_preset = plist[0].name
        # Giữ lại các preset đã chọn còn tồn tại; nếu chọn rỗng, mặc định preset đầu.
        kept = [n for n in self.selected_presets if n in names]
        self.selected_presets = kept or ([plist[0].name] if plist else [])

    def set_active_mode(self, mode: str):
        self.active_mode = mode

    def set_selected_preset(self, name: str):
        """Giữ cho code cũ gọi single-select vẫn chạy — đồng bộ luôn vào multi-select."""
        self.selected_preset = name
        self.selected_presets = [name]

    def toggle_preset_selected(self, name: str):
        """Tick/bỏ tick 1 preset trong danh sách chạy multi-size."""
        if name in self.selected_presets:
            if len(self.selected_presets) == 1:
                return  # luôn giữ ít nhất 1 preset được chọn
            self.selected_presets = [n for n in self.selected_presets if n != name]
        else:
            self.selected_presets = [*self.selected_presets, name]
        if self.selected_presets:
            self.selected_preset = self.selected_presets[0]

    # ── CUSTOM SIZE (tự thêm preset theo nhu cầu) ──────────────
    def set_custom_name(self, v: str):
        self.custom_name = v

    def set_custom_width(self, v: str):
        self.custom_width = v

    def set_custom_height(self, v: str):
        self.custom_height = v

    def set_custom_mode(self, v: str):
        self.custom_mode = v

    def add_custom_preset(self):
        self.custom_msg = ""
        name = (self.custom_name or "").strip()
        try:
            w = int((self.custom_width or "0").strip())
            h = int((self.custom_height or "0").strip())
        except ValueError:
            self.custom_msg = "⚠ Width/Height phải là số nguyên."
            return
        if w <= 0 or h <= 0:
            self.custom_msg = "⚠ Width/Height phải > 0."
            return
        if not name:
            name = f"Custom {w}x{h}"
        existing_names = {p["name"] for p in self.preset_options}
        if name in existing_names:
            name = f"{name} ({w}x{h})"
        preset = Preset(
            name=name,
            sizes=[SizeSpec(w, h, self.custom_mode or "letterbox")],
            quality=92, export_format="JPEG (.jpg)",
            template="{name}_{nn}", is_builtin=False,
            description=f"Preset tự thêm — {w}×{h}.",
        )
        ok = presets_mod.save_user_preset(preset)
        if not ok:
            self.custom_msg = "⚠ Không lưu được preset (kiểm tra quyền ghi file)."
            return
        self.load_presets()
        self.selected_presets = [*self.selected_presets, name] if name not in self.selected_presets else self.selected_presets
        self.selected_preset = name
        self.custom_name = ""
        self.custom_width = ""
        self.custom_height = ""
        self.custom_msg = f"✔ Đã thêm preset “{name}”."

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

    def _selected_preset_objs(self) -> list:
        """Danh sách Preset đã tick — chạy tuần tự, mỗi preset ra 1 zip riêng.
        Áp dụng run_scale_pct (slider Scale % thủ công) đè lên scale_pct gốc
        của từng preset nếu người dùng chỉnh khác 100%."""
        names = self.selected_presets or [self.selected_preset]
        objs = [presets_mod.get(n) for n in names]
        objs = [p for p in objs if p is not None]
        if not objs:
            fallback = self._current_preset_obj()
            objs = [fallback] if fallback else []
        if self.run_scale_pct != 100:
            objs = [dataclasses.replace(p, scale_pct=self.run_scale_pct) for p in objs]
        return objs

    def set_run_scale_pct(self, value: list[float]) -> None:
        v = int(value[0]) if isinstance(value, list) else int(value)
        self.run_scale_pct = max(60, min(200, v))

    def reset_run_scale_pct(self) -> None:
        self.run_scale_pct = 100

    async def _run_all_presets(self, mode: str, items_factory, download_fn):
        """
        Chạy pipeline cho TỪNG preset đã chọn (tuần tự — mỗi preset 1 zip
        riêng), và với mode "drive" thì mỗi preset lại chia nhỏ thành từng
        đợt tối đa DRIVE_CHUNK_SIZE file (nghỉ DRIVE_CHUNK_DELAY_S giây giữa
        các đợt) để giảm rủi ro bị Google chặn khi có quá nhiều link cùng lúc.

        items_factory: callable không tham số, mỗi lần gọi trả về 1 list
        TaskItem MỚI (build lại từ nguồn gốc — cần thiết cho local upload vì
        payload bytes bị xoá sau khi ghi; với web/drive rebuild lại cũng an
        toàn hơn là tái dùng list cũ giữa các preset).
        """
        presets = self._selected_preset_objs()
        async with self:
            self.is_batch_running = True
            self.batch_error_msg = ""
            self.run_outputs = []

        try:
            for p_idx, preset in enumerate(presets):
                items = items_factory()
                if not items:
                    continue
                if mode == "drive" and len(items) > DRIVE_CHUNK_SIZE:
                    chunks = [
                        items[i:i + DRIVE_CHUNK_SIZE]
                        for i in range(0, len(items), DRIVE_CHUNK_SIZE)
                    ]
                else:
                    chunks = [items]

                for c_idx, chunk in enumerate(chunks):
                    async with self:
                        if len(presets) > 1 or len(chunks) > 1:
                            self.batch_current_op = (
                                f"Preset {p_idx + 1}/{len(presets)} ({preset.name}) "
                                + (f"· đợt {c_idx + 1}/{len(chunks)}" if len(chunks) > 1 else "")
                            )
                    BatchManager.start_background(mode, preset, chunk, download_fn)
                    async for _ in self._poll_single_run():
                        yield
                    # Chốt lại kết quả (zip/report) của LƯỢT VỪA XONG trước khi
                    # lượt tiếp theo ghi đè sstate — nếu không sẽ mất đường dẫn.
                    bi = sstate.batch()
                    async with self:
                        self.run_outputs = [
                            *self.run_outputs,
                            {
                                "label": preset.name + (
                                    f" · đợt {c_idx + 1}/{len(chunks)}" if len(chunks) > 1 else ""
                                ),
                                "zip_path": bi.zip_path or "",
                                "report_path": bi.report_path or "",
                                "success": bi.success,
                                "total": bi.total,
                            },
                        ]
                    if c_idx < len(chunks) - 1:
                        await asyncio.sleep(DRIVE_CHUNK_DELAY_S)
        finally:
            async with self:
                self.is_batch_running = False
                sstate.release_batch_lock()
                hist = GLOBAL_SESSION_STATE.get("batch_history", [])
                self.history = list(hist[:10])
                self.batch_current_op = ""
            yield

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
            ok, msg = memory_ok_for_batch()
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

        async for _ in self._run_all_presets("web", lambda: _clone_items(items), _download_image_url):
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
            ok, msg = memory_ok_for_batch()
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

        async for _ in self._run_all_presets("drive", lambda: _clone_items(items), _download_drive_item):
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
            ok, msg = memory_ok_for_batch()
            if not ok:
                sstate.release_batch_lock()
                self.batch_error_msg = msg
                return
            preset = self._current_preset_obj()
            pending = list(self._local_pending)
            self.batch_error_msg = ""
            self.is_batch_running = True

        items = _build_local_items(pending)

        async with self:
            self._local_pending = []
            self.local_upload_names = []
            self.local_upload_ready = False
            if not items:
                sstate.release_batch_lock()
                self.is_batch_running = False
                self.batch_error_msg = "Không tìm thấy ảnh hợp lệ trong file đã upload."
                return

        # Rebuild items TỪ ĐẦU (không clone) cho mỗi preset — payload["data"]
        # bị xoá rỗng sau khi ghi file (_download_upload_item), nên clone thường
        # sẽ không còn bytes để dùng lại ở preset thứ 2 trở đi.
        async for _ in self._run_all_presets(
            "local", lambda: _build_local_items(pending), _download_upload_item
        ):
            yield

    # ── CONTROL ──────────────────────────────────────────────
    def cancel_batch(self):
        BatchManager.request_cancel()

    def cleanup_workspace(self):
        from core.batch import cleanup_old_workspaces
        stats = cleanup_old_workspaces(keep_last=3, max_age_hours=6)
        self.cleanup_msg = f"Đã xoá {stats['deleted']} batch cũ · giải phóng {stats['freed_mb']} MB"

    # ── POLL LOOP (background task → cập nhật UI mỗi 0.8s) ────
    async def _poll_single_run(self):
        """
        Generator dùng trong background event handler — thay thế cho
        `time.sleep(0.8) + st.rerun()` của bản Streamlit gốc.
        BatchManager chạy trong 1 daemon thread riêng (core/batch.py không
        đổi); handler này CHỈ đọc state dùng chung (sstate.batch()/items())
        và đẩy dữ liệu vào Reflex Var để browser tự cập nhật qua websocket.

        CHỈ theo dõi 1 lượt BatchManager.start_background() (1 preset / 1
        đợt-chunk). Việc bật/tắt is_batch_running và ghi lịch sử tổng được
        `_run_all_presets()` quản lý ở tầng ngoài (vì có thể có nhiều lượt
        nối tiếp nhau khi chạy multi-preset).
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

    def download_output_zip(self, idx: int):
        """Tải zip của 1 dòng trong run_outputs (dùng khi chạy multi-preset —
        mỗi preset/đợt có 1 zip riêng, không chỉ cái cuối cùng)."""
        if 0 <= idx < len(self.run_outputs):
            zp = self.run_outputs[idx].get("zip_path", "")
            if zp and Path(zp).exists():
                return rx.download(data=Path(zp).read_bytes(), filename=Path(zp).name)

    def download_output_report(self, idx: int):
        if 0 <= idx < len(self.run_outputs):
            rp = self.run_outputs[idx].get("report_path", "")
            if rp and Path(rp).exists():
                return rx.download(data=Path(rp).read_bytes(), filename=Path(rp).name)
