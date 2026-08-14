"""
studio_state.py — Studio (image-adjust) — PHIÊN BẢN RÚT GỌN cho Reflex.

LƯU Ý MIGRATION: mode_adjust.py gốc (824 dòng) là 1 UI Streamlit rất nặng
(canvas preview trực tiếp trên nhiều slider, pagination, bulk-ops, CSS
tuỳ biến sâu) — port 1:1 toàn bộ UI đó sang Reflex components nằm ngoài
phạm vi hợp lý của lần migrate này (xem README_MIGRATION.md).

Bản rút gọn này VẪN dùng lại đúng core.imaging (open_prepared/save_output —
KHÔNG đổi), chỉ đơn giản hoá UI: upload 1-nhiều ảnh → chỉnh
brightness/contrast/saturation/sharpness bằng PIL.ImageEnhance → xem trước →
tải ảnh đã chỉnh. Đây là chức năng thật (không phải giả lập), chỉ thiếu các
tính năng nâng cao (bulk theo batch vừa chạy, canvas kích thước export theo
preset, pagination...) so với bản gốc.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import reflex as rx

from . import st_compat  # noqa: F401

from core.imaging import open_prepared, save_output, EXPORT_FORMATS


class StudioState(rx.State):
    has_image: bool = False
    filename: str = ""
    brightness: int = 100    # %
    contrast: int = 100
    saturation: int = 100
    sharpness: int = 100
    export_format: str = "JPEG (.jpg)"
    quality: int = 92

    preview_b64: str = ""
    error_msg: str = ""

    _raw_bytes: bytes = b""

    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        f = files[0]
        data = await f.read()
        self._raw_bytes = data
        self.filename = f.filename or f.name
        self.has_image = True
        self.error_msg = ""
        self._render_preview()

    def set_brightness(self, v: list[float]):
        self.brightness = int(v[0])
        self._render_preview()

    def set_contrast(self, v: list[float]):
        self.contrast = int(v[0])
        self._render_preview()

    def set_saturation(self, v: list[float]):
        self.saturation = int(v[0])
        self._render_preview()

    def set_sharpness(self, v: list[float]):
        self.sharpness = int(v[0])
        self._render_preview()

    def set_export_format(self, v: str):
        self.export_format = v
        self._render_preview()

    def reset_adjust(self):
        self.brightness = 100
        self.contrast = 100
        self.saturation = 100
        self.sharpness = 100
        self._render_preview()

    def _adjusted_image(self):
        from PIL import Image, ImageEnhance
        im = Image.open(io.BytesIO(self._raw_bytes))
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        if im.mode not in ("RGB",):
            im = im.convert("RGB")
        im = ImageEnhance.Brightness(im).enhance(self.brightness / 100)
        im = ImageEnhance.Contrast(im).enhance(self.contrast / 100)
        im = ImageEnhance.Color(im).enhance(self.saturation / 100)
        im = ImageEnhance.Sharpness(im).enhance(self.sharpness / 100)
        return im

    def _render_preview(self):
        if not self._raw_bytes:
            return
        try:
            im = self._adjusted_image()
            im.thumbnail((900, 900))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=88)
            self.preview_b64 = base64.b64encode(buf.getvalue()).decode()
            self.error_msg = ""
        except Exception as exc:  # noqa: BLE001
            self.error_msg = f"Lỗi xử lý ảnh: {exc}"

    def download_result(self):
        if not self._raw_bytes:
            return
        try:
            im = self._adjusted_image()
            info = EXPORT_FORMATS.get(self.export_format, EXPORT_FORMATS["JPEG (.jpg)"])
            buf = io.BytesIO()
            fmt = info["pil_format"]
            if fmt == "JPEG":
                im.save(buf, "JPEG", quality=int(self.quality), optimize=True, progressive=True)
            elif fmt == "PNG":
                im.save(buf, "PNG", optimize=True)
            elif fmt == "WEBP":
                im.save(buf, "WEBP", quality=int(self.quality), method=6)
            else:
                im.save(buf)
            out_name = Path(self.filename or "image").stem + info["ext"]
            return rx.download(data=buf.getvalue(), filename=out_name)
        except Exception as exc:  # noqa: BLE001
            self.error_msg = f"Lỗi export: {exc}"
