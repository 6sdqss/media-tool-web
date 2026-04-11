import os
import re
import time
import streamlit as st
from pathlib import Path
from PIL import Image
import gdown
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_gdrive_service():
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = service_account.Credentials.from_service_account_info(
                creds_info, scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except: pass
    try:
        if os.path.exists('credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except: pass
    return None

def create_drive_folder(service, folder_name, parent_id):
    file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

def upload_to_drive(service, file_path, target_folder_id):
    file_metadata = {'name': os.path.basename(file_path), 'parents': [target_folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg', resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def extract_drive_id_and_type(url: str):
    folder_match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    file_match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    id_match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if folder_match: return folder_match.group(1), "folder"
    elif file_match: return file_match.group(1), "file"
    elif id_match: return id_match.group(1), "file"
    return None, None

def get_drive_name(file_id: str, kind: str):
    import requests
    try:
        url = f"https://drive.google.com/file/d/{file_id}/view" if kind == "file" else f"https://drive.google.com/drive/folders/{file_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if match:
                name = re.sub(r'[\\/*?:"<>|]', "", match.group(1)).strip()
                return name.replace(" - Google Drive", "")
    except: pass
    return file_id

def download_direct_file(file_id: str, save_folder: Path, drive_name: str):
    save_path = save_folder / f"{drive_name}.jpg"
    try:
        url = f'https://drive.google.com/uc?id={file_id}'
        gdown.download(url, str(save_path), quiet=True, fuzzy=True)
    except Exception as e:
        print(f"Lỗi tải file trực tiếp: {e}")
    return save_path

def resize_image(image_path: Path, output_path: Path, width=None, height=None):
    if not width or not height:
        import shutil
        shutil.copy2(image_path, output_path)
        return
    try:
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            else: img = img.convert("RGB")

            img_ratio = img.width / img.height
            target_ratio = width / height
            new_w, new_h = (width, int(width / img_ratio)) if img_ratio > target_ratio else (int(height * img_ratio), height)
            
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            new_img = Image.new("RGB", (width, height), (255, 255, 255))
            new_img.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
            new_img.save(output_path, "JPEG", quality=95)
    except Exception as e:
        print(f"Resize error: {e}")

def ignore_system_files(path: Path):
    return path.name.startswith("._") or path.name == ".DS_Store" or path.name.startswith("__MACOSX")

def check_pause_cancel_state():
    while st.session_state.download_status == 'paused':
        time.sleep(1)
    if st.session_state.download_status == 'cancelled':
        return False
    return True

def render_control_buttons():
    st.markdown('<div class="control-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⏸️ Tạm dừng", use_container_width=True):
            st.session_state.download_status = 'paused'
            st.rerun()
    with col2:
        if st.button("▶️ Tiếp tục", use_container_width=True):
            st.session_state.download_status = 'running'
            st.rerun()
    with col3:
        if st.button("⏹️ Hủy bỏ", type="primary", use_container_width=True):
            st.session_state.download_status = 'cancelled'
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
