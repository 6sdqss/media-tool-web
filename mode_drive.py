"""
mode_drive.py — Tab Google Drive v10.2
════════════════════════════════════════════════════════════════════════════════
CHANGELOG v10.2 (nâng từ v10.1 patch):

[UI]   Thêm hero-card header tại đầu run_mode_drive().
[PERF] Log Box: log_lines[-20:] → log_lines[-30:] — giữ 30 dòng gần nhất.
[COMPAT] Đồng bộ version với toàn bộ hệ thống v10.2.

GIỮ NGUYÊN TỪ v10.1 patch:
  [P1] api_download_folder_images → progress_cb log tiến độ realtime.
  [P2] download_direct_file → verify magic bytes sau tải.
  [P3] Delay giữa links: 3s để tránh Google rate limit (429).
  [P4] zip > 50MB không load RAM — đọc từ đĩa.
  [P5] Progress bar throttle: update sau mỗi 10%.
  [P6] Exception handling per-link, log rõ nguyên nhân.
  [P7] gdown folder retry + delay 5s.

KHÔNG thay đổi:
  - Tên hàm, signature, import list, UI layout, widget keys.
  - Logic Studio redirect, upload Drive section.
"""
from __future__ import annotations

import time
import logging
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
    show_processing_summary,
    upload_to_drive,
)

# [PATCH LOG] Dùng logger thay vì print
_log = logging.getLogger("mode_drive")

# [P4] Ngưỡng để quyết định load ZIP vào RAM hay đọc từ đĩa
_MAX_INMEM_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB

# [P3] Delay tối thiểu giữa các link để tránh Google rate limit
_INTER_LINK_DELAY_SECONDS = 3.0


