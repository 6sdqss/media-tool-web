"""
utils.py — Media Tool Pro v6.0
Thư viện tiện ích: Google Drive API, Resize ảnh, Naming template,
Preview, History, Session stats, Presets.
"""

import os
import re
import io
import time
import shutil
import streamlit as st
from pathlib import Path
from PIL import Image
from datetime import datetime

# Google APIs
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


# ╔══════════════════════════════════════════════════════════════╗
# ║  HẰNG SỐ                                                    ║
# ╚══════════════════════════════════════════════════════════════╝

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}

EXPORT_FORMATS = {
    "JPEG (.jpg)":  {"ext": ".jpg",  "pil_format": "JPEG", "mime": "image/jpeg"},
    "PNG (.png)":   {"ext": ".png",  "pil_format": "PNG",  "mime": "image/png"},
    "WebP (.webp)": {"ext": ".webp", "pil_format": "WEBP", "mime": "image/webp"},
}

SIZE_PRESETS = {
    "1020×680 Ngang chuẩn":     (1020, 680,  "letterbox"),
    "1020×570 Ngang rộng":      (1020, 570,  "letterbox"),
    "1200×1200 Vuông":          (1200, 1200, "letterbox"),
    "800×800 Shopee":           (800,  800,  "letterbox"),
    "1000×1000 PS Crop":        (1000, 1000, "crop_1000"),
    "Giữ gốc":                  (None, None, "letterbox"),
}

# Các bộ preset cấu hình nhanh
QUICK_PRESETS = {
    "TGDD / DMX": {
        "sizes": ["1020×680 Ngang chuẩn"],
        "quality": 95,
        "scale": 100,
        "template": "{name}_{nn}",
        "format": "JPEG (.jpg)",
    },
    "Shopee / Lazada": {
        "sizes": ["1200×1200 Vuông", "800×800 Shopee"],
        "quality": 85,
        "scale": 100,
        "template": "{name}_{nn}",
        "format": "JPEG (.jpg)",
    },
    "TikTok Shop": {
        "sizes": ["1200×1200 Vuông"],
        "quality": 90,
        "scale": 105,
        "template": "{name}_{color}_{nn}",
        "format": "JPEG (.jpg)",
    },
    "Photoshop Crop": {
        "sizes": ["1000×1000 PS Crop"],
        "quality": 95,
        "scale": 100,
        "template": "{name}_{nn}",
        "format": "JPEG (.jpg)",
    },
}


# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE DRIVE — Kết nối & Upload                            ║
# ╚══════════════════════════════════════════════════════════════╝

def get_gdrive_service():
    """Tạo Google Drive service từ Streamlit Secrets hoặc credentials.json."""
    # Ưu tiên 1: Streamlit Secrets (deploy trên cloud)
    try:
        if "gcp_service_account" in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass

    # Ưu tiên 2: File credentials.json (chạy local)
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
    """Tạo thư mục mới trên Drive, trả về folder ID."""
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder.get("id")


def upload_to_drive(service, file_path, target_folder_id: str) -> str:
    """Upload 1 file lên Drive, trả về file ID."""
    metadata = {
        "name": os.path.basename(file_path),
        "parents": [target_folder_id],
    }
    media = MediaFileUpload(str(file_path), mimetype="image/jpeg", resumable=True)
    result = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return result.get("id")


def extract_drive_id_and_type(url: str):
    """
    Trích xuất file/folder ID từ link Google Drive.
    Trả về (id, "folder"|"file") hoặc (None, None).
    """
    if not url:
        return None, None

    # Link thư mục: drive/folders/ABC123
    match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1), "folder"

    # Link file: file/d/ABC123
    match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1), "file"

    # Link dạng ?id=ABC123
    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1), "file"

    return None, None


# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE DRIVE — Tải file/folder bằng API                    ║
# ╚══════════════════════════════════════════════════════════════╝

def api_get_file_name(service, file_id: str) -> str:
    """Lấy tên file/folder từ Drive API."""
    try:
        metadata = service.files().get(
            fileId=file_id, fields="name", supportsAllDrives=True
        ).execute()
        return metadata.get("name", file_id)
    except Exception:
        return file_id


