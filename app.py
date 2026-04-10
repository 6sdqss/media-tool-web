import streamlit as st
import os
import re
import requests
import time
import shutil
import tempfile
import zipfile
import json
import concurrent.futures
from pathlib import Path
from PIL import Image
import gdown

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

st.set_page_config(page_title="Hệ thống Resize & Auto Upload", layout="centered", page_icon="🖼️")

st.markdown("""
<style>
    div.stButton > button:first-child { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; height: 45px; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    .control-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin-top: 10px;
        margin-bottom: 15px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

if 'download_status' not in st.session_state:
    st.session_state.download_status = 'idle'

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
    return path.name.startswith("._") or path.name == ".DS_Store" or path.name.startswith("__MACOSX")

RAW_COOKIES = [
    {"domain": ".thegioididong.com", "name": "_ce.clock_data", "value": "-110%2C113.161.59.60%2C1%2C91e1a2a41c0741f7f47615ab9de2fb8a%2CChrome%2CVN"},
    {"domain": ".thegioididong.com", "name": "_ce.s", "value": "v~10b349a1bfb597f2fbfafdd33af1d88e35768560~lcw~1775808302291~vir~returning~lva~1775788787457~vpv~198~v11ls~8496c620-34b3-11f1-b933-8983fd7f9723~v11.cs~453625~v11.s~8496c620-34b3-11f1-b933-8983fd7f9723~v11.vs~10b349a1bfb597f2fbfafdd33af1d88e35768560"},
    {"domain": ".thegioididong.com", "name": "cebs", "value": "1"},
    {"domain": ".thegioididong.com", "name": "cebsp_", "value": "32"},
    {"domain": ".thegioididong.com", "name": "mwgsp", "value": "1"},
    {"domain": "www.thegioididong.com", "name": "ASP.NET_SessionId", "value": "zgo0wxmkgvnqbqub0lkreuon"},
    {"domain": "www.thegioididong.com", "name": "SvID", "value": "beline26122|adivM|adhi9"},
    {"domain": "www.thegioididong.com", "name": "TBMCookie_3209819802479625248", "value": "272331001775808103SbF4f4kGHIEXWQ8vk5fTCgPn/0Q="}
]

TGDD_COOKIES_DICT = {c['name']: c['value'] for c in RAW_COOKIES}

def resolve_redirect_url(url: str) -> str:
    if "/sp-" in url or "/dtdd-" in url or "/may-tinh-bang-" in url:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            response = requests.get(url, headers=headers, cookies=TGDD_COOKIES_DICT, allow_redirects=True, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
                if meta_refresh:
                    content = meta_refresh.get("content", "")
                    if "url=" in content.lower():
                        redirect_url = content.split("url=")[-1].strip("'\"")
                        return urljoin(url, redirect_url)
            return response.url
        except: pass
    return url

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
        response = requests.get(main_url, headers=headers, cookies=TGDD_COOKIES_DICT, timeout=10)
        if response.status_code != 200: return "Sản_phẩm_không_tên"
        soup = BeautifulSoup(response.text, "html.parser")
        name_tag = soup.find("h1")
        if name_tag: name = name_tag.text.strip()
        else:
            text = soup.get_text()
            match = re.search(r'item_name\s*:\s*"(.*?)"', text)
            if match: name = match.group(1)
            else:
                title = soup.find("title")
                name = title.text.split("|")[0].strip() if title else "Sản phẩm"
        return clean_name(refine_product_name(name))
    except: return "Sản_phẩm_không_tên"

def get_color_links_and_names(main_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(main_url, headers=headers, cookies=TGDD_COOKIES_DICT, timeout=10)
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
        if not color_data: return [{"name": "Mặc định", "link": main_url}]
        return color_data
    except Exception: return [{"name": "Mặc định", "link": main_url}]

def get_gallery_image_urls(product_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, cookies=TGDD_COOKIES_DICT, timeout=10)
        if response.status_code != 200: return []
        soup = BeautifulSoup(response.text, "html.parser")
        img_tags = soup.find_all("img")
        img_urls = []
        for img in img_tags:
            src = img.get("data-src") or img.get("src")
            if src and "750x500" in src:
                original_url = re.sub(r"-750x500", "", urljoin(product_url, src))
                img_urls.append(original_url)
        return list(set(img_urls))
    except: return []

def check_pause_cancel_state():
    while st.session_state.download_status == 'paused':
        time.sleep(1)
    if st.session_state.download_status == 'cancelled':
        return False
    return True

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>📥 Tool Resize & Auto Upload Pro</h1>", unsafe_allow_html=True)

with st.container(border=True):
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

# ---------------------------------------------------------
# MODE 1: GOOGLE DRIVE (ĐÃ FIX LỖI GDOWN VÀ CHẶN)
# ---------------------------------------------------------
if "Google Drive" in mode:
    st.markdown("### 📥 1. NGUỒN ẢNH (Dán link cần tải)")
    links_text = st.text_area("Link File/Thư mục cần Resize (Mỗi link 1 dòng):", height=120)
    st.markdown("### 📤 2. ĐÍCH UPLOAD (Tự động up sau khi xử lý)")
    upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ muốn tải file ZIP về máy")
    
    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối API Upload Drive.")

    if st.button("🚀 BẮT ĐẦU CHẠY", type="primary", use_container_width=True):
        st.session_state.download_status = 'running'
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

        if not links:
            st.error("⚠️ Vui lòng dán link cần tải!")
            st.session_state.download_status = 'idle'
        else:
            render_control_buttons()
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                for i, url in enumerate(links):
                    if not check_pause_cancel_state(): break
                    file_id, kind = extract_drive_id_and_type(url)
                    if not file_id: continue
                    
                    status_text.info(f"⏳ Đang lấy thông tin bộ ảnh {i+1}/{len(links)}...")
                    drive_name = get_drive_name(file_id, kind)
                    out_dir = temp_path / drive_name
                    out_dir.mkdir(parents=True, exist_ok=True)

                    try:
                        if kind == "folder":
                            # Cơ chế Retry vượt rào Gdown Google chặn Rate limit
                            success = False
                            for attempt in range(3):
                                try:
                                    gdown.download_folder(id=file_id, output=str(out_dir), quiet=True, use_cookies=(attempt == 1))
                                    success = True
                                    break
                                except:
                                    time.sleep(4)
                            if not success:
                                st.warning(f"⚠️ Drive tạm thời chặn tải thư mục '{drive_name}'. Bỏ qua file này.")
                                continue
                            
                            for img in [f for f in out_dir.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]:
                                resize_image(img, w, h)
                        else:
                            file_path = download_direct_file(file_id, out_dir, drive_name)
                            resize_image(file_path, w, h)
                    except: continue
                    
                    if target_folder_id and drive_service and check_pause_cancel_state():
                        status_text.info(f"📤 Đang Upload **{drive_name}** lên Drive đích...")
                        try:
                            new_folder_id = create_drive_folder(drive_service, drive_name, target_folder_id)
                            for img in out_dir.rglob("*.jpg"):
                                upload_to_drive(drive_service, img, new_folder_id)
                        except: pass
                    progress_bar.progress((i+1) / len(links))
                
                if st.session_state.download_status == 'cancelled':
                    status_text.error("🚫 Đã hủy quá trình tải!")
                else:
                    status_text.success("🎉 HOÀN TẤT!")
                    shutil.make_archive(temp_path / "Drive_Images_Done", 'zip', temp_path)
                    with open(temp_path / "Drive_Images_Done.zip", "rb") as f:
                        st.download_button("📥 TẢI KẾT QUẢ", f, file_name="Drive_Images_Done.zip", mime="application/zip", use_container_width=True)
                st.session_state.download_status = 'idle'

# ---------------------------------------------------------
# MODE 2: LOCAL PC
# ---------------------------------------------------------
elif "máy tính" in mode or "Upload ZIP" in mode:
    st.info("💡 **HƯỚNG DẪN:** Nén các thư mục thành **1 file .zip hoặc .rar** rồi tải lên đây.")
    uploaded_file = st.file_uploader("📦 Tải lên file ZIP hoặc RAR:", type=['zip', 'rar'])
    upload_link = st.text_input("📤 Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ lấy file ZIP")

    if st.button("🚀 BẮT ĐẦU RESIZE LOCAL", type="primary", use_container_width=True):
        st.session_state.download_status = 'running'
        if not uploaded_file:
            st.error("⚠️ Bạn chưa tải file nào lên!")
            st.session_state.download_status = 'idle'
        else:
            render_control_buttons()
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                extract_path = temp_path / "Extracted"
                out_dir = temp_path / "Resized"
                
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                status_text.info("⏳ Đang giải nén file...")
                try:
                    file_ext = uploaded_file.name.split('.')[-1].lower()
                    if file_ext == 'zip':
                        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                            zip_ref.extractall(extract_path)
                    elif file_ext == 'rar':
                        import rarfile
                        temp_rar_path = temp_path / uploaded_file.name
                        with open(temp_rar_path, "wb") as f: f.write(uploaded_file.getbuffer())
                        with rarfile.RarFile(temp_rar_path, 'r') as rar_ref:
                            rar_ref.extractall(extract_path)
                except Exception as e:
                    st.error(f"❌ Lỗi giải nén: {e}")
                    st.session_state.download_status = 'idle'
                    st.stop()

                valid_files = [f for f in extract_path.rglob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp'] and not ignore_system_files(f)]

                if not valid_files:
                    st.error("⚠️ Không tìm thấy ảnh hợp lệ!")
                else:
                    def process_local_file(file_path):
                        if not check_pause_cancel_state(): return
                        rel_path = file_path.relative_to(extract_path)
                        if "MACOSX" in str(rel_path): return
                        img_target = out_dir / rel_path
                        img_target.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy2(file_path, img_target)
                            resize_image(img_target, w, h)
                        except: pass

                    processed_count = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(process_local_file, f) for f in valid_files]
                        for future in concurrent.futures.as_completed(futures):
                            if not check_pause_cancel_state(): break
                            processed_count += 1
                            progress_bar.progress(processed_count / len(valid_files))
                    
                    target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)
                    if target_folder_id and drive_service and check_pause_cancel_state():
                        status_text.info("📤 Đang Upload lên Google Drive...")
                        try:
                            root_folder_id = create_drive_folder(drive_service, f"Local_Resized_{int(time.time())}", target_folder_id)
                            folder_cache = {"": root_folder_id, ".": root_folder_id}
                            jpg_files = list(out_dir.rglob("*.jpg"))
                            for idx, img in enumerate(jpg_files):
                                if not check_pause_cancel_state(): break
                                rel_dir_str = str(img.parent.relative_to(out_dir))
                                if rel_dir_str not in folder_cache:
                                    current_parent = root_folder_id
                                    current_path = ""
                                    for part in Path(rel_dir_str).parts:
                                        current_path = os.path.join(current_path, part) if current_path else part
                                        if current_path not in folder_cache:
                                            folder_cache[current_path] = create_drive_folder(drive_service, part, current_parent)
                                        current_parent = folder_cache[current_path]
                                upload_to_drive(drive_service, img, folder_cache[rel_dir_str])
                        except: pass

                if st.session_state.download_status == 'cancelled':
                    status_text.error("🚫 Đã hủy quá trình!")
                else:
                    status_text.success("🎉 Hoàn tất!")
                    shutil.make_archive(temp_path / "Resized_Finished", 'zip', out_dir)
                    with open(temp_path / "Resized_Finished.zip", "rb") as f:
                        st.download_button("📥 TẢI KẾT QUẢ", f, file_name="Resized_Finished.zip", mime="application/zip", use_container_width=True)
                st.session_state.download_status = 'idle'

# ---------------------------------------------------------
# MODE 3: WEB CRAWLER (TGDD / DMX) - ĐA LUỒNG & FIX TRÙNG KEY
# ---------------------------------------------------------
elif "Web" in mode:
    st.info("💡 **HƯỚNG DẪN:** Dán link TGDD/DMX (kể cả link rút gọn). Hệ thống tự phân tích cấu trúc màu và xử lý siêu tốc.")
    
    if "web_scanned_data" not in st.session_state:
        st.session_state["web_scanned_data"] = []

    links_text = st.text_area("🔗 Dán Link sản phẩm (Mỗi link 1 dòng):", height=100)
    
    if st.button("🔍 1. QUÉT SẢN PHẨM & TÌM MÀU (ĐA LUỒNG)", use_container_width=True):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
        else:
            with st.spinner("Đang phân tích link siêu tốc..."):
                scanned_data = []
                
                # Hàm Worker Quét thông tin
                def scan_url_worker(link):
                    real_link = resolve_redirect_url(link)
                    name = get_item_name(real_link)
                    colors = get_color_links_and_names(real_link)
                    return {"original_link": link, "real_link": real_link, "product_name": name, "colors": colors}

                # Đẩy tốc độ quét lên bằng Multithreading
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(scan_url_worker, l) for l in links]
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            scanned_data.append(future.result())
                        except Exception: pass
                
                st.session_state["web_scanned_data"] = scanned_data
            st.success("✅ Đã quét xong! Chọn màu cần tải bên dưới.")

    if st.session_state["web_scanned_data"]:
        st.markdown("---")
        st.markdown("### 🎨 2. CHỌN MÀU CẦN TẢI")
        
        selected_tasks = []
        # Giải quyết lỗi DuplicateElementKey bằng cách chèn idx_item vào Key
        for idx_item, item in enumerate(st.session_state["web_scanned_data"]):
            st.markdown(f"**📦 {item['product_name']}**")
            cols = st.columns(3)
            for idx_color, color in enumerate(item["colors"]):
                with cols[idx_color % 3]:
                    # Unique Key: Bám theo index sản phẩm + tên màu
                    if st.checkbox(color["name"], value=True, key=f"cb_{idx_item}_{item['original_link']}_{color['name']}"):
                        selected_tasks.append({"product_name": item["product_name"], "color_name": color["name"], "link": color["link"]})
        
        st.markdown("---")
        st.markdown("### 📤 3. XỬ LÝ & UPLOAD")
        upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ lấy file ZIP", key="web_drive_input")
        
        if st.button("🚀 BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True):
            st.session_state.download_status = 'running'
            if not selected_tasks:
                st.error("⚠️ Bạn chưa chọn màu nào!")
                st.session_state.download_status = 'idle'
            else:
                render_control_buttons()
                target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    out_dir = temp_path / "Web_Images_Resized"
                    out_dir.mkdir(exist_ok=True)
                    
                    status_text = st.empty()
                    progress_bar = st.progress(0)
                    total_tasks = len(selected_tasks)

                    # Hàm Worker tải và Resize ảnh con
                    def process_image_url(img_url, color_dir, headers):
                        if not check_pause_cancel_state(): return
                        try:
                            img_name = os.path.basename(img_url.split("?")[0])
                            save_path = color_dir / img_name
                            img_data = requests.get(img_url, headers=headers, cookies=TGDD_COOKIES_DICT, timeout=10).content
                            with open(save_path, "wb") as f: f.write(img_data)
                            resize_image(save_path, w, h)
                        except Exception: pass

                    for i, task in enumerate(selected_tasks):
                        if not check_pause_cancel_state(): break
                        p_name, c_name, c_link = task["product_name"], task["color_name"], task["link"]
                        status_text.info(f"⏳ Đang xử lý: {p_name} - {c_name} ({i+1}/{total_tasks})")
                        
                        color_dir = out_dir / p_name / c_name
                        color_dir.mkdir(parents=True, exist_ok=True)
                        
                        img_urls = get_gallery_image_urls(c_link)
                        headers = {"User-Agent": "Mozilla/5.0"}
                        
                        # Tải đa luồng từng bức ảnh bên trong thư mục Màu
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            futures = [executor.submit(process_image_url, url, color_dir, headers) for url in img_urls]
                            concurrent.futures.wait(futures)
                            
                        progress_bar.progress((i + 1) / total_tasks)
                    
                    if target_folder_id and drive_service and check_pause_cancel_state():
                        status_text.info("📤 Đang Upload lên Google Drive...")
                        try:
                            root_folder_id = create_drive_folder(drive_service, f"Web_Resized_{int(time.time())}", target_folder_id)
                            folder_cache = {"": root_folder_id, ".": root_folder_id}
                            jpg_files = list(out_dir.rglob("*.jpg"))
                            for idx, img in enumerate(jpg_files):
                                if not check_pause_cancel_state(): break
                                rel_dir_str = str(img.parent.relative_to(out_dir))
                                if rel_dir_str not in folder_cache:
                                    current_parent = root_folder_id
                                    current_path = ""
                                    for part in Path(rel_dir_str).parts:
                                        current_path = os.path.join(current_path, part) if current_path else part
                                        if current_path not in folder_cache:
                                            folder_cache[current_path] = create_drive_folder(drive_service, part, current_parent)
                                        current_parent = folder_cache[current_path]
                                upload_to_drive(drive_service, img, folder_cache[rel_dir_str])
                        except: pass

                    if st.session_state.download_status == 'cancelled':
                        status_text.error("🚫 Đã hủy quá trình!")
                    else:
                        status_text.success("🎉 Hoàn tất!")
                        shutil.make_archive(temp_path / "Web_Images_Done", 'zip', out_dir)
                        with open(temp_path / "Web_Images_Done.zip", "rb") as f:
                            st.download_button("📥 TẢI KẾT QUẢ", f, file_name="Web_Images_Done.zip", mime="application/zip", use_container_width=True)
                    st.session_state.download_status = 'idle'
