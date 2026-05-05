"""
mode_local.py — Tab Local (ZIP)
Upload file ZIP → Giải nén → Resize multi-size → ZIP output.
Cải tiến: Tích hợp Workspace làm việc ổn định, kết nối trực tiếp với tab Studio Scale.
"""

import streamlit as st
import time
import zipfile
import concurrent.futures
from pathlib import Path

from utils import (
    clean_name,
    resize_to_multi_sizes,
    ignore_system_files,
    check_pause_cancel_state,
    render_control_buttons,
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


def _make_zip(source_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_size > 0:
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)


def run_mode_local(cfg: dict):
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    if "local_zip_data" not in st.session_state:
        st.session_state.local_zip_data = None

    st.markdown("""
    <div class="guide-box" style="padding:10px 14px;font-size:.84rem">
        💡 <b>Quy trình chuẩn:</b> Nén toàn bộ thư mục ảnh thành định dạng <b>.zip</b> và upload lên. Hệ thống xử lý song song với tốc độ cực nhanh, sau đó chuyển sang <b>Studio Scale</b> nếu cần chỉnh lệch viền.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sec-title">📦 CHỌN FILE ZIP ĐỂ UPLOAD</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Chọn file ZIP (Có thể up nhiều file một lúc):",
        type=["zip"],
        help="Hỗ trợ nhiều file .zip cùng lúc. Dung lượng khuyến nghị tối đa ~200MB/file.",
        label_visibility="collapsed",
        accept_multiple_files=True,
        key="local_upload_input",
    )

    custom_folder_names = {}
    if rename_enabled and uploaded_files:
        st.markdown('<div class="sec-title">✏️ THAY ĐỔI TÊN THƯ MỤC XUẤT RA</div>', unsafe_allow_html=True)
        st.caption("Mặc định hệ thống sẽ dùng tên gốc của file ZIP nếu bạn để trống.")

        for idx, uploaded_file in enumerate(uploaded_files):
            original_name = Path(uploaded_file.name).stem
            custom_name = st.text_input(
                f"📦 {uploaded_file.name}",
                value="",
                placeholder=f"Sẽ xuất ra thư mục: {original_name}",
                key=f"local_name_{idx}_{uploaded_file.name}",
            )
            if custom_name.strip():
                custom_folder_names[idx] = clean_name(custom_name.strip())

    st.write("")
    if st.button("BẮT ĐẦU GIẢI NÉN VÀ RESIZE", type="primary", use_container_width=True, key="btn_local_start"):
        if not uploaded_files:
            st.error("⚠️ Bạn chưa upload bất kỳ file ZIP nào để hệ thống xử lý!")
            return

        st.session_state.download_status = "running"
        st.session_state.local_zip_data = None

        render_control_buttons()
        start_time = time.time()

        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        log_placeholder = st.empty()
        log_messages: list[str] = []

        def log(message: str):
            log_messages.append(message)
            visible_logs = log_messages[-25:]
            log_placeholder.markdown(
                "<div class='log-box'>" + "<br>".join(visible_logs) + "</div>",
                unsafe_allow_html=True,
            )

        workspace = create_batch_workspace("local")
        temp_path = Path(workspace["root"])
        raw_dir = Path(workspace["raw_dir"])
        final_dir = Path(workspace["final_dir"])
        preview_dir = Path(workspace["preview_dir"])
        meta_dir = Path(workspace["meta_dir"])

        status_placeholder.info(f"⏳ Hệ thống đang giải nén {len(uploaded_files)} file ZIP. Vui lòng không làm mới trang...")

        for idx, uploaded_file in enumerate(uploaded_files):
            try:
                zip_save_path = temp_path / uploaded_file.name
                zip_save_path.write_bytes(uploaded_file.getbuffer())

                folder_name = custom_folder_names.get(idx, Path(uploaded_file.name).stem)
                extract_path = raw_dir / folder_name
                extract_path.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(zip_save_path, "r") as zf:
                    members = [
                        m for m in zf.namelist()
                        if not m.startswith("__MACOSX") and "/.DS_Store" not in m and not m.startswith(".") and "/._" not in m
                    ]
                    if not members:
                        members = zf.namelist()
                    zf.extractall(extract_path, members=members)

                zip_save_path.unlink()
                log(f"📂 Đã giải nén hoàn tất: {uploaded_file.name} ➡️ {folder_name}/")

            except zipfile.BadZipFile:
                st.error(f"❌ File {uploaded_file.name} cấu trúc ZIP bị hỏng, vui lòng nén lại file khác!")
            except Exception as exc:
                st.error(f"❌ Phát sinh lỗi lạ khi giải nén {uploaded_file.name}: {exc}")

        valid_images = [
            f for f in raw_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS and not ignore_system_files(f)
        ]

        if not valid_images:
            st.error("⚠️ Rất tiếc! Không tìm thấy ảnh nào hợp lệ bên trong các file ZIP này.")
            st.session_state.download_status = "idle"
            return

        total_images = len(valid_images)
        total_outputs = total_images * len(sizes)
        status_placeholder.info(f"🖼️ Tổng quan: {total_images} ảnh × {len(sizes)} kích thước = {total_outputs} tệp tin Output — Hệ thống đang tiến hành Resize siêu tốc...")
        log(f"⚡ Khởi động Multi-thread Resize cho {total_images} ảnh gốc")

        processed_count = 0
        was_stopped = False
        manifest_items = []

        def resize_one_image(file_path: Path):
            try:
                relative_path = file_path.relative_to(raw_dir)
                if str(relative_path.parent) != ".":
                    folder = str(relative_path.parent)
                else:
                    folder = file_path.stem

                resize_to_multi_sizes(
                    file_path, final_dir, folder, file_path.stem,
                    sizes, scale_pct, quality, export_format, huge_image_mode=cfg.get("huge_image_mode", True)
                )

                meta_info = safe_image_meta(file_path)
                preview_path = build_preview_image(file_path, preview_dir)
                item_manifest = {
                    "id": clean_name(f"loc_{folder}_{file_path.stem}"),
                    "product": folder,
                    "color": "Mặc định",
                    "folder_name": folder,
                    "source_path": str(file_path),
                    "preview_path": str(preview_path),
                    "original_name": file_path.stem,
                    "default_scale_pct": int(cfg.get("default_scale_pct", 100)),
                    "source_width": meta_info.get("width", 0),
                    "source_height": meta_info.get("height", 0),
                    "source_size_bytes": meta_info.get("size_bytes", 0),
                }
                return (file_path.name, True, "", item_manifest)
            except Exception as exc:
                return (file_path.name, False, str(exc), None)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_map = {executor.submit(resize_one_image, fp): fp for fp in valid_images}

            for future in concurrent.futures.as_completed(future_map):
                if not check_pause_cancel_state():
                    executor.shutdown(wait=False, cancel_futures=True)
                    was_stopped = True
                    break

                file_name, success, error_msg, item_manifest = future.result()
                processed_count += 1

                if success and item_manifest:
                    manifest_items.append(item_manifest)

                status_icon = "✅" if success else "⚠️"
                log_line = f"{status_icon} Xử lý xong: {file_name}"
                if error_msg:
                    log_line += f" — Báo lỗi: {error_msg}"
                log(log_line)

                progress_bar.progress(processed_count / total_images)

        if was_stopped:
            status_placeholder.warning(f"🚫 Bạn đã bấm hủy tác vụ — Đã dừng lại ở {processed_count}/{total_images} ảnh")
        else:
            status_placeholder.info(f"✔️ Tất cả {processed_count}/{total_images} ảnh đã được Scale xong — Máy chủ đang thực hiện đóng gói ZIP tự động...")

        duration = time.time() - start_time
        all_output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

        if all_output_files:
            renamed = batch_rename_with_template(final_dir, template)
            if renamed:
                log(f"✏️ Hệ thống đã đánh số và định dạng lại tên cho {renamed} ảnh")

            show_preview(final_dir)
            show_processing_summary(final_dir, sizes, duration)

            zip_output_path = temp_path / f"Local_Done_{workspace['batch_id']}.zip"
            _make_zip(final_dir, zip_output_path)

            if zip_output_path.exists() and zip_output_path.stat().st_size > 100:
                st.session_state.local_zip_data = zip_output_path.read_bytes()
                zip_size_kb = zip_output_path.stat().st_size // 1024
                status_placeholder.success(f"🎉 Rất tuyệt! Mọi thứ đã hoàn tất — Có sẵn {len(all_output_files)} ảnh chờ tải về.")
                log(f"📦 Kích thước gói ZIP: {zip_size_kb:,} KB")
            else:
                status_placeholder.error("❌ Quá trình tạo file ZIP Output bị lỗi bất thường do giới hạn bộ nhớ của máy chủ.")

            batch_meta = {
                "batch_id": workspace["batch_id"],
                "root": str(temp_path),
                "source_name": "Local ZIP",
                "source_count": len(manifest_items),
                "output_count": len(all_output_files),
                "zip_path": str(zip_output_path),
                "zip_size": readable_file_size(zip_output_path.stat().st_size if zip_output_path.exists() else 0),
            }
            save_json(manifest_items, meta_dir / "manifest.json")
            save_json(batch_meta, meta_dir / "meta.json")
            
            # Đẩy vào State để tab Studio Scale hoạt động được lập tức
            st.session_state.last_batch_manifest = manifest_items
            st.session_state.last_batch_cfg = dict(cfg)
            st.session_state.last_batch_meta = batch_meta

            size_label = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
            file_names = ", ".join([uf.name for uf in uploaded_files[:3]])
            add_to_history("Local", file_names, len(all_output_files), size_label, duration)
            
            st.info("💡 Mẹo VIP: Nếu bạn chưa ưng ý về kích thước tự động cắt của ảnh nào, chuyển ngay sang thẻ 'Studio Scale' để căn lại.")
        else:
            status_placeholder.error("❌ Quá trình resize không ra được file nào (Có thể ảnh bị lỗi cấu trúc).")

        st.session_state.download_status = "idle"

    if st.session_state.get("local_zip_data"):
        st.success("✅ File ZIP của bạn đã đóng gói thành công và sẵn sàng để lưu về máy!")
        st.download_button(
            label="📥 TẢI XUỐNG FILE ZIP NGAY",
            data=st.session_state.local_zip_data,
            file_name="Local_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_local_zip",
        )
