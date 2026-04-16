import streamlit as st
import os
import shutil
import tempfile
import zipfile
import time
import concurrent.futures
from pathlib import Path

from utils import (
    resize_image, ignore_system_files, create_drive_folder,
    upload_to_drive, check_pause_cancel_state, render_control_buttons
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def run_mode_local(w, h, drive_service, upload_link, extract_drive_id_and_type):
    st.info(
        "💡 **HƯỚNG DẪN:** Nén các thư mục ảnh thành **1 file .zip** rồi tải lên đây.\n\n"
        "Cấu trúc ZIP khuyên dùng: `tên_sản_phẩm/tên_màu/ảnh.jpg`"
    )

    uploaded_file = st.file_uploader(
        "📦 Tải file ZIP lên:",
        type=["zip"],
        help="Chỉ hỗ trợ .zip. Kích thước tối đa phụ thuộc cài đặt Streamlit."
    )

    if "local_zip_data" not in st.session_state:
        st.session_state.local_zip_data = None

    if st.button("🚀 BẮT ĐẦU RESIZE", type="primary", use_container_width=True, key="btn_local_start"):
        st.session_state.download_status = "running"
        st.session_state.local_zip_data  = None

        if not uploaded_file:
            st.error("⚠️ Bạn chưa tải file nào lên!")
            st.session_state.download_status = "idle"
        else:
            render_control_buttons()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                raw_dir   = temp_path / "RAW"
                final_dir = temp_path / "FINAL"
                raw_dir.mkdir(exist_ok=True)
                final_dir.mkdir(exist_ok=True)

                status_text  = st.empty()
                progress_bar = st.progress(0)
                log_box      = st.empty()
                logs         = []

                def add_log(msg: str):
                    logs.append(msg)
                    log_box.markdown(
                        "<div class='log-box'>" +
                        "<br>".join(logs[-20:]) +
                        "</div>",
                        unsafe_allow_html=True
                    )

                # ── GIẢI NÉN ──────────────────────────────
                status_text.info("⏳ Đang giải nén file...")
                try:
                    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
                    if ext == "zip":
                        with zipfile.ZipFile(uploaded_file, "r") as zf:
                            # Lọc bỏ __MACOSX và file hệ thống
                            members = [
                                m for m in zf.namelist()
                                if not m.startswith("__MACOSX")
                                and not os.path.basename(m).startswith("._")
                                and not os.path.basename(m) == ".DS_Store"
                            ]
                            zf.extractall(raw_dir, members=members)
                    else:
                        st.error("❌ Chỉ hỗ trợ file .zip!")
                        st.session_state.download_status = "idle"
                        st.stop()
                except zipfile.BadZipFile:
                    st.error("❌ File ZIP bị lỗi hoặc không đúng định dạng!")
                    st.session_state.download_status = "idle"
                    st.stop()
                except Exception as e:
                    st.error(f"❌ Lỗi giải nén: {e}")
                    st.session_state.download_status = "idle"
                    st.stop()

                # ── TÌM ẢNH HỢP LỆ ───────────────────────
                valid_files = [
                    f for f in raw_dir.rglob("*")
                    if f.is_file()
                    and f.suffix.lower() in IMAGE_EXTS
                    and not ignore_system_files(f)
                ]

                if not valid_files:
                    st.error("⚠️ Không tìm thấy ảnh hợp lệ trong file ZIP!")
                    st.session_state.download_status = "idle"
                    st.stop()

                status_text.info(f"🖼️ Tìm thấy **{len(valid_files)}** ảnh — bắt đầu resize...")
                add_log(f"Tổng số ảnh: {len(valid_files)}")

                # ── RESIZE SONG SONG ───────────────────────
                processed_count  = 0
                processed_ok     = 0
                cancel_flag      = [False]

                def process_one(file_path: Path):
                    """Hàm resize chạy trong thread pool."""
                    try:
                        rel_path = file_path.relative_to(raw_dir)
                        out_file = final_dir / rel_path.with_suffix(".jpg")
                        out_file.parent.mkdir(parents=True, exist_ok=True)
                        resize_image(file_path, out_file, w, h)
                        return str(rel_path), True
                    except Exception as e:
                        return str(file_path.name), False

                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                    future_map = {
                        executor.submit(process_one, f): f
                        for f in valid_files
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        # Kiểm tra cancel từ luồng chính
                        if not check_pause_cancel_state():
                            executor.shutdown(wait=False, cancel_futures=True)
                            cancel_flag[0] = True
                            break

                        name, ok = future.result()
                        processed_count += 1
                        if ok:
                            processed_ok += 1
                            add_log(f"✅ {name}")
                        else:
                            add_log(f"⚠️ Lỗi: {name}")

                        progress_bar.progress(processed_count / len(valid_files))

                if cancel_flag[0]:
                    status_text.warning("🚫 Đã hủy — các ảnh đã xử lý vẫn có thể tải.")
                else:
                    status_text.info(f"✔️ Resize xong {processed_ok}/{len(valid_files)} ảnh.")

                # ── UPLOAD LÊN DRIVE ───────────────────────
                target_folder_id, _ = (
                    extract_drive_id_and_type(upload_link)
                    if upload_link else (None, None)
                )

                if target_folder_id and drive_service and check_pause_cancel_state():
                    status_text.info("📤 Đang upload lên Google Drive...")
                    try:
                        root_fid = create_drive_folder(
                            drive_service,
                            f"Local_Resized_{int(time.time())}",
                            target_folder_id
                        )
                        folder_cache = {"": root_fid, ".": root_fid}

                        for img in final_dir.rglob("*.jpg"):
                            if not check_pause_cancel_state():
                                break
                            rel_dir = str(img.parent.relative_to(final_dir))
                            if rel_dir not in folder_cache:
                                current_parent = root_fid
                                current_path   = ""
                                for part in Path(rel_dir).parts:
                                    current_path = (
                                        os.path.join(current_path, part)
                                        if current_path else part
                                    )
                                    if current_path not in folder_cache:
                                        folder_cache[current_path] = create_drive_folder(
                                            drive_service, part, current_parent
                                        )
                                    current_parent = folder_cache[current_path]
                            upload_to_drive(drive_service, img, folder_cache[rel_dir])
                            add_log(f"📤 {img.name}")

                        add_log("✅ Upload Drive hoàn tất!")
                    except Exception as ue:
                        add_log(f"⚠️ Upload lỗi: {ue}")

                # ── TẠO ZIP OUTPUT ─────────────────────────
                status_text.success("🎉 Hoàn tất! Đang đóng gói ZIP...")
                zip_base = str(temp_path / "Local_Images_Done")
                shutil.make_archive(zip_base, "zip", final_dir)
                zip_path = Path(zip_base + ".zip")

                if zip_path.exists() and zip_path.stat().st_size > 22:
                    with open(zip_path, "rb") as f:
                        st.session_state.local_zip_data = f.read()
                    status_text.success(f"🎉 HOÀN TẤT — {processed_ok} ảnh đã resize xong!")
                else:
                    status_text.error("❌ Không có ảnh nào xử lý được.")

                st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP (luôn hiện nếu có dữ liệu) ──
    if st.session_state.get("local_zip_data"):
        st.download_button(
            label="📥 TẢI KẾT QUẢ (FILE ZIP)",
            data=st.session_state.local_zip_data,
            file_name="Local_Images_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_local_zip"
        )
