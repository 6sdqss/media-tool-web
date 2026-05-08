"""
mode_drive.py — Tab Google Drive v9.3 (FIX VĂNG APP)
─────────────────────────────────────────────────────────
v9.3 (giữ NGUYÊN logic Drive API/gdown/upload):
- THÊM `seq_in_folder` vào manifest item → Studio map đúng ảnh sau rename.
- Lưu zip_path ổn định trên đĩa (thay vì chỉ bytes) để Studio dùng "ZIP GỐC".
- FIX LỖI: Bọc try-except và time.sleep() để chống văng app (Disconnect WebSocket)
  khi chạy vòng lặp tải nhiều link Drive liên tiếp. Xoá show_preview để giải phóng RAM.
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
    show_processing_summary,
    upload_to_drive,
)


def run_mode_drive(cfg: dict, drive_service):
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg.get("template", "{name}_{nn}")
    rename_enabled = cfg.get("rename", True)

    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None
    if "drive_zip_path" not in st.session_state:
        st.session_state.drive_zip_path = ""

    st.markdown(
        "<div class='guide-box'>"
        "💡 <b>Workflow Drive:</b> Dán link Drive → Tự tải → Resize → Chuyển sang <b>Studio</b> chỉnh viền."
        "</div>",
        unsafe_allow_html=True,
    )

    links_text = st.text_area("Links Drive", height=85, label_visibility="collapsed", placeholder="Mỗi dòng 1 link Drive...")
    custom_names_text = st.text_area("Tên xuất (tùy chọn)", height=85, placeholder="Mỗi dòng 1 tên...") if rename_enabled else ""

    if st.button("🚀 BẮT ĐẦU", type="primary", use_container_width=True):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            return
            
        custom_names_lines = [n.strip() for n in custom_names_text.splitlines() if n.strip()] if rename_enabled else []

        st.session_state.download_status = "running"
        render_control_buttons()

        ws = create_batch_workspace("drive")
        root = Path(ws["root"])
        raw_dir = Path(ws["raw_dir"])
        final_dir = Path(ws["final_dir"])
        preview_dir = Path(ws["preview_dir"])
        meta_dir = Path(ws["meta_dir"])

        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        start_time = time.time()
        man_items = []
        f_count = {}

        for l_idx, url in enumerate(links):
            if not check_pause_cancel_state():
                break

            fid, kind = extract_drive_id_and_type(url)
            if not fid:
                continue
                
            try:
                if rename_enabled and l_idx < len(custom_names_lines):
                    fname = clean_name(custom_names_lines[l_idx])
                else:
                    fname = clean_name(get_drive_name(fid, kind, drive_service))

                c_raw = raw_dir / fname
                c_raw.mkdir(parents=True, exist_ok=True)

                status_placeholder.info(f"Đang tải link {l_idx + 1}/{len(links)}: {fname}")

                if kind == "folder" and drive_service:
                    api_download_folder_images(drive_service, fid, c_raw)
                else:
                    download_direct_file(fid, c_raw, fname, drive_service)

                # Dừng một nhịp để Streamlit không ngắt kết nối
                time.sleep(0.1)

                # Lọc ra các file ảnh hợp lệ
                valid_files = [fp for fp in c_raw.rglob("*.*") if fp.is_file() and fp.suffix.lower() in IMAGE_EXTENSIONS]

                for fp_idx, fp in enumerate(valid_files):
                    resize_to_multi_sizes(
                        fp, final_dir, fname, fp.stem, sizes, scale_pct, quality, export_format,
                        huge_image_mode=cfg.get("huge_image_mode", True)
                    )
                    f_count[fname] = f_count.get(fname, 0) + 1
                    
                    meta = safe_image_meta(fp)
                    man_items.append({
                        "id": f"drv_{fname}_{fp.stem}",
                        "product": fname,
                        "color": "Mặc định",
                        "folder_name": fname,
                        "seq_in_folder": f_count[fname],
                        "source_path": str(fp),
                        "preview_path": build_preview_image(fp, preview_dir),
                        "original_name": fp.stem,
                        "default_scale_pct": 100,
                        "source_width": meta.get("width", 0),
                        "source_height": meta.get("height", 0),
                        "source_size_bytes": meta.get("size_bytes", 0),
                    })
                    
                    # Giải phóng luồng bộ nhớ mỗi 10 ảnh
                    if fp_idx % 10 == 0:
                        time.sleep(0.05)

            except Exception as e:
                status_placeholder.warning(f"⚠️ Lỗi khi tải link thứ {l_idx + 1} ({fname}): {str(e)}. Đang bỏ qua...")
                time.sleep(0.5)

            progress_bar.progress((l_idx + 1) / len(links))

        all_output_files = list(final_dir.rglob("*.*"))
        if all_output_files:
            batch_rename_with_template(final_dir, template)

            zip_path = root / f"Drive_{ws['batch_id']}.zip"
            make_zip(final_dir, zip_path, int(cfg.get("zip_compression", 6)))

            duration = time.time() - start_time
            # ĐÃ XOÁ show_preview() Ở ĐÂY ĐỂ TRÁNH TRÀN BỘ NHỚ RAM TRÌNH DUYỆT
            show_processing_summary(final_dir, sizes, duration)

            batch_meta = {
                "batch_id": ws["batch_id"],
                "root": str(root),
                "final_dir": str(final_dir),
                "source_name": "Drive",
                "source_count": len(man_items),
                "output_count": len(all_output_files),
                "zip_path": str(zip_path),
                "zip_size": readable_file_size(zip_path.stat().st_size),
            }

            st.session_state.last_batch_manifest = man_items
            st.session_state.last_batch_cfg = dict(cfg)
            st.session_state.last_batch_meta = batch_meta

            st.session_state.pop("_adjusted_root", None)
            st.session_state.pop("_studio_thumb_b64_cache", None)
            st.session_state["_goto_studio"] = True

            size_label = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
            detail_text = "Nhiều thư mục" if len(links) > 1 else (man_items[0]["product"] if man_items else "Drive")
            add_to_history("Drive", detail_text, len(all_output_files), size_label, duration)
            
            status_placeholder.success("🎯 Render xong! Đang tự động chuyển sang **tab Studio**...")
        else:
            status_placeholder.error("❌ Không nhận được file ảnh hợp lệ.")

        st.session_state.download_status = "idle"
        st.rerun()

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
            key="download_drive_zip_legacy"
        )
