import streamlit as st
import os
import re
import requests
import time
import shutil
import tempfile
from pathlib import Path
from PIL import Image
import gdown

# Thư viện cho Google Drive Upload
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# CẤU HÌNH TRANG
# ==========================================
st.set_page_config(page_title="Hệ thống Resize & Auto Upload", layout="centered", page_icon="🖼️")

st.markdown("""
<style>
    div.stButton > button:first-child { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; height: 45px; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# HỆ THỐNG ĐĂNG NHẬP
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A; margin-bottom: 20px;'>🔐 ĐĂNG NHẬP HỆ THỐNG</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        username = st.text_input("👤 Tài khoản:")
        password = st.text_input("🔑 Mật khẩu:", type="password")
        if st.button("Đăng nhập", type="primary", use_container_width=True):
            if username == "ducpro" and password == "234766":
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu. Vui lòng thử lại!")
    st.stop()

with st.sidebar:
    st.markdown("### 👤 Xin chào, **ducpro**")
    if st.button("🚪 Đăng xuất"):
        st.session_state["logged_in"] = False
        st.rerun()

# ==========================================
# KẾT NỐI API UPLOAD GOOGLE DRIVE
# ==========================================
def get_gdrive_service():
    """Đọc file credentials.json để kết nối API Upload"""
    try:
        if os.path.exists('credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Lỗi API Google: {e}")
    return None

def create_drive_folder(service, folder_name, parent_id):
    """Tạo thư mục trên Drive đích"""
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

def upload_to_drive(service, file_path, target_folder_id):
    """Upload ảnh lên Drive"""
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [target_folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/jpeg', resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# ==========================================
# HÀM PHỤ & XỬ LÝ ẢNH (CHUẨN CODE GỐC)
# ==========================================
def get_unique_path(path: Path) -> Path:
    if not path.exists(): return path
    base, ext, counter = path.stem, path.suffix, 1
    while True:
        new_path = path.with_name(f"{base}_{counter}{ext}")
        if not new_path.exists(): return new_path
        counter += 1

def extract_drive_id_and_type(url: str):
    folder_match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    file_match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    id_match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if folder_match: return folder_match.group(1), "folder"
    elif file_match: return file_match.group(1), "file"
    elif id_match: return id_match.group(1), "file"
    return None, None

def get_drive_name(file_id: str, kind: str):
    try:
        url = f"https://drive.google.com/file/d/{file_id}/view" if kind == "file" else f"https://drive.google.com/drive/folders/{file_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if match:
                name = re.sub(r'[\\/*?:"<>|]', "", match.group(1)).strip()
                return os.path.splitext(name)[0] if kind == "file" else name
    except: pass
    return file_id

def download_direct_file(file_id: str, save_folder: Path, drive_name: str):
    base_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(base_url, stream=True, timeout=10)
    confirm_token = next((v for k, v in response.cookies.items() if k.startswith("download_warning")), None)
    if confirm_token: response = session.get(base_url + f"&confirm={confirm_token}", stream=True, timeout=10)
    
    save_path = get_unique_path(save_folder / f"{drive_name}.jpg")
    with open(save_path, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk: f.write(chunk)
    return save_path

def resize_image(image_path: Path, width=None, height=None):
    if not width or not height: return
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

            save_path = image_path.with_suffix(".jpg")
            new_img.save(save_path, "JPEG", quality=95)
            if str(image_path) != str(save_path): image_path.unlink(missing_ok=True)
    except Exception as e: print(f"Lỗi resize: {e}")

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>📥 Tool Resize & Auto Upload Pro</h1>", unsafe_allow_html=True)

with st.container(border=True):
    mode = st.radio("Chế độ:", ["🌐 Tải từ Google Drive", "💻 Tải ảnh từ máy tính (Local)"], horizontal=True)
    size_options = {
        "Tải & resize 1020x680": (1020, 680),
        "Tải & resize 1020x570": (1020, 570),
        "Tải & resize 1200x1200": (1200, 1200),
        "Tải hình gốc (Không Resize)": (None, None)
    }
    w, h = size_options[st.selectbox("Kích thước Resize:", list(size_options.keys()))]

st.write("")

if "Google Drive" in mode:
    st.markdown("### 📥 1. NGUỒN ẢNH (Dán link cần tải)")
    links_text = st.text_area("Link File/Thư mục cần Resize (Mỗi link 1 dòng):", height=120)
    
    st.markdown("### 📤 2. ĐÍCH UPLOAD (Tự động up sau khi xử lý)")
    upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ muốn tải file ZIP về máy")
    
    # Kiểm tra trạng thái API Upload
    drive_service = get_gdrive_service()
    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa được cấp file `credentials.json`. Ảnh sẽ được tải về dạng ZIP thay vì Upload tự động.")

    if st.button("🚀 BẮT ĐẦU CHẠY", type="primary", use_container_width=True):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

        if not links:
            st.error("⚠️ Vui lòng dán link cần tải!")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                for i, url in enumerate(links):
                    file_id, kind = extract_drive_id_and_type(url)
                    if not file_id: continue
                    
                    status_text.info(f"⏳ Đang lấy thông tin bộ ảnh {i+1}/{len(links)}...")
                    drive_name = get_drive_name(file_id, kind)
                    out_dir = temp_path / drive_name
                    out_dir.mkdir(parents=True, exist_ok=True)

                    status_text.info(f"📥 Đang xử lý: **{drive_name}**...")
                    
                    # --- XỬ LÝ TẢI VÀ RESIZE (BỎ QUA NẾU LỖI) ---
                    try:
                        if kind == "folder":
                            gdown.download_folder(id=file_id, output=str(out_dir), quiet=True)
                            for img in [f for f in out_dir.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]:
                                resize_image(img, w, h)
                        else:
                            file_path = download_direct_file(file_id, out_dir, drive_name)
                            resize_image(file_path, w, h)
                    except Exception as e:
                        st.warning(f"⚠️ Bỏ qua tải '{drive_name}' do lỗi quyền truy cập.")
                        continue # Nhảy sang link tiếp theo
                    
                    # --- XỬ LÝ UPLOAD (BỎ QUA NẾU LỖI) ---
                    if target_folder_id and drive_service:
                        status_text.info(f"📤 Đang Upload **{drive_name}** lên Drive đích...")
                        try:
                            # Tạo thư mục con mang đúng tên thư mục gốc trên Drive đích
                            new_folder_id = create_drive_folder(drive_service, drive_name, target_folder_id)
                            for img in out_dir.rglob("*.jpg"):
                                upload_to_drive(drive_service, img, new_folder_id)
                            st.success(f"✅ Đã Upload xong: {drive_name}")
                        except Exception as e:
                            st.warning(f"⚠️ Bỏ qua upload '{drive_name}'. Có thể thư mục đích chưa mở quyền Chỉnh Sửa.")

                    progress_bar.progress((i+1) / len(links))
                    if i < len(links) - 1: time.sleep(3)
                
                status_text.success("🎉 HOÀN TẤT TOÀN BỘ TIẾN TRÌNH!")
                shutil.make_archive(temp_path / "Drive_Images_Done", 'zip', temp_path)
                st.balloons()
                
                with open(temp_path / "Drive_Images_Done.zip", "rb") as f:
                    st.download_button("📥 TẢI DỰ PHÒNG TOÀN BỘ ẢNH (FILE ZIP)", f, file_name="Drive_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)

else:
    st.info("💡 Nhập đường dẫn các thư mục trên máy tính. Hệ thống sẽ tự động quét toàn bộ ảnh, bao gồm cả các thư mục con bên trong.")
    local_dirs_input = st.text_area("📂 Đường dẫn thư mục nguồn (Mỗi đường dẫn 1 dòng):", placeholder="Ví dụ:\nD:\\HinhAnh\\San_Pham_A\nE:\\Project\\Thu_Muc_Con")
    upload_link = st.text_input("📤 Link Thư mục Drive ĐÍCH (Nếu muốn Auto Upload):", placeholder="Bỏ trống nếu chỉ muốn lấy file ZIP")
    
    drive_service = get_gdrive_service()

    if st.button("🚀 BẮT ĐẦU RESIZE LOCAL", type="primary", use_container_width=True):
        local_dirs = [d.strip() for d in local_dirs_input.splitlines() if d.strip()]
        if not local_dirs:
            st.error("⚠️ Bạn chưa nhập đường dẫn thư mục nào!")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                out_dir = temp_path / "Local_Images_Resized"
                out_dir.mkdir(exist_ok=True)
                target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

                # Quét tìm ảnh trong các thư mục và thư mục con
                valid_files = []
                for d in local_dirs:
                    folder_path = Path(d)
                    if folder_path.exists() and folder_path.is_dir():
                        for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp', '*.PNG', '*.JPG', '*.JPEG', '*.WEBP'):
                            for file_path in folder_path.rglob(ext):
                                valid_files.append((folder_path, file_path))
                
                # Lọc file trùng lặp
                valid_files = list(set(valid_files))

                if not valid_files:
                    st.error("⚠️ Không tìm thấy ảnh hợp lệ trong các thư mục đã nhập! Vui lòng kiểm tra lại đường dẫn.")
                else:
                    # 1. Lưu & Resize
                    for i, (base_folder, file_path) in enumerate(valid_files):
                        status_text.info(f"⏳ Đang xử lý: {file_path.name} ({i+1}/{len(valid_files)})")
                        
                        # Tái tạo cấu trúc thư mục con để giữ nguyên hệ thống cây thư mục ban đầu
                        rel_path = file_path.relative_to(base_folder)
                        img_target = out_dir / base_folder.name / rel_path
                        img_target.parent.mkdir(parents=True, exist_ok=True)
                        
                        try:
                            shutil.copy2(file_path, img_target)
                            resize_image(img_target, w, h)
                        except Exception as e:
                            print(f"Lỗi xử lý file {file_path}: {e}")
                        
                        progress_bar.progress((i + 1) / len(valid_files))
                    
                    # 2. Upload (Nếu có cấu hình)
                    if target_folder_id and drive_service:
                        status_text.info("📤 Đang Upload lên Google Drive...")
                        try:
                            new_folder_id = create_drive_folder(drive_service, "Local_Resized_Images", target_folder_id)
                            for img in out_dir.rglob("*.jpg"):
                                upload_to_drive(drive_service, img, new_folder_id)
                            st.success("✅ Upload thành công!")
                        except Exception as e:
                            st.warning("⚠️ Quá trình Upload gặp lỗi, vui lòng lấy file qua nút tải ZIP bên dưới.")

                    status_text.success("🎉 Hoàn tất toàn bộ ảnh Offline!")
                    
                    # Nén đúng thư mục đã xử lý (để giải nén ra có sẵn cấu trúc thư mục con)
                    shutil.make_archive(temp_path / "Local_Images_Done", 'zip', out_dir)
                    st.balloons()
                    
                    with open(temp_path / "Local_Images_Done.zip", "rb") as f:
                        st.download_button("📥 TẢI XUỐNG BẢN LƯU (FILE ZIP)", f, file_name="Local_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)
