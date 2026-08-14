"""
core/download.py — engine tải file trung tâm.
Streaming, retry backoff phân loại lỗi, verify magic bytes trước khi trả path.
"""
from __future__ import annotations

import io
import logging
import re
import time
from pathlib import Path
from typing import Callable, Optional

from .imaging import is_real_image_file
from .memory import MAX_SOURCE_FILE_BYTES
from .types import ErrorType
from .validation import clean_name


_log = logging.getLogger("core.download")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


# ══════════════════════════════════════════════════════════════
# HTTP DOWNLOAD (streaming)
# ══════════════════════════════════════════════════════════════
def download_http(
    url: str,
    dest: Path,
    *,
    timeout: tuple[int, int] = (12, 45),
    max_size: int = MAX_SOURCE_FILE_BYTES,
    headers: Optional[dict] = None,
    verify_image: bool = True,
) -> tuple[bool, Optional[ErrorType], str]:
    """
    Tải 1 URL trực tiếp về `dest` bằng streaming (chunk 256KB).
    Kiểm tra content-length, magic bytes.
    Trả (success, error_type, message).
    """
    try:
        import requests
    except ImportError:
        return False, ErrorType.DOWNLOAD_FAILED, "requests không có sẵn"

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    hdr = {"User-Agent": DEFAULT_UA}
    if headers:
        hdr.update(headers)

    try:
        with requests.get(url, stream=True, timeout=timeout, headers=hdr,
                          allow_redirects=True) as resp:
            if resp.status_code == 429:
                return False, ErrorType.DRIVE_RATE_LIMIT, "HTTP 429"
            if resp.status_code == 403:
                return False, ErrorType.DRIVE_PERMISSION, "HTTP 403"
            if resp.status_code == 404:
                return False, ErrorType.DRIVE_NOT_FOUND, "HTTP 404"
            if resp.status_code != 200:
                return False, ErrorType.DOWNLOAD_FAILED, f"HTTP {resp.status_code}"

            # Content-Length check trước khi bắt đầu ghi
            length_hdr = resp.headers.get("Content-Length")
            if length_hdr and length_hdr.isdigit():
                if int(length_hdr) > max_size:
                    return False, ErrorType.FILE_TOO_LARGE, f"{int(length_hdr)/1e6:.1f}MB"

            total = 0
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)
                    if total > max_size:
                        try:
                            tmp.unlink(missing_ok=True)
                        except Exception:
                            pass
                        return False, ErrorType.FILE_TOO_LARGE, f"{total/1e6:.1f}MB"

            if total < 512:
                tmp.unlink(missing_ok=True)
                return False, ErrorType.DOWNLOAD_FAILED, "File tải về quá nhỏ"

            if verify_image and not is_real_image_file(tmp):
                tmp.unlink(missing_ok=True)
                return False, ErrorType.INVALID_IMAGE, "Không phải file ảnh hợp lệ"

            tmp.replace(dest)
            return True, None, ""

    except requests.exceptions.Timeout:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        return False, ErrorType.DOWNLOAD_TIMEOUT, "Timeout"
    except requests.exceptions.ConnectionError as exc:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        return False, ErrorType.DOWNLOAD_FAILED, f"Connection: {str(exc)[:80]}"
    except Exception as exc:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        _log.exception("download_http failed url=%s", url[:80])
        return False, ErrorType.DOWNLOAD_FAILED, str(exc)[:120]


# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE
# ══════════════════════════════════════════════════════════════
def _drive_direct_url(file_id: str) -> str:
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


