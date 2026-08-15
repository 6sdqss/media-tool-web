"""
core/imaging.py — pipeline xử lý ảnh an toàn với anti-OOM.
Mọi context Pillow đều đóng đúng, không giữ Image trong RAM sau khi save.
"""
from __future__ import annotations

import logging
import shutil
import warnings
from pathlib import Path
from typing import Optional

from PIL import Image, ImageFile, ImageFilter, ImageOps, UnidentifiedImageError

from .memory import MAX_IMAGE_PIXELS_SAFE
from .types import ErrorType


_log = logging.getLogger("core.imaging")


# ══════════════════════════════════════════════════════════════
# GLOBAL PILLOW CONFIG (đặt trần rõ ràng — KHÔNG tắt như bản cũ)
# ══════════════════════════════════════════════════════════════
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS_SAFE
try:
    # Biến DecompressionBombWarning thành exception để bắt được, thay vì
    # để nó im lặng và app crash sau đó vì OOM.
    warnings.simplefilter("error", Image.DecompressionBombWarning)
except Exception:
    pass


# ══════════════════════════════════════════════════════════════
# FORMAT MAP
# ══════════════════════════════════════════════════════════════
EXPORT_FORMATS: dict = {
    "JPEG (.jpg)": {"ext": ".jpg", "pil_format": "JPEG"},
    "PNG (.png)":  {"ext": ".png", "pil_format": "PNG"},
    "WebP (.webp)": {"ext": ".webp", "pil_format": "WEBP"},
}

IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif",
}


# ══════════════════════════════════════════════════════════════
# MAGIC BYTES VALIDATION
# ══════════════════════════════════════════════════════════════
def is_real_image_file(path: Path) -> bool:
    """
    Kiểm tra magic bytes — phòng Google trả về HTML giả ảnh, hoặc file trống.
    """
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size < 24:
            return False
        with open(p, "rb") as f:
            head = f.read(16)
        if head[:3] == b"\xff\xd8\xff":               # JPEG
            return True
        if head[:8] == b"\x89PNG\r\n\x1a\n":          # PNG
            return True
        if head[:4] == b"GIF8":                       # GIF
            return True
        if head[:2] == b"BM":                         # BMP
            return True
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":  # WebP
            return True
        # TIFF
        if head[:4] in (b"II*\x00", b"MM\x00*"):
            return True
        return False
    except Exception:
        return False


def probe_meta(path: Path) -> dict:
    """
    Đọc metadata (width, height, size_bytes) mà KHÔNG giải mã pixel đầy đủ.
    Rất rẻ về RAM.
    """
    meta = {"width": 0, "height": 0, "size_bytes": 0, "ok": False}
    try:
        p = Path(path)
        if not p.exists():
            return meta
        meta["size_bytes"] = p.stat().st_size
        with Image.open(p) as im:
            meta["width"], meta["height"] = im.size
        meta["ok"] = True
    except Exception:
        pass
    return meta


# ══════════════════════════════════════════════════════════════
# LOAD PIPELINE (anti-OOM)
# ══════════════════════════════════════════════════════════════
def _get_resample():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.ANTIALIAS  # Pillow <9


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, (0, 0), img)
        return bg.convert("RGB")
    if img.mode == "CMYK":
        return img.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def open_prepared(
    path: Path,
    target: tuple[int, int] | None,
    huge_mode: bool = True,
) -> Image.Image:
    """
    Mở ảnh, EXIF-transpose, downsize sớm nếu ảnh khổng lồ, convert RGB.
    Thứ tự này quan trọng: downsize TRƯỚC convert RGB để không nhét
    toàn bộ pixel PNG/WebP vào RAM chỉ để rồi thu nhỏ ở bước sau.
    """
    im = Image.open(path)

    # EXIF orientation
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass

    if huge_mode and target and target[0] and target[1]:
        # JPEG: draft() giảm bộ nhớ giải mã ngay khi mở
        try:
            dw = max(int(target[0] * 2.8), 1)
            dh = max(int(target[1] * 2.8), 1)
            im.draft("RGB", (dw, dh))
        except Exception:
            pass

        # PNG/WebP: draft không có tác dụng → phải thumbnail() ngay
        try:
            source_long = max(im.width, im.height)
            desired_long = max(target[0], target[1])
            if source_long > desired_long * 2:
                pre = int(desired_long * 2.4)
                im.thumbnail((pre, pre), _get_resample())
        except Exception:
            pass

    return _to_rgb(im)


