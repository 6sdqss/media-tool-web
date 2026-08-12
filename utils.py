"""
utils.py — Media Tool Pro VIP v10.1
─────────────────────────────────────────────────────────
Nâng cấp từ v9.3 → v10.1 (patch an toàn, giữ nguyên toàn bộ API public):

[FIX] api_download_file     : BytesIO→FileIO stream, chunk 8MB, retry 3 lần
[FIX] download_direct_file  : extension thật từ header/API, magic bytes verify,
                               requests bypass confirm token, gdown fallback đúng
[FIX] api_download_folder_images: retry per-file, progress_cb, delay chống rate-limit
[FIX] get_drive_name        : timeout đúng (connect+read riêng), retry 2 lần
[FIX] check_pause_cancel_state: sleep 0.7s→0.2s, max_pause_seconds auto-resume
[NEW] _download_via_requests: bypass Google virus-scan confirm token
[NEW] _is_real_image_bytes  : kiểm tra magic bytes JPEG/PNG/WebP/GIF/BMP
[NEW] _find_gdown_output    : tìm file thật sau khi gdown tự thêm extension
[FIX] init_app_state        : setup logging + auto cleanup temp dirs
"""

from __future__ import annotations

import io
import os
import re
import gc
import json
import time
import base64
import shutil
import hashlib
import logging
import tempfile
import warnings
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import streamlit as st
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

# Google APIs
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# ── Logger nội bộ ──────────────────────────────────────────────────
_log = logging.getLogger("media_tool_utils")


# ╔══════════════════════════════════════════════════════════════╗
# ║  CẤU HÌNH ẢNH LỚN                                            ║
# ╚══════════════════════════════════════════════════════════════╝
ImageFile.LOAD_TRUNCATED_IMAGES = True

# [FIX v11.0 — ANTI-OOM] TRƯỚC ĐÂY: Image.MAX_IMAGE_PIXELS = None → tắt HẲN
# giới hạn an toàn của Pillow. Hệ quả: 1 ảnh "nặng" (scan độ phân giải cao,
# ảnh RAW xuất PNG, hoặc file lỗi/độc hại) được giải mã full-res vào RAM
# không giới hạn → Streamlit Cloud (RAM giới hạn ~1GB) bị Out-Of-Memory và
# CRASH TOÀN BỘ APP (mất luôn cả các session khác đang chạy).
# NAY: đặt trần hợp lý (~120 triệu pixel — dư sức cho ảnh scan 4K-8K thật)
# để chặn ảnh "bomb" trước khi nó kịp ăn hết RAM, đồng thời log rõ ràng
# thay vì để tiến trình chết im lặng.
_MAX_SAFE_PIXELS = 120_000_000  # ~120 MP (ví dụ 12000x10000)
Image.MAX_IMAGE_PIXELS = _MAX_SAFE_PIXELS
try:
    # Không ignore nữa — convert thành exception để code bên dưới bắt được
    # và báo lỗi rõ ràng cho người dùng thay vì chỉ warn ra log rồi vẫn cố tải.
    warnings.simplefilter("error", Image.DecompressionBombWarning)
except Exception:
    pass


# ╔══════════════════════════════════════════════════════════════╗
# ║  HẰNG SỐ                                                     ║
# ╚══════════════════════════════════════════════════════════════╝
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}

EXPORT_FORMATS = {
    "JPEG (.jpg)": {"ext": ".jpg", "pil_format": "JPEG", "mime": "image/jpeg"},
    "PNG (.png)":  {"ext": ".png", "pil_format": "PNG",  "mime": "image/png"},
    "WebP (.webp)": {"ext": ".webp", "pil_format": "WEBP", "mime": "image/webp"},
}

SIZE_PRESETS = {
    "1020×680 TGDD chuẩn":  (1020, 680,  "letterbox"),
    "1200×1200 Vuông":       (1200, 1200, "letterbox"),
    "800×800 Sàn TMĐT":      (800,  800,  "letterbox"),
    "1000×1000 Crop giữa":   (1000, 1000, "crop_1000"),
    "Giữ gốc":               (None, None, "letterbox"),
}

BATCH_ROOT = Path(tempfile.gettempdir()) / "media_tool_pro_vip_batches"
BATCH_ROOT.mkdir(parents=True, exist_ok=True)

# Ngưỡng ZIP load vào RAM — lớn hơn thì đọc từ đĩa
_MAX_INMEM_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB


# ╔══════════════════════════════════════════════════════════════╗
# ║  SESSION DEFAULTS                                            ║
# ╚══════════════════════════════════════════════════════════════╝
def init_app_state():
    """
    Khởi tạo các state mặc định một lần duy nhất.
    [v10.1] Thêm: logging setup + auto cleanup temp dirs.
    """
    defaults = {
        "download_status": "idle",
        "logged_in": False,
        "auth_user": None,
        "processing_history": [],
        "session_stats": {
            "total_images": 0,
            "total_batches": 0,
            "total_time": 0.0,
        },
        "web_scanned": [],
        "web_zip_path": "",
        "drive_zip_data": None,
        "drive_zip_path": "",
        "local_zip_data": None,
        "local_zip_path": "",
        "adjust_zip_path": "",
        "last_batch_manifest": [],
        "last_batch_cfg": {},
        "last_batch_meta": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # [v10.1] Setup logging một lần mỗi session
    if not st.session_state.get("_logging_setup"):
        st.session_state["_logging_setup"] = True
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )

    # [v10.1] Auto cleanup temp dirs cũ — chạy 1 lần mỗi session
    if not st.session_state.get("_cleanup_done"):
        st.session_state["_cleanup_done"] = True
        try:
            from cleanup import cleanup
            stats = cleanup(force=False)
            if stats.get("deleted", 0) > 0:
                _log.info(
                    "Auto cleanup: xóa %d batch cũ, giải phóng %.1f MB",
                    stats["deleted"], stats.get("freed_mb", 0)
                )
        except Exception:
            pass  # cleanup.py không tồn tại hoặc lỗi — bỏ qua an toàn


# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE DRIVE — Kết nối & Upload                            ║
# ╚══════════════════════════════════════════════════════════════╝
def get_gdrive_service():
    """Tạo Google Drive service từ Streamlit Secrets hoặc credentials.json."""
    try:
        if "gcp_service_account" in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass

    try:
        if os.path.exists("credentials.json"):
            creds = service_account.Credentials.from_service_account_file(
                "credentials.json",
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass

    return None


def create_drive_folder(service, folder_name: str, parent_id: str) -> str:
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder.get("id")


def upload_to_drive(service, file_path, target_folder_id: str) -> str:
    ext = Path(file_path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    metadata = {
        "name": os.path.basename(file_path),
        "parents": [target_folder_id],
    }
    media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)
    result = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return result.get("id")


def extract_drive_id_and_type(url: str):
    if not url:
        return None, None

    match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1), "folder"

    match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1), "file"

    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1), "file"

    return None, None


