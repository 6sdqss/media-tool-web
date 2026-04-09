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

# ==========================================
# CẤU HÌNH TRANG
# ==========================================
st.set_page_config(page_title="Hệ thống Resize Ảnh Pro", layout="centered", page_icon="🖼️")

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
    st.stop() # Chặn không cho chạy phần code bên dưới nếu chưa đăng nhập

# Bấm nút Đăng xuất
with st.sidebar:
    st.markdown("### 👤 Xin chào, **ducpro**")
    if st.button("🚪 Đăng xuất"):
        st.session_state["logged_in"] = False
        st.rerun()

# ==========================================
# HÀM PHỤ & TIỆN ÍCH (CHUẨN CODE GỐC)
# ==========================================
def get_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    base = path.stem
    ext = path.suffix
    counter = 1
    while True:
        new_path = path.with_name(f"{base}_{counter}{ext}")
        if not new_path.exists():
            return new_path
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
    """Lấy tên thực tế của thư mục/file trên Google Drive để không bị đặt tên lung tung"""
    try:
        url = f"https://drive.google.com/file/d/{file_id}/view" if kind == "file" else f"https://drive.google.com/drive/folders/{file_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            match = re.search(r"<title>(.*?) - Google Drive</title>", resp.text)
            if match:
                name = match.group(1)
                # Xóa các ký tự cấm trong tên thư mục của Windows/Mac
                name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
                return os.path.splitext(name)[0] if kind == "file" else name
    except:
        pass
    return file_id # Nếu lỗi mạng thì lấy ID làm tên tạm

def download_direct_file(file_id: str, save_folder: Path, drive_name: str):
    """Hàm tải file đơn lẻ vượt warning của Drive (từ code gốc của bạn)"""
    base_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(base_url, stream=True, timeout=10)
    confirm_token = None

    for k, v in response.cookies.items():
        if k.startswith("download_warning"):
            confirm_token = v

    if confirm_token:
        response = session.get(base_url + f"&confirm={confirm_token}", stream=True, timeout=10)

    # Đặt tên file theo tên lấy được từ Drive
    filename = f"{drive_name}.jpg"
    save_path = get_unique_path(save_folder / filename)

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk: f.write(chunk)
    return save_path

# ==================== LOGIC RESIZE ẢNH (CHUẨN 100% CODE GỐC) ====================
def resize_image(image_path: Path, width=None, height=None):
    """Logic lọt lòng, bù nền trắng"""
    if not width or not height:
        return # Nếu chọn tải hình gốc thì bỏ qua

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
                new_w = width
                new_h = int(width / img_ratio)
            else:
                new_h = height
                new_w = int(height * img_ratio)

            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            new_img = Image.new("RGB", (width, height), (255, 255, 255))
            offset_x = (width - new_w) // 2
            offset_y = (height - new_h) // 2
            new_img.paste(resized, (offset_x, offset_y))

            save_path = image_path.with_suffix(".jpg")
            new_img.save(save_path, "JPEG", quality=95)
            if str(image_path) != str(save_path):
                image_path.unlink(missing_ok=True)
                
    except Exception as e:
        print(f"Lỗi resize ảnh: {e}")

# ==========================================
# GIAO DIỆN CHÍNH CỦA TOOL
# ==========================================
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>📥 Google Drive Downloader (Pro Max)</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6B7280;'>Tải hàng loạt, giữ đúng tên thư mục gốc, Resize lọt lòng siêu chuẩn.</p>", unsafe_allow_html=True)

with st.container(border=True):
    mode = st.radio("Chế độ hoạt động:", ["🌐 Tải từ Google Drive", "💻 Tải ảnh có sẵn trong máy tính"], horizontal=True)
    
    size_options = {
        "Tải hình gốc (Không Resize)": (None, None),
        "Tải & resize 1020x680": (1020, 680),
        "Tải & resize 1020x570": (1020, 570),
        "Tải & resize 1200x1200": (1200, 1200)
    }
    selected_size = st.selectbox("Kích thước Resize:", list(size_options.keys()))
    w, h = size_options[selected_size]

st.write("")

if "Google Drive" in mode:
    links_text = st.text_area("🔗 Dán link Google Drive (Mỗi link 1 dòng. Hỗ trợ Link File và Link Thư mục):", height=180)
    
    if st.button("🚀 BẮT ĐẦU CHẠY (DRIVE)", type="primary", use_container_width=True):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link Drive!")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                for i, url in enumerate(links):
                    file_id, kind = extract_drive_id_and_type(url)
                    if not file_id: continue
                    
                    status_text.info(f"⏳ Đang lấy thông tin tên thư mục từ link {i+1}/{len(links)}...")
                    drive_name = get_drive_name(file_id, kind)
                    
                    # TẠO THƯ MỤC CÓ TÊN ĐÚNG VỚI TÊN TRÊN DRIVE
                    out_dir = temp_path / drive_name
                    out_dir.mkdir(parents=True, exist_ok=True)

                    status_text.info(f"📥 Đang tải và xử lý: **{drive_name}**...")
                    if kind == "folder":
                        gdown.download_folder(id=file_id, output=str(out_dir), quiet=True)
                        images = [f for f in out_dir.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
                        for img in images:
                            resize_image(img, w, h)
                    else:
                        # Tải file đơn lẻ
                        file_path = download_direct_file(file_id, out_dir, drive_name)
                        resize_image(file_path, w, h)
                    
                    progress_bar.progress((i+1) / len(links))
                    if i < len(links) - 1:
                        time.sleep(3) # Nghỉ 3s chống block
                
                status_text.success("🎉 Nén file ZIP hoàn tất! Bạn hãy bấm nút tải xuống bên dưới.")
                shutil.make_archive(temp_path / "Drive_Images_Done", 'zip', temp_path)
                st.balloons()
                
                with open(temp_path / "Drive_Images_Done.zip", "rb") as f:
                    st.download_button("📥 TẢI XUỐNG TOÀN BỘ ẢNH (FILE ZIP)", f, file_name="Drive_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)

else:
    st.info("💡 **Mẹo:** Bấm nút Browse files, sau đó nhấn `Ctrl + A` để chọn hàng loạt ảnh trong máy tính.")
    uploaded_files = st.file_uploader("Kéo thả hoặc tải nhiều ảnh lên", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'webp'])
    
    if st.button("🚀 BẮT ĐẦU RESIZE LOCAL", type="primary", use_container_width=True):
        if not uploaded_files:
            st.error("⚠️ Bạn chưa tải ảnh nào lên!")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                # Tạo thư mục con để khi giải nén ra nó nằm gọn gàng
                out_dir = temp_path / "Local_Images_Resized"
                out_dir.mkdir(exist_ok=True)

                for i, file in enumerate(uploaded_files):
                    status_text.info(f"⏳ Đang xử lý: {file.name} ({i+1}/{len(uploaded_files)})")
                    img_path = out_dir / file.name
                    with open(img_path, "wb") as f:
                        f.write(file.getbuffer())
                    
                    resize_image(img_path, w, h)
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                status_text.success("🎉 Hoàn tất toàn bộ ảnh Offline! Đang tạo file ZIP...")
                shutil.make_archive(temp_path / "Local_Images_Done", 'zip', temp_path)
                st.balloons()
                
                with open(temp_path / "Local_Images_Done.zip", "rb") as f:
                    st.download_button("📥 TẢI XUỐNG TOÀN BỘ ẢNH (FILE ZIP)", f, file_name="Local_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)