# ══════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════
def save_output(
    img: Image.Image,
    out_path: Path,
    quality: int = 92,
    export_format: str = "JPEG (.jpg)",
) -> Path:
    """Ghi ra file theo format chỉ định. Trả về path thực tế."""
    info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
    out_path = Path(out_path).with_suffix(info["ext"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = info["pil_format"]

    if fmt == "JPEG":
        img.save(
            out_path, "JPEG",
            quality=int(quality), optimize=True,
            progressive=True, subsampling="4:2:0",
        )
    elif fmt == "PNG":
        img.save(out_path, "PNG", optimize=True)
    elif fmt == "WEBP":
        img.save(out_path, "WEBP", quality=int(quality), method=6)
    else:
        img.save(out_path)
    return out_path


# ══════════════════════════════════════════════════════════════
# RESIZE MODES
# ══════════════════════════════════════════════════════════════
def _fit_size(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[int, int]:
    r_src = src_w / max(src_h, 1)
    r_dst = dst_w / max(dst_h, 1)
    if r_src > r_dst:
        return dst_w, max(int(dst_w / max(r_src, 1e-9)), 1)
    return max(int(dst_h * r_src), 1), dst_h


# Cho phép phóng to tối đa 60% so với ảnh gốc để lấp khung tốt hơn khi
# ảnh gốc nhỏ hơn canvas nhiều — tránh ảnh bị co nhỏ giữa viền trắng rất to
# (nhìn khó chịu). 1.6x với LANCZOS + unsharp nhẹ vẫn giữ được độ nét ở mức
# chấp nhận được cho ảnh sản phẩm; không phóng vô hạn để tránh vỡ nét.
MAX_SAFE_UPSCALE = 1.6
# Nếu ảnh fit tự nhiên đã choán ≥ tỉ lệ này của khung thì không cần phóng
# thêm (đã đủ to, tránh phóng ảnh vốn đã gần vừa khung).
FILL_OK_RATIO = 0.94


def resize_letterbox(
    src_path: Path,
    out_path: Path,
    width: int,
    height: int,
    scale_pct: int = 100,
    quality: int = 92,
    export_format: str = "JPEG (.jpg)",
    no_upscale: bool = True,
    huge_mode: bool = True,
) -> tuple[bool, Optional[ErrorType], str]:
    """
    Fit ảnh vào canvas W×H với nền trắng. Nếu ảnh nhỏ hơn target, thay vì
    chặn phóng to hoàn toàn (khiến ảnh bé tí giữa viền trắng rất to), cho
    phép phóng có kiểm soát tối đa MAX_SAFE_UPSCALE lần để ảnh choán khung
    tốt hơn — vẫn không phóng vượt quá mức đó để giữ độ nét.
    """
    try:
        with open_prepared(src_path, (width, height), huge_mode) as img:
            factor = max(int(scale_pct), 1) / 100.0

            fit_w, fit_h = _fit_size(img.width, img.height, width, height)
            was_upscaled = False

            if no_upscale:
                # Tỉ lệ cần phóng để ảnh fit vừa khung (giữ tỉ lệ khung hình
                # gốc, do _fit_size đã tính theo đúng aspect ratio).
                fit_scale = fit_w / max(img.width, 1)
                if fit_scale > 1.0 and fit_scale > FILL_OK_RATIO:
                    # Ảnh gốc nhỏ hơn khung khá nhiều → phóng có kiểm soát
                    # thay vì giữ nguyên kích thước gốc.
                    allowed_scale = min(fit_scale, MAX_SAFE_UPSCALE)
                    new_w = max(int(img.width * allowed_scale * factor), 1)
                    new_h = max(int(img.height * allowed_scale * factor), 1)
                    was_upscaled = allowed_scale > 1.0
                else:
                    new_w = max(int(min(fit_w, img.width) * factor), 1)
                    new_h = max(int(min(fit_h, img.height) * factor), 1)
            else:
                new_w = max(int(fit_w * factor), 1)
                new_h = max(int(fit_h * factor), 1)

            resized = img.resize((new_w, new_h), _get_resample())
            if was_upscaled:
                # Bù lại độ mềm do phóng to bằng unsharp nhẹ — giữ cảm giác
                # "đủ nét" thay vì mờ nhòe.
                resized = resized.filter(
                    ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=2)
                )
            canvas = Image.new("RGB", (width, height), (255, 255, 255))

            paste_x = max(0, (width - resized.width) // 2)
            paste_y = max(0, (height - resized.height) // 2)

            if resized.width > width or resized.height > height:
                # Sau khi resize vẫn lớn hơn canvas (letterbox cho phép tràn?)
                # Ở đây thay vì crop, thu vừa canvas.
                resized.thumbnail((width, height), _get_resample())
                paste_x = max(0, (width - resized.width) // 2)
                paste_y = max(0, (height - resized.height) // 2)

            canvas.paste(resized, (paste_x, paste_y))
            save_output(canvas, out_path, quality, export_format)

            resized.close()
            canvas.close()
        return True, None, ""

    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        _log.error("Image too large [%s]: %s", src_path, exc)
        return False, ErrorType.IMAGE_TOO_LARGE, str(exc)[:200]
    except UnidentifiedImageError as exc:
        return False, ErrorType.INVALID_IMAGE, str(exc)[:200]
    except OSError as exc:
        # Disk full, truncated file, permission...
        msg = str(exc).lower()
        if "no space" in msg or "disk" in msg:
            return False, ErrorType.DISK_FULL, str(exc)[:200]
        return False, ErrorType.RESIZE_FAILED, str(exc)[:200]
    except Exception as exc:
        _log.exception("Resize failed [%s]", src_path)
        return False, ErrorType.RESIZE_FAILED, str(exc)[:200]


def resize_square_crop(
    src_path: Path,
    out_path: Path,
    target: int = 1000,
    quality: int = 92,
    export_format: str = "JPEG (.jpg)",
    huge_mode: bool = True,
) -> tuple[bool, Optional[ErrorType], str]:
    """Crop giữa thành hình vuông rồi resize (ảnh Photoshop style)."""
    try:
        with open_prepared(src_path, (target, target), huge_mode) as img:
            w, h = img.size
            if w > target or h > target:
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                cropped = img.crop((left, top, left + side, top + side))
                if side > target:
                    cropped = cropped.resize((target, target), _get_resample())
                final = cropped
            else:
                # Ảnh nhỏ hơn khung vuông → phóng có kiểm soát (như
                # resize_letterbox) để lấp khung tốt hơn thay vì để nguyên
                # ảnh bé giữa nền trắng rất to.
                side = max(w, h)
                fit_scale = target / max(side, 1)
                allowed_scale = min(fit_scale, MAX_SAFE_UPSCALE) if fit_scale > FILL_OK_RATIO else 1.0
                if allowed_scale > 1.0:
                    new_w = max(int(w * allowed_scale), 1)
                    new_h = max(int(h * allowed_scale), 1)
                    scaled = img.resize((new_w, new_h), _get_resample())
                    scaled = scaled.filter(
                        ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=2)
                    )
                    w, h = new_w, new_h
                else:
                    scaled = img
                final = Image.new("RGB", (target, target), (255, 255, 255))
                final.paste(scaled, ((target - w) // 2, (target - h) // 2))
                if scaled is not img:
                    scaled.close()

            save_output(final, out_path, quality, export_format)
            final.close()
        return True, None, ""
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        return False, ErrorType.IMAGE_TOO_LARGE, str(exc)[:200]
    except Exception as exc:
        _log.exception("Square crop failed [%s]", src_path)
        return False, ErrorType.RESIZE_FAILED, str(exc)[:200]


def copy_original(src_path: Path, out_path: Path) -> tuple[bool, Optional[ErrorType], str]:
    """Giữ nguyên ảnh gốc — dùng cho mode 'keep'."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_path), str(out_path))
        return True, None, ""
    except Exception as exc:
        return False, ErrorType.SAVE_FAILED, str(exc)[:200]


# ══════════════════════════════════════════════════════════════
# DISPATCH
# ══════════════════════════════════════════════════════════════
def apply_size(
    src_path: Path,
    out_path: Path,
    size,  # SizeSpec | tuple(w,h,mode)
    quality: int,
    export_format: str,
    scale_pct: int = 100,
    no_upscale: bool = True,
    huge_mode: bool = True,
) -> tuple[bool, Optional[ErrorType], str]:
    """Chọn engine resize phù hợp với mode."""
    if hasattr(size, "width"):
        w, h, mode = size.width, size.height, size.mode
    else:
        w, h, mode = size[0], size[1], size[2] if len(size) > 2 else "letterbox"

    if mode == "crop_1000":
        return resize_square_crop(src_path, out_path, w or 1000, quality, export_format, huge_mode)
    if mode == "keep":
        return copy_original(src_path, out_path)
    # letterbox / fit / mặc định
    return resize_letterbox(
        src_path, out_path, w, h,
        scale_pct=scale_pct, quality=quality, export_format=export_format,
        no_upscale=no_upscale, huge_mode=huge_mode,
    )


# ══════════════════════════════════════════════════════════════
# PREVIEW THUMBNAIL
# ══════════════════════════════════════════════════════════════
def build_preview_thumb(src: Path, out_dir: Path, max_size: int = 480) -> str:
    """Tạo thumbnail JPEG nhỏ cho Studio preview. Trả path (str)."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / (Path(src).stem + "_thumb.jpg")
        with open_prepared(src, (max_size, max_size), True) as img:
            img.thumbnail((max_size, max_size), _get_resample())
            img.save(out, "JPEG", quality=80, optimize=True)
        return str(out)
    except Exception:
        return ""