def api_get_file_name(service, file_id: str) -> str:
    try:
        metadata = service.files().get(
            fileId=file_id, fields="name", supportsAllDrives=True
        ).execute()
        return metadata.get("name", file_id)
    except Exception:
        return file_id


# ─────────────────────────────────────────────────────────────────
# [v10.1 FIX] api_download_file — stream thẳng ra đĩa, không BytesIO
# Lỗi cũ: io.BytesIO() nạp toàn bộ file vào RAM → 20MB ảnh = 40MB RAM
#          (BytesIO + write_bytes). 100 ảnh = 4GB → OOM crash.
# Fix: io.FileIO() stream từng 8MB chunk → RAM không đổi dù file bao lớn.
# ─────────────────────────────────────────────────────────────────
def api_download_file(
    service,
    file_id: str,
    save_path: Path,
    chunk_size: int = 8 * 1024 * 1024,  # 8 MB / chunk
    max_retries: int = 3,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> bool:
    """
    Tải file từ Google Drive API — stream trực tiếp ra đĩa.
    Không load vào RAM. Retry tối đa max_retries lần với exponential backoff.
    """
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = save_path.with_suffix(save_path.suffix + ".tmp")

    for attempt in range(1, max_retries + 1):
        try:
            request = service.files().get_media(fileId=file_id)

            # [FIX] Stream vào file thật — không dùng BytesIO
            with io.FileIO(str(tmp_path), mode="wb") as fh:
                downloader = MediaIoBaseDownload(fh, request, chunksize=chunk_size)
                done = False
                while not done:
                    try:
                        status, done = downloader.next_chunk()
                        if progress_cb and status:
                            progress_cb(int(status.resumable_progress))
                    except Exception as chunk_exc:
                        _log.warning(
                            "[Drive API] Chunk error file=%s attempt=%d: %s",
                            file_id, attempt, chunk_exc,
                        )
                        raise  # bubble up để retry

            # Verify file thực sự được ghi
            if tmp_path.exists() and tmp_path.stat().st_size > 0:
                tmp_path.rename(save_path)
                _log.info(
                    "[Drive API] OK file=%s size=%d bytes",
                    file_id, save_path.stat().st_size,
                )
                return True
            else:
                _log.warning("[Drive API] Empty file after download file=%s", file_id)
                tmp_path.unlink(missing_ok=True)
                return False

        except Exception as exc:
            tmp_path.unlink(missing_ok=True)
            _log.warning(
                "[Drive API] Attempt %d/%d failed file=%s: %s",
                attempt, max_retries, file_id, exc,
            )
            if attempt < max_retries:
                backoff = 2 ** attempt  # 2s, 4s, 8s
                _log.info("[Drive API] Retry in %ds...", backoff)
                time.sleep(backoff)
            else:
                _log.error("[Drive API] All retries failed file=%s", file_id)

    return False


def api_list_folder_images(service, folder_id: str) -> list:
    image_mimes = [
        "image/jpeg", "image/png", "image/webp",
        "image/gif", "image/bmp", "image/tiff",
    ]
    mime_query = " or ".join([f"mimeType='{m}'" for m in image_mimes])
    query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"

    results = []
    page_token = None

    while True:
        try:
            response = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        except Exception:
            break

    subfolder_query = (
        f"'{folder_id}' in parents "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and trashed=false"
    )
    try:
        sub_response = service.files().list(
            q=subfolder_query,
            fields="files(id, name)",
            pageSize=50,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        for subfolder in sub_response.get("files", []):
            sub_images = api_list_folder_images(service, subfolder["id"])
            results.extend(sub_images)
    except Exception:
        pass

    return results


# ─────────────────────────────────────────────────────────────────
# [v10.1 FIX] api_download_folder_images — retry per-file + progress_cb
# Lỗi cũ: không retry → 1 file lỗi mạng thoáng qua = mất ảnh đó luôn.
#          không có delay giữa các file → Google Drive API trả 429 rate limit.
# ─────────────────────────────────────────────────────────────────
def api_download_folder_images(
    service,
    folder_id: str,
    save_dir: Path,
    max_files: int = None,
    max_retries: int = 2,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    delay_between_files: float = 0.35,
) -> int:
    """
    Tải toàn bộ ảnh trong folder Google Drive về save_dir.
    Retry per-file, có delay giữa các request để tránh rate limit.
    """
    images = api_list_folder_images(service, folder_id)
    if not images:
        _log.warning("[folder_dl] No images in folder=%s", folder_id)
        return 0
    if max_files:
        images = images[:max_files]

    total = len(images)
    _log.info("[folder_dl] %d images in folder=%s", total, folder_id)
    save_dir = Path(save_dir)

    count = 0
    for idx, img_meta in enumerate(images):
        file_name = re.sub(r'[\\/*?:"<>|]', "", img_meta["name"]).strip()
        if not file_name:
            file_name = f"{img_meta['id']}.jpg"

        save_path = save_dir / file_name

        # Skip nếu đã tải (chống duplicate khi retry batch)
        if save_path.exists() and save_path.stat().st_size > 0:
            count += 1
            if progress_cb:
                progress_cb(idx + 1, total)
            continue

        success = False
        for attempt in range(1, max_retries + 1):
            ok = api_download_file(service, img_meta["id"], save_path)
            if ok and save_path.exists() and save_path.stat().st_size > 0:
                success = True
                break
            _log.warning(
                "[folder_dl] Retry %d/%d: %s", attempt, max_retries, file_name
            )
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

        if success:
            count += 1
        else:
            _log.error("[folder_dl] FAILED: %s (id=%s)", file_name, img_meta["id"])

        if progress_cb:
            progress_cb(idx + 1, total)

        # Delay giữa các file để tránh Drive API rate limit (429)
        if idx < total - 1:
            time.sleep(delay_between_files)

    _log.info("[folder_dl] Done: %d/%d downloaded from folder=%s", count, total, folder_id)
    return count


# ─────────────────────────────────────────────────────────────────
# [v10.1 FIX] get_drive_name — timeout đúng chuẩn, retry, fallback đẹp
# Lỗi cũ: timeout=10 chỉ là read_timeout, connect_timeout = None → hang DNS.
# ─────────────────────────────────────────────────────────────────
def get_drive_name(file_id: str, kind: str, service=None) -> str:
    """
    Lấy tên file/folder từ Google Drive.
    Ưu tiên: Service Account API → HTML scraping → fallback ID prefix.
    """
    if not file_id:
        return "unknown"

    # API path (nếu có service account)
    if service:
        name = api_get_file_name(service, file_id)
        if name and name != file_id:
            return name
        # Nếu API fail, thử HTML scrape

    # HTML scraping với timeout đúng (connect, read)
    try:
        import requests as _req
    except ImportError:
        prefix = file_id[:8] if len(file_id) >= 8 else file_id
        return f"Drive_{prefix}"

    if kind == "file":
        url = f"https://drive.google.com/file/d/{file_id}/view"
    else:
        url = f"https://drive.google.com/drive/folders/{file_id}"

    for attempt in range(1, 3):
        try:
            resp = _req.get(
                url,
                timeout=(10, 15),   # [FIX] (connect_timeout, read_timeout) riêng
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            if resp.status_code == 200:
                match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
                if match:
                    name = re.sub(r'[\\/*?:"<>|]', "", match.group(1)).strip()
                    if name and name.lower() not in ("google drive",):
                        return name
        except _req.exceptions.Timeout:
            _log.warning("[get_name] Timeout attempt=%d id=%s", attempt, file_id)
        except Exception as exc:
            _log.warning("[get_name] Scrape error attempt=%d: %s", attempt, exc)

        if attempt < 2:
            time.sleep(2)

    # [FIX] Fallback đẹp hơn — không trả raw ID
    prefix = file_id[:8] if len(file_id) >= 8 else file_id
    fallback = f"Drive_{prefix}"
    _log.warning("[get_name] Fallback: %s", fallback)
    return fallback


# ─────────────────────────────────────────────────────────────────
# [v10.1 FIX] download_direct_file — extension thật, magic bytes verify,
#             requests bypass confirm token, gdown fallback
# Lỗi cũ:
#   1. Hardcode .jpg → PNG/WebP lưu sai extension → Pillow crash
#   2. gdown không xử lý virus-scan warning page → tải về file HTML giả ảnh
#   3. Không verify file → trả path dù file là HTML 5KB
# ─────────────────────────────────────────────────────────────────
def download_direct_file(
    file_id: str,
    save_folder: Path,
    drive_name: str,
    service=None,
    max_retries: int = 3,
) -> Path:
    """
    Tải 1 file đơn từ Google Drive.
    Ưu tiên: Drive API → requests+confirm token → gdown fallback.
    Luôn verify file thật bằng magic bytes trước khi trả về.
    """
    save_folder = Path(save_folder)
    save_folder.mkdir(parents=True, exist_ok=True)
    fallback_path = save_folder / f"{drive_name}.jpg"

    # ── Nhánh 1: Google Drive Service Account API ────────────────
    if service:
        try:
            # Lấy extension thật từ metadata
            try:
                meta = service.files().get(
                    fileId=file_id,
                    fields="name,mimeType",
                    supportsAllDrives=True,
                ).execute()
                real_name = meta.get("name", "")
                real_ext = Path(real_name).suffix.lower() if real_name else ".jpg"
                if real_ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}:
                    real_ext = ".jpg"
            except Exception:
                real_ext = ".jpg"

            api_path = save_folder / f"{drive_name}{real_ext}"
            ok = api_download_file(service, file_id, api_path, max_retries=max_retries)
            if ok and api_path.exists() and api_path.stat().st_size > 0:
                if _is_real_image_bytes(api_path):
                    _log.info("[direct_dl] API OK: %s", api_path.name)
                    return api_path
                else:
                    _log.warning("[direct_dl] API response not image: %s", api_path.name)
                    api_path.unlink(missing_ok=True)
        except Exception as exc:
            _log.warning("[direct_dl] API path failed: %s", exc)

    # ── Nhánh 2: requests + confirm token (bypass virus-scan warning) ──
    for attempt in range(1, max_retries + 1):
        result = _download_via_requests(file_id, save_folder, drive_name)
        if result and result.exists() and result.stat().st_size > 0:
            if _is_real_image_bytes(result):
                _log.info("[direct_dl] requests OK attempt=%d: %s", attempt, result.name)
                return result
            else:
                _log.warning("[direct_dl] requests returned non-image attempt=%d", attempt)
                result.unlink(missing_ok=True)
        else:
            _log.warning("[direct_dl] requests failed attempt=%d", attempt)
        if attempt < max_retries:
            time.sleep(2 ** attempt)  # 2s, 4s

    # ── Nhánh 3: gdown fallback ──────────────────────────────────
    for attempt in range(1, 3):
        try:
            import gdown as _gdown
            download_url = f"https://drive.google.com/uc?id={file_id}"
            tmp_path = save_folder / f"{drive_name}_gdown_tmp"
            _gdown.download(download_url, str(tmp_path), quiet=True, fuzzy=True)
            actual_path = _find_gdown_output(tmp_path, save_folder, drive_name)
            if actual_path and actual_path.exists() and actual_path.stat().st_size > 0:
                if _is_real_image_bytes(actual_path):
                    _log.info("[direct_dl] gdown OK: %s", actual_path.name)
                    return actual_path
                else:
                    _log.warning("[direct_dl] gdown returned non-image")
                    actual_path.unlink(missing_ok=True)
        except ImportError:
            _log.warning("[direct_dl] gdown not installed")
            break
        except Exception as exc:
            _log.warning("[direct_dl] gdown attempt=%d failed: %s", attempt, exc)
            if attempt < 2:
                time.sleep(5)

    _log.error("[direct_dl] All methods failed file_id=%s", file_id)
    return fallback_path  # Caller phải kiểm tra .exists() và .stat().st_size > 0


# ─────────────────────────────────────────────────────────────────
# [v10.1 NEW] _download_via_requests
# Bypass Google virus-scan confirmation page bằng cách:
#   1. Thử drive.usercontent.google.com (endpoint ít bị chặn hơn)
#   2. Nếu nhận HTML → parse confirm token → retry với token
#   3. Stream chunk-by-chunk (512KB) không load toàn bộ vào RAM
# ─────────────────────────────────────────────────────────────────
def _download_via_requests(
    file_id: str,
    save_folder: Path,
    name_hint: str,
) -> Optional[Path]:
    """
    Tải file Google Drive qua requests, xử lý confirm token tự động.
    Trả Path nếu thành công, None nếu thất bại.
    """
    try:
        import requests as _req
    except ImportError:
        return None

    # usercontent endpoint ổn định hơn uc?export=download
    PRIMARY_URL = (
        f"https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&confirm=t"
    )
    FALLBACK_URL = f"https://drive.google.com/uc?export=download&id={file_id}"

    session = _req.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    for base_url in [PRIMARY_URL, FALLBACK_URL]:
        try:
            resp = session.get(
                base_url,
                stream=True,
                timeout=(15, 60),        # (connect_timeout, read_timeout)
                allow_redirects=True,
            )

            if resp.status_code == 429:
                _log.warning("[requests_dl] Rate limited (429) file=%s", file_id)
                continue

            if resp.status_code != 200:
                _log.warning("[requests_dl] HTTP %d file=%s", resp.status_code, file_id)
                continue

            # Phát hiện HTML confirm page (virus scan warning)
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                html_chunk = next(resp.iter_content(8192), b"")
                confirm_match = re.search(rb"confirm=([0-9A-Za-z_\-]+)", html_chunk)
                if confirm_match:
                    confirm_token = confirm_match.group(1).decode("ascii")
                    confirm_url = f"{FALLBACK_URL}&confirm={confirm_token}"
                    _log.info("[requests_dl] Got confirm token, retrying...")
                    resp = session.get(
                        confirm_url, stream=True, timeout=(15, 120), allow_redirects=True
                    )
                    if resp.status_code != 200:
                        continue
                else:
                    _log.warning("[requests_dl] HTML without confirm token (rate-limited?)")
                    continue

            # Xác định extension từ Content-Disposition
            ext = ".jpg"
            content_disp = resp.headers.get("Content-Disposition", "")
            if content_disp:
                m = re.search(r'filename[*]?=["\']?([^"\';\n]+)', content_disp)
                if m:
                    fname = m.group(1).strip().strip('"').strip("'")
                    detected_ext = Path(fname).suffix.lower()
                    if detected_ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
                        ext = detected_ext

            save_path = save_folder / f"{name_hint}{ext}"
            tmp_path = save_path.with_suffix(ext + ".tmp")

            # Stream chunk-by-chunk — không load vào RAM
            total_bytes = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=512 * 1024):  # 512KB
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)

            if total_bytes > 1024:  # Ít nhất 1KB mới hợp lệ
                tmp_path.rename(save_path)
                return save_path
            else:
                tmp_path.unlink(missing_ok=True)
                _log.warning("[requests_dl] File too small (%d bytes)", total_bytes)

        except _req.exceptions.Timeout:
            _log.warning("[requests_dl] Timeout file=%s url=%s", file_id, base_url[:70])
        except _req.exceptions.ConnectionError as exc:
            _log.warning("[requests_dl] Connection error: %s", exc)
        except Exception as exc:
            _log.warning("[requests_dl] Error: %s", exc)

    return None


