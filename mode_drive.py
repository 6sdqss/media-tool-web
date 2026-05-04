import streamlit as st
import os
import re
import time
import shutil
import tempfile
from pathlib import Path
from utils import (extract_drive_id_and_type, get_drive_name, download_direct_file,
                   resize_image, create_drive_folder, upload_to_drive,
                   check_pause_cancel_state, render_control_buttons,
                   api_download_folder_images, api_get_file_name,
                   show_preview, batch_rename_files, add_to_history, get_size_label)


def _clean_name(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return re.sub(r"\s+", "_", name).strip("_") or "Untitled"


def run_mode_drive(w, h, drive_service, scale_pct=100, mode="letterbox", rename=False):
    st.markdown('<div class="sec-title">📥 NGUỒN ẢNH</div>', unsafe_allow_html=True)
    links_text = st.text_area(
        "Dán link Drive (mỗi dòng 1 link):", height=110,
        placeholder="https://drive.google.com/drive/folders/...\nhttps://drive.google.com/file/d/...",
        key="drive_links_input",
    )

    # ── ĐẶT TÊN TÙY CHỈNH ──
    custom_names_text = ""
    if rename:
        st.markdown('<div class="sec-title">✏️ TÊN TÙY CHỈNH (mỗi dòng = 1 link)</div>',
                    unsafe_allow_html=True)
        st.caption("Điền tên tương ứng từng link phía trên. Dòng trống = dùng tên gốc từ Drive.")
        custom_names_text = st.text_area(
            "Tên tùy chỉnh:", height=110,
            placeholder="Samsung_Galaxy_S25_Ultra\niPhone_16_Pro_Max\n(bỏ trống = tên gốc)",
            key="drive_custom_names",
        )

    st.markdown('<div class="sec-title">📤 ĐÍCH UPLOAD (tuỳ chọn)</div>', unsafe_allow_html=True)
    upload_link = st.text_input(
        "Link thư mục Drive đích:", placeholder="Bỏ trống nếu chỉ lấy ZIP",
        key="drive_upload_link",
    )

    if upload_link and not drive_service:
        st.warning("⚠️ Chưa kết nối Drive API — không thể upload.")

    if not drive_service:
        st.warning("⚠️ Chưa có Service Account — tải file dùng gdown (dễ bị chặn trên cloud).")

    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    # ── NÚT BẮT ĐẦU ──
    st.write("")
    if st.button("BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True, key="btn_drive"):
        st.session_state.download_status = 'running'
        st.session_state.drive_zip_data = None

        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        custom_names = [n.strip() for n in custom_names_text.splitlines()] if rename else []
        target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

        if not links:
            st.error("⚠️ Vui lòng dán link!")
            st.session_state.download_status = 'idle'
            return

        render_control_buttons()
        _t_start = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            raw_dir = temp_path / "RAW"
            final_dir = temp_path / "FINAL"
            raw_dir.mkdir(); final_dir.mkdir()

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

                # Tên: ưu tiên custom → auto detect
                auto_name = get_drive_name(file_id, kind, service=drive_service)
                if rename and i < len(custom_names) and custom_names[i]:
                    drive_name = _clean_name(custom_names[i])
                else:
                    drive_name = auto_name

                current_raw = raw_dir / drive_name
                current_final = final_dir / drive_name
                current_raw.mkdir(parents=True, exist_ok=True)

                status_text.info(f"📥 [{i+1}/{len(links)}] **{drive_name}**")

                try:
                    if kind == "folder":
                        if drive_service:
                            count = api_download_folder_images(
                                drive_service, file_id, current_raw, max_files=None)
                            if count == 0:
                                with log_container:
                                    st.warning(f"⚠️ '{drive_name}' — không có ảnh")
                                shutil.rmtree(current_raw, ignore_errors=True)
                                continue
                            with log_container:
                                st.success(f"✅ {count} ảnh từ '{drive_name}'")
                        else:
                            try:
                                import gdown
                                folder_url = f"https://drive.google.com/drive/folders/{file_id}"
                                success = False
                                for use_cookie in [False, True, False]:
                                    try:
                                        gdown.download_folder(
                                            url=folder_url, output=str(current_raw),
                                            quiet=True, use_cookies=use_cookie)
                                        if any(current_raw.iterdir()):
                                            success = True; break
                                    except Exception:
                                        time.sleep(2)
                                if not success:
                                    with log_container:
                                        st.warning(f"⚠️ '{drive_name}' — gdown bị chặn")
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
                            resize_image(img, out_file, w, h,
                                         scale_pct=scale_pct, mode=mode)
                    else:
                        file_path = download_direct_file(
                            file_id, current_raw, drive_name, service=drive_service)

                        if not file_path or not file_path.exists() or file_path.stat().st_size == 0:
                            try:
                                import gdown
                                fb = current_raw / f"{drive_name}_gdown"
                                res = gdown.download(url=url, output=str(fb), quiet=True, fuzzy=True)
                                if res and fb.exists() and fb.stat().st_size > 0:
                                    file_path = fb
                            except Exception:
                                pass

                        if file_path and file_path.exists() and file_path.stat().st_size > 0:
                            current_final.mkdir(parents=True, exist_ok=True)
                            out_file = current_final / f"{file_path.stem}.jpg"
                            resize_image(file_path, out_file, w, h,
                                         scale_pct=scale_pct, mode=mode)
                            with log_container:
                                st.success(f"✅ '{drive_name}'")
                        else:
                            with log_container:
                                st.warning(f"⚠️ '{drive_name}' — không tải được")
                            continue

                    successful_links += 1

                    if target_folder_id and drive_service and check_pause_cancel_state():
                        try:
                            nf = create_drive_folder(drive_service, drive_name, target_folder_id)
                            for img in current_final.rglob("*.jpg"):
                                upload_to_drive(drive_service, img, nf)
                        except Exception as e:
                            with log_container:
                                st.warning(f"⚠️ Upload '{drive_name}' lỗi: {e}")

                except Exception as e:
                    with log_container:
                        st.warning(f"⚠️ Lỗi '{drive_name}': {e}")
                    shutil.rmtree(current_raw, ignore_errors=True)
                    continue

                progress_bar.progress((i + 1) / len(links))

            # === KẾT THÚC ===
            _duration = time.time() - _t_start
            all_final = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

            if successful_links > 0 or st.session_state.download_status == 'cancelled':
                if st.session_state.download_status == 'cancelled':
                    status_text.warning(f"🚫 Đã hủy — {len(all_final)} ảnh trước đó vẫn có thể tải")
                else:
                    status_text.success(f"🎉 Hoàn tất {successful_links}/{len(links)} link")

                # Rename nếu bật + không có custom name (dùng auto-rename pattern)
                if rename and all_final:
                    batch_rename_files(final_dir)

                show_preview(final_dir)

                shutil.make_archive(str(temp_path / "Drive_Images_Done"), 'zip', final_dir)
                zp = temp_path / "Drive_Images_Done.zip"
                if zp.exists():
                    with open(zp, "rb") as f:
                        st.session_state.drive_zip_data = f.read()

                detail = ", ".join([l.split("/")[-1][:20] for l in links[:3]])
                add_to_history("Drive", detail, len(all_final),
                               get_size_label(w, h, mode), _duration)
            else:
                status_text.error("❌ Không có ảnh nào — kiểm tra quyền chia sẻ.")

        st.session_state.download_status = 'idle'

    if st.session_state.get('drive_zip_data'):
        st.download_button(
            "📥 TẢI FILE ZIP",
            st.session_state.drive_zip_data,
            "Drive_Images_Done.zip", "application/zip",
            type="primary", use_container_width=True, key="dl_drive")
