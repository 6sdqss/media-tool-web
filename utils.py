import os
import re
import io
import time
import streamlit as st
from pathlib import Path
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


def get_gdrive_service():
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = service_account.Credentials.from_service_account_info(
                creds_info, scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except:
        pass
    try:
        if os.path.exists('credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except:
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
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')


def extract_drive_id_and_type(url: str):
    if not url:
        return None, None
    folder_match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    file_match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    id_match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if folder_match:
        return folder_match.group(1), "folder"
    elif file_match:
        return file_match.group(1), "file"
    elif id_match:
        return id_match.group(1), "file"
    return None, None


# ============================================================
# DRIVE API FUNCTIONS
# ============================================================

def api_get_file_name(service, file_id):
    try:
        meta = service.files().get(fileId=file_id, fields='name', supportsAllDrives=True).execute()
        return meta.get('name', file_id)
    except Exception as e:
        print(f"[API] Không lấy được tên cho {file_id}: {e}")
        return file_id


def api_download_file(service, file_id, save_path: Path):
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(fh.getvalue())
        return True
    except Exception as e:
        print(f"[API] Lỗi tải file {file_id}: {e}")
        return False


def api_list_folder_images(service, folder_id):
    image_mimes = [
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "image/bmp", "image/tiff"
    ]
    mime_query = " or ".join([f"mimeType='{m}'" for m in image_mimes])
    query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"

    results = []
    page_token = None
    while True:
        try:
            resp = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100, pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True
            ).execute()
            results.extend(resp.get('files', []))
            page_token = resp.get('nextPageToken')
            if not page_token:
                break
        except Exception as e:
            print(f"[API] Lỗi liệt kê folder {folder_id}: {e}")
            break

    subfolder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    try:
        sub_resp = service.files().list(
            q=subfolder_query, fields="files(id, name)", pageSize=50,
            supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()
        for subfolder in sub_resp.get('files', []):
            sub_images = api_list_folder_images(service, subfolder['id'])
            results.extend(sub_images)
    except Exception as e:
        print(f"[API] Lỗi liệt kê subfolder: {e}")

    return results


def api_download_folder_images(service, folder_id, save_dir: Path, max_files=None):
    images = api_list_folder_images(service, folder_id)
    if not images:
        return 0
    if max_files and len(images) > max_files:
        images = images[:max_files]

    count = 0
    for img_meta in images:
        file_name = img_meta['name']
        file_name = re.sub(r'[\\/*?:"<>|]', "", file_name).strip()
        if not file_name:
            file_name = f"{img_meta['id']}.jpg"
        save_path = save_dir / file_name
        if api_download_file(service, img_meta['id'], save_path):
            count += 1
    return count


# ============================================================
# DRIVE NAME + DOWNLOAD HELPERS
# ============================================================

def get_drive_name(file_id: str, kind: str, service=None):
    if service:
        return api_get_file_name(service, file_id)
    import requests
    try:
        url = (f"https://drive.google.com/file/d/{file_id}/view"
               if kind == "file"
               else f"https://drive.google.com/drive/folders/{file_id}")
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if match:
                name = re.sub(r'[\\/*?:"<>|]', "", match.group(1)).strip()
                return name.replace(" - Google Drive", "")
    except:
        pass
    return file_id


def download_direct_file(file_id: str, save_folder: Path, drive_name: str, service=None):
    save_path = save_folder / f"{drive_name}.jpg"
    if service:
        success = api_download_file(service, file_id, save_path)
        if success and save_path.exists() and save_path.stat().st_size > 0:
            return save_path
    try:
        import gdown
        url = f'https://drive.google.com/uc?id={file_id}'
        gdown.download(url, str(save_path), quiet=True, fuzzy=True)
    except Exception as e:
        print(f"Lỗi tải file (gdown fallback): {e}")
    return save_path


# ============================================================
# RESIZE (letterbox + scale_pct + crop_1000)
# ============================================================

def resize_image(image_path: Path, output_path: Path, width=None, height=None,
                 scale_pct=100, mode="letterbox"):
    if mode == "crop_1000":
        crop_photoshop_square(image_path, output_path)
        return

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
            else:
                img = img.convert("RGB")

            img_ratio = img.width / img.height
            target_ratio = width / height
            if img_ratio > target_ratio:
                fit_w, fit_h = width, int(width / img_ratio)
            else:
                fit_w, fit_h = int(height * img_ratio), height

            factor = scale_pct / 100.0
            new_w = max(int(fit_w * factor), 1)
            new_h = max(int(fit_h * factor), 1)

            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.ANTIALIAS

            resized = img.resize((new_w, new_h), resample)
            new_img = Image.new("RGB", (width, height), (255, 255, 255))

            if new_w > width or new_h > height:
                cl = max(0, (new_w - width) // 2)
                ct = max(0, (new_h - height) // 2)
                cropped = resized.crop((cl, ct, cl + min(new_w, width), ct + min(new_h, height)))
                px = max(0, (width - cropped.width) // 2)
                py = max(0, (height - cropped.height) // 2)
                new_img.paste(cropped, (px, py))
            else:
                px = (width - new_w) // 2
                py = (height - new_h) // 2
                new_img.paste(resized, (px, py))

            new_img.save(output_path, "JPEG", quality=95)
    except Exception as e:
        print(f"Resize error: {e}")


def crop_photoshop_square(image_path: Path, output_path: Path, target=1000):
    try:
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            else:
                img = img.convert("RGB")

            w, h = img.size
            if w > target or h > target:
                crop_size = min(w, h)
                left = (w - crop_size) // 2
                top = (h - crop_size) // 2
                cropped = img.crop((left, top, left + crop_size, top + crop_size))
                if crop_size > target:
                    try:
                        rs = Image.Resampling.LANCZOS
                    except AttributeError:
                        rs = Image.ANTIALIAS
                    cropped = cropped.resize((target, target), rs)
                final_img = cropped
            else:
                canvas = Image.new("RGB", (target, target), (255, 255, 255))
                canvas.paste(img, ((target - w) // 2, (target - h) // 2))
                final_img = canvas

            final_img.save(output_path, "JPEG", quality=95)
    except Exception as e:
        print(f"Crop 1000 error: {e}")


# ============================================================
# TIỆN ÍCH CHUNG
# ============================================================

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


# ============================================================
# PREVIEW THUMBNAIL
# ============================================================

def show_preview(final_dir: Path, max_images=6):
    all_imgs = sorted([
        f for f in final_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        and f.stat().st_size > 0
    ])
    if not all_imgs:
        return

    preview = all_imgs[:max_images]
    st.markdown(
        f"<div class='sec-title'>👁️ XEM TRƯỚC ({len(preview)}/{len(all_imgs)} ảnh)</div>",
        unsafe_allow_html=True)

    ncols = min(len(preview), 3)
    cols = st.columns(ncols)
    for idx, img_path in enumerate(preview):
        with cols[idx % ncols]:
            try:
                img = Image.open(img_path)
                thumb = img.copy()
                try:
                    rs = Image.Resampling.LANCZOS
                except AttributeError:
                    rs = Image.ANTIALIAS
                thumb.thumbnail((360, 360), rs)
                st.image(thumb, caption=img_path.name, use_container_width=True)
                st.caption(f"📐 {img.width}×{img.height}")
                img.close()
            except Exception:
                st.caption(f"⚠️ {img_path.name}")

    if len(all_imgs) > max_images:
        st.caption(f"… và {len(all_imgs) - max_images} ảnh khác")


# ============================================================
# BATCH RENAME
# ============================================================

def batch_rename_files(final_dir: Path):
    renamed = 0
    leaf_dirs = set()
    for f in final_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            leaf_dirs.add(f.parent)

    for folder in sorted(leaf_dirs):
        rel = folder.relative_to(final_dir)
        parts = [p for p in rel.parts if p]
        prefix = "_".join(parts) if parts else "image"
        prefix = re.sub(r'[\\/*?:"<>|]', "", prefix)
        prefix = re.sub(r"\s+", "_", prefix).strip("_") or "image"

        images = sorted([
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ])

        # Bước 1: rename thành tên tạm để tránh xung đột
        temp_map = []
        for idx, img in enumerate(images, start=1):
            tmp = folder / f"__tmp_rename_{idx:04d}{img.suffix}"
            img.rename(tmp)
            temp_map.append((tmp, f"{prefix}_{idx:02d}{img.suffix}"))

        # Bước 2: rename từ tên tạm sang tên cuối
        for tmp_path, final_name in temp_map:
            final_path = folder / final_name
            tmp_path.rename(final_path)
            renamed += 1

    return renamed


# ============================================================
# HISTORY
# ============================================================

def _init_history():
    if "processing_history" not in st.session_state:
        st.session_state.processing_history = []


def add_to_history(source: str, detail: str, count: int,
                   size_label: str, duration_sec: float):
    from datetime import datetime
    _init_history()
    entry = {
        "time":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        "source":   source,
        "detail":   detail[:60],
        "count":    count,
        "size":     size_label,
        "duration": f"{duration_sec:.1f}s",
    }
    st.session_state.processing_history.insert(0, entry)
    st.session_state.processing_history = st.session_state.processing_history[:20]


def render_history_sidebar():
    _init_history()
    history = st.session_state.processing_history
    if not history:
        st.caption("Chưa có lịch sử.")
        return

    for h in history[:8]:
        icon = {"Drive": "🌐", "Local": "💻", "Web": "🛒"}.get(h["source"], "📦")
        st.markdown(
            f"<div style='font-size:.76rem;padding:5px 0;border-bottom:1px solid rgba(99,130,190,0.12)'>"
            f"{icon} <b style='color:#e2e8f0'>{h['detail']}</b><br>"
            f"<span style='color:#64748b'>{h['time']} · {h['count']} ảnh · "
            f"{h['size']} · ⏱ {h['duration']}</span></div>",
            unsafe_allow_html=True)

    if len(history) > 8:
        st.caption(f"… +{len(history) - 8} bản ghi khác")


def get_size_label(w, h, mode):
    if mode == "crop_1000":
        return "1000² Crop"
    if w is None:
        return "Gốc"
    return f"{w}×{h}"
