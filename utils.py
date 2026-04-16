import os
import re
import time
import requests
import streamlit as st
from pathlib import Path
from PIL import Image
import gdown
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ══════════════════════════════════════════════════════════════
# GOOGLE DRIVE SERVICE
# ══════════════════════════════════════════════════════════════
def get_gdrive_service():
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
    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    f = service.files().create(body=meta, fields="id").execute()
    return f.get("id")


def upload_to_drive(service, file_path, target_folder_id: str) -> str:
    meta = {"name": os.path.basename(file_path), "parents": [target_folder_id]}
    media = MediaFileUpload(file_path, mimetype="image/jpeg", resumable=True)
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    return f.get("id")


# ══════════════════════════════════════════════════════════════
# EXTRACT DRIVE ID / TYPE
# ══════════════════════════════════════════════════════════════
def extract_drive_id_and_type(url: str):
    if not url or not url.strip():
        return None, None
    fm = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    fi = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    im = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if fm:  return fm.group(1), "folder"
    if fi:  return fi.group(1), "file"
    if im:  return im.group(1), "file"
    return None, None


# ══════════════════════════════════════════════════════════════
# LẤY TÊN FILE/FOLDER TỪ DRIVE
# ══════════════════════════════════════════════════════════════
def get_drive_name(file_id: str, kind: str) -> str:
    """Lấy tên từ Drive API public, fallback về scrape HTML title."""
    # Phương thức 1: Drive API (không cần key với file public)
    try:
        r = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name&supportsAllDrives=true",
            timeout=8,
        )
        if r.status_code == 200:
            name = r.json().get("name", "").strip()
            if name:
                return re.sub(r'[\\/\*?:"<>|]', "", name).strip()
    except Exception:
        pass

    # Phương thức 2: scrape <title>
    try:
        url = (
            f"https://drive.google.com/file/d/{file_id}/view"
            if kind == "file"
            else f"https://drive.google.com/drive/folders/{file_id}"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            m = re.search(r"<title>(.*?) - Google Drive</title>", r.text)
            if m:
                name = re.sub(r'[\\/\*?:"<>|]', "", m.group(1)).strip()
                if name:
                    return name
    except Exception:
        pass

    return file_id


# ══════════════════════════════════════════════════════════════
# TẢI FILE ĐƠN TỪ DRIVE (multi-method)
# ══════════════════════════════════════════════════════════════
def download_direct_file(file_id: str, save_folder: Path, drive_name: str) -> Path:
    """
    Tải 1 file ảnh từ Drive.
    Trả về Path file đã tải (có thể chưa tồn tại nếu thất bại).
    """
    save_folder.mkdir(parents=True, exist_ok=True)
    save_path = save_folder / f"{drive_name}.jpg"

    # Phương thức 1: gdown fuzzy
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        out = gdown.download(url, str(save_path), quiet=True, fuzzy=True)
        if out and Path(out).exists() and Path(out).stat().st_size > 2048:
            return save_path
    except Exception:
        pass

    # Phương thức 2: requests stream + confirm token
    try:
        sess = requests.Session()
        hdrs = {"User-Agent": "Mozilla/5.0"}
        url  = f"https://drive.google.com/uc?export=download&id={file_id}"
        resp = sess.get(url, headers=hdrs, stream=True, timeout=30)

        # Xử lý trang confirm "virus scan"
        if "Content-Disposition" not in resp.headers:
            token = None
            for k, v in resp.cookies.items():
                if k.startswith("download_warning"):
                    token = v
                    break
            if not token:
                m = re.search(r"confirm=([0-9A-Za-z_\-]+)", resp.text)
                token = m.group(1) if m else "t"
            url  = f"https://drive.google.com/uc?export=download&confirm={token}&id={file_id}"
            resp = sess.get(url, headers=hdrs, stream=True, timeout=30)

        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(32768):
                    if chunk:
                        f.write(chunk)
            if save_path.exists() and save_path.stat().st_size > 2048:
                return save_path
    except Exception as e:
        print(f"[download_direct_file] {e}")

    return save_path


# ══════════════════════════════════════════════════════════════
# RESIZE ẢNH — LETTERBOX (giữ tỉ lệ, fill trắng, không méo)
# ══════════════════════════════════════════════════════════════
def resize_image(image_path: Path, output_path: Path, width=None, height=None):
    """
    Resize ảnh về width×height.
    - Giữ nguyên tỉ lệ gốc (không méo)
    - Phần thừa fill màu trắng (letterbox)
    - Xuất JPEG chất lượng 95
    """
    # Không resize → copy nguyên
    if not width or not height:
        import shutil
        try:
            shutil.copy2(image_path, output_path)
        except Exception:
            pass
        return

    try:
        with Image.open(image_path) as img:
            # Chuẩn hóa về RGB (xử lý RGBA, P, LA...)
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, (0, 0), img if img.mode == "RGBA" else img.convert("RGBA"))
                img = bg.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            orig_w, orig_h = img.size
            if orig_w == 0 or orig_h == 0:
                return

            # Bộ lọc resize chất lượng cao
            try:
                flt = Image.Resampling.LANCZOS
            except AttributeError:
                flt = Image.ANTIALIAS  # Pillow < 9

            # Scale FIT — không crop, không stretch
            ratio_w = width  / orig_w
            ratio_h = height / orig_h
            scale   = min(ratio_w, ratio_h)
            new_w   = max(1, int(orig_w * scale))
            new_h   = max(1, int(orig_h * scale))

            resized = img.resize((new_w, new_h), flt)

            # Canvas trắng, dán ảnh căn giữa
            canvas = Image.new("RGB", (width, height), (255, 255, 255))
            paste_x = (width  - new_w) // 2
            paste_y = (height - new_h) // 2
            canvas.paste(resized, (paste_x, paste_y))

            output_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(output_path, "JPEG", quality=95, optimize=True)

    except Exception as e:
        print(f"[resize_image] Lỗi '{image_path.name}': {e}")


# ══════════════════════════════════════════════════════════════
# TIỆN ÍCH
# ══════════════════════════════════════════════════════════════
def ignore_system_files(path: Path) -> bool:
    n = path.name
    return (
        n.startswith("._")
        or n == ".DS_Store"
        or "__MACOSX" in str(path)
        or n.lower() == "thumbs.db"
    )


def check_pause_cancel_state() -> bool:
    """True = tiếp tục, False = đã hủy."""
    while st.session_state.get("download_status") == "paused":
        time.sleep(0.5)
    return st.session_state.get("download_status") != "cancelled"


def render_control_buttons():
    st.markdown('<div class="control-box">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⏸️ Tạm dừng", use_container_width=True, key="_btn_pause"):
            st.session_state.download_status = "paused"
            st.rerun()
    with c2:
        if st.button("▶️ Tiếp tục", use_container_width=True, key="_btn_resume"):
            st.session_state.download_status = "running"
            st.rerun()
    with c3:
        if st.button("⏹️ Hủy bỏ", type="primary", use_container_width=True, key="_btn_cancel"):
            st.session_state.download_status = "cancelled"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
