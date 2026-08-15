"""
core/batch.py — BatchManager v11.0.2 — background thread + pause/resume.

Kiến trúc:
  • start_background()  — spawn 1 daemon thread, return NGAY
                          (main thread rảnh để UI polling)
  • request_pause()     — set pause_evt; worker sleep loop cho tới khi clear
  • request_resume()    — clear pause_evt
  • request_cancel()    — set cancel_evt; worker break, futures chưa chạy bị cancel

Thread-safety:
  • BatchInfo và items list được share qua reference (Python mutable object).
    Main thread và worker thread cùng đọc/ghi cùng 1 object → Streamlit rerun
    trong main thread sẽ thấy state cập nhật.
  • Control signals (Event objects) không dùng session_state — sống trong
    module-level dict `_CONTROL` với `_CONTROL_LOCK`. Session_state là
    thread-local trong Streamlit nên KHÔNG dùng được từ worker.
  • Việc mutate int/str field trên BatchInfo là atomic nhờ Python GIL.
    List operations (`.append`, `del [:-n]`) không atomic hoàn toàn nhưng
    chỉ dùng cho log tail → race chỉ gây hiển thị lệch, không data corruption.

UI polling:
  • `is_thread_alive(batch_id)` cho UI biết worker còn chạy.
  • Main thread `time.sleep(0.8) + st.rerun()` để tự refresh UI khi active.
"""
from __future__ import annotations

import concurrent.futures as futures
import gc
import logging
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import streamlit as st

from . import state as sstate
from . import memory
from .archive import make_zip_stream
from .imaging import (
    EXPORT_FORMATS, apply_size, probe_meta, is_real_image_file,
    build_preview_thumb,
)
from .naming import render as render_name, unique_path
from .report import write_csv, write_json_summary
from .types import (
    BatchInfo, BatchState, ErrorType, ItemState, NON_RETRYABLE_ERRORS,
    Preset, TaskItem, new_id,
)


_log = logging.getLogger("core.batch")


# ══════════════════════════════════════════════════════════════
# WORKSPACE
# ══════════════════════════════════════════════════════════════
BATCH_ROOT = Path.home() / ".tmp" / "media_tool_pro_v11"


@dataclass
class Workspace:
    batch_id: str
    root: Path
    raw: Path
    final: Path
    preview: Path
    meta: Path


def create_workspace(mode: str) -> Workspace:
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    bid = f"{mode}_{int(time.time()*1000)}_{new_id('b').split('_')[1]}"
    root = BATCH_ROOT / bid
    ws = Workspace(
        batch_id=bid,
        root=root,
        raw=root / "raw",
        final=root / "final",
        preview=root / "preview",
        meta=root / "meta",
    )
    for d in (ws.raw, ws.final, ws.preview, ws.meta):
        d.mkdir(parents=True, exist_ok=True)
    return ws


