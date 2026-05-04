"""
mode_drive.py — Tab Google Drive
Tải ảnh từ Google Drive (folder/file) → Resize multi-size → ZIP.
Hỗ trợ: API tải trực tiếp, gdown fallback, custom naming, upload đích.
"""

import streamlit as st
import time
import shutil
import tempfile
from pathlib import Path

from utils import (
    clean_name,
    extract_drive_id_and_type,
    get_drive_name,
    download_direct_file,
    resize_to_multi_sizes,
    create_drive_folder,
    upload_to_drive,
    check_pause_cancel_state,
    render_control_buttons,
    api_download_folder_images,
    show_preview,
    show_processing_summary,
    batch_rename_with_template,
    add_to_history,
    get_size_label,
    IMAGE_EXTENSIONS,
)


def run_mode_drive(cfg: dict, drive_service):
    """
    Giao diện và logic xử lý tab Google Drive.

    Args:
        cfg: Config dict từ render_config_panel()
        drive_service: Google Drive API service (hoặc None)
    """
    # Unpack config
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    # ── INPUT: Link nguồn ──
    st.markdown(
        '<div class="sec-title">📥 NGUỒN ẢNH (Google Drive)</div>',
        unsafe_allow_html=True,
    )
    links_text = st.text_area(
        "Dán link Google Drive (mỗi dòng 1 link):",
        height=100,
        placeholder=(
            "https://drive.google.com/drive/folders/ABC123...\n"
            "https://drive.google.com/file/d/XYZ789..."
        ),
        key="drive_links_input",
    )

    # ── INPUT: Tên tùy chỉnh (hiện khi bật toggle) ──
    custom_names_text = ""
    if rename_enabled:
        st.markdown(
            '<div class="sec-title">✏️ TÊN TÙY CHỈNH (mỗi dòng ứng với 1 link)</div>',
            unsafe_allow_html=True,
        )
        st.caption("Dòng trống = dùng tên tự động từ Drive")
        custom_names_text = st.text_area(
            "Tên tùy chỉnh:",
            height=100,
            placeholder="Samsung_Galaxy_S25_Ultra\niPhone_16_Pro_Max\n(bỏ trống = auto)",
            key="drive_custom_names",
        )

    # ── INPUT: Đích upload Drive ──
    st.markdown(
        '<div class="sec-title">📤 ĐÍCH UPLOAD (tuỳ chọn)</div>',
        unsafe_allow_html=True,
    )
    upload_link = st.text_input(
        "Link thư mục Drive đích:",
        placeholder="Bỏ trống nếu chỉ cần tải ZIP về máy",
        key="drive_upload_dest",
    )

    if upload_link and not drive_service:
        st.warning("⚠️ Chưa kết nối Drive API — không thể upload lên Drive đích.")
    if not drive_service:
        st.info("ℹ️ Không có Service Account — sẽ dùng gdown (có thể bị Google chặn trên cloud).")

    # ── SESSION STATE cho ZIP data ──
    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    # ══════════════════════════════════════════════════════════
    # NÚT BẮT ĐẦU XỬ LÝ
    # ══════════════════════════════════════════════════════════
    st.write("")
    if st.button("BẮT ĐẦU XỬ LÝ", type="primary", use_container_width=True, key="btn_drive_start"):
        st.session_state.download_status = "running"
        st.session_state.drive_zip_data = None

        # Parse links
        links = [line.strip() for line in links_text.splitlines() if line.strip()]
        custom_names = (
            [name.strip() for name in custom_names_text.splitlines()]
            if rename_enabled else []
        )

        # Parse link đích
        target_folder_id, _ = (
            extract_drive_id_and_type(upload_link) if upload_link else (None, None)
        )

        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
            st.session_state.download_status = "idle"
            return

        # Hiện nút điều khiển
        render_control_buttons()
        start_time = time.time()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            raw_dir = temp_path / "RAW"
            final_dir = temp_path / "FINAL"
            raw_dir.mkdir()
            final_dir.mkdir()

            # UI elements
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            log_container = st.container()

            successful_count = 0
            total_links = len(links)

            # ── XỬ LÝ TỪNG LINK ──
            for link_index, url in enumerate(links):
                if not check_pause_cancel_state():
                    break

                # Trích xuất Drive ID
                file_id, kind = extract_drive_id_and_type(url)
                if not file_id:
                    with log_container:
                        st.warning(f"⚠️ Link không hợp lệ: {url}")
                    continue

                # Xác định tên: custom hoặc auto
                auto_name = get_drive_name(file_id, kind, service=drive_service)
                if (rename_enabled
                        and link_index < len(custom_names)
                        and custom_names[link_index]):
                    folder_name = clean_name(custom_names[link_index])
                else:
                    folder_name = auto_name

                # Tạo thư mục raw cho link này
                current_raw = raw_dir / folder_name
                current_raw.mkdir(parents=True, exist_ok=True)

                status_placeholder.info(
                    f"📥 [{link_index + 1}/{total_links}] **{folder_name}**"
                )

                try:
                    # ════ TẢI FOLDER ════
                    if kind == "folder":
                        if drive_service:
                            count = api_download_folder_images(
                                drive_service, file_id, current_raw, max_files=None
                            )
                            if count == 0:
                                with log_container:
                                    st.warning(f"⚠️ '{folder_name}' — folder rỗng hoặc không có quyền")
                                shutil.rmtree(current_raw, ignore_errors=True)
                                continue
                            with log_container:
                                st.success(f"✅ {count} ảnh từ '{folder_name}' (API)")
                        else:
                            # Fallback: gdown
                            try:
                                import gdown
                                download_url = f"https://drive.google.com/drive/folders/{file_id}"
                                success = False
                                for use_cookies in [False, True]:
                                    try:
                                        gdown.download_folder(
                                            url=download_url,
                                            output=str(current_raw),
                                            quiet=True,
                                            use_cookies=use_cookies,
                                        )
                                        if any(current_raw.iterdir()):
                                            success = True
                                            break
                                    except Exception:
                                        time.sleep(2)

                                if not success:
                                    with log_container:
                                        st.warning(f"⚠️ '{folder_name}' — gdown bị chặn")
                                    shutil.rmtree(current_raw, ignore_errors=True)
                                    continue
                            except ImportError:
                                with log_container:
                                    st.error("❌ Không có thư viện gdown và không có Drive API!")
                                continue

                        # Resize tất cả ảnh trong folder
                        raw_images = [
                            f for f in current_raw.rglob("*.*")
                            if f.suffix.lower() in IMAGE_EXTENSIONS
                            and not f.name.startswith("._")
                        ]
                        for img_path in raw_images:
                            resize_to_multi_sizes(
                                img_path, final_dir, folder_name, img_path.stem,
                                sizes, scale_pct, quality, export_format,
                            )

                    # ════ TẢI FILE ĐƠN ════
                    else:
                        file_path = download_direct_file(
                            file_id, current_raw, folder_name, service=drive_service
                        )

                        # Fallback gdown nếu API thất bại
                        if not file_path or not file_path.exists() or file_path.stat().st_size == 0:
                            try:
                                import gdown
                                fallback_path = current_raw / f"{folder_name}_fallback"
                                gdown.download(
                                    url=url, output=str(fallback_path),
                                    quiet=True, fuzzy=True,
                                )
                                if fallback_path.exists() and fallback_path.stat().st_size > 0:
                                    file_path = fallback_path
                            except Exception:
                                pass

                        if file_path and file_path.exists() and file_path.stat().st_size > 0:
                            resize_to_multi_sizes(
                                file_path, final_dir, folder_name, file_path.stem,
                                sizes, scale_pct, quality, export_format,
                            )
                            with log_container:
                                st.success(f"✅ '{folder_name}'")
                        else:
                            with log_container:
                                st.warning(f"⚠️ '{folder_name}' — không tải được file")
                            continue

                    successful_count += 1

                    # Upload lên Drive đích (nếu có)
                    if target_folder_id and drive_service and check_pause_cancel_state():
                        try:
                            new_folder_id = create_drive_folder(
                                drive_service, folder_name, target_folder_id
                            )
                            for img in final_dir.rglob("*.jpg"):
                                upload_to_drive(drive_service, img, new_folder_id)
                        except Exception as exc:
                            with log_container:
                                st.warning(f"⚠️ Upload '{folder_name}' lỗi: {exc}")

                except Exception as exc:
                    with log_container:
                        st.warning(f"⚠️ Lỗi xử lý '{folder_name}': {exc}")
                    shutil.rmtree(current_raw, ignore_errors=True)
                    continue

                progress_bar.progress((link_index + 1) / total_links)

            # ══════════════════════════════════════════════════
            # KẾT THÚC — ĐÓNG GÓI ZIP
            # ══════════════════════════════════════════════════
            duration = time.time() - start_time
            all_output_files = [
                f for f in final_dir.rglob("*")
                if f.is_file() and f.stat().st_size > 0
            ]

            if successful_count > 0 or st.session_state.download_status == "cancelled":
                if st.session_state.download_status == "cancelled":
                    status_placeholder.warning(
                        f"🚫 Đã hủy — {len(all_output_files)} ảnh trước đó vẫn có thể tải"
                    )
                else:
                    status_placeholder.success(
                        f"🎉 Hoàn tất {successful_count}/{total_links} link "
                        f"· {len(all_output_files)} ảnh"
                    )

                # Đổi tên theo template
                batch_rename_with_template(final_dir, template)

                # Preview + Summary
                show_preview(final_dir)
                show_processing_summary(final_dir, sizes, duration)

                # Đóng gói ZIP
                shutil.make_archive(str(temp_path / "Drive_Done"), "zip", final_dir)
                zip_path = temp_path / "Drive_Done.zip"
                if zip_path.exists():
                    st.session_state.drive_zip_data = zip_path.read_bytes()

                # Lưu lịch sử
                size_label = " + ".join([
                    get_size_label(w, h, m) for w, h, m in sizes
                ])
                detail_text = ", ".join([
                    url.split("/")[-1][:15] for url in links[:3]
                ])
                add_to_history("Drive", detail_text, len(all_output_files),
                               size_label, duration)
            else:
                status_placeholder.error(
                    "❌ Không có ảnh nào xử lý được — kiểm tra quyền chia sẻ Drive."
                )

        st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP (hiện ngoài block xử lý) ──
    if st.session_state.get("drive_zip_data"):
        st.download_button(
            label="📥 TẢI FILE ZIP",
            data=st.session_state.drive_zip_data,
            file_name="Drive_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_drive_zip",
        )
