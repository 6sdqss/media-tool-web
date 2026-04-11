import streamlit as st
import time
import shutil
import tempfile
import concurrent.futures
from pathlib import Path
import gdown
from utils import (extract_drive_id_and_type, get_drive_name, download_direct_file, 
                   resize_image, create_drive_folder, upload_to_drive, 
                   check_pause_cancel_state, render_control_buttons)

def run_mode_drive(w, h, drive_service):
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
            return

        render_control_buttons()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # CÔ LẬP THƯ MỤC: Raw chứa ảnh gốc, Final chứa ảnh thành phẩm
            raw_dir = temp_path / "RAW_IMAGES"
            final_dir = temp_path / "FINAL_RESIZED"
            raw_dir.mkdir(exist_ok=True)
            final_dir.mkdir(exist_ok=True)
            
            status_text = st.empty()
            progress_bar = st.progress(0)
            successful_links = 0
            
            for i, url in enumerate(links):
                if not check_pause_cancel_state(): break
                file_id, kind = extract_drive_id_and_type(url)
                if not file_id: continue
                
                status_text.info(f"⏳ Đang lấy thông tin bộ ảnh {i+1}/{len(links)}...")
                drive_name = get_drive_name(file_id, kind)
                
                # Thư mục cho link hiện tại
                current_raw = raw_dir / drive_name
                current_final = final_dir / drive_name
                current_raw.mkdir(parents=True, exist_ok=True)
                current_final.mkdir(parents=True, exist_ok=True)

                status_text.info(f"📥 Đang tải và xử lý: **{drive_name}**...")
                
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
                            except Exception:
                                time.sleep(2)
                                
                        if not success:
                            st.error(f"❌ Google chặn tải thư mục '{drive_name}'. Bỏ qua link này.")
                            continue
                        
                        all_images = [f for f in current_raw.rglob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
                        
                        # LUẬT LẤY MAX 7 HÌNH ĐẦU TIÊN
                        if len(all_images) > 7:
                            all_images = sorted(all_images, key=lambda x: x.name)
                            images_to_process = all_images[:7]
                            st.toast(f"Đã giới hạn lấy 7 hình đầu tiên cho '{drive_name}' để tránh rác.", icon="⚠️")
                        else:
                            images_to_process = all_images
                        
                        # Xử lý Resize chuyển từ RAW sang FINAL
                        for img in images_to_process:
                            out_file = current_final / f"{img.stem}.jpg"
                            resize_image(img, out_file, w, h)
                    else:
                        file_path = download_direct_file(file_id, current_raw, drive_name)
                        if file_path and file_path.exists():
                            out_file = current_final / f"{file_path.stem}.jpg"
                            resize_image(file_path, out_file, w, h)
                            
                    successful_links += 1
                    
                except Exception as e:
                    st.warning(f"⚠️ Bỏ qua tải '{drive_name}' do lỗi: {e}")
                    continue 
                
                # UPLOAD TỪ THƯ MỤC FINAL ĐỂ ĐẢM BẢO CHỈ UP ẢNH ĐÃ RESIZE
                if target_folder_id and drive_service and check_pause_cancel_state():
                    status_text.info(f"📤 Đang Upload **{drive_name}** lên Drive đích...")
                    try:
                        new_folder_id = create_drive_folder(drive_service, drive_name, target_folder_id)
                        for img in current_final.rglob("*.jpg"):
                            upload_to_drive(drive_service, img, new_folder_id)
                    except: pass

                progress_bar.progress((i+1) / len(links))
                if i < len(links) - 1: time.sleep(3) 
            
            # KẾT THÚC VÀ CHỈ NÉN THƯ MỤC FINAL_RESIZED (Dù chỉ 1 link thành công vẫn có ZIP)
            if successful_links > 0 or st.session_state.download_status == 'cancelled':
                if st.session_state.download_status == 'cancelled':
                    status_text.warning("🚫 Đã hủy! File thành công trước đó vẫn có thể tải.")
                else:
                    status_text.success("🎉 HOÀN TẤT! Vui lòng tải file bên dưới.")
                
                shutil.make_archive(temp_path / "Drive_Images_Done", 'zip', final_dir)
                st.balloons()
                
                if os.path.exists(temp_path / "Drive_Images_Done.zip"):
                    with open(temp_path / "Drive_Images_Done.zip", "rb") as f:
                        st.download_button("📥 TẢI XUỐNG CÁC FILE THÀNH CÔNG (ZIP)", f, file_name="Drive_Images_Done.zip", mime="application/zip", type="primary", use_container_width=True)
            else:
                status_text.error("❌ Tất cả các link đều bị lỗi. Không có file nào được tạo ra.")
            
            st.session_state.download_status = 'idle'