def _drive_fallback_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def download_drive_file(
    file_id: str,
    dest_dir: Path,
    name_hint: str = "drive",
    *,
    service=None,
    max_retries: int = 3,
) -> tuple[Optional[Path], Optional[ErrorType], str]:
    """
    Tải 1 file Drive. Ưu tiên Drive API (service account) → requests+confirm token.
    Trả (path, error_type, message).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name_hint = clean_name(name_hint) or "drive_file"

    # ── Route 1: Drive API ───────────────────────────────
    if service is not None:
        try:
            meta = service.files().get(
                fileId=file_id, fields="name,mimeType,size",
                supportsAllDrives=True,
            ).execute()
            real_name = meta.get("name", "")
            size = int(meta.get("size", 0) or 0)
            if size > MAX_SOURCE_FILE_BYTES:
                return None, ErrorType.FILE_TOO_LARGE, f"{size/1e6:.1f}MB"

            ext = Path(real_name).suffix.lower() if real_name else ".jpg"
            if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}:
                ext = ".jpg"
            api_path = dest_dir / f"{name_hint}{ext}"

            ok = _api_download_stream(service, file_id, api_path)
            if ok and api_path.exists() and is_real_image_file(api_path):
                return api_path, None, ""
            api_path.unlink(missing_ok=True)
        except Exception as exc:
            _log.warning("Drive API path failed: %s", exc)

    # ── Route 2: requests với confirm token ──────────────
    for attempt in range(1, max_retries + 1):
        for base_url in (_drive_direct_url(file_id), _drive_fallback_url(file_id)):
            out_path = dest_dir / f"{name_hint}.jpg"  # ext sẽ điều chỉnh sau
            ok, err, msg = _drive_download_requests(base_url, file_id, out_path)
            if ok:
                # Sửa ext theo magic bytes thật
                real_ext = _detect_ext(out_path)
                if real_ext and real_ext != out_path.suffix.lower():
                    new_path = out_path.with_suffix(real_ext)
                    try:
                        out_path.rename(new_path)
                        out_path = new_path
                    except Exception:
                        pass
                return out_path, None, ""
            if err in (ErrorType.DRIVE_PERMISSION, ErrorType.DRIVE_NOT_FOUND):
                return None, err, msg
        if attempt < max_retries:
            time.sleep(1.5 * attempt)

    return None, ErrorType.DOWNLOAD_FAILED, "Đã thử hết các phương án"


def _api_download_stream(service, file_id: str, save_path: Path) -> bool:
    """Stream Drive API → file. Không đưa toàn bộ vào RAM."""
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError:
        return False

    tmp = save_path.with_suffix(save_path.suffix + ".tmp")
    try:
        request = service.files().get_media(fileId=file_id)
        with io.FileIO(str(tmp), mode="wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=4 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        if tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(save_path)
            return True
    except Exception:
        pass
    tmp.unlink(missing_ok=True)
    return False


def _drive_download_requests(
    base_url: str, file_id: str, out_path: Path,
) -> tuple[bool, Optional[ErrorType], str]:
    """Tải qua requests, xử lý confirm token nếu Google trả HTML."""
    try:
        import requests
    except ImportError:
        return False, ErrorType.DOWNLOAD_FAILED, "requests không có"

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_UA})

    try:
        resp = session.get(base_url, stream=True, timeout=(12, 60), allow_redirects=True)
        if resp.status_code == 429:
            return False, ErrorType.DRIVE_RATE_LIMIT, "HTTP 429"
        if resp.status_code == 403:
            return False, ErrorType.DRIVE_PERMISSION, "HTTP 403"
        if resp.status_code == 404:
            return False, ErrorType.DRIVE_NOT_FOUND, "HTTP 404"
        if resp.status_code != 200:
            return False, ErrorType.DOWNLOAD_FAILED, f"HTTP {resp.status_code}"

        # Nếu Content-Type là HTML → confirm token page
        ct = resp.headers.get("Content-Type", "")
        if "text/html" in ct:
            first_chunk = next(resp.iter_content(8192), b"")
            m = re.search(rb"confirm=([0-9A-Za-z_\-]+)", first_chunk)
            if m:
                token = m.group(1).decode("ascii")
                confirm_url = f"{_drive_fallback_url(file_id)}&confirm={token}"
                resp = session.get(confirm_url, stream=True, timeout=(12, 120), allow_redirects=True)
                if resp.status_code != 200:
                    return False, ErrorType.DOWNLOAD_FAILED, f"HTTP {resp.status_code} (confirm)"
            else:
                return False, ErrorType.DRIVE_PERMISSION, "HTML page không có confirm token"

        total = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=512 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                total += len(chunk)
                if total > MAX_SOURCE_FILE_BYTES:
                    tmp.unlink(missing_ok=True)
                    return False, ErrorType.FILE_TOO_LARGE, f"{total/1e6:.1f}MB"

        if total < 512 or not is_real_image_file(tmp):
            tmp.unlink(missing_ok=True)
            return False, ErrorType.INVALID_IMAGE, "File không phải ảnh"

        tmp.replace(out_path)
        return True, None, ""

    except requests.exceptions.Timeout:
        tmp.unlink(missing_ok=True)
        return False, ErrorType.DOWNLOAD_TIMEOUT, "Timeout"
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return False, ErrorType.DOWNLOAD_FAILED, str(exc)[:120]


def _detect_ext(path: Path) -> str:
    """Đọc magic bytes để xác định extension đúng."""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except Exception:
        return ""
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:4] == b"GIF8":
        return ".gif"
    if head[:2] == b"BM":
        return ".bmp"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return ""


# ══════════════════════════════════════════════════════════════
# DRIVE FOLDER LISTING
# ══════════════════════════════════════════════════════════════
def list_drive_folder(service, folder_id: str) -> list[dict]:
    """
    Liệt kê toàn bộ ảnh trong folder Drive (bao gồm subfolder).
    Yêu cầu service account. Trả [] nếu không có service.
    """
    if service is None:
        return []
    mimes = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/tiff"]
    q_mime = " or ".join([f"mimeType='{m}'" for m in mimes])
    query = f"'{folder_id}' in parents and ({q_mime}) and trashed=false"

    results: list[dict] = []
    page_token = None
    while True:
        try:
            resp = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageSize=100, pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            results.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        except Exception as exc:
            _log.warning("list_drive_folder page error: %s", exc)
            break

    # Đệ quy subfolder
    try:
        sub_q = (f"'{folder_id}' in parents and "
                 f"mimeType='application/vnd.google-apps.folder' and trashed=false")
        sub_resp = service.files().list(
            q=sub_q, fields="files(id, name)", pageSize=50,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        for sub in sub_resp.get("files", []):
            results.extend(list_drive_folder(service, sub["id"]))
    except Exception:
        pass

    return results


def drive_name_scrape(file_id: str, kind: str) -> str:
    """Fallback lấy tên file/folder khi không có Drive API."""
    try:
        import requests
    except ImportError:
        return f"Drive_{file_id[:8]}"

    url = (f"https://drive.google.com/file/d/{file_id}/view"
           if kind == "drive_file" else
           f"https://drive.google.com/drive/folders/{file_id}")
    try:
        resp = requests.get(url, timeout=(8, 12), headers={"User-Agent": DEFAULT_UA})
        if resp.status_code == 200:
            m = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if m:
                nm = clean_name(m.group(1))
                if nm and nm.lower() not in ("google_drive", "unnamed"):
                    return nm
    except Exception:
        pass
    return f"Drive_{file_id[:8]}"
