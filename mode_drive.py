"""
mode_drive.py — Tab Google Drive v9.3
─────────────────────────────────────────────────────────
v9.3 (giữ NGUYÊN logic Drive API/gdown/upload):
- THÊM `seq_in_folder` vào manifest item → Studio map đúng ảnh sau rename.
- Lưu zip_path ổn định trên đĩa (thay vì chỉ bytes) để Studio dùng "ZIP GỐC".
"""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from utils import (
    EXPORT_FORMATS,
    IMAGE_EXTENSIONS,
    add_to_history,
    api_download_folder_images,
    batch_rename_with_template,
    build_preview_image,
    check_pause_cancel_state,
    clean_name,
    create_batch_workspace,
    create_drive_folder,
    download_direct_file,
    extract_drive_id_and_type,
    get_drive_name,
    get_size_label,
    make_zip,
    open_zip_for_download,
    readable_file_size,
    render_batch_kpis,
    render_control_buttons,
    resize_to_multi_sizes,
    safe_image_meta,
    save_json,
    show_preview,
    show_processing_summary,
    upload_to_drive,
)


def run_mode_drive(cfg: dict, drive_service):
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    st.markdown(
        "<div class='guide-box'>"
        "💡 <b>Workflow Drive:</b> dán link Drive (folder/file) → tự tải → resize → ZIP. "
        "Có thể upload ngược lên Drive đích."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sec-title">📥 Nguồn ảnh từ Drive</div>', unsafe_allow_html=True)
    links_text = st.text_area(
        "Links",
        height=85,
        placeholder=(
            "https://drive.google.com/drive/folders/ABC123...\n"
            "https://drive.google.com/file/d/XYZ789..."
        ),
        label_visibility="collapsed",
        key="drive_links_input",
    )

    custom_names_text = ""
    if rename_enabled:
        st.markdown(
            '<div class="sec-title">✏️ Tên xuất tùy chỉnh (tương ứng từng link)</div>',
            unsafe_allow_html=True,
        )
        st.caption("Dòng trống = dùng tên gốc của Google Drive.")
        custom_names_text = st.text_area(
            "Custom names",
            height=85,
            placeholder="Samsung_Galaxy_S25_Ultra\niPhone_16_Pro_Max",
            label_visibility="collapsed",
            key="drive_custom_names",
        )

    st.markdown('<div class="sec-title">📤 Đích upload Drive (tùy chọn)</div>', unsafe_allow_html=True)
    upload_link = st.text_input(
        "Link folder Drive đích",
        placeholder="Bỏ trống nếu chỉ cần ZIP về máy",
        label_visibility="collapsed",
        key="drive_upload_dest",
    )

    if upload_link and not drive_service:
        st.warning("⚠️ Chưa kết nối Drive API — Không thể upload ngược.")
    if not drive_service:
        st.info("ℹ️ Không có Service Account — Sẽ dùng gdown fallback (có thể bị giới hạn).")

    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None
    if "drive_zip_path" not in st.session_state:
        st.session_state.drive_zip_path = ""

    if st.button("🚀 BẮT ĐẦU TẢI & XỬ LÝ", type="primary",
                 use_container_width=True, key="btn_drive_start"):
        st.session_state.download_status = "running"
        st.session_state.drive_zip_data = None
        st.session_state.drive_zip_path = ""

        links = [line.strip() for line in links_text.splitlines() if line.strip()]
        custom_names = [name.strip() for name in custom_names_text.splitlines()] if rename_enabled else []
        target_folder_id, _ = extract_drive_id_and_type(upload_link) if upload_link else (None, None)

        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link Drive.")
            st.session_state.download_status = "idle"
            return

        render_control_buttons()
        start_time = time.time()

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
        folder_counter: dict[str, int] = {}

        def _bump_seq(folder_key: str) -> int:
            folder_counter[folder_key] = folder_counter.get(folder_key, 0) + 1
            return folder_counter[folder_key]

        for link_index, url in enumerate(links):
            if not check_pause_cancel_state():
                break

            file_id, kind = extract_drive_id_and_type(url)
            if not file_id:
                with log_container:
                    st.warning(f"⚠️ Link sai định dạng: {url}")
                continue

            auto_name = get_drive_name(file_id, kind, service=drive_service)
            if rename_enabled and link_index < len(custom_names) and custom_names[link_index]:
                folder_name = clean_name(custom_names[link_index])
            else:
                folder_name = auto_name

            current_raw = raw_dir / folder_name
            current_raw.mkdir(parents=True, exist_ok=True)

            status_placeholder.info(f"📥 [{link_index + 1}/{total_links}] {folder_name}")

            try:
                if kind == "folder":
                    if drive_service:
                        count = api_download_folder_images(
                            drive_service, file_id, current_raw, max_files=None
                        )
                        if count == 0:
                            with log_container:
                                st.warning(f"⚠️ '{folder_name}' rỗng/khóa quyền.")
                            continue
                        with log_container:
                            st.success(f"✅ Tải {count} ảnh từ '{folder_name}' (API).")
                    else:
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
                                    st.warning(f"⚠️ '{folder_name}' bị Google chặn fallback.")
                                continue
                        except ImportError:
                            with log_container:
                                st.error("❌ Thiếu gdown và Google API.")
                            continue

                    raw_images = sorted([
                        f for f in current_raw.rglob("*.*")
                        if f.suffix.lower() in IMAGE_EXTENSIONS and not f.name.startswith("._")
                    ])
                    for img_path in raw_images:
                        resize_to_multi_sizes(
                            img_path, final_dir, folder_name, img_path.stem,
                            sizes, scale_pct, quality, export_format,
                            huge_image_mode=cfg.get("huge_image_mode", True),
                        )
                        meta_info = safe_image_meta(img_path)
                        preview_path = build_preview_image(img_path, preview_dir)
                        seq = _bump_seq(folder_name)
                        manifest_items.append({
                            "id": clean_name(f"drv_{folder_name}_{img_path.stem}_{seq}"),
                            "product": folder_name,
                            "color": "Mặc định",
                            "folder_name": folder_name,
                            "seq_in_folder": seq,
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
                            sizes, scale_pct, quality, export_format,
                            huge_image_mode=cfg.get("huge_image_mode", True),
                        )
                        meta_info = safe_image_meta(file_path)
                        preview_path = build_preview_image(file_path, preview_dir)
                        seq = _bump_seq(folder_name)
                        manifest_items.append({
                            "id": clean_name(f"drv_{folder_name}_{file_path.stem}_{seq}"),
                            "product": folder_name,
                            "color": "Mặc định",
                            "folder_name": folder_name,
                            "seq_in_folder": seq,
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
                            st.warning(f"⚠️ Tải file '{folder_name}' thất bại.")
                        continue

                successful_count += 1

                if target_folder_id and drive_service and check_pause_cancel_state():
                    try:
                        new_folder_id = create_drive_folder(drive_service, folder_name, target_folder_id)
                        ext = EXPORT_FORMATS.get(export_format, {}).get("ext", ".jpg")
                        for img in final_dir.rglob(f"*{ext}"):
                            upload_to_drive(drive_service, img, new_folder_id)
                    except Exception as exc:
                        with log_container:
                            st.warning(f"⚠️ Upload '{folder_name}' lỗi: {exc}")

            except Exception as exc:
                with log_container:
                    st.warning(f"⚠️ Sự cố '{folder_name}': {exc}")
                continue

            progress_bar.progress((link_index + 1) / total_links)

        duration = time.time() - start_time
        all_output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

        if successful_count > 0 or st.session_state.download_status == "cancelled":
            if st.session_state.download_status == "cancelled":
                status_placeholder.warning(
                    f"🚫 Đã hủy — {len(all_output_files)} ảnh đã xử lý xong."
                )
            else:
                status_placeholder.success(
                    f"🎉 Hoàn tất {successful_count}/{total_links} link — "
                    f"{len(all_output_files)} ảnh!"
                )

            batch_rename_with_template(final_dir, template)
            show_preview(final_dir)
            show_processing_summary(final_dir, sizes, duration)

            zip_path = temp_path / f"Drive_Done_{workspace['batch_id']}.zip"
            try:
                make_zip(final_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))
            except Exception:
                pass

            if zip_path.exists() and zip_path.stat().st_size > 100:
                st.session_state.drive_zip_path = str(zip_path)
                try:
                    st.session_state.drive_zip_data = zip_path.read_bytes()
                except Exception:
                    st.session_state.drive_zip_data = None

            batch_meta = {
                "batch_id": workspace["batch_id"],
                "root": str(temp_path),
                "final_dir": str(final_dir),
                "source_name": "Google Drive",
                "source_count": len(manifest_items),
                "output_count": len(all_output_files),
                "zip_path": str(zip_path),
                "zip_size": readable_file_size(zip_path.stat().st_size if zip_path.exists() else 0),
            }
            render_batch_kpis(batch_meta)
            save_json(manifest_items, meta_dir / "manifest.json")
            save_json(batch_meta, meta_dir / "meta.json")
            st.session_state.last_batch_manifest = manifest_items
            st.session_state.last_batch_cfg = dict(cfg)
            st.session_state.last_batch_meta = batch_meta
            st.session_state.pop("_adjusted_root", None)
            st.session_state.pop("_studio_thumb_b64_cache", None)
            st.session_state["_goto_studio"] = True

            size_label = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
            detail_text = ", ".join([url.split("/")[-1][:15] for url in links[:3]])
            add_to_history("Drive", detail_text, len(all_output_files), size_label, duration)
            st.success("🎯 Render xong! Đang chuyển sang **tab Studio** để bạn xem & chỉnh ảnh...")
        else:
            status_placeholder.error("❌ Không nhận được file ảnh hợp lệ.")

        st.session_state.download_status = "idle"

    # ── Tải ZIP — ưu tiên đọc từ disk (path), fallback bytes ──
    zip_file_handle = open_zip_for_download(st.session_state.get("drive_zip_path", ""))
    if zip_file_handle:
        try:
            zp = Path(st.session_state.drive_zip_path)
            size_text = readable_file_size(zp.stat().st_size)
            st.success(f"✅ ZIP Drive đã sẵn sàng · {size_text}")
            st.download_button(
                label="📥 TẢI TOÀN BỘ ZIP",
                data=zip_file_handle,
                file_name=zp.name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="download_drive_zip",
            )
        finally:
            zip_file_handle.close()
    elif st.session_state.get("drive_zip_data"):
        st.success("✅ ZIP Drive đã sẵn sàng!")
        st.download_button(
            label="📥 TẢI TOÀN BỘ ZIP",
            data=st.session_state.drive_zip_data,
            file_name="Drive_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_drive_zip_bytes",
        )
