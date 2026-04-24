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
# HÀM TẢI FILE BẰNG GOOGLE DRIVE API (thay thế gdown)
# ============================================================

def api_get_file_name(service, file_id):
    """Lấy tên file/folder qua API."""
    try:
        meta = service.files().get(fileId=file_id, fields='name', supportsAllDrives=True).execute()
        return meta.get('name', file_id)
    except Exception as e:
        print(f"[API] Không lấy được tên cho {file_id}: {e}")
        return file_id


def api_download_file(service, file_id, save_path: Path):
    """Tải 1 file từ Drive bằng API. Trả về True nếu thành công."""
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
    """Liệt kê tất cả file ảnh trong 1 folder Drive (không đệ quy sâu)."""
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
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            results.extend(resp.get('files', []))
            page_token = resp.get('nextPageToken')
            if not page_token:
                break
        except Exception as e:
            print(f"[API] Lỗi liệt kê folder {folder_id}: {e}")
            break

    # Cũng kiểm tra subfolder (đệ quy 1 cấp)
    subfolder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    try:
        sub_resp = service.files().list(
            q=subfolder_query,
            fields="files(id, name)",
            pageSize=50,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        for subfolder in sub_resp.get('files', []):
            sub_images = api_list_folder_images(service, subfolder['id'])
            results.extend(sub_images)
    except Exception as e:
        print(f"[API] Lỗi liệt kê subfolder: {e}")

    return results


def api_download_folder_images(service, folder_id, save_dir: Path, max_files=None):
    """Tải tất cả ảnh trong folder về save_dir. Trả về số file tải được."""
    images = api_list_folder_images(service, folder_id)
    if not images:
        return 0

    if max_files and len(images) > max_files:
        images = images[:max_files]

    count = 0
    for img_meta in images:
        file_name = img_meta['name']
        # Đảm bảo tên file hợp lệ
        file_name = re.sub(r'[\\/*?:"<>|]', "", file_name).strip()
        if not file_name:
            file_name = f"{img_meta['id']}.jpg"
        save_path = save_dir / file_name
        if api_download_file(service, img_meta['id'], save_path):
            count += 1
    return count


# ============================================================
# HÀM GỌI TÊN (fallback nếu không có API)
# ============================================================

def get_drive_name(file_id: str, kind: str, service=None):
    """Lấy tên file/folder. Ưu tiên dùng API, fallback dùng requests."""
    if service:
        return api_get_file_name(service, file_id)
    # Fallback: scrape tên từ HTML (không ổn định trên cloud)
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
    """Tải 1 file. Ưu tiên API, fallback gdown."""
    save_path = save_folder / f"{drive_name}.jpg"
    if service:
        success = api_download_file(service, file_id, save_path)
        if success and save_path.exists() and save_path.stat().st_size > 0:
            return save_path
        # Nếu API thất bại, thử gdown
    try:
        import gdown
        url = f'https://drive.google.com/uc?id={file_id}'
        gdown.download(url, str(save_path), quiet=True, fuzzy=True)
    except Exception as e:
        print(f"Lỗi tải file (gdown fallback): {e}")
    return save_path


# ============================================================
# RESIZE ẢNH (NÂNG CẤP: thêm scale_pct + mode crop_1000)
# ============================================================

def resize_image(image_path: Path, output_path: Path, width=None, height=None,
                 scale_pct=100, mode="letterbox"):
    """
    Resize ảnh với các chế độ:
    - mode="letterbox": Giữ tỉ lệ, fill nền trắng (mặc định)
      + scale_pct: % phóng to ảnh trên canvas (100=vừa khung, >100=to hơn/crop, <100=nhỏ hơn)
    - mode="crop_1000": Crop 1:1 chính giữa → resize về 1000×1000 (kiểu Photoshop)
    """
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

            # Tính kích thước "vừa khung" (fit)
            if img_ratio > target_ratio:
                fit_w, fit_h = width, int(width / img_ratio)
            else:
                fit_w, fit_h = int(height * img_ratio), height

            # Áp dụng scale_pct: phóng to/thu nhỏ so với kích thước fit
            factor = scale_pct / 100.0
            new_w = int(fit_w * factor)
            new_h = int(fit_h * factor)

            # Đảm bảo tối thiểu 1px
            new_w = max(new_w, 1)
            new_h = max(new_h, 1)

            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.ANTIALIAS

            resized = img.resize((new_w, new_h), resample_filter)

            # Tạo canvas trắng và paste ảnh vào giữa
            new_img = Image.new("RGB", (width, height), (255, 255, 255))

            # Tính vị trí paste (giữa canvas)
            paste_x = (width - new_w) // 2
            paste_y = (height - new_h) // 2

            # Nếu ảnh lớn hơn canvas (scale > 100%), crop phần thừa
            if new_w > width or new_h > height:
                # Crop vùng giữa của ảnh đã resize để vừa canvas
                crop_left = max(0, (new_w - width) // 2)
                crop_top = max(0, (new_h - height) // 2)
                crop_right = crop_left + min(new_w, width)
                crop_bottom = crop_top + min(new_h, height)
                cropped = resized.crop((crop_left, crop_top, crop_right, crop_bottom))
                paste_x = max(0, (width - cropped.width) // 2)
                paste_y = max(0, (height - cropped.height) // 2)
                new_img.paste(cropped, (paste_x, paste_y))
            else:
                new_img.paste(resized, (paste_x, paste_y))

            new_img.save(output_path, "JPEG", quality=95)
    except Exception as e:
        print(f"Resize error: {e}")


def crop_photoshop_square(image_path: Path, output_path: Path, target=1000):
    """
    Crop 1:1 chính giữa kiểu Photoshop → resize về target×target.
    - Ảnh lớn → crop center 1:1 → resize down (không upscale)
    - Ảnh nhỏ → giữ nguyên kích thước, đặt vào nền trắng target×target
    """
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

            # Ảnh lớn → crop 1:1 giữa → resize down
            if w > target or h > target:
                crop_size = min(w, h)
                left = (w - crop_size) // 2
                top = (h - crop_size) // 2
                cropped = img.crop((left, top, left + crop_size, top + crop_size))

                if crop_size > target:
                    try:
                        resample = Image.Resampling.LANCZOS
                    except AttributeError:
                        resample = Image.ANTIALIAS
                    cropped = cropped.resize((target, target), resample)

                final_img = cropped
            else:
                # Ảnh nhỏ → không upscale, đặt lên nền trắng
                canvas = Image.new("RGB", (target, target), (255, 255, 255))
                offset_x = (target - w) // 2
                offset_y = (target - h) // 2
                canvas.paste(img, (offset_x, offset_y))
                final_img = canvas

            final_img.save(output_path, "JPEG", quality=95)
    except Exception as e:
        print(f"Crop 1000 error: {e}")


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
# PREVIEW THUMBNAIL SAU KHI RESIZE
# ============================================================

def show_preview(final_dir: Path, max_images=6):
    """Hiện thumbnail ảnh đã resize để kiểm tra trước khi tải ZIP."""
    all_imgs = sorted([
        f for f in final_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        and f.stat().st_size > 0
    ])
    if not all_imgs:
        return

    preview_imgs = all_imgs[:max_images]
    st.markdown(
        f"<div class='sec-title'>👁️ XEM TRƯỚC ({len(preview_imgs)}/{len(all_imgs)} ảnh)</div>",
        unsafe_allow_html=True,
    )

    # Hiện grid 3 cột
    ncols = min(len(preview_imgs), 3)
    cols = st.columns(ncols)
    for idx, img_path in enumerate(preview_imgs):
        with cols[idx % ncols]:
            try:
                img = Image.open(img_path)
                # Tạo thumbnail nhỏ để hiển thị nhanh
                thumb = img.copy()
                thumb.thumbnail((360, 360), Image.Resampling.LANCZOS
                                if hasattr(Image, "Resampling") else Image.ANTIALIAS)
                st.image(thumb, caption=img_path.name, use_container_width=True)
                # Hiện kích thước gốc bên dưới
                st.caption(f"📐 {img.width}×{img.height}")
                img.close()
            except Exception:
                st.caption(f"⚠️ {img_path.name}")

    if len(all_imgs) > max_images:
        st.caption(f"… và {len(all_imgs) - max_images} ảnh khác")


# ============================================================
# ĐẶT TÊN HÀNG LOẠT (BATCH RENAME)
# ============================================================

def batch_rename_files(final_dir: Path):
    """
    Đổi tên ảnh theo cấu trúc thư mục:
      FINAL/Samsung_S25/Den/abc.jpg → Samsung_S25/Den/Samsung_S25_Den_01.jpg
      FINAL/FolderName/xyz.jpg      → FolderName/FolderName_01.jpg

    Giữ nguyên cấu trúc thư mục, chỉ đổi tên file.
    Trả về số file đã đổi tên.
    """
    renamed = 0

    # Tìm tất cả thư mục lá (chứa ảnh trực tiếp)
    leaf_dirs = set()
    for f in final_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            leaf_dirs.add(f.parent)

    for folder in sorted(leaf_dirs):
        # Tạo prefix từ đường dẫn tương đối
        rel = folder.relative_to(final_dir)
        parts = [p for p in rel.parts if p]
        prefix = "_".join(parts) if parts else "image"
        # Làm sạch prefix
        prefix = re.sub(r'[\\/*?:"<>|]', "", prefix)
        prefix = re.sub(r"\s+", "_", prefix).strip("_") or "image"

        # Lấy danh sách ảnh, sắp xếp theo tên
        images = sorted([
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ])

        for idx, img in enumerate(images, start=1):
            new_name = f"{prefix}_{idx:02d}{img.suffix}"
            new_path = folder / new_name
            if img != new_path:
                # Tránh trùng tên nếu file đích đã tồn tại
                if new_path.exists() and new_path != img:
                    # Đổi tên tạm trước
                    tmp = folder / f"_tmp_{idx:02d}_{img.name}"
                    img.rename(tmp)
                    img = tmp
                img.rename(new_path)
                renamed += 1

    return renamed


# ============================================================
# LỊCH SỬ XỬ LÝ (PROCESSING HISTORY)
# ============================================================

def _init_history():
    """Khởi tạo list lịch sử trong session_state."""
    if "processing_history" not in st.session_state:
        st.session_state.processing_history = []


def add_to_history(source: str, detail: str, count: int,
                   size_label: str, duration_sec: float):
    """
    Thêm 1 bản ghi vào lịch sử.
    - source:     "Drive" | "Local" | "Web"
    - detail:     tên sản phẩm / folder / file
    - count:      số ảnh đã xử lý
    - size_label: ví dụ "1020×680"
    - duration_sec: thời gian xử lý (giây)
    """
    from datetime import datetime
    _init_history()

    entry = {
        "time":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        "source":   source,
        "detail":   detail[:60],  # giới hạn dài
        "count":    count,
        "size":     size_label,
        "duration": f"{duration_sec:.1f}s",
    }
    st.session_state.processing_history.insert(0, entry)  # mới nhất lên đầu
    # Giữ tối đa 20 bản ghi
    st.session_state.processing_history = st.session_state.processing_history[:20]


def render_history_sidebar():
    """Hiển thị lịch sử xử lý trong sidebar."""
    _init_history()
    history = st.session_state.processing_history
    if not history:
        st.caption("Chưa có lịch sử xử lý.")
        return

    for i, h in enumerate(history[:8]):  # hiện tối đa 8 gần nhất
        icon = {"Drive": "🌐", "Local": "💻", "Web": "🛒"}.get(h["source"], "📦")
        st.markdown(
            f"<div style='font-size:.78rem;padding:5px 0;border-bottom:1px solid #334155'>"
            f"{icon} <b>{h['detail']}</b><br>"
            f"<span style='color:#94a3b8'>{h['time']} · {h['count']} ảnh · "
            f"{h['size']} · ⏱ {h['duration']}</span></div>",
            unsafe_allow_html=True,
        )

    if len(history) > 8:
        st.caption(f"… và {len(history) - 8} bản ghi khác")


def get_size_label(w, h, mode):
    """Tạo label kích thước để lưu vào history."""
    if mode == "crop_1000":
        return "1000×1000 Crop"
    if w is None:
        return "Gốc"
    return f"{w}×{h}"