def api_download_file(service, file_id: str, save_path: Path) -> bool:
    """Tải 1 file từ Drive bằng API. Trả về True nếu thành công."""
    try:
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(buffer.getvalue())
        return True
    except Exception as exc:
        print(f"[Drive API] Lỗi tải file {file_id}: {exc}")
        return False


def api_list_folder_images(service, folder_id: str) -> list:
    """Liệt kê tất cả file ảnh trong folder (đệ quy 1 cấp subfolder)."""
    image_mimes = [
        "image/jpeg", "image/png", "image/webp",
        "image/gif", "image/bmp", "image/tiff",
    ]
    mime_query = " or ".join([f"mimeType='{m}'" for m in image_mimes])
    query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"

    results = []
    page_token = None

    # Lấy ảnh trực tiếp trong folder
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

    # Quét subfolder 1 cấp
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


def api_download_folder_images(service, folder_id: str, save_dir: Path,
                                max_files: int = None) -> int:
    """Tải tất cả ảnh trong folder về save_dir. Trả về số file tải OK."""
    images = api_list_folder_images(service, folder_id)
    if not images:
        return 0
    if max_files:
        images = images[:max_files]

    count = 0
    for img_meta in images:
        # Làm sạch tên file
        file_name = re.sub(r'[\\/*?:"<>|]', "", img_meta["name"]).strip()
        if not file_name:
            file_name = f"{img_meta['id']}.jpg"
        save_path = save_dir / file_name
        if api_download_file(service, img_meta["id"], save_path):
            count += 1

    return count


def get_drive_name(file_id: str, kind: str, service=None) -> str:
    """Lấy tên file/folder. Ưu tiên API, fallback scrape HTML."""
    if service:
        return api_get_file_name(service, file_id)

    # Fallback: Scrape tên từ trang web Drive
    import requests
    try:
        if kind == "file":
            url = f"https://drive.google.com/file/d/{file_id}/view"
        else:
            url = f"https://drive.google.com/drive/folders/{file_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if match:
                name = re.sub(r'[\\/*?:"<>|]', "", match.group(1)).strip()
                return name
    except Exception:
        pass

    return file_id


def download_direct_file(file_id: str, save_folder: Path,
                          drive_name: str, service=None) -> Path:
    """Tải 1 file đơn. Ưu tiên API → fallback gdown."""
    save_path = save_folder / f"{drive_name}.jpg"

    # Thử API trước
    if service:
        success = api_download_file(service, file_id, save_path)
        if success and save_path.exists() and save_path.stat().st_size > 0:
            return save_path

    # Fallback: gdown
    try:
        import gdown
        download_url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(download_url, str(save_path), quiet=True, fuzzy=True)
    except Exception as exc:
        print(f"Lỗi tải file (gdown fallback): {exc}")

    return save_path


# ╔══════════════════════════════════════════════════════════════╗
# ║  RESIZE ẢNH                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _get_resample_filter():
    """Lấy filter LANCZOS tương thích cả Pillow cũ và mới."""
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.ANTIALIAS


def _convert_to_rgb(img: Image.Image) -> Image.Image:
    """Chuyển ảnh có transparency về RGB với nền trắng."""
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, (0, 0), img)
        return background.convert("RGB")
    return img.convert("RGB")


