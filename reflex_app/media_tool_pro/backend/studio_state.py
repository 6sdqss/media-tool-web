"""
studio_state.py — Studio (image-adjust) — port đầy đủ tính năng từ
mode_adjust.py (824 dòng, Streamlit) sang Reflex.

Nguồn dữ liệu: batch vừa chạy xong (core.batch.BatchManager, qua
core.state / core.presets — KHÔNG đổi). mode_adjust.py bản gốc đọc
`st.session_state["last_batch_manifest"/"last_batch_cfg"/"last_batch_meta"]`
— các key này thuộc 1 schema TaskItem cũ hơn (dict phẳng: folder_name,
seq_in_folder, product, color...) không còn được core/batch.py v11 tạo ra
nữa (core/batch.py hiện dùng dataclass TaskItem với group_name/output_paths/
source_width/height/size_bytes — xem core/types.py). Vì vậy Studio ở đây
build "manifest" tương đương trực tiếp từ `core.state.items()` +
`core.state.batch()` + preset đã dùng cho batch đó (core.presets.get),
thay vì đọc lại field không tồn tại — đây là cách duy nhất để tính năng
thực sự hoạt động với engine batch hiện tại của repo, đồng thời vẫn
KHÔNG đổi core/*, utils.py, mode_adjust.py.

Toàn bộ pixel-processing dùng lại utils.py (compat shim, KHÔNG sửa):
  - estimate_default_scale_for_size, build_live_preview_b64,
    resize_to_multi_sizes, merge_final_with_adjusted, make_zip,
    open_zip_for_download, readable_file_size, get_size_label,
    apply_name_template, add_to_history.

Tính năng đã port so với bản Streamlit gốc:
  • Nạp batch gần nhất (manifest + cfg + meta) — tương đương phần đọc
    session_state["last_batch_*"] trong render_adjustment_studio().
  • Bulk ops: chọn tất cả / bỏ chọn tất cả / chọn ảnh nhỏ / xoá chọn,
    áp dụng scale/x/y hàng loạt cho trang hiện tại hoặc toàn bộ filter.
  • Per-item: slider Scale/X/Y, nút Reset / -5% / +5%, checkbox chọn,
    trạng thái pill (Chưa render / Đã render / Đã chỉnh), cảnh báo ảnh nhỏ.
  • Bộ lọc: từ khoá, sản phẩm, trạng thái chọn/ảnh nhỏ.
  • Pagination (6/10/16/24 mỗi trang) với first/prev/page-input/next/last.
  • Render hàng loạt ảnh đã chọn (background event handler — polling
    progress, giống batch_state._poll_loop) dùng resize_to_multi_sizes
    với scale% RIÊNG của từng ảnh (khác _run_render gốc — xem NOTE bên dưới).
  • Export ZIP gộp (final + adjusted, ưu tiên adjusted) qua
    merge_final_with_adjusted + make_zip; tải ZIP gốc / ZIP gộp.
  • KPI batch (render_batch_kpis).

NOTE (khác biệt có chủ đích so với gọi hàm y hệt mode_adjust.py):
  1. mode_adjust.py gọi `resize_to_multi_sizes(src, adj_root,
     item["folder_name"], es, sizes, ...)` — 5 vị trí, nhưng hàm thật
     trong utils.py chỉ nhận 4 (source_path, out_dir, base_name, sizes) —
     gọi y nguyên sẽ luôn TypeError. Code dưới đây gọi hàm này ĐÚNG chữ
     ký thật của nó (không thêm/sửa gì trong utils.py).
  2. mode_adjust.py gọi `estimate_default_scale_for_size(source_width,
     source_height, tw, th)` (4 số) nhưng chữ ký thật trong utils.py là
     `estimate_default_scale_for_size(source_path, target_w, target_h,
     default=100)` (nhận đường dẫn file, mở ảnh bằng PIL). Code dưới gọi
     đúng chữ ký thật (truyền source_path).
  3. `resize_to_multi_sizes` không có khái niệm "group/folder" lồng
     trong out_dir (chỉ out_dir/size_label/name.ext) trong khi cây
     `final/` thật của core/batch.py là final/size_label/group/name.ext
     (đa size) hay final/group/name.ext (1 size). Để `merge_final_with_
     adjusted` (so khớp theo path tương đối) hoạt động đúng, sau khi
     `resize_to_multi_sizes` xuất file (dùng lại 100% pixel-engine của
     nó), ta di chuyển file kết quả vào đúng vị trí lồng theo cấu trúc
     của final/ — không tự viết lại phép resize.
  4. Offset X/Y (pan ảnh trong khung) trong bản gốc CHỈ là hiệu ứng
     CSS transform cho live-preview — `core.imaging.apply_size` /
     `resize_letterbox` không có tham số pan pixel nào, nên bản gốc
     (dù gọi đúng chữ ký) cũng không áp dụng offset vào ảnh export
     thật. Reflex Studio giữ đúng hành vi này (offset chỉ ảnh hưởng
     preview trực tiếp trên trình duyệt), không giả vờ hỗ trợ pan thật.
"""
from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Optional

