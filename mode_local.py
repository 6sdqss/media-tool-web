"""
mode_local.py — Tab Local (ZIP)
Upload file ZIP → Giải nén → Resize multi-size → ZIP output.
Hỗ trợ: nhiều file ZIP, custom folder name, parallel resize.
"""

import streamlit as st
import time
import tempfile
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
)


def _make_zip(source_dir: Path, zip_path: Path):
    """Tạo ZIP từ thư mục, giữ cấu trúc, bỏ file rỗng."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_size > 0:
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)


def run_mode_local(cfg: dict):
    """
    Giao diện và logic xử lý tab Local (ZIP upload).

    Args:
        cfg: Config dict từ render_config_panel()
    """
    # Unpack config
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    # Session state cho ZIP output
    if "local_zip_data" not in st.session_state:
        st.session_state.local_zip_data = None

    # ── HƯỚNG DẪN ──
    st.markdown("""
    <div class="guide-box" style="padding:10px 14px;font-size:.84rem">
        💡 <b>Cách dùng:</b> Nén thư mục ảnh thành file <b>.zip</b> rồi upload lên đây.
        Có thể upload <b>nhiều file ZIP</b> cùng lúc.
    </div>
    """, unsafe_allow_html=True)

    # ── UPLOAD FILE ZIP ──
    st.markdown(
        '<div class="sec-title">📦 UPLOAD FILE ZIP</div>',
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "Chọn file ZIP:",
        type=["zip"],
        help="Hỗ trợ nhiều file .zip cùng lúc. Tối đa ~200MB/file.",
        label_visibility="collapsed",
        accept_multiple_files=True,
        key="local_upload_input",
    )

    # ── TÊN TÙY CHỈNH CHO TỪNG FILE ZIP ──
    custom_folder_names = {}
    if rename_enabled and uploaded_files:
        st.markdown(
            '<div class="sec-title">✏️ TÊN FOLDER OUTPUT CHO TỪNG ZIP</div>',
            unsafe_allow_html=True,
        )
        st.caption("Bỏ trống = dùng tên gốc của file ZIP")

        for idx, uploaded_file in enumerate(uploaded_files):
            original_name = Path(uploaded_file.name).stem
            custom_name = st.text_input(
                f"📦 {uploaded_file.name}",
                value="",
                placeholder=f"{original_name}  (tên gốc)",
                key=f"local_name_{idx}_{uploaded_file.name}",
            )
            if custom_name.strip():
                custom_folder_names[idx] = clean_name(custom_name.strip())

    # ══════════════════════════════════════════════════════════
    # NÚT BẮT ĐẦU
    # ══════════════════════════════════════════════════════════
    st.write("")
    if st.button("BẮT ĐẦU RESIZE", type="primary", use_container_width=True, key="btn_local_start"):
        if not uploaded_files:
            st.error("⚠️ Chưa upload file nào!")
            return

        st.session_state.download_status = "running"
        st.session_state.local_zip_data = None

        render_control_buttons()
        start_time = time.time()

        # UI elements
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        log_placeholder = st.empty()
        log_messages: list[str] = []

        def log(message: str):
            """Thêm message vào terminal log."""
            log_messages.append(message)
            # Chỉ hiện 25 dòng gần nhất
            visible_logs = log_messages[-25:]
            log_placeholder.markdown(
                "<div class='log-box'>" + "<br>".join(visible_logs) + "</div>",
                unsafe_allow_html=True,
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            raw_dir = temp_path / "RAW"
            final_dir = temp_path / "FINAL"
            raw_dir.mkdir()
            final_dir.mkdir()

            # ── GIẢI NÉN TẤT CẢ FILE ZIP ──
            status_placeholder.info(f"⏳ Đang giải nén {len(uploaded_files)} file ZIP...")

            for idx, uploaded_file in enumerate(uploaded_files):
                try:
                    # Ghi file ZIP xuống đĩa (tránh giữ trên RAM)
                    zip_save_path = temp_path / uploaded_file.name
                    zip_save_path.write_bytes(uploaded_file.getbuffer())

                    # Xác định tên folder output
                    if idx in custom_folder_names:
                        folder_name = custom_folder_names[idx]
                    else:
                        folder_name = Path(uploaded_file.name).stem

                    extract_path = raw_dir / folder_name
                    extract_path.mkdir(parents=True, exist_ok=True)

                    # Giải nén, lọc bỏ file hệ thống Mac/Windows
                    with zipfile.ZipFile(zip_save_path, "r") as zf:
                        members = [
                            m for m in zf.namelist()
                            if not m.startswith("__MACOSX")
                            and "/.DS_Store" not in m
                            and not m.startswith(".")
                            and "/._" not in m
                        ]
                        if not members:
                            members = zf.namelist()
                        zf.extractall(extract_path, members=members)

                    # Xóa file ZIP tạm
                    zip_save_path.unlink()
                    log(f"📂 {uploaded_file.name} → {folder_name}/")

                except zipfile.BadZipFile:
                    st.error(f"❌ File {uploaded_file.name} bị hỏng hoặc không đúng định dạng!")
                except Exception as exc:
                    st.error(f"❌ Lỗi giải nén {uploaded_file.name}: {exc}")

            # ── TÌM TẤT CẢ ẢNH HỢP LỆ ──
            valid_images = [
                f for f in raw_dir.rglob("*")
                if f.is_file()
                and f.suffix.lower() in IMAGE_EXTENSIONS
                and not ignore_system_files(f)
            ]

            if not valid_images:
                st.error("⚠️ Không tìm thấy ảnh hợp lệ trong ZIP!")
                st.session_state.download_status = "idle"
                return

            total_images = len(valid_images)
            total_outputs = total_images * len(sizes)
            status_placeholder.info(
                f"🖼️ {total_images} ảnh × {len(sizes)} kích thước = {total_outputs} output — đang resize..."
            )
            log(f"Tổng: {total_images} ảnh × {len(sizes)} size = {total_outputs} output")

            # ── RESIZE SONG SONG (multi-thread) ──
            processed_count = 0
            was_stopped = False

            def resize_one_image(file_path: Path):
                """Resize 1 ảnh sang tất cả kích thước. Chạy trong thread."""
                try:
                    relative_path = file_path.relative_to(raw_dir)
                    # Dùng parent path làm folder name (giữ cấu trúc thư mục)
                    if str(relative_path.parent) != ".":
                        folder = str(relative_path.parent)
                    else:
                        folder = file_path.stem

                    resize_to_multi_sizes(
                        file_path, final_dir, folder, file_path.stem,
                        sizes, scale_pct, quality, export_format,
                    )
                    return (file_path.name, True, "")
                except Exception as exc:
                    return (file_path.name, False, str(exc))

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                future_map = {
                    executor.submit(resize_one_image, fp): fp
                    for fp in valid_images
                }

                for future in concurrent.futures.as_completed(future_map):
                    if not check_pause_cancel_state():
                        executor.shutdown(wait=False, cancel_futures=True)
                        was_stopped = True
                        break

                    file_name, success, error_msg = future.result()
                    processed_count += 1

                    status_icon = "✅" if success else "⚠️"
                    log_line = f"{status_icon} {file_name}"
                    if error_msg:
                        log_line += f" — {error_msg}"
                    log(log_line)

                    progress_bar.progress(processed_count / total_images)

            if was_stopped:
                status_placeholder.warning(
                    f"🚫 Đã hủy — {processed_count}/{total_images} ảnh đã xử lý"
                )
            else:
                status_placeholder.info(
                    f"✔️ Resize xong {processed_count}/{total_images} ảnh — đang đóng gói ZIP..."
                )

            # ── ĐÓNG GÓI ZIP OUTPUT ──
            duration = time.time() - start_time
            all_output_files = [
                f for f in final_dir.rglob("*")
                if f.is_file() and f.stat().st_size > 0
            ]

            if all_output_files:
                # Đổi tên theo template
                renamed = batch_rename_with_template(final_dir, template)
                if renamed:
                    log(f"✏️ Đã đổi tên {renamed} ảnh theo template")

                # Preview + Summary
                show_preview(final_dir)
                show_processing_summary(final_dir, sizes, duration)

                # Tạo ZIP
                zip_output_path = temp_path / "Local_Done.zip"
                _make_zip(final_dir, zip_output_path)

                if zip_output_path.exists() and zip_output_path.stat().st_size > 100:
                    st.session_state.local_zip_data = zip_output_path.read_bytes()
                    zip_size_kb = zip_output_path.stat().st_size // 1024
                    status_placeholder.success(
                        f"🎉 Hoàn tất — {len(all_output_files)} ảnh!"
                    )
                    log(f"📦 ZIP: {zip_size_kb:,} KB")
                else:
                    status_placeholder.error("❌ ZIP tạo lỗi bất thường.")

                # Lưu lịch sử
                size_label = " + ".join([
                    get_size_label(w, h, m) for w, h, m in sizes
                ])
                file_names = ", ".join([uf.name for uf in uploaded_files[:3]])
                add_to_history("Local", file_names, len(all_output_files),
                               size_label, duration)
            else:
                status_placeholder.error("❌ Không có ảnh nào xử lý được!")

            st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ──
    if st.session_state.get("local_zip_data"):
        st.success("✅ Sẵn sàng tải xuống!")
        st.download_button(
            label="📥 TẢI FILE ZIP",
            data=st.session_state.local_zip_data,
            file_name="Local_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_local_zip",
        )
