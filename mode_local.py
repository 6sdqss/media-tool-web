import streamlit as st
import time
import shutil
import tempfile
import zipfile
import concurrent.futures
from pathlib import Path
from utils import (resize_image, ignore_system_files, create_drive_folder, 
                   upload_to_drive, check_pause_cancel_state, render_control_buttons)

def run_mode_local(w, h, drive_service, upload_link, extract_drive_id_and_type):
    st.info("💡 **HƯỚNG DẪN:** Nén tất cả các thư mục cần làm thành **1 file .zip hoặc .rar** rồi tải lên đây.")
    
    uploaded_file = st.file_uploader("📦 Tải lên file ZIP hoặc RAR chứa các thư mục ảnh:", type=['zip', 'rar'])

    if st.button("🚀 BẮT ĐẦU RESIZE LOCAL", type="primary", use_container_width=True):
        st.session_state.download_status = 'running'
        if not uploaded_file:
            st.error("⚠️ Bạn chưa tải file lên!")
            st.session_state.download_status = 'idle'
            return

        render_control_buttons()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            raw_dir = temp_path / "RAW_EXTRACTED"
            final_dir = temp_path / "FINAL_RESIZED"
            raw_dir.mkdir(exist_ok=True)
            final_dir.mkdir(exist_ok=True)
            
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            status_text.info("⏳ Đang giải nén file...")
            try:
                file_ext = uploaded_file.name.split('.')[-1].lower()
                if file_ext == 'zip':
                    with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                        zip_ref.extractall(raw_dir)
                elif file_ext == 'rar':
                    import rarfile
                    temp_rar_path = temp_path / uploaded_file.name
                    with open(temp_rar_path, "wb") as f: f.write(uploaded_file.getbuffer())
                    with rarfile.RarFile(temp_rar_path, 'r') as rar_ref:
                        rar_ref.extractall(raw_dir)
            except Exception as e:
                st.error(f"❌ Lỗi giải nén: {e}")
                st.session_state.download_status = 'idle'
                st.stop()

            valid_files = [f for f in raw_dir.rglob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp'] and not ignore_system_files(f)]

            if not valid_files:
                st.error("⚠️ Không tìm thấy ảnh hợp lệ!")
            else:
                status_text.info(f"⏳ Đang xử lý Đa luồng {len(valid_files)} ảnh...")
                
                def process_local_file(file_path):
                    if not check_pause_cancel_state(): return
                    rel_path = file_path.relative_to(raw_dir)
                    if "MACOSX" in str(rel_path): return
                    
                    # Đổi đuôi thành jpg để lưu vào FINAL
                    out_file = final_dir / rel_path.with_suffix('.jpg')
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        resize_image(file_path, out_file, w, h)
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
                        jpg_files = list(final_dir.rglob("*.jpg"))
                        for idx, img in enumerate(jpg_files):
                            if not check_pause_cancel_state(): break
                            rel_dir_str = str(img.parent.relative_to(final_dir))
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
                shutil.make_archive(temp_path / "Resized_Finished", 'zip', final_dir)
                with open(temp_path / "Resized_Finished.zip", "rb") as f:
                    st.download_button("📥 TẢI KẾT QUẢ", f, file_name="Resized_Finished.zip", mime="application/zip", use_container_width=True)
            st.session_state.download_status = 'idle'