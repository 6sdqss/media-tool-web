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

# ─────────────────────────────────────────────
# GOOGLE DRIVE SERVICE
# ─────────────────────────────────────────────
def get_gdrive_service():
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = service_account.Credentials.from_service_account_info(
                creds_info, scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except Exception:
        pass
    try:
        if os.path.exists('credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except Exception:
        pass
    return None


def create_drive_folder(service, folder_name, parent_id):
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')


def upload_to_drive(service, file_path, target_folder_id):
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [target_folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/jpeg', resumable=True)
    file = service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()
    return file.get('id')


# ─────────────────────────────────────────────
# EXTRACT DRIVE ID / TYPE
# ─────────────────────────────────────────────
def extract_drive_id_and_type(url: str):
    if not url or not url.strip():
        return None, None
    folder_match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    file_match   = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    id_match     = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if folder_match:
        return folder_match.group(1), "folder"
    elif file_match:
        return file_match.group(1), "file"
    elif id_match:
        return id_match.group(1), "file"
    return None, None


# ─────────────────────────────────────────────
# LẤY TÊN FILE/FOLDER TỪ GOOGLE DRIVE
# ─────────────────────────────────────────────
def get_drive_name(file_id: str, kind: str) -> str:
    """
    Lấy tên file/folder từ Google Drive qua API public metadata.
    Ưu tiên dùng API không cần xác thực, fallback về scrape HTML title.
    """
    # Phương thức 1: dùng Drive API public (không cần key)
    try:
        api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name&supportsAllDrives=true"
        resp = requests.get(api_url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("name", "").strip()
            if name:
                return re.sub(r'[\\/\*?:"<>|]', "", name).strip()
    except Exception:
        pass

    # Phương thức 2: scrape title từ trang HTML
    try:
        if kind == "file":
            view_url = f"https://drive.google.com/file/d/{file_id}/view"
        else:
            view_url = f"https://drive.google.com/drive/folders/{file_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(view_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if match:
                name = re.sub(r'[\\/\*?:"<>|]', "", match.group(1)).strip()
                name = name.replace(" - Google Drive", "")
                if name:
                    return name
    except Exception:
        pass

    return file_id


# ─────────────────────────────────────────────
# TẢI FILE ĐƠN LẺ TỪ DRIVE (nhiều phương thức)
# ─────────────────────────────────────────────
def download_direct_file(file_id: str, save_folder: Path, drive_name: str) -> Path:
    """
    Tải 1 file ảnh từ Google Drive về máy.
    Thử lần lượt: gdown fuzzy → direct export → requests stream
    """
    save_folder.mkdir(parents=True, exist_ok=True)
    save_path = save_folder / f"{drive_name}.jpg"

    # Phương thức 1: gdown fuzzy
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        result = gdown.download(url, str(save_path), quiet=True, fuzzy=True)
        if result and Path(result).exists() and Path(result).stat().st_size > 1024:
            return save_path
    except Exception:
        pass

    # Phương thức 2: requests stream với confirm token
    try:
        session = requests.Session()
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = session.get(url, headers=headers, stream=True, timeout=30)

        # Xử lý trang xác nhận virus scan của Google
        if "Content-Disposition" not in response.headers:
            # Tìm confirm token
            confirm_token = None
            for key, value in response.cookies.items():
                if key.startswith("download_warning"):
                    confirm_token = value
                    break
            if not confirm_token:
                match = re.search(r'confirm=([0-9A-Za-z_\-]+)', response.text)
                confirm_token = match.group(1) if match else "t"

            url2 = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
            response = session.get(url2, headers=headers, stream=True, timeout=30)

        if response.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            if save_path.exists() and save_path.stat().st_size > 1024:
                return save_path
    except Exception as e:
        print(f"[download_direct_file] Lỗi: {e}")

    return save_path


# ─────────────────────────────────────────────
# RESIZE ẢNH – GIỮ TỈ LỆ, NỀN TRẮNG, ĐẸP
# ─────────────────────────────────────────────
def resize_image(image_path: Path, output_path: Path, width=None, height=None):
    """
    Resize ảnh về đúng kích thước width×height, giữ tỉ lệ gốc,
    phần thừa fill trắng (letterbox). Không bao giờ méo ảnh.
    """
    if not width or not height:
        import shutil
        shutil.copy2(image_path, output_path)
        return

    try:
        with Image.open(image_path) as img:
            # Chuẩn hóa mode về RGB
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            else:
                img = img.convert("RGB")

            # Chọn bộ lọc resize tốt nhất
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.ANTIALIAS  # Pillow < 9

            orig_w, orig_h = img.size
            if orig_w == 0 or orig_h == 0:
                return

            img_ratio    = orig_w / orig_h
            target_ratio = width / height

            # Scale để FIT bên trong khung, không crop
            if img_ratio > target_ratio:
                new_w = width
                new_h = max(1, int(width / img_ratio))
            else:
                new_h = height
                new_w = max(1, int(height * img_ratio))

            resized = img.resize((new_w, new_h), resample_filter)

            # Dán vào nền trắng, căn giữa
            canvas = Image.new("RGB", (width, height), (255, 255, 255))
            offset_x = (width  - new_w) // 2
            offset_y = (height - new_h) // 2
            canvas.paste(resized, (offset_x, offset_y))
            canvas.save(output_path, "JPEG", quality=95, optimize=True)

    except Exception as e:
        print(f"[resize_image] Lỗi resize '{image_path}': {e}")


# ─────────────────────────────────────────────
# TIỆN ÍCH
# ─────────────────────────────────────────────
def ignore_system_files(path: Path) -> bool:
    """Bỏ qua các file hệ thống macOS / Windows."""
    return (
        path.name.startswith("._")
        or path.name == ".DS_Store"
        or path.name.startswith("__MACOSX")
        or path.name.startswith("Thumbs")
    )


def check_pause_cancel_state() -> bool:
    """
    Kiểm tra trạng thái tạm dừng / hủy.
    Trả về True nếu được tiếp tục, False nếu đã hủy.
    """
    while st.session_state.get("download_status") == "paused":
        time.sleep(0.5)
    return st.session_state.get("download_status") != "cancelled"


def render_control_buttons():
    """Hiển thị 3 nút điều khiển: Tạm dừng / Tiếp tục / Hủy."""
    st.markdown(
        '<div class="control-box">',
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⏸️ Tạm dừng", use_container_width=True, key="btn_pause"):
            st.session_state.download_status = "paused"
            st.rerun()
    with col2:
        if st.button("▶️ Tiếp tục", use_container_width=True, key="btn_resume"):
            st.session_state.download_status = "running"
            st.rerun()
    with col3:
        if st.button("⏹️ Hủy bỏ", type="primary", use_container_width=True, key="btn_cancel"):
            st.session_state.download_status = "cancelled"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
