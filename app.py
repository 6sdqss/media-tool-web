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

# Thư viện cho Web Scraping (Chế độ 3)
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

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
# CÁC HÀM PHỤ CHO SCRAPING WEB (CHẾ ĐỘ 3)
# ==========================================
def clean_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

def refine_product_name(name: str) -> str:
    name = re.sub(r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*))", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def get_item_name(main_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(main_url, headers=headers, timeout=10)
        if response.status_code != 200: return "Sản_phẩm_không_tên"
        soup = BeautifulSoup(response.text, "html.parser")

        name_tag = soup.find("h1")
        if name_tag:
            name = name_tag.text.strip()
        else:
            text = soup.get_text()
            match = re.search(r'item_name\s*:\s*"(.*?)"', text)
            if match:
                name = match.group(1)
            else:
                title = soup.find("title")
                name = title.text.split("|")[0].strip() if title else "Sản phẩm"
        return clean_name(refine_product_name(name))
    except:
        return "Sản_phẩm_không_tên"

def get_color_links_and_names(main_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(main_url, headers=headers, timeout=10)
        if response.status_code != 200: return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        parsed = urlparse(main_url)
        base_path = parsed.path

        color_data = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if base_path in href and "?code=" in href:
                color_name = a.get_text(strip=True)
                color_link = urljoin(main_url, href)
                if color_name and color_link not in [c["link"] for c in color_data]:
                    color_data.append({"name": clean_name(color_name), "link": color_link})

        if not color_data:
            return [{"name": "Mặc định", "link": main_url}]
        return color_data
    except Exception as e:
        return [{"name": "Mặc định", "link": main_url}]

def get_gallery_image_urls(product_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code != 200: return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        img_tags = soup.find_all("img")
        img_urls = []
        for img in img_tags:
            src = img.get("data-src") or img.get("src")
            if src and "750x500" in src:
                # Xóa hậu tố 750x500 để lấy ảnh gốc độ phân giải cao nhất
                original_url = re.sub(r"-750x500", "", urljoin(product_url, src))
                img_urls.append(original_url)
        return list(set(img_urls))
    except:
        return []

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>📥 Tool Resize & Auto Upload Pro</h1>", unsafe_allow_html=True)

with st.container(border=True):
    # --- ĐÃ THÊM CHẾ ĐỘ 3 VÀO RADIO BUTTON ---
    mode = st.radio("Chế độ:", ["🌐 Tải từ Google Drive", "💻 Tải ảnh từ máy tính (Upload ZIP)", "🛒 Tải từ Web (TGDD / DMX)"], horizontal=True)
    
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
elif "máy tính" in mode or "Upload ZIP" in mode:
    st.info("💡 **HƯỚNG DẪN:** Để giữ nguyên cấu trúc thư mục khi làm việc trên Web, bạn hãy nén tất cả các thư mục cần làm thành **1 file .zip** rồi tải lên đây.")
    
    uploaded_zip = st.file_uploader("📦 Tải lên file ZIP chứa các thư mục ảnh:", type=['zip'])
    upload_link = st.text_input("📤 Link Thư mục Drive ĐÍCH (Nếu muốn Auto Upload):", placeholder="Bỏ trống nếu chỉ muốn lấy file ZIP")

    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối API Upload Drive. Ảnh sẽ được tải về dạng ZIP thay vì Upload tự động.")

    if st.button("🚀 BẮT ĐẦU RESIZE LOCAL", type="primary", use_container_width=True):
        if not uploaded_zip:
            st.error("⚠️ Bạn chưa tải file ZIP lên!")
        else:
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

                valid_files = []
                for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp', '*.PNG', '*.JPG', '*.JPEG', '*.WEBP'):
                    for file_path in extract_path.rglob(ext):
                        if not ignore_system_files(file_path):
                            valid_files.append(file_path)

                if not valid_files:
                    st.error("⚠️ Không tìm thấy ảnh hợp lệ nào trong file ZIP!")
                else:
                    status_text.info(f"⏳ Đang xử lý Đa luồng {len(valid_files)} ảnh...")
                    
                    def process_local_file(file_path):
                        rel_path = file_path.relative_to(extract_path)
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
                    
                    target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)
                    
                    if target_folder_id and drive_service:
                        status_text.info("📤 Đang phân tích cấu trúc và Upload lên Google Drive...")
                        try:
                            root_folder_name = f"Local_Resized_Images_{int(time.time())}"
                            root_folder_id = create_drive_folder(drive_service, root_folder_name, target_folder_id)
                            
                            folder_cache = {"": root_folder_id, ".": root_folder_id}
                            jpg_files = list(out_dir.rglob("*.jpg"))
                            
                            for idx, img in enumerate(jpg_files):
                                rel_dir = img.parent.relative_to(out_dir)
                                rel_dir_str = str(rel_dir)
                                
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
                    shutil.make_archive(temp_path / "Resized_Finished", 'zip', out_dir)
                    st.balloons()
                    
                    with open(temp_path / "Resized_Finished.zip", "rb") as f:
                        st.download_button("📥 TẢI XUỐNG KẾT QUẢ (FILE ZIP)", f, file_name="Resized_Finished.zip", mime="application/zip", type="primary", use_container_width=True)

# ---------------------------------------------------------
# MODE 3: WEB CRAWLER (TGDD / DMX) - CHẾ ĐỘ MỚI
# ---------------------------------------------------------
elif "Web" in mode:
    st.info("💡 **HƯỚNG DẪN:** Dán link sản phẩm Thế Giới Di Động hoặc Điện Máy Xanh. Hệ thống sẽ quét màu, cho bạn tick chọn, tải ảnh gốc, Resize và Upload.")
    
    if "web_scanned_data" not in st.session_state:
        st.session_state["web_scanned_data"] = []

    links_text = st.text_area("🔗 Dán Link sản phẩm (Mỗi link 1 dòng):", height=100)
    
    if st.button("🔍 1. QUÉT SẢN PHẨM & TÌM MÀU", use_container_width=True):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
        else:
            with st.spinner("Đang quét dữ liệu từ web..."):
                scanned_data = []
                for link in links:
                    name = get_item_name(link)
                    colors = get_color_links_and_names(link)
                    scanned_data.append({
                        "original_link": link,
                        "product_name": name,
                        "colors": colors
                    })
                st.session_state["web_scanned_data"] = scanned_data
            st.success("✅ Đã quét xong! Vui lòng chọn màu bên dưới.")

    if st.session_state["web_scanned_data"]:
        st.markdown("---")
        st.markdown("### 🎨 2. CHỌN MÀU CẦN TẢI")
        
        selected_tasks = []
        for item in st.session_state["web_scanned_data"]:
            st.markdown(f"**📦 {item['product_name']}**")
            cols = st.columns(3)
            for idx, color in enumerate(item["colors"]):
                with cols[idx % 3]:
                    if st.checkbox(color["name"], value=True, key=f"cb_{item['original_link']}_{color['name']}"):
                        selected_tasks.append({
                            "product_name": item["product_name"],
                            "color_name": color["name"],
                            "link": color["link"]
                        })
        
        st.markdown("---")
        st.markdown("### 📤 3. XỬ LÝ & UPLOAD")
        upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ muốn tải file ZIP về máy", key="web_drive_input")
        
        if st.button("🚀 BẮT ĐẦU TẢI, RESIZE & UPLOAD", type="primary", use_container_width=True):
            if not selected_tasks:
                st.error("⚠️ Bạn chưa chọn màu nào để tải!")
            else:
                target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    out_dir = temp_path / "Web_Images_Resized"
                    out_dir.mkdir(exist_ok=True)
                    
                    status_text = st.empty()
                    progress_bar = st.progress(0)
                    
                    total_tasks = len(selected_tasks)
                    for i, task in enumerate(selected_tasks):
                        p_name = task["product_name"]
                        c_name = task["color_name"]
                        c_link = task["link"]
                        
                        status_text.info(f"⏳ Đang tải: {p_name} - Màu: {c_name} ({i+1}/{total_tasks})")
                        
                        color_dir = out_dir / p_name / c_name
                        color_dir.mkdir(parents=True, exist_ok=True)
                        
                        img_urls = get_gallery_image_urls(c_link)
                        if not img_urls:
                            continue
                            
                        headers = {"User-Agent": "Mozilla/5.0"}
                        for idx, img_url in enumerate(img_urls):
                            try:
                                img_name = os.path.basename(img_url.split("?")[0])
                                save_path = color_dir / img_name
                                
                                img_data = requests.get(img_url, headers=headers, timeout=10).content
                                with open(save_path, "wb") as f:
                                    f.write(img_data)
                                    
                                resize_image(save_path, w, h)
                            except Exception as e:
                                print(f"Lỗi tải/resize {img_url}: {e}")
                                
                        progress_bar.progress((i + 1) / total_tasks)
                    
                    if target_folder_id and drive_service:
                        status_text.info("📤 Đang Upload lên Google Drive (Giữ nguyên cấu trúc)...")
                        try:
                            root_folder_name = f"Web_Resized_Images_{int(time.time())}"
                            root_folder_id = create_drive_folder(drive_service, root_folder_name, target_folder_id)
                            folder_cache = {"": root_folder_id, ".": root_folder_id}
                            jpg_files = list(out_dir.rglob("*.jpg"))
                            
                            for idx, img in enumerate(jpg_files):
                                rel_dir = img.parent.relative_to(out_dir)
                                rel_dir_str = str(rel_dir)
                                
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
                                
                            st.success(f"✅ Upload thành công {len(jpg_files)} ảnh!")
                        except Exception as e:
                            st.warning(f"⚠️ Lỗi Upload: {e}")

                    status_text.success("🎉 Hoàn tất cào dữ liệu và xử lý!")
                    shutil.make_archive(temp_path / "Web_Images_Done", 'zip', out_dir)
                    st.balloons()
                    with open(temp_path / "Web_Images_Done.zip", "rb") as f:
                        st.download_button("📥 TẢI XUỐNG KẾT QUẢ (FILE ZIP)", f, file_name="Web_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)