def run_mode_drive(cfg: dict, drive_service):
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    st.markdown(
        "<div class='hero-card'>"
        "<h2>🌐 Drive v10.2</h2>"
        "<p>Tải ảnh từ Google Drive (folder hoặc file đơn) → Resize → ZIP. "
        "Hỗ trợ upload ngược lên Drive đích sau khi xử lý.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

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
        st.info("ℹ️ Không có Service Account — Sẽ dùng requests/gdown fallback.")

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

        # [P6] Dùng 1 log container cố định thay vì nhiều st.warning/st.success lẻ
        log_placeholder = st.empty()
        log_lines: list[str] = []

        def _log_ui(msg: str):
            """Thread-safe log vào UI placeholder."""
            log_lines.append(msg)
            # [v10.2 FIX] Giới hạn 30 dòng thay vì 20 — đủ context mà không nặng DOM
            visible = log_lines[-30:]
            log_placeholder.markdown(
                "<div class='log-box'>" + "<br>".join(visible) + "</div>",
                unsafe_allow_html=True,
            )
            _log.info("UI_LOG: %s", msg)

        successful_count = 0
        total_links = len(links)
        manifest_items: list[dict] = []
        folder_counter: dict[str, int] = {}

        def _bump_seq(folder_key: str) -> int:
            folder_counter[folder_key] = folder_counter.get(folder_key, 0) + 1
            return folder_counter[folder_key]

        # [P5] Throttle progress bar — chỉ update mỗi 10% hoặc link cuối
        _last_progress_pct = -1

        def _update_progress(current: int, total: int):
            nonlocal _last_progress_pct
            pct = int(current / total * 100)
            if pct >= _last_progress_pct + 10 or current == total:
                progress_bar.progress(current / total)
                _last_progress_pct = pct

        # ── Main loop ────────────────────────────────────────────────
        for link_index, url in enumerate(links):
            if not check_pause_cancel_state():
                _log_ui("🚫 Đã hủy bởi người dùng.")
                break

            file_id, kind = extract_drive_id_and_type(url)
            if not file_id:
                _log_ui(f"⚠️ [{link_index + 1}/{total_links}] Link sai định dạng: {url[:60]}")
                _log.warning("Invalid Drive URL: %s", url)
                _update_progress(link_index + 1, total_links)
                continue

            # Lấy tên folder
            try:
                auto_name = get_drive_name(file_id, kind, service=drive_service)
            except Exception as exc:
                _log.warning("get_drive_name failed for %s: %s", file_id, exc)
                auto_name = f"Drive_{file_id[:8]}"

            if rename_enabled and link_index < len(custom_names) and custom_names[link_index]:
                folder_name = clean_name(custom_names[link_index])
            else:
                folder_name = clean_name(auto_name) if auto_name else f"Drive_{file_id[:8]}"

            current_raw = raw_dir / folder_name
            current_raw.mkdir(parents=True, exist_ok=True)

            status_placeholder.info(
                f"📥 [{link_index + 1}/{total_links}] Đang tải: **{folder_name}**"
            )
            _log.info("Processing link %d/%d: %s (kind=%s)", link_index + 1, total_links, folder_name, kind)

            try:
                # ──────────────────────────────────────────────────────
                # CASE 1: FOLDER
                # ──────────────────────────────────────────────────────
                if kind == "folder":
                    if drive_service:
                        # [P1] Truyền progress_cb để log tiến độ folder
                        def _folder_progress_cb(done: int, total: int, fname=folder_name):
                            if done % 5 == 0 or done == total:
                                _log_ui(f"  📁 {fname}: {done}/{total} ảnh đã tải")

                        count = api_download_folder_images(
                            drive_service,
                            file_id,
                            current_raw,
                            max_files=None,
                            max_retries=2,
                            progress_cb=_folder_progress_cb,
                            delay_between_files=0.4,  # [P3] Delay per file
                        )
                        if count == 0:
                            _log_ui(f"⚠️ '{folder_name}' rỗng hoặc không có quyền truy cập.")
                            _log.warning("Empty folder or no permission: folder_id=%s", file_id)
                            _update_progress(link_index + 1, total_links)
                            continue
                        _log_ui(f"✅ Tải {count} ảnh từ '{folder_name}' (Drive API).")

                    else:
                        # [P7] gdown folder với retry + delay cải thiện
                        success = False
                        try:
                            import gdown
                            download_url = f"https://drive.google.com/drive/folders/{file_id}"

                            for use_cookies in [False, True]:
                                if success:
                                    break
                                try:
                                    _log_ui(f"  🔄 gdown folder (use_cookies={use_cookies})...")
                                    gdown.download_folder(
                                        url=download_url,
                                        output=str(current_raw),
                                        quiet=True,
                                        use_cookies=use_cookies,
                                    )
                                    downloaded = [
                                        f for f in current_raw.rglob("*")
                                        if f.is_file() and f.stat().st_size > 0
                                    ]
                                    if downloaded:
                                        success = True
                                        _log_ui(f"✅ gdown tải được {len(downloaded)} file từ '{folder_name}'.")
                                    else:
                                        _log_ui("⚠️ gdown trả về folder rỗng, thử lại...")
                                except Exception as gdown_exc:
                                    _log.warning("gdown folder attempt failed: %s", gdown_exc)
                                    _log_ui(f"⚠️ gdown lỗi: {str(gdown_exc)[:80]}")
                                    # [P7] Tăng delay lên 5s thay vì 2s
                                    time.sleep(5)

                            if not success:
                                _log_ui(f"❌ '{folder_name}' bị Google chặn — bỏ qua link này.")
                                _update_progress(link_index + 1, total_links)
                                continue

                        except ImportError:
                            _log_ui("❌ Thiếu gdown và Google API — không thể tải folder.")
                            _update_progress(link_index + 1, total_links)
                            continue

                    # Resize ảnh đã tải
                    raw_images = sorted([
                        f for f in current_raw.rglob("*")
                        if f.is_file()
                        and f.suffix.lower() in IMAGE_EXTENSIONS
                        and not f.name.startswith("._")
                        and f.stat().st_size > 0
                    ])

                    if not raw_images:
                        _log_ui(f"⚠️ '{folder_name}': Không có ảnh hợp lệ sau khi tải.")
                        _update_progress(link_index + 1, total_links)
                        continue

                    _log_ui(f"  🔄 Resize {len(raw_images)} ảnh từ '{folder_name}'...")
                    for img_path in raw_images:
                        try:
                            resize_to_multi_sizes(
                                img_path, final_dir, folder_name, img_path.stem,
                                sizes, scale_pct, quality, export_format,
                                huge_image_mode=cfg.get("huge_image_mode", True),
                            )
                        except Exception as resize_exc:
                            _log.warning("Resize failed for %s: %s", img_path.name, resize_exc)
                            _log_ui(f"  ⚠️ Resize lỗi: {img_path.name}")
                            continue

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

                # ──────────────────────────────────────────────────────
                # CASE 2: FILE ĐƠN
                # ──────────────────────────────────────────────────────
                else:
                    file_path = download_direct_file(
                        file_id, current_raw, folder_name, service=drive_service,
                        max_retries=3,
                    )

                    # [P2] Kiểm tra file có hợp lệ không (utils_patch đã thêm magic bytes check)
                    if not file_path or not file_path.exists() or file_path.stat().st_size == 0:
                        _log_ui(f"❌ Tải file '{folder_name}' thất bại hoàn toàn.")
                        _log.error("download_direct_file returned empty for %s", file_id)
                        _update_progress(link_index + 1, total_links)
                        continue

                    try:
                        resize_to_multi_sizes(
                            file_path, final_dir, folder_name, file_path.stem,
                            sizes, scale_pct, quality, export_format,
                            huge_image_mode=cfg.get("huge_image_mode", True),
                        )
                    except Exception as resize_exc:
                        _log.warning("Resize failed for %s: %s", file_path.name, resize_exc)
                        _log_ui(f"  ⚠️ Resize lỗi: {file_path.name} — {resize_exc}")
                        _update_progress(link_index + 1, total_links)
                        continue

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
                    _log_ui(f"✅ Đã xử lý file '{folder_name}'")

                successful_count += 1

                # Upload ngược lên Drive
                if target_folder_id and drive_service and check_pause_cancel_state():
                    try:
                        new_folder_id = create_drive_folder(drive_service, folder_name, target_folder_id)
                        ext = EXPORT_FORMATS.get(export_format, {}).get("ext", ".jpg")
                        uploaded_count = 0
                        for img in final_dir.rglob(f"*{ext}"):
                            upload_to_drive(drive_service, img, new_folder_id)
                            uploaded_count += 1
                        _log_ui(f"  ☁️ Upload {uploaded_count} ảnh lên Drive thành công.")
                    except Exception as upload_exc:
                        _log_ui(f"  ⚠️ Upload '{folder_name}' lỗi: {str(upload_exc)[:60]}")
                        _log.warning("Upload to Drive failed: %s", upload_exc)

            except Exception as exc:
                # [P6] Catch-all per-link — không crash toàn bộ batch
                _log_ui(f"❌ Sự cố không xử lý được với '{folder_name}': {str(exc)[:100]}")
                _log.exception("Unhandled exception for link %s:", url)
                _update_progress(link_index + 1, total_links)
                continue

            _update_progress(link_index + 1, total_links)

            # [P3] Delay giữa các link để tránh rate limit
            if link_index < total_links - 1 and check_pause_cancel_state():
                remaining = total_links - link_index - 1
                _log_ui(f"  ⏳ Đợi {_INTER_LINK_DELAY_SECONDS:.0f}s trước link tiếp ({remaining} còn lại)...")
                time.sleep(_INTER_LINK_DELAY_SECONDS)

        # ── Post-processing ──────────────────────────────────────────
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
            show_processing_summary(final_dir, sizes, duration)

            zip_path = temp_path / f"Drive_Done_{workspace['batch_id']}.zip"
            try:
                make_zip(final_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))
            except Exception as zip_exc:
                _log.error("make_zip failed: %s", zip_exc)

            if zip_path.exists() and zip_path.stat().st_size > 100:
                st.session_state.drive_zip_path = str(zip_path)
                zip_size = zip_path.stat().st_size

                # [P4] Chỉ load vào RAM nếu file nhỏ
                if zip_size <= _MAX_INMEM_ZIP_BYTES:
                    try:
                        st.session_state.drive_zip_data = zip_path.read_bytes()
                    except Exception:
                        st.session_state.drive_zip_data = None
                else:
                    st.session_state.drive_zip_data = None
                    _log_ui(f"ℹ️ ZIP lớn ({readable_file_size(zip_size)}) — tải trực tiếp từ đĩa")

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
            status_placeholder.error(
                "❌ Không nhận được file ảnh hợp lệ. "
                "Kiểm tra: link có công khai không? Drive API có được cấu hình chưa?"
            )

        st.session_state.download_status = "idle"

    # ── Download ZIP ─────────────────────────────────────────────────
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