def cleanup_old_workspaces(keep_last: int = 5, max_age_hours: int = 6) -> dict:
    if not BATCH_ROOT.exists():
        return {"deleted": 0, "freed_mb": 0, "kept": 0}
    all_ws = sorted(
        [d for d in BATCH_ROOT.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime, reverse=True,
    )
    active_root = ""
    try:
        bi = st.session_state.get("batch_info")
        if bi is not None:
            active_root = getattr(bi, "workspace_root", "")
    except Exception:
        pass

    now = time.time()
    max_age = max_age_hours * 3600
    deleted, freed, kept = 0, 0, 0

    for idx, ws in enumerate(all_ws):
        if str(ws) == active_root:
            kept += 1
            continue
        age = now - ws.stat().st_mtime
        if age > max_age or idx >= keep_last:
            try:
                size = sum(f.stat().st_size for f in ws.rglob("*") if f.is_file())
                shutil.rmtree(ws, ignore_errors=True)
                deleted += 1
                freed += size
            except Exception:
                pass
        else:
            kept += 1

    return {"deleted": deleted, "freed_mb": round(freed / (1024 * 1024), 1), "kept": kept}


# ══════════════════════════════════════════════════════════════
# ADAPTER PROTOCOL
# ══════════════════════════════════════════════════════════════
@dataclass
class DownloadResult:
    ok: bool
    local_path: Optional[Path] = None
    error_type: ErrorType = ErrorType.NONE
    error_message: str = ""


DownloadFn = Callable[[TaskItem, Workspace], DownloadResult]


# ══════════════════════════════════════════════════════════════
# MODULE-LEVEL CONTROL REGISTRY (thread-safe)
# ══════════════════════════════════════════════════════════════
_CONTROL: dict[str, dict] = {}   # {batch_id: {"pause": Event, "cancel": Event, "thread": Thread}}
_CONTROL_LOCK = threading.Lock()


def _register_control(batch_id: str, pause_evt, cancel_evt, thread) -> None:
    with _CONTROL_LOCK:
        _CONTROL[batch_id] = {
            "pause": pause_evt, "cancel": cancel_evt, "thread": thread,
        }


def _get_control(batch_id: str) -> Optional[dict]:
    with _CONTROL_LOCK:
        return _CONTROL.get(batch_id)


def _unregister_control(batch_id: str) -> None:
    with _CONTROL_LOCK:
        _CONTROL.pop(batch_id, None)


def is_thread_alive(batch_id: str) -> bool:
    """Có thread worker đang chạy cho batch_id không."""
    ctrl = _get_control(batch_id)
    if not ctrl:
        return False
    t = ctrl.get("thread")
    return bool(t and t.is_alive())


# ══════════════════════════════════════════════════════════════
# BATCH MANAGER
# ══════════════════════════════════════════════════════════════
class BatchManager:

    # ── START (background thread) ────────────────────────────
    @staticmethod
    def start_background(
        mode: str,
        preset: Preset,
        items: list[TaskItem],
        download_fn: DownloadFn,
    ) -> Workspace:
        """
        Spawn 1 daemon thread chạy pipeline. Return NGAY để main thread render UI.
        """
        ws = create_workspace(mode)

        bi = BatchInfo(
            batch_id=ws.batch_id,
            state=BatchState.PREPARING,
            source_mode=mode,
            preset_name=preset.name,
            workspace_root=str(ws.root),
            final_dir=str(ws.final),
            total=len(items),
            queued=len(items),
            started_at=time.time(),
        )
        # Share references vào session_state — worker thread giữ chính object này
        sstate.set_batch(bi)
        sstate.set_items(items)

        # Control events
        pause_evt = threading.Event()
        cancel_evt = threading.Event()

        thread = threading.Thread(
            target=BatchManager._bg_pipeline,
            args=(ws, preset, items, download_fn, bi, pause_evt, cancel_evt),
            daemon=True,
            name=f"batch-{ws.batch_id[-8:]}",
        )
        _register_control(ws.batch_id, pause_evt, cancel_evt, thread)
        thread.start()
        return ws

    # ── LEGACY blocking start (giữ để backward compat) ──────
    @staticmethod
    def start(
        mode: str,
        preset: Preset,
        items: list[TaskItem],
        download_fn: DownloadFn,
    ) -> Workspace:
        """
        Blocking start — chạy toàn bộ pipeline trong caller thread.
        Trước là API chính, v11.0.2 chuyển sang alias của start_background()
        + join để giữ behavior blocking.
        """
        ws = BatchManager.start_background(mode, preset, items, download_fn)
        ctrl = _get_control(ws.batch_id)
        if ctrl and ctrl["thread"]:
            ctrl["thread"].join(timeout=3600)  # tối đa 1 giờ
        return ws

    # ── BACKGROUND PIPELINE ─────────────────────────────────
    @staticmethod
    def _bg_pipeline(ws, preset, items, download_fn, bi, pause_evt, cancel_evt) -> None:
        """Chạy trong worker thread. KHÔNG gọi st.* hoặc sstate.* trực tiếp."""
        try:
            _bg_log(bi, f"▶ Bắt đầu batch {ws.batch_id} · {len(items)} items")
            bi.state = BatchState.RUNNING

            # Dedup fingerprint
            seen: set[str] = set()
            for it in items:
                if it.fingerprint and it.fingerprint in seen:
                    it.status = ItemState.SKIPPED
                    it.error_message = "Trùng với item khác — bỏ qua"
                elif it.fingerprint:
                    seen.add(it.fingerprint)

            active_items = [it for it in items if it.status != ItemState.SKIPPED]

            n_workers = memory.suggest_resize_workers()
            _log.info("Batch %s: workers=%d, items=%d/%d",
                      ws.batch_id, n_workers, len(active_items), len(items))

            with futures.ThreadPoolExecutor(
                max_workers=n_workers, thread_name_prefix="batch-worker",
            ) as pool:
                fut_map = {
                    pool.submit(
                        BatchManager._process_item_ctrl,
                        it, ws, preset, download_fn, pause_evt, cancel_evt,
                    ): it for it in active_items
                }
                done_counter = 0
                for fut in futures.as_completed(fut_map):
                    if cancel_evt.is_set():
                        _bg_log(bi, "🚫 Nhận yêu cầu huỷ — dừng batch")
                        for f in fut_map:
                            if not f.done() and not f.running():
                                f.cancel()
                        # Đánh dấu các item chưa chạy là CANCELLED
                        for f, it in fut_map.items():
                            if it.status in (ItemState.QUEUED, ItemState.RUNNING) and f.cancelled():
                                it.status = ItemState.CANCELLED
                                it.error_type = ErrorType.CANCELLED
                        break

                    try:
                        fut.result(timeout=180)
                    except futures.TimeoutError:
                        it = fut_map[fut]
                        it.status = ItemState.FAILED
                        it.error_type = ErrorType.DOWNLOAD_TIMEOUT
                        it.error_message = "Item timeout sau 180s"
                    except Exception as exc:
                        it = fut_map[fut]
                        it.status = ItemState.FAILED
                        it.error_type = ErrorType.UNKNOWN
                        it.error_message = str(exc)[:200]

                    done_counter += 1
                    _bg_refresh_counters(bi, items)
                    # GC dày hơn khi RAM đang căng (container nhỏ như Render
                    # free 512MB) để tránh tích luỹ rác giữa các item, gây
                    # OOM-kill làm mất cả batch đang chạy.
                    gc_every = 3 if memory.memory_pressure_high() else 8
                    if done_counter % gc_every == 0:
                        gc.collect()

            _bg_refresh_counters(bi, items)

        except Exception as exc:
            _log.exception("Background pipeline crashed")
            bi.state = BatchState.FAILED
            bi.warnings.append(f"Pipeline crash: {str(exc)[:200]}")

        finally:
            BatchManager._bg_finalize(ws, preset, bi, items, cancel_evt)
            _unregister_control(ws.batch_id)

    # ── PROCESS 1 ITEM ──────────────────────────────────────
    @staticmethod
    def _process_item_ctrl(
        item: TaskItem, ws: Workspace, preset: Preset, download_fn: DownloadFn,
        pause_evt: threading.Event, cancel_evt: threading.Event,
    ) -> None:
        """
        Xử lý 1 item với pause/cancel checkpoints.
        Pause chỉ chặn ở đầu mỗi item và giữa các stage — KHÔNG chặn giữa
        download stream hay resize giữa chừng (blocking I/O đã bắt đầu).
        """
        # Checkpoint 0: chờ nếu đang pause
        BatchManager._wait_if_paused(pause_evt, cancel_evt)
        if cancel_evt.is_set():
            item.status = ItemState.CANCELLED
            item.error_type = ErrorType.CANCELLED
            item.error_message = "Huỷ trước khi xử lý"
            return

        item.started_at = time.time()
        item.status = ItemState.RUNNING

        try:
            local_path: Optional[Path] = None

            # Retry loop
            for attempt in range(1, item.max_attempts + 1):
                if cancel_evt.is_set():
                    item.status = ItemState.CANCELLED
                    item.error_type = ErrorType.CANCELLED
                    return
                BatchManager._wait_if_paused(pause_evt, cancel_evt)
                if cancel_evt.is_set():
                    item.status = ItemState.CANCELLED
                    item.error_type = ErrorType.CANCELLED
                    return

                item.attempt = attempt
                if attempt > 1:
                    item.status = ItemState.RETRYING
                    backoff = 1.0 + 2.5 * (attempt - 1)
                    # Sleep có thể bị cancel/pause interrupt
                    slept = 0.0
                    step = 0.25
                    while slept < min(backoff, 6.0):
                        if cancel_evt.is_set():
                            item.status = ItemState.CANCELLED
                            item.error_type = ErrorType.CANCELLED
                            return
                        time.sleep(step)
                        slept += step

                res: DownloadResult = download_fn(item, ws)
                if res.ok and res.local_path and res.local_path.exists():
                    local_path = res.local_path
                    break
                if res.error_type in NON_RETRYABLE_ERRORS:
                    item.status = ItemState.FAILED
                    item.error_type = res.error_type
                    item.error_message = res.error_message
                    return
                item.error_type = res.error_type or ErrorType.DOWNLOAD_FAILED
                item.error_message = res.error_message

            if not local_path:
                item.status = ItemState.FAILED
                if item.error_type == ErrorType.NONE:
                    item.error_type = ErrorType.DOWNLOAD_FAILED
                return

            # Verify image
            if not is_real_image_file(local_path):
                item.status = ItemState.FAILED
                item.error_type = ErrorType.INVALID_IMAGE
                item.error_message = "File tải về không phải ảnh"
                return

            meta = probe_meta(local_path)
            item.source_width = meta.get("width", 0)
            item.source_height = meta.get("height", 0)
            item.source_size_bytes = meta.get("size_bytes", 0)
            item.downloaded_path = str(local_path)

            # Preview thumb (cho Studio)
            build_preview_thumb(local_path, ws.preview)

            # Checkpoint: pause có thể xảy ra giữa download và resize
            BatchManager._wait_if_paused(pause_evt, cancel_evt)
            if cancel_evt.is_set():
                item.status = ItemState.CANCELLED
                item.error_type = ErrorType.CANCELLED
                return

            # Resize N kích thước
            outputs: list[str] = []
            info = EXPORT_FORMATS.get(preset.export_format, EXPORT_FORMATS["JPEG (.jpg)"])
            ext = info["ext"]
            is_multi = len(preset.sizes) > 1

            for size in preset.sizes:
                if cancel_evt.is_set():
                    for op in outputs:
                        try: Path(op).unlink(missing_ok=True)
                        except Exception: pass
                    item.status = ItemState.CANCELLED
                    item.error_type = ErrorType.CANCELLED
                    return

                base_name = render_name(
                    preset.template,
                    name=item.display_name or Path(local_path).stem,
                    original=Path(local_path).stem,
                    color=item.group_name,
                    index=1,
                    width=size.width, height=size.height,
                    fmt=ext.lstrip("."),
                )
                if is_multi:
                    out_dir = ws.final / size.label() / (item.group_name or "default")
                else:
                    out_dir = ws.final / (item.group_name or "default")

                out_path = unique_path(out_dir, base_name, ext)
                ok, err, msg = apply_size(
                    local_path, out_path, size,
                    quality=preset.quality,
                    export_format=preset.export_format,
                    scale_pct=preset.scale_pct,
                    no_upscale=preset.no_upscale,
                    huge_mode=True,
                )
                if ok:
                    outputs.append(str(out_path))
                else:
                    item.status = ItemState.FAILED
                    item.error_type = err or ErrorType.RESIZE_FAILED
                    item.error_message = msg
                    for op in outputs:
                        try: Path(op).unlink(missing_ok=True)
                        except Exception: pass
                    return

            item.output_paths = outputs
            item.status = ItemState.SUCCESS
            item.error_type = ErrorType.NONE
            item.error_message = ""

        finally:
            item.completed_at = time.time()
            item.duration = max(0.0, item.completed_at - item.started_at)

    @staticmethod
    def _wait_if_paused(pause_evt: threading.Event, cancel_evt: threading.Event) -> None:
        """Sleep loop chờ pause được clear. Break nếu cancel."""
        while pause_evt.is_set():
            if cancel_evt.is_set():
                return
            time.sleep(0.3)

    # ── FINALIZE (background) ───────────────────────────────
    @staticmethod
    def _bg_finalize(ws, preset, bi, items, cancel_evt) -> None:
        """Sinh ZIP + CSV + JSON summary. Chạy trong worker thread."""
        # ZIP toàn bộ final/
        try:
            zip_path = ws.root / f"{ws.batch_id}.zip"
            make_zip_stream(ws.final, zip_path, compresslevel=preset.zip_compression)
            bi.zip_path = str(zip_path)
        except Exception as exc:
            _log.warning("ZIP failed: %s", exc)
            bi.warnings.append(f"ZIP lỗi: {str(exc)[:120]}")

        # Report CSV
        try:
            csv_path = ws.meta / "report.csv"
            write_csv(items, csv_path)
            bi.report_path = str(csv_path)
        except Exception as exc:
            _log.warning("Report CSV failed: %s", exc)

        # Summary JSON
        try:
            write_json_summary(bi, items, ws.meta / "summary.json")
        except Exception:
            pass

        bi.completed_at = time.time()
        if cancel_evt.is_set() or bi.state == BatchState.CANCELLING:
            bi.state = BatchState.DONE  # partial done
            _bg_log(bi, f"⏹ Đã dừng · thành công {bi.success}/{bi.total}")
        elif bi.state != BatchState.FAILED:
            bi.state = BatchState.DONE
            _bg_log(bi, f"✔ Xong {bi.success}/{bi.total} · "
                        f"fail {bi.failed} · {bi.duration:.1f}s")

        # Release lock — main thread có thể start batch mới
        sstate.release_batch_lock()

        # Ghi lịch sử
        sstate.push_history({
            "batch_id": bi.batch_id,
            "mode": bi.source_mode,
            "preset": bi.preset_name,
            "total": bi.total,
            "success": bi.success,
            "failed": bi.failed,
            "duration": round(bi.duration, 1),
            "at": time.strftime("%H:%M:%S"),
        })

    # ── CONTROL API ─────────────────────────────────────────
    @staticmethod
    def request_pause() -> None:
        """Set pause. Batch chuyển PAUSED. Worker sẽ block ở checkpoint kế tiếp."""
        bi = sstate.batch()
        ctrl = _get_control(bi.batch_id)
        if not ctrl:
            return
        if bi.state == BatchState.RUNNING:
            ctrl["pause"].set()
            bi.state = BatchState.PAUSED
            _bg_log(bi, "⏸ Pause requested")

    @staticmethod
    def request_resume() -> None:
        bi = sstate.batch()
        ctrl = _get_control(bi.batch_id)
        if not ctrl:
            return
        if bi.state == BatchState.PAUSED:
            ctrl["pause"].clear()
            bi.state = BatchState.RUNNING
            _bg_log(bi, "▶ Resume")

    @staticmethod
    def request_cancel() -> None:
        bi = sstate.batch()
        ctrl = _get_control(bi.batch_id)
        if not ctrl:
            # Không có worker → có thể batch đã xong hoặc chưa start
            if bi.state in (BatchState.RUNNING, BatchState.PREPARING,
                            BatchState.PAUSED):
                bi.state = BatchState.CANCELLING
            return
        if bi.state in (BatchState.RUNNING, BatchState.PREPARING,
                        BatchState.PAUSED):
            ctrl["cancel"].set()
            ctrl["pause"].clear()  # unblock worker khỏi pause loop
            bi.state = BatchState.CANCELLING
            _bg_log(bi, "⏹ Cancel requested")

    @staticmethod
    def get_failed_items() -> list[TaskItem]:
        return [it for it in sstate.items() if it.status == ItemState.FAILED]


# ══════════════════════════════════════════════════════════════
# BACKGROUND-SAFE HELPERS
# ══════════════════════════════════════════════════════════════
_STATE_TO_COUNTER = {
    ItemState.QUEUED:    "queued",
    ItemState.RUNNING:   "running",
    ItemState.SUCCESS:   "success",
    ItemState.FAILED:    "failed",
    ItemState.RETRYING:  "retrying",
    ItemState.CANCELLED: "cancelled",
    ItemState.SKIPPED:   "skipped",
}


def _bg_refresh_counters(bi: BatchInfo, items: list[TaskItem]) -> None:
    """Cập nhật counter — không dùng session_state (an toàn với worker thread)."""
    counters = {v: 0 for v in _STATE_TO_COUNTER.values()}
    current_name = ""
    current_op = ""
    for it in items:
        counters[_STATE_TO_COUNTER.get(it.status, "queued")] += 1
        if it.status == ItemState.RUNNING and not current_name:
            current_name = it.display_name or it.source[:60]
            current_op = f"attempt {it.attempt}"
    for k, v in counters.items():
        setattr(bi, k, v)
    bi.current_item_name = current_name
    bi.current_operation = current_op


def _bg_log(bi: BatchInfo, line: str) -> None:
    """Append log an toàn — không dùng session_state."""
    try:
        bi.log_tail.append(line)
        # Trim
        if len(bi.log_tail) > 40:
            del bi.log_tail[:-40]
    except Exception:
        pass