# ─────────────────────────────────────────────────────────────────
# [v10.1 NEW] _is_real_image_bytes
# Kiểm tra magic bytes để phát hiện file HTML giả ảnh từ Google
# ─────────────────────────────────────────────────────────────────
def _is_real_image_bytes(path: Path) -> bool:
    """
    Kiểm tra nhanh magic bytes xác nhận file là ảnh thật.

    Magic bytes được kiểm tra:
      JPEG : FF D8 FF
      PNG  : 89 50 4E 47 0D 0A 1A 0A
      GIF  : 47 49 46 38 (GIF8)
      WebP : 52 49 46 46 ?? ?? ?? ?? 57 45 42 50
      BMP  : 42 4D

    Trả False nếu file là HTML/text (tức Google trả trang xác nhận).
    """
    try:
        if not path.exists() or path.stat().st_size < 12:
            return False
        with open(path, "rb") as f:
            header = f.read(12)
        if header[:3] == b"\xff\xd8\xff":               # JPEG
            return True
        if header[:8] == b"\x89PNG\r\n\x1a\n":          # PNG
            return True
        if header[:4] in (b"GIF8",):                     # GIF
            return True
        if header[:2] == b"BM":                          # BMP
            return True
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":  # WebP
            return True
        return False
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
# [v10.1 NEW] _find_gdown_output
# gdown đôi khi tự thêm extension → tìm file thật sau khi tải
# ─────────────────────────────────────────────────────────────────
def _find_gdown_output(
    expected_path: Path,
    folder: Path,
    name_hint: str,
) -> Optional[Path]:
    """
    Tìm file thật mà gdown đã tải.
    gdown có thể tự thêm extension: "product_tmp" → "product_tmp.jpg"
    """
    # File tồn tại đúng path kỳ vọng
    if expected_path.exists() and expected_path.stat().st_size > 0:
        # Detect extension thật và rename
        ext = ".jpg"
        try:
            with Image.open(expected_path) as im:
                fmt = im.format
                ext = {
                    "JPEG": ".jpg", "PNG": ".png",
                    "WEBP": ".webp", "GIF": ".gif",
                }.get(fmt or "", ".jpg")
        except Exception:
            ext = ".jpg"
        final = folder / f"{name_hint}{ext}"
        try:
            expected_path.rename(final)
            return final
        except Exception:
            return expected_path

    # Tìm file có prefix trùng tên (gdown thêm extension)
    try:
        for candidate in sorted(folder.iterdir()):
            if (
                candidate.name.startswith(expected_path.name)
                and candidate.is_file()
                and candidate.stat().st_size > 0
            ):
                return candidate
    except Exception:
        pass

    return None


