import streamlit as st
import os
import re
import requests
import time
import shutil
import tempfile
import zipfile
import concurrent.futures
from pathlib import Path
from PIL import Image
import gdown

# Thư viện cho Google Drive Upload
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# CẤU HÌNH TRANG & CSS
# ==========================================
st.set_page_config(page_title="Hệ thống Resize & Auto Upload", layout="centered", page_icon="🖼️")

st.markdown("""
<style>
    /* Nâng cấp giao diện nút bấm */
    div.stButton > button:first-child { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; height: 45px; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    
    /* ẨN MENU VÀ GITHUB ICON CỦA STREAMLIT */
    #MainMenu {visibility: hidden;} /* Ẩn menu hamburger */
    header {visibility: hidden;} /* Ẩn thanh header chứa nút GitHub/Deploy */
    footer {visibility: hidden;} /* Ẩn footer "Made with Streamlit" */
    
    /* Khoảng trống bù lại khi ẩn header để giao diện không bị đẩy lên quá cao */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
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
    """Hỗ trợ cả Streamlit Secrets (Cloud) và File Local"""
    try:
        # 1. Ưu tiên đọc từ Streamlit Secrets nếu chạy trên Cloud
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = service_account.Credentials.from_service_account_info(
                creds_info, scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except: pass

    try:
        # 2. Đọc từ file credentials.json nếu chạy ở máy tính local
        if os.path.exists('credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=['https://www.googleapis.com/auth/drive']
            )
            return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Lỗi API Google: {e}")
    
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

# ==========================================
# HÀM PHỤ & XỬ LÝ ẢNH
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

def ignore_system_files(path: Path):
    """Bỏ qua các file rác của MacOS hoặc Windows khi giải nén ZIP"""
    return path.name.startswith("._") or path.name == ".DS_Store" or path.name.startswith("__MACOSX")

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>📥 Tool Resize & Auto Upload Pro</h1>", unsafe_allow_html=True)

with st.container(border=True):
    mode = st.radio("Chế độ:", ["🌐 Tải từ Google Drive", "💻 Tải ảnh từ máy tính (Upload ZIP)"], horizontal=True)
    size_options = {
        "Tải & resize 1020x680": (1020, 680),
        "Tải & resize 1020x570": (1020, 570),
        "Tải & resize 1200x1200": (1200, 1200),
        "Tải hình gốc (Không Resize)": (None, None)
    }
    w, h = size_options[st.selectbox("Kích thước Resize:", list(size_options.keys()))]

st.write("")
drive_service = get_gdrive_service()

# ---------------------------------------------------------
# MODE 1: GOOGLE DRIVE (Giữ nguyên luồng xử lý ổn định)
# ---------------------------------------------------------
if "Google Drive" in mode:
    st.markdown("### 📥 1. NGUỒN ẢNH (Dán link cần tải)")
    links_text = st.text_area("Link File/Thư mục cần Resize (Mỗi link 1 dòng):", height=120)
    
    st.markdown("### 📤 2. ĐÍCH UPLOAD (Tự động up sau khi xử lý)")
    upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ muốn tải file ZIP về máy")
    
    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối API Upload Drive. Ảnh sẽ được tải về dạng ZIP thay vì Upload tự động.")

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
                    
                    try:
                        if kind == "folder":
                            gdown.download_folder(id=file_id, output=str(out_dir), quiet=True, use_cookies=False)
                            for img in [f for f in out_dir.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]:
                                resize_image(img, w, h)
                        else:
                            file_path = download_direct_file(file_id, out_dir, drive_name)
                            resize_image(file_path, w, h)
                    except Exception as e:
                        st.warning(f"⚠️ Bỏ qua tải '{drive_name}' do lỗi quyền truy cập.")
                        continue
                    
                    if target_folder_id and drive_service:
                        status_text.info(f"📤 Đang Upload **{drive_name}** lên Drive đích...")
                        try:
                            new_folder_id = create_drive_folder(drive_service, drive_name, target_folder_id)
                            for img in out_dir.rglob("*.jpg"):
                                upload_to_drive(drive_service, img, new_folder_id)
                            st.success(f"✅ Đã Upload xong: {drive_name}")
                        except Exception as e:
                            st.warning(f"⚠️ Bỏ qua upload '{drive_name}'.")

                    progress_bar.progress((i+1) / len(links))
                    if i < len(links) - 1: time.sleep(3)
                
                status_text.success("🎉 HOÀN TẤT TOÀN BỘ TIẾN TRÌNH!")
                shutil.make_archive(temp_path / "Drive_Images_Done", 'zip', temp_path)
                st.balloons()
                with open(temp_path / "Drive_Images_Done.zip", "rb") as f:
                    st.download_button("📥 TẢI DỰ PHÒNG TOÀN BỘ ẢNH (FILE ZIP)", f, file_name="Drive_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)

# ---------------------------------------------------------
# MODE 2: LOCAL PC (CHUẨN WEB APP BẰNG FILE ZIP)
# ---------------------------------------------------------
else:
    st.info("💡 **HƯỚNG DẪN:** Để giữ nguyên cấu trúc thư mục khi làm việc trên Web, bạn hãy nén tất cả các thư mục cần làm thành **1 file .zip** rồi tải lên đây.")
    
    uploaded_zip = st.file_uploader("📦 Tải lên file ZIP chứa các thư mục ảnh:", type=['zip'])
    upload_link = st.text_input("📤 Link Thư mục Drive ĐÍCH (Nếu muốn Auto Upload):", placeholder="Bỏ trống nếu chỉ muốn lấy file ZIP")

    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối API Upload Drive. Ảnh sẽ được tải về dạng ZIP thay vì Upload tự động.")

    if st.button("🚀 BẮT ĐẦU RESIZE LOCAL", type="primary", use_container_width=True):
        if not uploaded_zip:
            st.error("⚠️ Bạn chưa tải file ZIP lên!")
        else:
            # Dùng thư mục tạm thời độc lập cho mỗi user
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                extract_path = temp_path / "Extracted"
                out_dir = temp_path / "Resized"
                
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                status_text.info("⏳ Đang giải nén file ZIP...")
                try:
                    with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)
                except Exception as e:
                    st.error("❌ Lỗi: File ZIP bị hỏng hoặc không đúng định dạng.")
                    st.stop()

                # Quét tìm ảnh hợp lệ (Bỏ qua file rác của MacOS)
                valid_files = []
                for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp', '*.PNG', '*.JPG', '*.JPEG', '*.WEBP'):
                    for file_path in extract_path.rglob(ext):
                        if not ignore_system_files(file_path):
                            valid_files.append(file_path)

                if not valid_files:
                    st.error("⚠️ Không tìm thấy ảnh hợp lệ nào trong file ZIP!")
                else:
                    # 1. Lưu & Resize đa luồng
                    status_text.info(f"⏳ Đang xử lý Đa luồng {len(valid_files)} ảnh...")
                    
                    def process_local_file(file_path):
                        # Lấy đường dẫn tương đối từ thư mục giải nén để giữ nguyên cấu trúc
                        rel_path = file_path.relative_to(extract_path)
                        
                        # Bỏ qua thư mục rác __MACOSX nếu zip từ máy Mac
                        if "MACOSX" in str(rel_path): return
                        
                        img_target = out_dir / rel_path
                        img_target.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy2(file_path, img_target)
                            resize_image(img_target, w, h)
                        except Exception as e:
                            print(f"Lỗi xử lý: {e}")

                    processed_count = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                        futures = [executor.submit(process_local_file, f) for f in valid_files]
                        for future in concurrent.futures.as_completed(futures):
                            processed_count += 1
                            status_text.info(f"⏳ Đang xử lý: {processed_count}/{len(valid_files)} ảnh...")
                            progress_bar.progress(processed_count / len(valid_files))
                    
                    # 2. Upload Google Drive (Tự tạo cấu trúc thư mục)
                    target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)
                    
                    if target_folder_id and drive_service:
                        status_text.info("📤 Đang phân tích cấu trúc và Upload lên Google Drive...")
                        try:
                            # Tạo thư mục gốc chứa lô hàng này
                            root_folder_name = f"Local_Resized_Images_{int(time.time())}"
                            root_folder_id = create_drive_folder(drive_service, root_folder_name, target_folder_id)
                            
                            folder_cache = {"": root_folder_id, ".": root_folder_id}
                            jpg_files = list(out_dir.rglob("*.jpg"))
                            
                            for idx, img in enumerate(jpg_files):
                                rel_dir = img.parent.relative_to(out_dir)
                                rel_dir_str = str(rel_dir)
                                
                                # Tạo cây thư mục trên Drive
                                if rel_dir_str not in folder_cache:
                                    current_parent = root_folder_id
                                    current_path = ""
                                    for part in rel_dir.parts:
                                        current_path = os.path.join(current_path, part) if current_path else part
                                        if current_path not in folder_cache:
                                            new_id = create_drive_folder(drive_service, part, current_parent)
                                            folder_cache[current_path] = new_id
                                        current_parent = folder_cache[current_path]
                                
                                dest_folder_id = folder_cache[rel_dir_str]
                                upload_to_drive(drive_service, img, dest_folder_id)
                                status_text.info(f"📤 Đã upload {idx + 1}/{len(jpg_files)} ảnh...")
                                
                            st.success(f"✅ Upload thành công {len(jpg_files)} ảnh, giữ nguyên 100% cấu trúc thư mục!")
                        except Exception as e:
                            st.warning(f"⚠️ Lỗi Upload: {e}. Vui lòng tải ZIP dự phòng bên dưới.")

                    status_text.success("🎉 Hoàn tất quá trình xử lý!")
                    
                    # 3. Nén ZIP trả về cho người dùng
                    shutil.make_archive(temp_path / "Resized_Finished", 'zip', out_dir)
                    st.balloons()
                    
                    with open(temp_path / "Resized_Finished.zip", "rb") as f:
                        st.download_button("📥 TẢI XUỐNG KẾT QUẢ (FILE ZIP)", f, file_name="Resized_Finished.zip", mime="application/zip", type="primary", use_container_width=True)