import reflex as rx

from . import st_compat  # noqa: F401 — đăng ký shim streamlit trước

from core import presets as presets_mod
from core import state as sstate
from core.types import BatchState as CoreBatchState, ItemState
from core.validation import clean_name

from utils import (
    EXPORT_FORMATS,
    add_to_history,
    apply_name_template,
    build_live_preview_b64,
    estimate_default_scale_for_size,
    get_size_label,
    make_zip,
    merge_final_with_adjusted,
    open_zip_for_download,
    readable_file_size,
    resize_to_multi_sizes,
)

_SMALL_THR = 600
_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_PER_PAGE_OPTIONS = [6, 10, 16, 24]


def _is_small(it: dict) -> bool:
    w, h = int(it.get("source_width", 0)), int(it.get("source_height", 0))
    return (0 < w < _SMALL_THR) or (0 < h < _SMALL_THR)


class StudioState(rx.State):
    # ── batch data (nạp từ core.state) ──────────────────────────
    manifest: list[dict] = []
    meta: dict = {}
    cfg_sizes: list[list] = []          # [[w, h, mode], ...]
    cfg_default_scale_pct: int = 100
    cfg_quality: int = 92
    cfg_export_format: str = "JPEG (.jpg)"
    cfg_template: str = "{name}_{nn}"
    cfg_zip_compression: int = 6
    canvas_w: int = 1020
    canvas_h: int = 680

    loaded: bool = False
    error_msg: str = ""

    # ── filters & pagination ─────────────────────────────────────
    search_kw: str = ""
    filter_product: str = "Tất cả"
    filter_status: str = "Tất cả"
    per_page: int = 10
    page: int = 1

    # ── bulk controls ────────────────────────────────────────────
    bulk_scale: int = 100
    bulk_x: int = 0
    bulk_y: int = 0

    # ── render/export ────────────────────────────────────────────
    is_rendering: bool = False
    render_progress_pct: int = 0
    render_current_name: str = ""
    render_errors: list[str] = []
    render_done_msg: str = ""

    is_exporting: bool = False
    export_msg: str = ""
    zip_orig_path: str = ""
    zip_orig_size: str = ""
    zip_merged_path: str = ""
    zip_merged_size: str = ""

    _adjusted_root: str = ""

    # ══════════════════════════════════════════════════════════
    # LOAD BATCH
    # ══════════════════════════════════════════════════════════
    def load_from_last_batch(self):
        """Tương đương phần đọc last_batch_manifest/cfg/meta ở đầu
        render_adjustment_studio() trong mode_adjust.py gốc — nhưng lấy
        trực tiếp từ core.state (nguồn thật của batch v11)."""
        self.error_msg = ""
        bi = sstate.batch()
        items = sstate.items()

        if not items or bi.state not in (CoreBatchState.DONE, CoreBatchState.FAILED):
            if not items:
                self.error_msg = "⚠️ Chưa có batch. Chạy tab Web / Drive / Local trước."
                return
            # batch có nhưng chưa xong — vẫn cho xem những item SUCCESS đã có
        preset = presets_mod.get(bi.preset_name)
        if preset is None:
            plist = presets_mod.load_all()
            preset = plist[0] if plist else None

        sizes = [list(s.as_tuple()) for s in (preset.sizes if preset else [])]
        self.cfg_sizes = sizes
        self.cfg_default_scale_pct = int(preset.scale_pct) if preset else 100
        self.cfg_quality = int(preset.quality) if preset else 92
        self.cfg_export_format = preset.export_format if preset else "JPEG (.jpg)"
        self.cfg_template = preset.template if preset else "{name}_{nn}"
        self.cfg_zip_compression = int(preset.zip_compression) if preset else 6

        tw, th = 1020, 680
        if sizes:
            w, h, _m = sizes[0]
            if w and h:
                tw, th = int(w), int(h)
        self.canvas_w, self.canvas_h = tw, th

        manifest: list[dict] = []
        for it in items:
            if it.status != ItemState.SUCCESS or not it.output_paths:
                continue
            src = it.downloaded_path or it.source
            group = it.group_name or "default"
            if "/" in group:
                product, color = group.split("/", 1)
            else:
                product, color = group, ""
            default_scale = int(self.cfg_default_scale_pct)
            sug = estimate_default_scale_for_size(src, tw, th, default_scale) if src else default_scale
            scale = max(default_scale, sug) if (
                0 < it.source_width < _SMALL_THR or 0 < it.source_height < _SMALL_THR
            ) else default_scale
            manifest.append({
                "id": it.item_id,
                "folder_name": group,
                "product": product,
                "color": color,
                "original_name": it.display_name or Path(src).name,
                "source_path": src,
                "source_width": int(it.source_width),
                "source_height": int(it.source_height),
                "source_size_bytes": int(it.source_size_bytes),
                "output_paths": list(it.output_paths),
                "default_scale_pct": default_scale,
                "scale": int(scale),
                "offset_x": 0,
                "offset_y": 0,
                "selected": bool(_is_small({"source_width": it.source_width, "source_height": it.source_height})),
                "status": "rendered",
                "adjusted_path": "",
            })
            if len(manifest) >= 500:
                break

        self.manifest = manifest
        self.meta = {
            "batch_id": bi.batch_id,
            "root": bi.workspace_root,
            "final_dir": bi.final_dir,
            "zip_path": bi.zip_path,
            "total": bi.total,
            "success": bi.success,
            "failed": bi.failed,
            "duration": round(bi.duration, 1),
        }
        self.zip_orig_path = bi.zip_path or ""
        self._adjusted_root = str(Path(bi.workspace_root) / "ADJUSTED") if bi.workspace_root else ""
        self.page = 1
        self.loaded = True
        if not manifest:
            self.error_msg = "⚠️ Batch chưa có ảnh nào xử lý thành công để chỉnh."

    # ══════════════════════════════════════════════════════════
    # COMPUTED — filter / pagination
    # ══════════════════════════════════════════════════════════
    @rx.var
    def product_names(self) -> list[str]:
        names = sorted({it["product"] for it in self.manifest if it.get("product")})
        return ["Tất cả", *names]

    @rx.var
    def total_count(self) -> int:
        return len(self.manifest)

    @rx.var
    def selected_count(self) -> int:
        return sum(1 for it in self.manifest if it.get("selected"))

    @rx.var
    def small_count(self) -> int:
        return sum(1 for it in self.manifest if _is_small(it))

    @rx.var
    def filtered(self) -> list[dict]:
        kw = (self.search_kw or "").strip().lower()
        out = []
        for it in self.manifest:
            if self.filter_product != "Tất cả" and it.get("product") != self.filter_product:
                continue
            if kw:
                hay = " ".join([
                    it.get("product", ""), it.get("color", ""),
                    it.get("original_name", ""), it.get("folder_name", ""),
                ]).lower()
                if kw not in hay:
                    continue
            sel = bool(it.get("selected"))
            if self.filter_status == "Chỉ ảnh đã chọn sửa" and not sel:
                continue
            if self.filter_status == "Chỉ ảnh chưa chọn" and sel:
                continue
            if self.filter_status == "Chỉ ảnh nhỏ (bị giãn)" and not _is_small(it):
                continue
            out.append(it)
        return out

    @rx.var
    def filtered_count(self) -> int:
        return len(self.filtered)

    @rx.var
    def total_pages(self) -> int:
        n = len(self.filtered)
        pp = max(1, int(self.per_page))
        return max((n - 1) // pp + 1, 1)

    @rx.var
    def page_items(self) -> list[dict]:
        pp = max(1, int(self.per_page))
        cur = max(1, min(self.page, self.total_pages))
        s = (cur - 1) * pp
        page = self.filtered[s:s + pp]
        out = []
        for it in page:
            preview_src = it.get("adjusted_path") or (
                it["output_paths"][0] if it.get("output_paths") else ""
            ) or it.get("source_path", "")
            b64 = build_live_preview_b64(preview_src, max_size=420) if preview_src else ""
            out.append({**it, "preview_b64": b64, "is_small": _is_small(it)})
        return out

    # ══════════════════════════════════════════════════════════
    # FILTER / PAGE EVENTS
    # ══════════════════════════════════════════════════════════
    def set_search_kw(self, v: str):
        self.search_kw = v
        self.page = 1

    def set_filter_product(self, v: str):
        self.filter_product = v
        self.page = 1

    def set_filter_status(self, v: str):
        self.filter_status = v
        self.page = 1

    def set_per_page(self, v: str):
        self.per_page = int(v)
        self.page = 1

    def go_first_page(self):
        self.page = 1

    def go_prev_page(self):
        self.page = max(1, self.page - 1)

    def go_next_page(self):
        self.page = min(self.total_pages, self.page + 1)

    def go_last_page(self):
        self.page = self.total_pages

    def set_page_input(self, v: str):
        try:
            n = int(v)
        except ValueError:
            return
        self.page = max(1, min(n, self.total_pages))

    # ══════════════════════════════════════════════════════════
    # PER-ITEM EVENTS
    # ══════════════════════════════════════════════════════════
    def _mutate_item(self, item_id: str, **fields):
        new_manifest = []
        for it in self.manifest:
            if it["id"] == item_id:
                it = {**it, **fields}
            new_manifest.append(it)
        self.manifest = new_manifest

    def toggle_select(self, item_id: str):
        for it in self.manifest:
            if it["id"] == item_id:
                self._mutate_item(item_id, selected=not it.get("selected", False))
                return

    def set_item_scale(self, item_id: str, v: list[float]):
        self._mutate_item(item_id, scale=int(v[0]), selected=True)

    def set_item_x(self, item_id: str, v: list[float]):
        self._mutate_item(item_id, offset_x=int(v[0]), selected=True)

    def set_item_y(self, item_id: str, v: list[float]):
        self._mutate_item(item_id, offset_y=int(v[0]), selected=True)

    def reset_item(self, item_id: str):
        for it in self.manifest:
            if it["id"] == item_id:
                d = int(it.get("default_scale_pct", self.cfg_default_scale_pct))
                self._mutate_item(item_id, scale=d, offset_x=0, offset_y=0, selected=True)
                return

    def nudge_item(self, item_id: str, delta: int):
        for it in self.manifest:
            if it["id"] == item_id:
                new_scale = max(60, min(200, int(it.get("scale", 100)) + delta))
                self._mutate_item(item_id, scale=new_scale, selected=True)
                return

    # ══════════════════════════════════════════════════════════
    # BULK OPS
    # ══════════════════════════════════════════════════════════
    def select_all_filtered(self):
        ids = {it["id"] for it in self.filtered}
        self.manifest = [
            {**it, "selected": True} if it["id"] in ids else it for it in self.manifest
        ]

    def deselect_all_filtered(self):
        ids = {it["id"] for it in self.filtered}
        self.manifest = [
            {**it, "selected": False} if it["id"] in ids else it for it in self.manifest
        ]

    def select_all_small(self):
        self.manifest = [
            {**it, "selected": True} if _is_small(it) else it for it in self.manifest
        ]

    def clear_all_selection(self):
        self.manifest = [{**it, "selected": False} for it in self.manifest]

    def set_bulk_scale(self, v: list[float]):
        self.bulk_scale = int(v[0])

    def set_bulk_x(self, v: list[float]):
        self.bulk_x = int(v[0])

    def set_bulk_y(self, v: list[float]):
        self.bulk_y = int(v[0])

    def apply_bulk_current_page(self):
        ids = {it["id"] for it in self.page_items}
        self.manifest = [
            {**it, "scale": self.bulk_scale, "offset_x": self.bulk_x,
             "offset_y": self.bulk_y, "selected": True}
            if it["id"] in ids else it
            for it in self.manifest
        ]

    def apply_bulk_all_filtered(self):
        ids = {it["id"] for it in self.filtered}
        self.manifest = [
            {**it, "scale": self.bulk_scale, "offset_x": self.bulk_x,
             "offset_y": self.bulk_y, "selected": True}
            if it["id"] in ids else it
            for it in self.manifest
        ]

    # ══════════════════════════════════════════════════════════
    # RENDER (per-item scale) — background, giống _run_render gốc
    # ══════════════════════════════════════════════════════════
    @rx.event(background=True)
    async def render_selected(self):
        async with self:
            if self.is_rendering:
                return
            sel_items = [dict(it) for it in self.manifest if it.get("selected")]
            if not sel_items:
                self.error_msg = "⚠️ Chưa chọn ảnh nào để render."
                return
            root = self.meta.get("root", "")
            if not root or not Path(root).exists():
                self.error_msg = "❌ Workspace batch đã bị xoá (container reset). Vui lòng chạy lại batch."
                return
            self.is_rendering = True
            self.render_progress_pct = 0
            self.render_current_name = ""
            self.render_errors = []
            self.render_done_msg = ""

        adj_root = Path(root) / "ADJUSTED"
        tmp_root = adj_root / "_tmp"
        sizes = [tuple(s) for s in self.cfg_sizes]
        is_multi = len(sizes) > 1
        quality = self.cfg_quality
        export_format = self.cfg_export_format
        info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
        ext = info["ext"]

        ok_n = 0
        errors: list[str] = []
        total = len(sel_items)
        t0 = time.time()

        for idx, it in enumerate(sel_items, 1):
            async with self:
                self.render_current_name = it.get("original_name", "")
                self.render_progress_pct = int((idx - 1) / total * 100)
            await asyncio.sleep(0)

            name = it.get("original_name", f"item_{idx}")
            src = Path(it.get("source_path", ""))
            if not src.exists():
                errors.append(f"{name}: source không tồn tại")
                continue

            group = it.get("folder_name", "default")
            out_paths = it.get("output_paths", [])
            scale_pct = int(it.get("scale", self.cfg_default_scale_pct))

            item_tmp = tmp_root / it["id"]
            first_size_dest = ""
            try:
                for size_idx, size in enumerate(sizes):
                    w, h, mode = size
                    size_label = get_size_label(w, h, mode)
                    # stem/ext lấy đúng theo file FINAL tương ứng (nếu có)
                    if size_idx < len(out_paths):
                        stem = Path(out_paths[size_idx]).stem
                        out_ext = Path(out_paths[size_idx]).suffix or ext
                    else:
                        stem = clean_name(apply_name_template(
                            self.cfg_template, name=it.get("product", "image"),
                            color=it.get("color", ""), index=idx,
                            original=name,
                        ))
                        out_ext = ext

                    produced = resize_to_multi_sizes(
                        src, item_tmp, stem, [size],
                        quality=quality, export_format=export_format,
                        scale_pct=scale_pct, no_upscale=True,
                    )
                    if not produced:
                        raise RuntimeError("resize_to_multi_sizes không xuất được file")

                    final_dest = (
                        adj_root / size_label / group / f"{stem}{out_ext}"
                        if is_multi else adj_root / group / f"{stem}{out_ext}"
                    )
                    final_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(produced[0], final_dest)
                    if size_idx == 0:
                        first_size_dest = str(final_dest)

                ok_n += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
            finally:
                shutil.rmtree(item_tmp, ignore_errors=True)

            async with self:
                if first_size_dest:
                    self._mutate_item(it["id"], status="adjusted", adjusted_path=first_size_dest)
                self.render_progress_pct = int(idx / total * 100)

        shutil.rmtree(tmp_root, ignore_errors=True)
        dt = time.time() - t0

        async with self:
            self.is_rendering = False
            self.render_current_name = ""
            self.render_errors = errors[:30]
            self._adjusted_root = str(adj_root)
            if ok_n > 0:
                self.render_done_msg = f"✅ Render {ok_n}/{total} ảnh trong {dt:.1f}s"
                sizes_label = " + ".join(
                    get_size_label(w, h, m) for w, h, m in sizes
                ) if sizes else ""
                add_to_history("Adjust", sizes_label, dt, total=total, success=ok_n)
            else:
                self.render_done_msg = ""
            self.error_msg = "" if ok_n > 0 else "❌ Render thất bại cho toàn bộ ảnh đã chọn."
            yield

    # ══════════════════════════════════════════════════════════
    # EXPORT ZIP (merge final + adjusted)
    # ══════════════════════════════════════════════════════════
    @rx.event(background=True)
    async def export_zip(self):
        async with self:
            if self.is_exporting:
                return
            root = self.meta.get("root", "")
            final_dir = self.meta.get("final_dir", "")
            if not root or not Path(root).exists():
                self.error_msg = "❌ Workspace không tồn tại."
                return
            if not final_dir or not Path(final_dir).exists():
                self.error_msg = "❌ Thư mục FINAL không tồn tại."
                return
            self.is_exporting = True
            self.export_msg = ""
            self.error_msg = ""

        root_p = Path(root)
        final_p = Path(final_dir)
        adj_p = Path(self._adjusted_root) if self._adjusted_root else (root_p / "ADJUSTED")
        uid = int(time.time())

        try:
            md = root_p / f"MERGED_{uid}"
            md.mkdir(parents=True, exist_ok=True)
            stats = merge_final_with_adjusted(final_p, adj_p, md)
            zp = root_p / f"FullExport_{self.meta.get('batch_id', 'b')}_{uid}.zip"
            make_zip(md, zp, compresslevel=int(self.cfg_zip_compression))
            shutil.rmtree(md, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001
            async with self:
                self.is_exporting = False
                self.error_msg = f"❌ Tạo ZIP thất bại: {exc}"
            return

        async with self:
            self.is_exporting = False
            if zp.exists() and zp.stat().st_size > 0:
                self.zip_merged_path = str(zp)
                self.zip_merged_size = readable_file_size(zp.stat().st_size)
                self.export_msg = (
                    f"📦 ZIP sẵn sàng · Ghi đè {stats['overridden']} · "
                    f"Giữ nguyên {stats['copied']}"
                )
                if not self.zip_orig_path or not Path(self.zip_orig_path).exists():
                    try:
                        fb = root_p / f"OrigExport_{self.meta.get('batch_id', 'b')}.zip"
                        if not fb.exists():
                            make_zip(final_p, fb, compresslevel=6)
                        if fb.exists():
                            self.zip_orig_path = str(fb)
                    except Exception:  # noqa: BLE001
                        pass
                if self.zip_orig_path and Path(self.zip_orig_path).exists():
                    self.zip_orig_size = readable_file_size(Path(self.zip_orig_path).stat().st_size)
            else:
                self.error_msg = "❌ Tạo ZIP thất bại."

    # ══════════════════════════════════════════════════════════
    # DOWNLOADS
    # ══════════════════════════════════════════════════════════
    def download_zip_original(self):
        h = open_zip_for_download(self.zip_orig_path)
        if not h:
            self.error_msg = "ZIP gốc chưa có."
            return
        try:
            data = h.read()
        finally:
            h.close()
        return rx.download(data=data, filename=Path(self.zip_orig_path).name)

    def download_zip_merged(self):
        h = open_zip_for_download(self.zip_merged_path)
        if not h:
            self.error_msg = "Bấm 'Tạo ZIP gộp' trước."
            return
        try:
            data = h.read()
        finally:
            h.close()
        return rx.download(data=data, filename=Path(self.zip_merged_path).name)

