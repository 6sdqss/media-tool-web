import streamlit as st
import os
import time
import shutil
import tempfile
from pathlib import Path
import gdown
from utils import (extract_drive_id_and_type, get_drive_name, download_direct_file, 
                   resize_image, create_drive_folder, upload_to_drive, 
                   check_pause_cancel_state, render_control_buttons)

def run_mode_drive(w, h, drive_service):
    st.markdown("### 📥 1. NGUỒN ẢNH (Dán link cần tải)")
    links_text = st.text_area("Link File/Thư mục cần Resize (Mỗi link 1 dòng):", height=120)
    
    st.markdown("### 📤 2. ĐÍCH UPLOAD (Tự động up sau khi xử lý)")
    upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ lấy file ZIP")
    
    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối API Upload Drive.")

    # [NÂNG CẤP]: Dùng Session State để lưu file ZIP vào RAM, không bị mất file khi load lại trang
    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    if st.button("🚀 BẮT ĐẦU CHẠY", type="primary", use_container_width=True):
        st.session_state.download_status = 'running'
        st.session_state.drive_zip_data = None  # Reset lại dữ liệu tải cũ
        
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

        if not links:
            st.error("⚠️ Vui lòng dán link!")
            st.session_state.download_status = 'idle'
        else:
            render_control_buttons()
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                raw_dir = temp_path / "RAW"
                final_dir = temp_path / "FINAL"
                raw_dir.mkdir(exist_ok=True)
                final_dir.mkdir(exist_ok=True)
                
                status_text = st.empty()
                progress_bar = st.progress(0)
                successful_links = 0

                for i, url in enumerate(links):
                    if not check_pause_cancel_state(): break
                    file_id, kind = extract_drive_id_and_type(url)
                    if not file_id: continue
                    
                    drive_name = get_drive_name(file_id, kind)
                    current_raw = raw_dir / drive_name
                    current_final = final_dir / drive_name
                    current_raw.mkdir(parents=True, exist_ok=True)

                    status_text.info(f"📥 Đang tải: {drive_name}...")
                    
                    try:
                        if kind == "folder":
                            folder_url = f"https://drive.google.com/drive/folders/{file_id}"
                            success = False
                            for use_cookie in [False, True, False]:
                                try:
                                    gdown.download_folder(url=folder_url, output=str(current_raw), quiet=True, use_cookies=use_cookie)
                                    if any(current_raw.iterdir()): 
                                        success = True
                                        break
                                except Exception: time.sleep(2)
                                    
                            if not success:
                                st.warning(f"⚠️ Bỏ qua tải '{drive_name}' do bị Google chặn.")
                                shutil.rmtree(current_raw, ignore_errors=True)
                                continue 
                            
                            current_final.mkdir(parents=True, exist_ok=True)
                            all_images = [f for f in current_raw.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
                            
                            if len(all_images) > 7:
                                all_images = sorted(all_images, key=lambda x: x.name)
                                images_to_process = all_images[:7]
                                st.toast(f"Đã giới hạn 7 hình cho '{drive_name}'", icon="⚠️")
                            else:
                                images_to_process = all_images
                                
                            for img in images_to_process:
                                out_file = current_final / f"{img.stem}.jpg"
                                resize_image(img, out_file, w, h)
                        else:
                            file_path = download_direct_file(file_id, current_raw, drive_name)
                            if file_path and file_path.exists():
                                current_final.mkdir(parents=True, exist_ok=True)
                                out_file = current_final / f"{file_path.stem}.jpg"
                                resize_image(file_path, out_file, w, h)
                                
                        successful_links += 1
                        
                        if target_folder_id and drive_service and check_pause_cancel_state():
                            try:
                                new_folder_id = create_drive_folder(drive_service, drive_name, target_folder_id)
                                for img in current_final.rglob("*.jpg"):
                                    upload_to_drive(drive_service, img, new_folder_id)
                            except: pass

                    except Exception as e:
                        st.warning(f"⚠️ Lỗi: {e}")
                        shutil.rmtree(current_raw, ignore_errors=True)
                        continue
                    
                    progress_bar.progress((i+1)/len(links))

                if successful_links > 0 or st.session_state.download_status == 'cancelled':
                    if st.session_state.download_status == 'cancelled':
                        status_text.warning("🚫 Đã hủy! File thành công trước đó vẫn có thể tải.")
                    else:
                        status_text.success("🎉 HOÀN TẤT TOÀN BỘ TIẾN TRÌNH!")
                    
                    shutil.make_archive(str(temp_path / "Drive_Images_Done"), 'zip', final_dir)
                    
                    if os.path.exists(temp_path / "Drive_Images_Done.zip"):
                        with open(temp_path / "Drive_Images_Done.zip", "rb") as f:
                            st.session_state.drive_zip_data = f.read() # Lưu vào RAM
                else:
                    status_text.error("❌ Tất cả các link đều bị lỗi quyền truy cập.")
                
                st.session_state.download_status = 'idle'

    # Hiển thị nút Tải Xuống vĩnh viễn ở ngoài vòng lặp
    if st.session_state.get('drive_zip_data'):
        st.download_button("📥 TẢI DỰ PHÒNG TOÀN BỘ ẢNH (FILE ZIP)", st.session_state.drive_zip_data, "Drive_Images_Done.zip", "application/zip", type="primary", use_container_width=True)
