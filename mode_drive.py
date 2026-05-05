"""
mode_drive.py — Tab Google Drive
Tải ảnh từ Google Drive (folder/file) → Resize multi-size → ZIP.
Hỗ trợ: API tải trực tiếp, gdown fallback, custom naming, upload đích.
Cải tiến: Tích hợp Workspace bền vững để có thể tiếp tục chỉnh sửa ở tab Studio Scale.
"""

import streamlit as st
import time
import shutil
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
    create_batch_workspace,
    safe_image_meta,
    build_preview_image,
    save_json,
    readable_file_size
)


def run_mode_drive(cfg: dict, drive_service):
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    st.markdown('<div class="sec-title">📥 NGUỒN ẢNH TỪ GOOGLE DRIVE</div>', unsafe_allow_html=True)
    links_text = st.text_area(
        "Dán link Google Drive (mỗi dòng 1 link):",
        height=100,
        placeholder="https://drive.google.com/drive/folders/ABC123...\nhttps://drive.google.com/file/d/XYZ789...",
        key="drive_links_input",
    )

    custom_names_text = ""
    if rename_enabled:
        st.markdown('<div class="sec-title">✏️ TÊN TÙY CHỈNH CHO THƯ MỤC XUẤT (Tương ứng theo từng link)</div>', unsafe_allow_html=True)
        st.caption("Mẹo: Dòng trống = tự động lấy tên gốc của Google Drive")
        custom_names_text = st.text_area(
            "Tên tùy chỉnh:",
            height=100,
            placeholder="Samsung_Galaxy_S25_Ultra\niPhone_16_Pro_Max",
            key="drive_custom_names",
        )

    st.markdown('<div class="sec-title">📤 ĐÍCH UPLOAD DRIVE (Tùy chọn tải ngược lên)</div>', unsafe_allow_html=True)
    upload_link = st.text_input(
        "Link thư mục Drive đích:",
        placeholder="Bỏ trống nếu chỉ cần tải ZIP về máy tính",
        key="drive_upload_dest",
    )

    if upload_link and not drive_service:
        st.warning("⚠️ Hệ thống chưa kết nối Drive API — Không thể thực hiện tính năng upload ngược lên Drive đích.")
    if not drive_service:
        st.info("ℹ️ Không tìm thấy Service Account — Hệ thống sẽ tự động chuyển qua gdown fallback (có thể bị giới hạn nếu quá tải).")

    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    st.write("")
    if st.button("BẮT ĐẦU TẢI VÀ XỬ LÝ", type="primary", use_container_width=True, key="btn_drive_start"):
        st.session_state.download_status = "running"
        st.session_state.drive_zip_data = None

        links = [line.strip() for line in links_text.splitlines() if line.strip()]
        custom_names = [name.strip() for name in custom_names_text.splitlines()] if rename_enabled else []
        target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link Google Drive hợp lệ!")
            st.session_state.download_status = "idle"
            return

        render_control_buttons()
        start_time = time.time()

        # Thay vì TemporaryDirectory, tạo workspace lưu giữ lâu dài cho phép dùng ở Studio Scale
        workspace = create_batch_workspace("drive")
        temp_path = Path(workspace["root"])
        raw_dir = Path(workspace["raw_dir"])
        final_dir = Path(workspace["final_dir"])
        preview_dir = Path(workspace["preview_dir"])
        meta_dir = Path(workspace["meta_dir"])

        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        log_container = st.container()

        successful_count = 0
        total_links = len(links)
        manifest_items: list[dict] = []
        all_output_files = []

        for link_index, url in enumerate(links):
            if not check_pause_cancel_state():
                break

            file_id, kind = extract_drive_id_and_type(url)
            if not file_id:
                with log_container:
                    st.warning(f"⚠️ Link không đúng định dạng Drive: {url}")
                continue

            auto_name = get_drive_name(file_id, kind, service=drive_service)
            if rename_enabled and link_index < len(custom_names) and custom_names[link_index]:
                folder_name = clean_name(custom_names[link_index])
            else:
                folder_name = auto_name

            current_raw = raw_dir / folder_name
            current_raw.mkdir(parents=True, exist_ok=True)

            status_placeholder.info(f"📥 [{link_index + 1}/{total_links}] Đang nạp: **{folder_name}**")

            try:
                if kind == "folder":
                    if drive_service:
                        count = api_download_folder_images(drive_service, file_id, current_raw, max_files=None)
                        if count == 0:
                            with log_container:
                                st.warning(f"⚠️ Thư mục '{folder_name}' rỗng hoặc bị khóa quyền truy cập.")
                            continue
                        with log_container:
                            st.success(f"✅ Tải thành công {count} ảnh từ thư mục '{folder_name}' bằng API.")
                    else:
                        try:
                            import gdown
                            download_url = f"https://drive.google.com/drive/folders/{file_id}"
                            success = False
                            for use_cookies in [False, True]:
                                try:
                                    gdown.download_folder(url=download_url, output=str(current_raw), quiet=True, use_cookies=use_cookies)
                                    if any(current_raw.iterdir()):
                                        success = True
                                        break
                                except Exception:
                                    time.sleep(2)
                            if not success:
                                with log_container:
                                    st.warning(f"⚠️ '{folder_name}' — Bị hệ thống Google chặn download fallback.")
                                continue
                        except ImportError:
                            with log_container:
                                st.error("❌ Môi trường đang thiếu thư viện gdown và Google API Service.")
                            continue

                    raw_images = [
                        f for f in current_raw.rglob("*.*")
                        if f.suffix.lower() in IMAGE_EXTENSIONS and not f.name.startswith("._")
                    ]
                    for img_path in raw_images:
                        resize_to_multi_sizes(
                            img_path, final_dir, folder_name, img_path.stem,
                            sizes, scale_pct, quality, export_format, huge_image_mode=cfg.get("huge_image_mode", True)
                        )
                        # Trích xuất Manifest cho phép Studio Scale điều chỉnh lại
                        meta_info = safe_image_meta(img_path)
                        preview_path = build_preview_image(img_path, preview_dir)
                        manifest_items.append({
                            "id": clean_name(f"drv_{folder_name}_{img_path.stem}"),
                            "product": folder_name,
                            "color": "Mặc định",
                            "folder_name": folder_name,
                            "source_path": str(img_path),
                            "preview_path": str(preview_path),
                            "original_name": img_path.stem,
                            "default_scale_pct": int(cfg.get("default_scale_pct", 100)),
                            "source_width": meta_info.get("width", 0),
                            "source_height": meta_info.get("height", 0),
                            "source_size_bytes": meta_info.get("size_bytes", 0),
                        })

                else:
                    file_path = download_direct_file(file_id, current_raw, folder_name, service=drive_service)
                    if not file_path or not file_path.exists() or file_path.stat().st_size == 0:
                        try:
                            import gdown
                            fallback_path = current_raw / f"{folder_name}_fallback"
                            gdown.download(url=url, output=str(fallback_path), quiet=True, fuzzy=True)
                            if fallback_path.exists() and fallback_path.stat().st_size > 0:
                                file_path = fallback_path
                        except Exception:
                            pass

                    if file_path and file_path.exists() and file_path.stat().st_size > 0:
                        resize_to_multi_sizes(
                            file_path, final_dir, folder_name, file_path.stem,
                            sizes, scale_pct, quality, export_format, huge_image_mode=cfg.get("huge_image_mode", True)
                        )
                        meta_info = safe_image_meta(file_path)
                        preview_path = build_preview_image(file_path, preview_dir)
                        manifest_items.append({
                            "id": clean_name(f"drv_{folder_name}_{file_path.stem}"),
                            "product": folder_name,
                            "color": "Mặc định",
                            "folder_name": folder_name,
                            "source_path": str(file_path),
                            "preview_path": str(preview_path),
                            "original_name": file_path.stem,
                            "default_scale_pct": int(cfg.get("default_scale_pct", 100)),
                            "source_width": meta_info.get("width", 0),
                            "source_height": meta_info.get("height", 0),
                            "source_size_bytes": meta_info.get("size_bytes", 0),
                        })
                        with log_container:
                            st.success(f"✅ Đã xử lý '{folder_name}'")
                    else:
                        with log_container:
                            st.warning(f"⚠️ Thất bại khi tải file '{folder_name}'.")
                        continue

                successful_count += 1

                if target_folder_id and drive_service and check_pause_cancel_state():
                    try:
                        new_folder_id = create_drive_folder(drive_service, folder_name, target_folder_id)
                        for img in final_dir.rglob(f"*{EXPORT_FORMATS.get(export_format, {}).get('ext', '.jpg')}"):
                            upload_to_drive(drive_service, img, new_folder_id)
                    except Exception as exc:
                        with log_container:
                            st.warning(f"⚠️ Upload lên Drive đích '{folder_name}' bị lỗi: {exc}")

            except Exception as exc:
                with log_container:
                    st.warning(f"⚠️ Xảy ra sự cố bất thường '{folder_name}': {exc}")
                continue

            progress_bar.progress((link_index + 1) / total_links)

        duration = time.time() - start_time
        all_output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

        if successful_count > 0 or st.session_state.download_status == "cancelled":
            if st.session_state.download_status == "cancelled":
                status_placeholder.warning(f"🚫 Tác vụ bị hủy giữa chừng — Vẫn có thể tải {len(all_output_files)} ảnh đã xử lý thành công.")
            else:
                status_placeholder.success(f"🎉 Hoàn tất {successful_count}/{total_links} links — Tổng cộng {len(all_output_files)} ảnh!")

            batch_rename_with_template(final_dir, template)
            show_preview(final_dir)
            show_processing_summary(final_dir, sizes, duration)

            zip_path = temp_path / f"Drive_Done_{workspace['batch_id']}.zip"
            shutil.make_archive(str(zip_path.with_suffix("")), "zip", final_dir)
            if zip_path.exists():
                st.session_state.drive_zip_data = zip_path.read_bytes()

            # Lưu Workspace Meta để sử dụng cho Tab Studio Scale
            batch_meta = {
                "batch_id": workspace["batch_id"],
                "root": str(temp_path),
                "source_name": "Google Drive",
                "source_count": len(manifest_items),
                "output_count": len(all_output_files),
                "zip_path": str(zip_path),
                "zip_size": readable_file_size(zip_path.stat().st_size if zip_path.exists() else 0),
            }
            save_json(manifest_items, meta_dir / "manifest.json")
            save_json(batch_meta, meta_dir / "meta.json")
            st.session_state.last_batch_manifest = manifest_items
            st.session_state.last_batch_cfg = dict(cfg)
            st.session_state.last_batch_meta = batch_meta

            size_label = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
            detail_text = ", ".join([url.split("/")[-1][:15] for url in links[:3]])
            add_to_history("Drive", detail_text, len(all_output_files), size_label, duration)
            st.info("💡 Mẹo: Nếu ảnh xuất ra bị lệch khung, bạn có thể sang tab 'Studio Scale' để căn chỉnh riêng lẻ và render lại ngay lập tức!")
        else:
            status_placeholder.error("❌ Hệ thống không nhận dạng được bất kỳ file ảnh nào hợp lệ để xử lý.")

        st.session_state.download_status = "idle"

    if st.session_state.get("drive_zip_data"):
        st.download_button(
            label="📥 TẢI TOÀN BỘ FILE ZIP",
            data=st.session_state.drive_zip_data,
            file_name="Drive_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_drive_zip",
        )
