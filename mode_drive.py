import streamlit as st
import os
import time
import shutil
import tempfile
from pathlib import Path
import gdown

from utils import (
    extract_drive_id_and_type, get_drive_name, download_direct_file,
    resize_image, create_drive_folder, upload_to_drive,
    check_pause_cancel_state, render_control_buttons
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
MAX_IMAGES_PER_FOLDER = 7


def _download_drive_folder(file_id: str, raw_dir: Path) -> bool:
    """
    Tải thư mục Google Drive về local với nhiều phương thức fallback.
    Trả về True nếu tải được ít nhất 1 file.
    """
    folder_url = f"https://drive.google.com/drive/folders/{file_id}"

    for attempt, (use_cookies, fuzzy) in enumerate([
        (False, True),
        (True,  True),
        (False, False),
    ]):
        try:
            gdown.download_folder(
                url=folder_url,
                output=str(raw_dir),
                quiet=True,
                use_cookies=use_cookies,
                remaining_ok=True,
            )
            files = list(raw_dir.rglob("*"))
            if any(f.is_file() for f in files):
                return True
        except Exception:
            pass
        time.sleep(1.5)

    return False


def run_mode_drive(w, h, drive_service):
    st.markdown("### 📥 1. NGUỒN ẢNH")
    st.caption("Dán link file hoặc thư mục Google Drive — mỗi link 1 dòng.")
    links_text = st.text_area(
        "Link File / Thư mục Drive:",
        height=130,
        placeholder="https://drive.google.com/drive/folders/...\nhttps://drive.google.com/file/d/..."
    )

    st.markdown("### 📤 2. ĐÍCH UPLOAD *(tùy chọn)*")
    upload_link = st.text_input(
        "Link Thư mục Drive ĐÍCH:",
        placeholder="Bỏ trống nếu chỉ muốn tải file ZIP về máy"
    )

    if upload_link and not drive_service:
        st.warning("⚠️ Chưa kết nối Google Drive API — chức năng upload sẽ bị bỏ qua.")

    # Khởi tạo session state
    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    # ── NÚT BẮT ĐẦU ──────────────────────────────
    if st.button("🚀 BẮT ĐẦU CHẠY", type="primary", use_container_width=True, key="btn_drive_start"):
        st.session_state.download_status = "running"
        st.session_state.drive_zip_data  = None

        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
            st.session_state.download_status = "idle"
        else:
            target_folder_id, _ = (
                extract_drive_id_and_type(upload_link)
                if upload_link else (None, None)
            )

            render_control_buttons()
            status_text  = st.empty()
            progress_bar = st.progress(0)
            log_box      = st.empty()
            logs         = []

            def add_log(msg: str):
                logs.append(msg)
                log_box.markdown(
                    "<div class='log-box'>" +
                    "<br>".join(logs[-20:]) +   # hiển thị 20 dòng cuối
                    "</div>",
                    unsafe_allow_html=True
                )

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                raw_dir   = temp_path / "RAW"
                final_dir = temp_path / "FINAL"
                raw_dir.mkdir(exist_ok=True)
                final_dir.mkdir(exist_ok=True)

                successful = 0

                for i, url in enumerate(links):
                    if not check_pause_cancel_state():
                        break

                    file_id, kind = extract_drive_id_and_type(url)
                    if not file_id:
                        add_log(f"⚠️ Link không hợp lệ: {url[:60]}")
                        continue

                    drive_name = get_drive_name(file_id, kind)
                    status_text.info(f"⏳ [{i+1}/{len(links)}] Đang tải: **{drive_name}**")

                    curr_raw   = raw_dir   / drive_name
                    curr_final = final_dir / drive_name
                    curr_raw.mkdir(parents=True, exist_ok=True)

                    try:
                        # ── TẢI FOLDER ─────────────────────────
                        if kind == "folder":
                            ok = _download_drive_folder(file_id, curr_raw)
                            if not ok:
                                add_log(f"❌ Không tải được folder '{drive_name}' (bị chặn / không có quyền)")
                                shutil.rmtree(curr_raw, ignore_errors=True)
                                continue

                            curr_final.mkdir(parents=True, exist_ok=True)
                            all_imgs = sorted(
                                [f for f in curr_raw.rglob("*") if f.suffix.lower() in IMAGE_EXTS],
                                key=lambda x: x.name
                            )

                            if len(all_imgs) > MAX_IMAGES_PER_FOLDER:
                                st.toast(f"Giới hạn {MAX_IMAGES_PER_FOLDER} ảnh cho '{drive_name}'", icon="⚠️")
                                all_imgs = all_imgs[:MAX_IMAGES_PER_FOLDER]

                            for img in all_imgs:
                                if not check_pause_cancel_state():
                                    break
                                out_file = curr_final / f"{img.stem}.jpg"
                                resize_image(img, out_file, w, h)
                                add_log(f"✅ Resize: {img.name}")

                        # ── TẢI FILE ĐƠN ───────────────────────
                        else:
                            file_path = download_direct_file(file_id, curr_raw, drive_name)
                            if file_path and file_path.exists() and file_path.stat().st_size > 1024:
                                curr_final.mkdir(parents=True, exist_ok=True)
                                out_file = curr_final / f"{file_path.stem}.jpg"
                                resize_image(file_path, out_file, w, h)
                                add_log(f"✅ File: {drive_name}")
                            else:
                                add_log(f"❌ Không tải được file '{drive_name}'")
                                continue

                        successful += 1

                        # ── UPLOAD LÊN DRIVE ────────────────────
                        if target_folder_id and drive_service and check_pause_cancel_state():
                            try:
                                new_fid = create_drive_folder(drive_service, drive_name, target_folder_id)
                                for img in curr_final.rglob("*.jpg"):
                                    upload_to_drive(drive_service, img, new_fid)
                                add_log(f"📤 Uploaded '{drive_name}' lên Drive")
                            except Exception as ue:
                                add_log(f"⚠️ Upload lỗi '{drive_name}': {ue}")

                    except Exception as e:
                        add_log(f"❌ Lỗi '{drive_name}': {e}")
                        shutil.rmtree(curr_raw, ignore_errors=True)

                    progress_bar.progress((i + 1) / len(links))

                # ── KẾT THÚC ───────────────────────────────
                if st.session_state.download_status == "cancelled":
                    status_text.warning("🚫 Đã hủy! Các file hoàn thành trước đó vẫn có thể tải.")
                elif successful == 0:
                    status_text.error("❌ Tất cả link đều bị lỗi — kiểm tra quyền chia sẻ Drive.")
                else:
                    status_text.success(f"🎉 HOÀN TẤT! Đã xử lý {successful}/{len(links)} link.")

                # Tạo ZIP và lưu vào RAM
                zip_base = str(temp_path / "Drive_Images_Done")
                shutil.make_archive(zip_base, "zip", final_dir)
                zip_path = Path(zip_base + ".zip")
                if zip_path.exists() and zip_path.stat().st_size > 22:  # > header rỗng
                    with open(zip_path, "rb") as f:
                        st.session_state.drive_zip_data = f.read()

                st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP (luôn hiện nếu có dữ liệu) ──
    if st.session_state.get("drive_zip_data"):
        st.download_button(
            label="📥 TẢI TOÀN BỘ ẢNH (FILE ZIP)",
            data=st.session_state.drive_zip_data,
            file_name="Drive_Images_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_drive_zip"
        )
