import streamlit as st
import os
import time
import shutil
import tempfile
from pathlib import Path
from utils import (extract_drive_id_and_type, get_drive_name, download_direct_file,
                   resize_image, create_drive_folder, upload_to_drive,
                   check_pause_cancel_state, render_control_buttons,
                   api_download_folder_images, api_get_file_name)


def run_mode_drive(w, h, drive_service):
    st.markdown("### 📥 1. NGUỒN ẢNH (Dán link cần tải)")
    links_text = st.text_area("Link File/Thư mục cần Resize (Mỗi link 1 dòng):", height=120)

    st.markdown("### 📤 2. ĐÍCH UPLOAD (Tự động up sau khi xử lý)")
    upload_link = st.text_input("Link Thư mục Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ lấy file ZIP")

    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối API Upload Drive.")

    if not drive_service:
        st.warning("⚠️ Chưa có Service Account Drive API — tải file sẽ dùng gdown (dễ bị Google chặn trên cloud).")

    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    if st.button("🚀 BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True):
        st.session_state.download_status = 'running'
        st.session_state.drive_zip_data = None

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
                log_container = st.container()

                successful_links = 0
                for i, url in enumerate(links):
                    if not check_pause_cancel_state():
                        break

                    file_id, kind = extract_drive_id_and_type(url)
                    if not file_id:
                        with log_container:
                            st.warning(f"⚠️ Link không hợp lệ: {url}")
                        continue

                    # Lấy tên qua API (ưu tiên) hoặc scrape
                    drive_name = get_drive_name(file_id, kind, service=drive_service)
                    current_raw = raw_dir / drive_name
                    current_final = final_dir / drive_name
                    current_raw.mkdir(parents=True, exist_ok=True)

                    status_text.info(f"📥 Đang tải: **{drive_name}**...")

                    try:
                        if kind == "folder":
                            # === TẢI FOLDER ===
                            if drive_service:
                                count = api_download_folder_images(
                                    drive_service, file_id, current_raw, max_files=None
                                )
                                if count == 0:
                                    with log_container:
                                        st.warning(f"⚠️ Folder '{drive_name}' — không tìm thấy ảnh hoặc không có quyền.")
                                    shutil.rmtree(current_raw, ignore_errors=True)
                                    continue
                                with log_container:
                                    st.success(f"✅ Tải được {count} ảnh từ '{drive_name}' qua API")
                            else:
                                try:
                                    import gdown
                                    folder_url = f"https://drive.google.com/drive/folders/{file_id}"
                                    success = False
                                    for use_cookie in [False, True, False]:
                                        try:
                                            gdown.download_folder(
                                                url=folder_url,
                                                output=str(current_raw),
                                                quiet=True,
                                                use_cookies=use_cookie
                                            )
                                            if any(current_raw.iterdir()):
                                                success = True
                                                break
                                        except Exception:
                                            time.sleep(2)
                                    if not success:
                                        with log_container:
                                            st.warning(f"⚠️ Bỏ qua '{drive_name}' — Google chặn gdown.")
                                        shutil.rmtree(current_raw, ignore_errors=True)
                                        continue
                                except ImportError:
                                    with log_container:
                                        st.error("❌ Không có gdown và không có Drive API!")
                                    continue

                            current_final.mkdir(parents=True, exist_ok=True)
                            all_images = [
                                f for f in current_raw.rglob("*.*")
                                if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
                                and not f.name.startswith("._")
                            ]
                            for img in all_images:
                                out_file = current_final / f"{img.stem}.jpg"
                                resize_image(img, out_file, w, h)

                        else:
                            # === TẢI FILE ĐƠN ===
                            file_path = download_direct_file(
                                file_id, current_raw, drive_name, service=drive_service
                            )
                            
                            # === NÂNG CẤP: Xử lý link chỉ Xem/Nhận xét ===
                            if not file_path or not file_path.exists() or file_path.stat().st_size == 0:
                                try:
                                    import gdown
                                    fallback_path = current_raw / f"{drive_name}_gdown"
                                    res = gdown.download(url=url, output=str(fallback_path), quiet=True, fuzzy=True)
                                    if res and fallback_path.exists() and fallback_path.stat().st_size > 0:
                                        file_path = fallback_path
                                except Exception:
                                    pass

                            if file_path and file_path.exists() and file_path.stat().st_size > 0:
                                current_final.mkdir(parents=True, exist_ok=True)
                                out_file = current_final / f"{file_path.stem}.jpg"
                                resize_image(file_path, out_file, w, h)
                                with log_container:
                                    st.success(f"✅ '{drive_name}'")
                            else:
                                with log_container:
                                    st.warning(f"⚠️ Không tải được '{drive_name}' — file rỗng hoặc bị chặn quyền tải xuống cứng.")
                                continue

                        successful_links += 1

                        # Upload lên Drive đích (nếu có)
                        if target_folder_id and drive_service and check_pause_cancel_state():
                            try:
                                new_folder_id = create_drive_folder(drive_service, drive_name, target_folder_id)
                                for img in current_final.rglob("*.jpg"):
                                    upload_to_drive(drive_service, img, new_folder_id)
                            except Exception as e:
                                with log_container:
                                    st.warning(f"⚠️ Upload '{drive_name}' lỗi: {e}")

                    except Exception as e:
                        with log_container:
                            st.warning(f"⚠️ Lỗi xử lý '{drive_name}': {e}")
                        shutil.rmtree(current_raw, ignore_errors=True)
                        continue

                    progress_bar.progress((i + 1) / len(links))

                # === KẾT THÚC ===
                if successful_links > 0 or st.session_state.download_status == 'cancelled':
                    if st.session_state.download_status == 'cancelled':
                        status_text.warning("🚫 Đã hủy! File thành công trước đó vẫn có thể tải.")
                    else:
                        status_text.success(f"🎉 HOÀN TẤT! Đã xử lý {successful_links}/{len(links)} link.")

                    shutil.make_archive(str(temp_path / "Drive_Images_Done"), 'zip', final_dir)
                    zip_path = temp_path / "Drive_Images_Done.zip"
                    if zip_path.exists():
                        with open(zip_path, "rb") as f:
                            st.session_state.drive_zip_data = f.read()
                else:
                    status_text.error("❌ Không có ảnh nào xử lý được — kiểm tra quyền chia sẻ Drive.")

            st.session_state.download_status = 'idle'

    # Nút tải ZIP (hiển thị ngoài vòng lặp)
    if st.session_state.get('drive_zip_data'):
        st.download_button(
            "📥 TẢI DỰ PHÒNG TOÀN BỘ ẢNH (FILE ZIP)",
            st.session_state.drive_zip_data,
            "Drive_Images_Done.zip",
            "application/zip",
            type="primary",
            use_container_width=True
        )