# ╔══════════════════════════════════════════════════════════════╗
# ║  TIỆN ÍCH CHUNG                                              ║
# ╚══════════════════════════════════════════════════════════════╝
def clean_name(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", str(name or ""))
    name = re.sub(r"\s+", "_", name).strip("_")
    return name or "Untitled"


def ignore_system_files(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("._")
        or name == ".DS_Store"
        or name.startswith("__MACOSX")
        or name.startswith("__tmp_")
    )


def compute_file_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def create_batch_workspace(prefix: str = "web") -> dict:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_id = f"{prefix}_{stamp}_{int(time.time() * 1000) % 100000}"
    root = BATCH_ROOT / batch_id
    raw_dir = root / "RAW"
    final_dir = root / "FINAL"
    preview_dir = root / "PREVIEW"
    meta_dir = root / "META"
    for p in [root, raw_dir, final_dir, preview_dir, meta_dir]:
        p.mkdir(parents=True, exist_ok=True)
    return {
        "batch_id": batch_id,
        "root": str(root),
        "raw_dir": str(raw_dir),
        "final_dir": str(final_dir),
        "preview_dir": str(preview_dir),
        "meta_dir": str(meta_dir),
    }


def save_json(data, path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def open_zip_for_download(zip_path: str):
    if not zip_path:
        return None
    path = Path(zip_path)
    if not path.exists() or path.stat().st_size <= 0:
        return None
    return open(path, "rb")


def readable_file_size(num_bytes: int) -> str:
    value = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def get_size_label(width, height, mode: str) -> str:
    if mode == "crop_1000":
        return "1000x1000_Crop"
    if width is None or height is None:
        return "original"
    return f"{width}x{height}"


def safe_image_meta(image_path: Path) -> dict:
    try:
        with Image.open(image_path) as img:
            return {
                "width": int(img.width),
                "height": int(img.height),
                "mode": img.mode,
                "format": img.format or image_path.suffix.lower().replace(".", "").upper(),
                "size_bytes": int(image_path.stat().st_size) if image_path.exists() else 0,
            }
    except Exception:
        return {
            "width": 0,
            "height": 0,
            "mode": "?",
            "format": image_path.suffix.lower().replace(".", "").upper(),
            "size_bytes": int(image_path.stat().st_size) if image_path.exists() else 0,
        }


def build_preview_image(src_path: Path, preview_dir: Path, max_size: int = 480) -> str:
    preview_dir = Path(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"preview_{compute_file_hash(str(src_path))}.jpg"
    try:
        with Image.open(src_path) as img:
            img = ImageOps.exif_transpose(img)
            thumb = _convert_to_rgb(img)
            thumb.thumbnail((max_size, max_size), _get_resample_filter())
            thumb.save(preview_path, "JPEG", quality=85, optimize=True)
        return str(preview_path)
    except Exception:
        return str(src_path)


# ─────────────────────────────────────────────────────────────────
# [v10.1 FIX] check_pause_cancel_state — giảm sleep, thêm max_pause
# Lỗi cũ: time.sleep(0.7) block Streamlit main thread → WebSocket timeout
#          khi tải nhiều link → app bị disconnect.
# ─────────────────────────────────────────────────────────────────
def check_pause_cancel_state(max_pause_seconds: float = 600.0) -> bool:
    """
    Kiểm tra trạng thái pause/cancel của download loop.
    Trả True = tiếp tục, False = đã cancel.

    [FIX] sleep 0.7s → 0.2s để giảm WebSocket timeout risk.
    [FIX] max_pause_seconds: tự động resume sau N giây (mặc định 10 phút)
          để tránh bị treo mãi nếu user quên bấm resume.
    """
    paused_since: Optional[float] = None

    while True:
        status = st.session_state.get("download_status", "idle")
        if status == "cancelled":
            return False
        if status == "paused":
            if paused_since is None:
                paused_since = time.time()
            elif time.time() - paused_since > max_pause_seconds:
                # Auto-resume
                st.session_state["download_status"] = "running"
                _log.warning("Auto-resume after %.0fs pause", max_pause_seconds)
                return True
            time.sleep(0.2)    # [FIX] 0.7s → 0.2s
        else:
            return True   # running hoặc idle → tiếp tục


def render_control_buttons():
    """Hiển thị 3 nút điều khiển — phong cách compact."""
    st.markdown('<div class="ctrl-row">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⏸ Tạm dừng", use_container_width=True, key=f"pause_{time.time_ns()}"):
            st.session_state.download_status = "paused"
            st.rerun()
    with c2:
        if st.button("▶ Tiếp tục", use_container_width=True, key=f"resume_{time.time_ns()}"):
            st.session_state.download_status = "running"
            st.rerun()
    with c3:
        if st.button("⏹ Hủy bỏ", type="primary", use_container_width=True, key=f"cancel_{time.time_ns()}"):
            st.session_state.download_status = "cancelled"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════╗
# ║  RESIZE ENGINE                                               ║
# ╚══════════════════════════════════════════════════════════════╝
def _get_resample_filter():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.ANTIALIAS


def _convert_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, (0, 0), img)
        return background.convert("RGB")
    if img.mode == "CMYK":
        return img.convert("RGB")
    return img.convert("RGB")


def _calculate_fit_dimensions(
    src_w: int, src_h: int, dst_w: int, dst_h: int
) -> tuple[int, int]:
    img_ratio = src_w / max(src_h, 1)
    target_ratio = dst_w / max(dst_h, 1)
    if img_ratio > target_ratio:
        fit_width = dst_w
        fit_height = max(int(dst_w / max(img_ratio, 1e-9)), 1)
    else:
        fit_width = max(int(dst_h * img_ratio), 1)
        fit_height = dst_h
    return fit_width, fit_height


def _calc_centered_crop_position(extra_space: int, offset_pct: int) -> int:
    if extra_space <= 0:
        return 0
    center = extra_space / 2.0
    shifted = center + (offset_pct / 100.0) * center
    shifted = max(0, min(extra_space, shifted))
    return int(round(shifted))


def _calc_centered_paste_position(free_space: int, offset_pct: int) -> int:
    if free_space <= 0:
        return 0
    center = free_space / 2.0
    shifted = center + (offset_pct / 100.0) * center
    shifted = max(0, min(free_space, shifted))
    return int(round(shifted))


def _prepare_pillow_image(
    image_path: Path,
    target_hint: tuple[int, int] | None = None,
    huge_image_mode: bool = True,
) -> Image.Image:
    """
    [FIX v11.0 — ANTI-OOM] Thứ tự xử lý được đảo lại so với bản cũ.

    Lỗi cũ: convert RGB TRƯỚC khi thu nhỏ. img.draft() chỉ có tác dụng
    với ảnh JPEG (không hỗ trợ PNG/WebP) → với 1 ảnh PNG/WebP "nặng"
    (vd ảnh chụp màn hình, ảnh scan độ phân giải cao), Pillow phải giải mã
    TOÀN BỘ pixel gốc vào RAM rồi mới thu nhỏ → đỉnh RAM rất cao, kết hợp
    nhiều ảnh xử lý song song (ThreadPoolExecutor) → tràn RAM, sập app.

    Nay: cố downsize bằng thumbnail() NGAY SAU khi mở ảnh (trước convert
    RGB), giảm ngưỡng kích hoạt từ *4 xuống *2 lần kích thước đích → thu
    nhỏ sớm hơn, giảm đáng kể RAM đỉnh cho ảnh siêu lớn.
    """
    img = Image.open(image_path)

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if huge_image_mode and target_hint and target_hint[0] and target_hint[1]:
        # JPEG: draft() giảm RAM giải mã ngay từ lúc mở file (nhanh & rẻ)
        try:
            draft_w = max(int(target_hint[0] * 2.8), 1)
            draft_h = max(int(target_hint[1] * 2.8), 1)
            img.draft("RGB", (draft_w, draft_h))
        except Exception:
            pass

        # [FIX] Thu nhỏ TRƯỚC khi convert RGB — quan trọng nhất với PNG/WebP
        # vì draft() không có tác dụng với các định dạng này.
        try:
            source_long = max(img.width, img.height)
            desired_long = max(target_hint[0], target_hint[1])
            if source_long > desired_long * 2:  # hạ ngưỡng từ *4 → *2
                pre_limit = int(desired_long * 2.4)
                img.thumbnail((pre_limit, pre_limit), _get_resample_filter())
        except Exception:
            pass

    img = _convert_to_rgb(img)
    return img


def _save_output_image(
    final_image: Image.Image,
    output_path: Path,
    quality: int = 95,
    export_format: str = "JPEG (.jpg)",
):
    fmt_info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
    output_path = output_path.with_suffix(fmt_info["ext"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil_format = fmt_info["pil_format"]

    if pil_format == "JPEG":
        final_image.save(
            output_path,
            "JPEG",
            quality=int(quality),
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
        )
    elif pil_format == "PNG":
        final_image.save(output_path, "PNG", optimize=True)
    elif pil_format == "WEBP":
        final_image.save(output_path, "WEBP", quality=int(quality), method=6)
    else:
        final_image.save(output_path)


def crop_photoshop_square(
    image_path: Path,
    output_path: Path,
    target: int = 1000,
    quality: int = 95,
    export_format: str = "JPEG (.jpg)",
):
    try:
        with _prepare_pillow_image(image_path, (target, target), True) as img:
            w, h = img.size
            if w > target or h > target:
                crop_size = min(w, h)
                left = (w - crop_size) // 2
                top = (h - crop_size) // 2
                cropped = img.crop((left, top, left + crop_size, top + crop_size))
                if crop_size > target:
                    cropped = cropped.resize((target, target), _get_resample_filter())
                final_image = cropped
            else:
                final_image = Image.new("RGB", (target, target), (255, 255, 255))
                offset_x = (target - w) // 2
                offset_y = (target - h) // 2
                final_image.paste(img, (offset_x, offset_y))

            _save_output_image(final_image, output_path, quality, export_format)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        _log.error(
            "Crop bỏ qua — ảnh vượt trần an toàn %d px [%s]: %s",
            _MAX_SAFE_PIXELS, image_path.name, exc,
        )
    except Exception as exc:
        _log.warning("Crop error [%s]: %s", image_path.name, exc)


def resize_image(
    image_path: Path,
    output_path: Path,
    width: int = None,
    height: int = None,
    scale_pct: int = 100,
    mode: str = "letterbox",
    quality: int = 95,
    export_format: str = "JPEG (.jpg)",
    offset_x: int = 0,
    offset_y: int = 0,
    huge_image_mode: bool = True,
):
    """Resize ảnh hỗ trợ scale + offset riêng từng ảnh."""
    if mode == "crop_1000":
        crop_photoshop_square(
            image_path, output_path,
            target=1000, quality=quality, export_format=export_format,
        )
        return

    if not width or not height:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_path, output_path)
        return

    try:
        with _prepare_pillow_image(
            image_path,
            target_hint=(
                max(int(width * max(scale_pct, 100) / 100), width),
                max(int(height * max(scale_pct, 100) / 100), height),
            ),
            huge_image_mode=huge_image_mode,
        ) as img:
            fit_width, fit_height = _calculate_fit_dimensions(
                img.width, img.height, width, height
            )
            factor = max(scale_pct, 1) / 100.0
            new_width = max(int(fit_width * factor), 1)
            new_height = max(int(fit_height * factor), 1)

            resized = img.resize((new_width, new_height), _get_resample_filter())
            canvas = Image.new("RGB", (width, height), (255, 255, 255))

            if new_width > width or new_height > height:
                extra_x = max(new_width - width, 0)
                extra_y = max(new_height - height, 0)
                crop_left = _calc_centered_crop_position(extra_x, int(offset_x))
                crop_top = _calc_centered_crop_position(extra_y, int(offset_y))
                crop_box = (
                    crop_left, crop_top,
                    crop_left + min(width, new_width),
                    crop_top + min(height, new_height),
                )
                cropped = resized.crop(crop_box)
                paste_x = _calc_centered_paste_position(
                    max(width - cropped.width, 0), int(offset_x)
                )
                paste_y = _calc_centered_paste_position(
                    max(height - cropped.height, 0), int(offset_y)
                )
                canvas.paste(cropped, (paste_x, paste_y))
            else:
                paste_x = _calc_centered_paste_position(width - new_width, int(offset_x))
                paste_y = _calc_centered_paste_position(height - new_height, int(offset_y))
                canvas.paste(resized, (paste_x, paste_y))

            _save_output_image(canvas, output_path, quality, export_format)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        # [FIX v11.0] Trước đây bị nuốt im lặng bởi warnings.simplefilter("ignore"),
        # khiến app cố giải mã ảnh khổng lồ và OOM crash mà không rõ nguyên nhân.
        # Nay: chặn sớm + log rõ ràng, ảnh này bị bỏ qua thay vì làm sập cả batch.
        _log.error(
            "Resize bỏ qua — ảnh vượt trần an toàn %d px [%s]: %s",
            _MAX_SAFE_PIXELS, image_path.name, exc,
        )
    except (UnidentifiedImageError, OSError) as exc:
        _log.warning("Resize error [%s]: %s", image_path.name, exc)
    except Exception as exc:
        _log.warning("Resize error [%s]: %s", image_path.name, exc)
    finally:
        # [FIX v11.0 — ANTI-OOM] Giải phóng ngay các buffer ảnh trung gian
        # (resized/canvas/cropped có thể vài chục MB mỗi cái) thay vì chờ GC
        # tự động — quan trọng khi resize hàng trăm ảnh liên tiếp trong 1 batch.
        for _tmp_name in ("canvas", "resized", "cropped"):
            _tmp_obj = locals().get(_tmp_name)
            if _tmp_obj is not None:
                try:
                    _tmp_obj.close()
                except Exception:
                    pass


# [FIX v11.0 — ANTI-OOM] Đếm số lần gọi để định kỳ gc.collect().
# Đặt ở đây (thay vì sửa riêng từng vòng lặp trong mode_web/mode_local/
# mode_drive) để áp dụng đồng bộ cho CẢ 3 MODULE cùng lúc — đúng yêu cầu
# đồng bộ tính năng batch, không cần sửa 3 nơi.
_resize_call_counter = 0
_GC_EVERY_N_IMAGES = 6


def resize_to_multi_sizes(
    src_path: Path,
    final_dir: Path,
    folder_name: str,
    file_stem: str,
    sizes: list,
    scale_pct: int = 100,
    quality: int = 95,
    export_format: str = "JPEG (.jpg)",
    per_image_settings: dict | None = None,
    huge_image_mode: bool = True,
):
    """Resize 1 ảnh sang nhiều kích thước cùng lúc."""
    global _resize_call_counter

    fmt_info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
    is_multi = len(sizes) > 1
    item_scale = int((per_image_settings or {}).get("scale_pct", scale_pct))
    item_offset_x = int((per_image_settings or {}).get("offset_x", 0))
    item_offset_y = int((per_image_settings or {}).get("offset_y", 0))

    for target_w, target_h, resize_mode in sizes:
        size_label = get_size_label(target_w, target_h, resize_mode)
        if is_multi:
            output_dir = final_dir / size_label / folder_name
        else:
            output_dir = final_dir / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{file_stem}{fmt_info['ext']}"
        resize_image(
            src_path, output_file,
            width=target_w, height=target_h,
            scale_pct=item_scale, mode=resize_mode,
            quality=quality, export_format=export_format,
            offset_x=item_offset_x, offset_y=item_offset_y,
            huge_image_mode=huge_image_mode,
        )

    # [FIX v11.0 — ANTI-OOM] Batch nhiều trăm ảnh liên tiếp có thể tích tụ
    # rác tham chiếu vòng (Pillow ImageFile) mà GC thế hệ 0 không dọn kịp,
    # đặc biệt khi chạy trong nhiều ThreadPoolExecutor worker song song.
    # Ép gc.collect() định kỳ (không phải mỗi ảnh — tốn CPU) để giữ RAM ổn định
    # xuyên suốt batch dài thay vì tăng dần tới lúc bị Streamlit Cloud kill.
    _resize_call_counter += 1
    if _resize_call_counter % _GC_EVERY_N_IMAGES == 0:
        gc.collect()


# ╔══════════════════════════════════════════════════════════════╗
# ║  NAMING TEMPLATE                                             ║
# ╚══════════════════════════════════════════════════════════════╝
def apply_name_template(
    template: str,
    name: str = "",
    color: str = "",
    index: int = 1,
    original: str = "",
) -> str:
    result = template
    result = result.replace("{name}", name)
    result = result.replace("{color}", color)
    result = result.replace("{nn}", f"{index:02d}")
    result = result.replace("{nnn}", f"{index:03d}")
    result = result.replace("{original}", original)
    result = re.sub(r'[\\/*?:"<>|]', "", result)
    result = re.sub(r"_+", "_", result).strip("_")
    return result or f"image_{index:02d}"


def batch_rename_with_template(final_dir: Path, template: str = "{name}_{nn}") -> int:
    renamed_count = 0
    leaf_directories: set = set()
    for file_path in final_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
            leaf_directories.add(file_path.parent)

    for folder in sorted(leaf_directories):
        relative_path = folder.relative_to(final_dir)
        path_parts = [part for part in relative_path.parts if part]
        name_parts = [
            part for part in path_parts
            if not re.match(r"^\d+x\d+", part)
            and part != "original"
            and "Crop" not in part
        ]

        product_name = name_parts[0] if len(name_parts) >= 1 else "image"
        color_name = name_parts[1] if len(name_parts) >= 2 else ""
        product_name = re.sub(r"\s+", "_", product_name).strip("_")
        color_name = re.sub(r"\s+", "_", color_name).strip("_")

        images = sorted([
            f for f in folder.iterdir()
            if f.is_file()
            and f.suffix.lower() in IMAGE_EXTENSIONS
            and not f.name.startswith("__tmp_")
        ])
        if not images:
            continue

        temp_mapping = []
        for idx, img_path in enumerate(images, start=1):
            original_stem = img_path.stem
            temp_name = f"__tmp_rename_{idx:04d}{img_path.suffix}"
            temp_path = folder / temp_name
            img_path.rename(temp_path)

            new_name = apply_name_template(
                template,
                name=product_name, color=color_name,
                index=idx, original=original_stem,
            )
            final_name = f"{new_name}{img_path.suffix}"
            temp_mapping.append((temp_path, final_name))

        for temp_path, final_name in temp_mapping:
            final_path = folder / final_name
            temp_path.rename(final_path)
            renamed_count += 1

    return renamed_count


# ╔══════════════════════════════════════════════════════════════╗
# ║  ZIP / PREVIEW / SUMMARY                                     ║
# ╚══════════════════════════════════════════════════════════════╝
def make_zip(source_dir: Path, zip_path: Path, compresslevel: int = 6):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        zip_path, "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=max(0, min(9, int(compresslevel))),
    ) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_size > 0:
                zf.write(file_path, file_path.relative_to(source_dir))


def show_preview(final_dir: Path, max_images: int = 6):
    """Preview compact 3 cột."""
    all_images = sorted([
        f for f in final_dir.rglob("*")
        if f.is_file()
        and f.suffix.lower() in IMAGE_EXTENSIONS
        and f.stat().st_size > 0
    ])
    if not all_images:
        return

    preview_images = all_images[:max_images]
    total = len(all_images)
    st.markdown(
        f"<div class='sec-title'>👁 Xem trước ({len(preview_images)}/{total})</div>",
        unsafe_allow_html=True,
    )

    columns = st.columns(min(3, len(preview_images)))
    for idx, img_path in enumerate(preview_images):
        with columns[idx % len(columns)]:
            try:
                with Image.open(img_path) as img:
                    thumb = img.copy()
                    thumb.thumbnail((360, 360), _get_resample_filter())
                    st.image(thumb, caption=img_path.name, use_container_width=True)
                    st.markdown(
                        f"<div class='preview-meta'>{img.width}×{img.height} · "
                        f"{readable_file_size(img_path.stat().st_size)}</div>",
                        unsafe_allow_html=True,
                    )
            except Exception:
                st.caption(f"⚠ {img_path.name}")

    if total > max_images:
        st.caption(f"… và {total - max_images} ảnh khác")


def show_processing_summary(final_dir: Path, sizes: list, duration: float):
    all_files = [
        f for f in final_dir.rglob("*")
        if f.is_file() and f.stat().st_size > 0
    ]
    total_size = sum(f.stat().st_size for f in all_files)
    size_labels = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
    st.markdown(
        f"<div class='summary-card'>"
        f"<b>📊 Tổng kết batch</b><br>"
        f"📁 <b>{len(all_files)}</b> ảnh · "
        f"💾 <b>{readable_file_size(total_size)}</b> · "
        f"⏱ <b>{duration:.1f}s</b><br>"
        f"📐 {size_labels}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_batch_kpis(meta: dict):
    if not meta:
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nguồn", meta.get("source_count", 0))
    col2.metric("Output", meta.get("output_count", 0))
    col3.metric("ZIP", meta.get("zip_size", "0 B"))
    col4.metric("Batch", str(meta.get("batch_id", "-"))[-10:])


# ╔══════════════════════════════════════════════════════════════╗
# ║  HISTORY & SESSION STATS                                     ║
# ╚══════════════════════════════════════════════════════════════╝
def add_to_history(
    source: str,
    detail: str,
    count: int,
    size_label: str,
    duration_sec: float,
):
    init_app_state()
    entry = {
        "time": datetime.now().strftime("%d/%m %H:%M"),
        "source": source,
        "detail": (detail or "")[:60],
        "count": count,
        "size": size_label,
        "duration": f"{duration_sec:.1f}s",
    }
    st.session_state.processing_history.insert(0, entry)
    st.session_state.processing_history = st.session_state.processing_history[:30]

    stats = st.session_state.session_stats
    stats["total_images"] += count
    stats["total_batches"] += 1
    stats["total_time"] += duration_sec


def render_history_sidebar():
    init_app_state()
    history = st.session_state.processing_history
    if not history:
        st.caption("Chưa có lịch sử.")
        return

    icons = {"Drive": "🌐", "Local": "💻", "Web": "🛒", "Adjust": "🎚"}
    for entry in history[:5]:
        icon = icons.get(entry["source"], "📦")
        st.markdown(
            f"<div class='history-item'>"
            f"<div class='hi-top'>{icon} <b>{entry['detail']}</b></div>"
            f"<div class='hi-bot'>{entry['time']} · {entry['count']} ảnh · ⏱ {entry['duration']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    remaining = len(history) - 5
    if remaining > 0:
        st.caption(f"+{remaining} bản ghi cũ")


def render_session_stats():
    init_app_state()
    stats = st.session_state.session_stats
    if stats["total_images"] == 0:
        st.caption("Chưa có dữ liệu phiên.")
        return

    st.markdown(
        f"<div class='stat-row'>"
        f"<div class='stat-pill stat-a'>"
        f"<div class='sp-num'>{stats['total_images']}</div>"
        f"<div class='sp-lbl'>Ảnh</div></div>"
        f"<div class='stat-pill stat-b'>"
        f"<div class='sp-num'>{stats['total_batches']}</div>"
        f"<div class='sp-lbl'>Batch</div></div>"
        f"<div class='stat-pill stat-c'>"
        f"<div class='sp-num'>{stats['total_time']:.0f}s</div>"
        f"<div class='sp-lbl'>Time</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║  MERGE HELPER — v9.1                                         ║
# ║  Gộp FINAL gốc + ADJUSTED, ưu tiên ảnh đã chỉnh khi trùng.  ║
# ╚══════════════════════════════════════════════════════════════╝
def merge_final_with_adjusted(
    final_dir: Path,
    adjusted_dir: Path,
    merged_dir: Path,
) -> dict:
    """
    Gộp FINAL gốc + ADJUSTED thành thư mục mới.
    File trong adjusted_dir ghi đè file cùng relative path trong final_dir.
    """
    merged_dir.mkdir(parents=True, exist_ok=True)
    stats = {"kept": 0, "overridden": 0, "added": 0, "total": 0}

    if final_dir.exists():
        for src in final_dir.rglob("*"):
            if not src.is_file() or src.stat().st_size <= 0:
                continue
            rel = src.relative_to(final_dir)
            dst = merged_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            stats["kept"] += 1

    if adjusted_dir.exists():
        for src in adjusted_dir.rglob("*"):
            if not src.is_file() or src.stat().st_size <= 0:
                continue
            rel = src.relative_to(adjusted_dir)
            dst = merged_dir / rel
            existed = dst.exists()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if existed:
                stats["overridden"] += 1
                stats["kept"] -= 1
            else:
                stats["added"] += 1

    stats["total"] = stats["kept"] + stats["overridden"] + stats["added"]
    return stats


# ╔══════════════════════════════════════════════════════════════╗
# ║  v9.3 — STUDIO LIVE PREVIEW HELPERS (giữ nguyên hoàn toàn)  ║
# ╚══════════════════════════════════════════════════════════════╝
_STUDIO_PREVIEW_MAX = 720


def estimate_default_scale_for_size(
    src_w: int, src_h: int,
    target_w: int, target_h: int,
) -> int:
    if not src_w or not src_h or not target_w or not target_h:
        return 100
    if src_w >= target_w and src_h >= target_h:
        return 100
    ratio_w = target_w / max(src_w, 1)
    ratio_h = target_h / max(src_h, 1)
    needed = max(ratio_w, ratio_h) * 100
    suggested = int(min(max(needed, 100), 130))
    return suggested


def find_rendered_image_for_item(
    item: dict,
    root: Path,
    final_dir: Path,
    adjusted_dir: Path,
    sizes: list,
) -> tuple[str, str]:
    """
    Tìm ảnh đã render thật sự.
    Map theo seq_in_folder (1-based) để chính xác sau khi rename template.
    Ưu tiên: ADJUSTED → FINAL → preview_path → source_path.
    Trả về (path_str, status) với status ∈ {"adjusted","rendered","source"}.
    """
    folder_name = item.get("folder_name", "") or ""
    original_name = item.get("original_name", "") or ""
    seq = int(item.get("seq_in_folder", 0) or 0)
    is_multi = isinstance(sizes, list) and len(sizes) > 1

    size_label = ""
    if sizes:
        try:
            w, h, m = sizes[0]
            size_label = get_size_label(w, h, m)
        except Exception:
            size_label = ""

    candidate_dirs: list[tuple[str, Path]] = []
    if adjusted_dir and adjusted_dir.exists():
        if is_multi and size_label:
            candidate_dirs.append(("adjusted", adjusted_dir / size_label / folder_name))
        candidate_dirs.append(("adjusted", adjusted_dir / folder_name))
    if final_dir and final_dir.exists():
        if is_multi and size_label:
            candidate_dirs.append(("rendered", final_dir / size_label / folder_name))
        candidate_dirs.append(("rendered", final_dir / folder_name))

    for status, d in candidate_dirs:
        if not d.exists() or not d.is_dir():
            continue

        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = d / f"{original_name}{ext}"
            if p.exists() and p.stat().st_size > 0:
                return str(p), status

        try:
            files_sorted = sorted([
                f for f in d.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                and not f.name.startswith("__tmp_")
                and f.stat().st_size > 0
            ])
            if seq and 1 <= seq <= len(files_sorted):
                return str(files_sorted[seq - 1]), status
            if original_name:
                for f in files_sorted:
                    if original_name in f.stem:
                        return str(f), status
            if files_sorted:
                return str(files_sorted[0]), status
        except Exception:
            pass

    fallback = item.get("preview_path") or item.get("source_path") or ""
    return fallback, "source"


def build_live_preview_b64(image_path: str, max_size: int = _STUDIO_PREVIEW_MAX) -> str:
    """
    Đọc ảnh đã render, thumbnail → base64 JPEG cho Studio Live Preview.
    Cache theo path+mtime để không đọc lại nhiều lần.
    """
    if not image_path:
        return ""
    p = Path(image_path)
    if not p.exists() or p.stat().st_size <= 0:
        return ""

    cache = st.session_state.setdefault("_studio_thumb_b64_cache", {})
    cache_key = f"{p}|{p.stat().st_mtime_ns}|{max_size}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        with Image.open(p) as img:
            img = ImageOps.exif_transpose(img)
            img = _convert_to_rgb(img)
            img.thumbnail((max_size, max_size), _get_resample_filter())
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=85, optimize=True)
            data = buf.getvalue()
        b64 = base64.b64encode(data).decode("ascii")
        data_uri = f"data:image/jpeg;base64,{b64}"
        if len(cache) > 300:
            cache.clear()
        cache[cache_key] = data_uri
        return data_uri
    except Exception:
        return ""