def resize_image(image_path: Path, output_path: Path,
                  width: int = None, height: int = None,
                  scale_pct: int = 100, mode: str = "letterbox",
                  quality: int = 95, export_format: str = "JPEG (.jpg)"):
    """
    Resize ảnh với nhiều chế độ:
    - letterbox: Giữ tỉ lệ, fill nền trắng, hỗ trợ scale %
    - crop_1000: Crop 1:1 center → 1000×1000 (kiểu Photoshop)

    Args:
        image_path: Đường dẫn ảnh nguồn
        output_path: Đường dẫn file output
        width, height: Kích thước target (None = giữ gốc)
        scale_pct: Tỉ lệ phóng to/thu nhỏ (100 = vừa khung)
        mode: "letterbox" hoặc "crop_1000"
        quality: Chất lượng JPEG/WebP (1-100)
        export_format: Key trong EXPORT_FORMATS
    """
    # Mode crop đặc biệt
    if mode == "crop_1000":
        crop_photoshop_square(image_path, output_path,
                               quality=quality, export_format=export_format)
        return

    # Giữ gốc — chỉ copy file
    if not width or not height:
        shutil.copy2(image_path, output_path)
        return

    try:
        fmt_info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
        # Sửa extension output cho đúng format
        output_path = output_path.with_suffix(fmt_info["ext"])

        with Image.open(image_path) as img:
            img = _convert_to_rgb(img)

            # Tính kích thước "vừa khung" (fit) giữ tỉ lệ
            img_ratio = img.width / img.height
            target_ratio = width / height

            if img_ratio > target_ratio:
                # Ảnh rộng hơn target → fit theo width
                fit_width = width
                fit_height = int(width / img_ratio)
            else:
                # Ảnh cao hơn target → fit theo height
                fit_width = int(height * img_ratio)
                fit_height = height

            # Áp dụng scale %
            factor = scale_pct / 100.0
            new_width = max(int(fit_width * factor), 1)
            new_height = max(int(fit_height * factor), 1)

            resample = _get_resample_filter()
            resized = img.resize((new_width, new_height), resample)

            # Tạo canvas trắng
            canvas = Image.new("RGB", (width, height), (255, 255, 255))

            if new_width > width or new_height > height:
                # Scale > 100% → ảnh lớn hơn canvas → crop giữa
                crop_left = max(0, (new_width - width) // 2)
                crop_top = max(0, (new_height - height) // 2)
                crop_right = crop_left + min(new_width, width)
                crop_bottom = crop_top + min(new_height, height)
                cropped = resized.crop((crop_left, crop_top, crop_right, crop_bottom))
                paste_x = max(0, (width - cropped.width) // 2)
                paste_y = max(0, (height - cropped.height) // 2)
                canvas.paste(cropped, (paste_x, paste_y))
            else:
                # Ảnh nhỏ hơn canvas → paste giữa
                paste_x = (width - new_width) // 2
                paste_y = (height - new_height) // 2
                canvas.paste(resized, (paste_x, paste_y))

            # Lưu theo format
            pil_format = fmt_info["pil_format"]
            if pil_format == "JPEG":
                canvas.save(output_path, "JPEG", quality=quality, optimize=True)
            elif pil_format == "PNG":
                canvas.save(output_path, "PNG", optimize=True)
            elif pil_format == "WEBP":
                canvas.save(output_path, "WEBP", quality=quality)

    except Exception as exc:
        print(f"Resize error [{image_path.name}]: {exc}")


def crop_photoshop_square(image_path: Path, output_path: Path,
                           target: int = 1000, quality: int = 95,
                           export_format: str = "JPEG (.jpg)"):
    """
    Crop 1:1 center giống Photoshop → resize về target×target.
    - Ảnh lớn: crop center 1:1 → resize down
    - Ảnh nhỏ: giữ nguyên, đặt vào nền trắng
    """
    try:
        fmt_info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
        output_path = output_path.with_suffix(fmt_info["ext"])

        with Image.open(image_path) as img:
            img = _convert_to_rgb(img)
            w, h = img.size

            if w > target or h > target:
                # Crop center 1:1
                crop_size = min(w, h)
                left = (w - crop_size) // 2
                top = (h - crop_size) // 2
                cropped = img.crop((left, top, left + crop_size, top + crop_size))

                # Resize down nếu cần
                if crop_size > target:
                    cropped = cropped.resize(
                        (target, target), _get_resample_filter()
                    )
                final_image = cropped
            else:
                # Ảnh nhỏ → đặt lên nền trắng, KHÔNG upscale
                final_image = Image.new("RGB", (target, target), (255, 255, 255))
                offset_x = (target - w) // 2
                offset_y = (target - h) // 2
                final_image.paste(img, (offset_x, offset_y))

            pil_format = fmt_info["pil_format"]
            if pil_format == "JPEG":
                final_image.save(output_path, "JPEG", quality=quality, optimize=True)
            elif pil_format == "PNG":
                final_image.save(output_path, "PNG", optimize=True)
            elif pil_format == "WEBP":
                final_image.save(output_path, "WEBP", quality=quality)

    except Exception as exc:
        print(f"Crop error [{image_path.name}]: {exc}")


def resize_to_multi_sizes(src_path: Path, final_dir: Path, folder_name: str,
                           file_stem: str, sizes: list,
                           scale_pct: int = 100, quality: int = 95,
                           export_format: str = "JPEG (.jpg)"):
    """
    Resize 1 ảnh nguồn sang nhiều kích thước cùng lúc.
    Nếu chọn >1 size → tạo subfolder theo tên size.
    Nếu chọn 1 size → output phẳng (không subfolder size).
    """
    fmt_info = EXPORT_FORMATS.get(export_format, EXPORT_FORMATS["JPEG (.jpg)"])
    is_multi = len(sizes) > 1

    for target_w, target_h, resize_mode in sizes:
        size_label = get_size_label(target_w, target_h, resize_mode)

        # Tạo đường dẫn output
        if is_multi:
            output_dir = final_dir / size_label / folder_name
        else:
            output_dir = final_dir / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{file_stem}{fmt_info['ext']}"
        resize_image(
            src_path, output_file,
            width=target_w, height=target_h,
            scale_pct=scale_pct, mode=resize_mode,
            quality=quality, export_format=export_format,
        )


# ╔══════════════════════════════════════════════════════════════╗
# ║  NAMING TEMPLATE                                             ║
# ╚══════════════════════════════════════════════════════════════╝

def apply_name_template(template: str, name: str = "", color: str = "",
                         index: int = 1, original: str = "") -> str:
    """
    Thay thế biến trong template đặt tên:
        {name}     → tên sản phẩm / folder
        {color}    → tên màu sắc
        {nn}       → số thứ tự 2 chữ số (01, 02, 03...)
        {nnn}      → số thứ tự 3 chữ số (001, 002...)
        {original} → tên file gốc (không extension)

    Returns:
        Tên file đã format (không có extension)
    """
    result = template
    result = result.replace("{name}", name)
    result = result.replace("{color}", color)
    result = result.replace("{nn}", f"{index:02d}")
    result = result.replace("{nnn}", f"{index:03d}")
    result = result.replace("{original}", original)

    # Dọn ký tự không hợp lệ cho tên file
    result = re.sub(r'[\\/*?:"<>|]', "", result)
    result = re.sub(r"_+", "_", result).strip("_")

    return result or f"image_{index:02d}"


def batch_rename_with_template(final_dir: Path, template: str = "{name}_{nn}") -> int:
    """
    Đổi tên tất cả ảnh trong final_dir theo template.
    Tự động nhận diện name/color từ cấu trúc thư mục.
    Trả về số file đã đổi tên.
    """
    renamed_count = 0

    # Tìm tất cả thư mục lá (chứa ảnh trực tiếp)
    leaf_directories = set()
    for file_path in final_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
            leaf_directories.add(file_path.parent)

    for folder in sorted(leaf_directories):
        relative_path = folder.relative_to(final_dir)
        path_parts = [part for part in relative_path.parts if part]

        # Bỏ qua size label khi tạo name (vd: "1020x680", "1000x1000_Crop")
        name_parts = [
            part for part in path_parts
            if not re.match(r"^\d+x\d+", part)
            and part != "original"
            and "Crop" not in part
        ]

        # Tách product name và color
        product_name = name_parts[0] if len(name_parts) >= 1 else "image"
        color_name = name_parts[1] if len(name_parts) >= 2 else ""
        product_name = re.sub(r"\s+", "_", product_name).strip("_")

        # Lấy danh sách ảnh, sắp xếp theo tên
        images = sorted([
            f for f in folder.iterdir()
            if f.is_file()
            and f.suffix.lower() in IMAGE_EXTENSIONS
            and not f.name.startswith("__tmp_")
        ])

        if not images:
            continue

        # Phase 1: Rename → tên tạm (tránh xung đột)
        temp_mapping = []
        for idx, img_path in enumerate(images, start=1):
            original_stem = img_path.stem
            temp_name = f"__tmp_rename_{idx:04d}{img_path.suffix}"
            temp_path = folder / temp_name
            img_path.rename(temp_path)

            new_name = apply_name_template(
                template,
                name=product_name,
                color=color_name,
                index=idx,
                original=original_stem,
            )
            final_name = f"{new_name}{img_path.suffix}"
            temp_mapping.append((temp_path, final_name))

        # Phase 2: Tên tạm → tên cuối cùng
        for temp_path, final_name in temp_mapping:
            final_path = folder / final_name
            temp_path.rename(final_path)
            renamed_count += 1

    return renamed_count


# ╔══════════════════════════════════════════════════════════════╗
# ║  TIỆN ÍCH CHUNG                                             ║
# ╚══════════════════════════════════════════════════════════════╝

def clean_name(name: str) -> str:
    """Làm sạch chuỗi thành tên file/folder hợp lệ."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name or "Untitled"


def ignore_system_files(path: Path) -> bool:
    """Kiểm tra file hệ thống cần bỏ qua."""
    name = path.name
    return (
        name.startswith("._")
        or name == ".DS_Store"
        or name.startswith("__MACOSX")
        or name.startswith("__tmp_")
    )


def get_size_label(width, height, mode: str) -> str:
    """Tạo label dễ đọc cho 1 kích thước."""
    if mode == "crop_1000":
        return "1000x1000_Crop"
    if width is None:
        return "original"
    return f"{width}x{height}"


def check_pause_cancel_state() -> bool:
    """Kiểm tra trạng thái pause/cancel. Block khi paused, False khi cancelled."""
    while st.session_state.get("download_status") == "paused":
        time.sleep(1)
    return st.session_state.get("download_status") != "cancelled"


def render_control_buttons():
    """Hiện 3 nút điều khiển: Tạm dừng / Tiếp tục / Hủy."""
    st.markdown('<div class="control-box">', unsafe_allow_html=True)
    col_pause, col_resume, col_cancel = st.columns(3)
    with col_pause:
        if st.button("⏸️ Tạm dừng", use_container_width=True):
            st.session_state.download_status = "paused"
            st.rerun()
    with col_resume:
        if st.button("▶️ Tiếp tục", use_container_width=True):
            st.session_state.download_status = "running"
            st.rerun()
    with col_cancel:
        if st.button("⏹️ Hủy bỏ", type="primary", use_container_width=True):
            st.session_state.download_status = "cancelled"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ╔══════════════════════════════════════════════════════════════╗
# ║  PREVIEW THUMBNAIL                                           ║
# ╚══════════════════════════════════════════════════════════════╝

def show_preview(final_dir: Path, max_images: int = 6):
    """Hiện lưới thumbnail ảnh đã resize (tối đa max_images ảnh)."""
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
        f"<div class='sec-title'>👁️ XEM TRƯỚC ({len(preview_images)}/{total} ảnh)</div>",
        unsafe_allow_html=True,
    )

    num_cols = min(len(preview_images), 3)
    columns = st.columns(num_cols)

    for idx, img_path in enumerate(preview_images):
        with columns[idx % num_cols]:
            try:
                img = Image.open(img_path)
                thumbnail = img.copy()
                thumbnail.thumbnail((360, 360), _get_resample_filter())
                st.image(thumbnail, caption=img_path.name, use_container_width=True)
                st.caption(f"📐 {img.width}×{img.height}")
                img.close()
            except Exception:
                st.caption(f"⚠️ {img_path.name}")

    if total > max_images:
        st.caption(f"… và {total - max_images} ảnh khác trong ZIP")


# ╔══════════════════════════════════════════════════════════════╗
# ║  PROCESSING SUMMARY                                          ║
# ╚══════════════════════════════════════════════════════════════╝

def show_processing_summary(final_dir: Path, sizes: list, duration: float):
    """Hiện bảng tổng kết sau khi xử lý xong."""
    all_files = [
        f for f in final_dir.rglob("*")
        if f.is_file() and f.stat().st_size > 0
    ]
    total_size_kb = sum(f.stat().st_size for f in all_files) // 1024

    # Đếm ảnh theo size
    size_counts = {}
    for f in all_files:
        rel = f.relative_to(final_dir)
        first_part = rel.parts[0] if len(rel.parts) > 1 else "output"
        size_counts[first_part] = size_counts.get(first_part, 0) + 1

    # Hiển thị
    size_labels = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#f0fdf4,#dcfce7);"
        f"border:1px solid #86efac;border-radius:12px;padding:14px 18px;margin:10px 0;"
        f"font-size:.84rem'>"
        f"<b style='color:#166534'>📊 Tổng kết</b><br>"
        f"📁 <b>{len(all_files)}</b> ảnh · "
        f"💾 <b>{total_size_kb:,} KB</b> · "
        f"⏱ <b>{duration:.1f}s</b> · "
        f"📐 {size_labels}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║  HISTORY & SESSION STATS                                     ║
# ╚══════════════════════════════════════════════════════════════╝

def _init_history():
    """Khởi tạo session state cho history và stats."""
    if "processing_history" not in st.session_state:
        st.session_state.processing_history = []
    if "session_stats" not in st.session_state:
        st.session_state.session_stats = {
            "total_images": 0,
            "total_batches": 0,
            "total_time": 0.0,
        }


def add_to_history(source: str, detail: str, count: int,
                    size_label: str, duration_sec: float):
    """
    Thêm 1 bản ghi vào lịch sử xử lý.

    Args:
        source: "Drive" | "Local" | "Web"
        detail: Mô tả ngắn (tên sản phẩm, file...)
        count: Số ảnh đã xử lý
        size_label: Kích thước đã dùng
        duration_sec: Thời gian xử lý (giây)
    """
    _init_history()

    entry = {
        "time": datetime.now().strftime("%d/%m %H:%M"),
        "source": source,
        "detail": detail[:50],
        "count": count,
        "size": size_label,
        "duration": f"{duration_sec:.1f}s",
    }
    st.session_state.processing_history.insert(0, entry)
    st.session_state.processing_history = st.session_state.processing_history[:30]

    # Cập nhật stats tích lũy
    stats = st.session_state.session_stats
    stats["total_images"] += count
    stats["total_batches"] += 1
    stats["total_time"] += duration_sec


def render_history_sidebar():
    """Hiển thị lịch sử xử lý trong sidebar."""
    _init_history()
    history = st.session_state.processing_history

    if not history:
        st.caption("Chưa có lịch sử.")
        return

    for entry in history[:6]:
        icon = {"Drive": "🌐", "Local": "💻", "Web": "🛒"}.get(entry["source"], "📦")
        st.markdown(
            f"<div style='font-size:.74rem;padding:4px 0;"
            f"border-bottom:1px solid rgba(99,130,190,0.1)'>"
            f"{icon} <b style='color:#e2e8f0'>{entry['detail']}</b><br>"
            f"<span style='color:#64748b;font-size:.7rem'>"
            f"{entry['time']} · {entry['count']} ảnh · "
            f"{entry['size']} · ⏱{entry['duration']}"
            f"</span></div>",
            unsafe_allow_html=True,
        )

    remaining = len(history) - 6
    if remaining > 0:
        st.caption(f"+{remaining} bản ghi trước đó")


def render_session_stats():
    """Hiện 3 stat cards tổng hợp phiên làm việc."""
    _init_history()
    stats = st.session_state.session_stats

    if stats["total_images"] == 0:
        return

    total_images = stats["total_images"]
    total_batches = stats["total_batches"]
    total_time = stats["total_time"]

    st.markdown(
        f"<div style='display:flex;gap:6px;margin:4px 0 8px'>"
        # Card: Tổng ảnh
        f"<div style='flex:1;background:rgba(99,102,241,0.15);border-radius:8px;"
        f"padding:6px 8px;text-align:center'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#c7d2fe'>{total_images}</div>"
        f"<div style='font-size:.65rem;color:#94a3b8'>Ảnh</div></div>"
        # Card: Số lần chạy
        f"<div style='flex:1;background:rgba(16,185,129,0.15);border-radius:8px;"
        f"padding:6px 8px;text-align:center'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#a7f3d0'>{total_batches}</div>"
        f"<div style='font-size:.65rem;color:#94a3b8'>Lần</div></div>"
        # Card: Tổng thời gian
        f"<div style='flex:1;background:rgba(251,191,36,0.15);border-radius:8px;"
        f"padding:6px 8px;text-align:center'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#fde68a'>{total_time:.0f}s</div>"
        f"<div style='font-size:.65rem;color:#94a3b8'>Tổng</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
