"""
mode_local.py — Tab Local ZIP v9.3
─────────────────────────────────────────────────────────
v9.3 (giữ NGUYÊN logic giải nén / multi-thread resize):
- THÊM `seq_in_folder` vào manifest item → Studio map đúng ảnh sau rename.
- Lưu zip_path ổn định trên đĩa để Studio dùng "ZIP GỐC".
"""

from __future__ import annotations

import time
import zipfile
import concurrent.futures
import threading
from pathlib import Path

import streamlit as st

from utils import (
    IMAGE_EXTENSIONS,
    add_to_history,
    batch_rename_with_template,
    build_preview_image,
    check_pause_cancel_state,
    clean_name,
    create_batch_workspace,
    get_size_label,
    ignore_system_files,
    make_zip,
    readable_file_size,
    render_batch_kpis,
    render_control_buttons,
    resize_to_multi_sizes,
    safe_image_meta,
    save_json,
)


def run_mode_local(cfg: dict):
    sizes = cfg["sizes"]
    scale_pct = cfg["scale_pct"]
    quality = cfg["quality"]
    export_format = cfg["export_format"]
    template = cfg["template"]
    rename_enabled = cfg["rename"]

    if "local_zip_data" not in st.session_state:
        st.session_state.local_zip_data = None
    if "local_zip_path" not in st.session_state:
        st.session_state.local_zip_path = ""

    st.markdown(
        "<div class='guide-box'>"
        "💡 <b>Workflow Local:</b> nén thư mục ảnh thành <b>.zip</b> → upload → "
        "tự giải nén & resize song song. Sau đó qua <b>Studio</b> nếu cần chỉnh viền."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sec-title">📦 Chọn file ZIP</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "ZIP files",
        type=["zip"],
        help="Hỗ trợ nhiều file ZIP. Khuyến nghị tối đa ~200MB/file.",
        label_visibility="collapsed",
        accept_multiple_files=True,
        key="local_upload_input",
    )

    custom_folder_names = {}
    if rename_enabled and uploaded_files:
        st.markdown(
            '<div class="sec-title">✏️ Đổi tên thư mục xuất</div>',
            unsafe_allow_html=True,
        )
        st.caption("Trống = dùng tên gốc của file ZIP.")

        for idx, uploaded_file in enumerate(uploaded_files):
            original_name = Path(uploaded_file.name).stem
            custom_name = st.text_input(
                f"📦 {uploaded_file.name}",
                value="",
                placeholder=f"Mặc định: {original_name}",
                key=f"local_name_{idx}_{uploaded_file.name}",
            )
            if custom_name.strip():
                custom_folder_names[idx] = clean_name(custom_name.strip())

    if st.button("🚀 GIẢI NÉN & RESIZE", type="primary",
                 use_container_width=True, key="btn_local_start"):
        if not uploaded_files:
            st.error("⚠️ Bạn chưa upload file ZIP nào.")
            return

        st.session_state.download_status = "running"
        st.session_state.local_zip_data = None
        st.session_state.local_zip_path = ""

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

        status_placeholder.info(f"⏳ Đang giải nén {len(uploaded_files)} file ZIP...")

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
                        if not m.startswith("__MACOSX")
                        and "/.DS_Store" not in m
                        and not m.startswith(".")
                        and "/._" not in m
                    ]
                    if not members:
                        members = zf.namelist()
                    zf.extractall(extract_path, members=members)

                zip_save_path.unlink()
                log(f"📂 Giải nén: {uploaded_file.name} → {folder_name}/")

            except zipfile.BadZipFile:
                st.error(f"❌ ZIP hỏng: {uploaded_file.name}")
            except Exception as exc:
                st.error(f"❌ Lỗi {uploaded_file.name}: {exc}")

        valid_images = sorted([
            f for f in raw_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS and not ignore_system_files(f)
        ])

        if not valid_images:
            st.error("⚠️ Không tìm thấy ảnh hợp lệ trong các file ZIP này.")
            st.session_state.download_status = "idle"
            return

        total_images = len(valid_images)
        total_outputs = total_images * len(sizes)
        status_placeholder.info(
            f"🖼 {total_images} ảnh × {len(sizes)} size = {total_outputs} output — Đang resize..."
        )
        log(f"⚡ Multi-thread resize {total_images} ảnh")

        processed_count = 0
        was_stopped = False
        manifest_items = []

        # seq_in_folder sequence — cần thread-safe nên dùng lock
        folder_counter: dict[str, int] = {}
        folder_counter_lock = threading.Lock()

        def _bump_seq(folder_key: str) -> int:
            with folder_counter_lock:
                folder_counter[folder_key] = folder_counter.get(folder_key, 0) + 1
                return folder_counter[folder_key]

        def resize_one_image(file_path: Path):
            try:
                relative_path = file_path.relative_to(raw_dir)
                if str(relative_path.parent) != ".":
                    folder = str(relative_path.parent)
                else:
                    folder = file_path.stem

                resize_to_multi_sizes(
                    file_path, final_dir, folder, file_path.stem,
                    sizes, scale_pct, quality, export_format,
                    huge_image_mode=cfg.get("huge_image_mode", True),
                )

                meta_info = safe_image_meta(file_path)
                preview_path = build_preview_image(file_path, preview_dir)
                seq = _bump_seq(folder)
                item_manifest = {
                    "id": clean_name(f"loc_{folder}_{file_path.stem}_{seq}"),
                    "product": folder,
                    "color": "Mặc định",
                    "folder_name": folder,
                    "seq_in_folder": seq,
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

        max_workers = min(8, max(1, int(cfg.get("max_workers", 4))))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(resize_one_image, fp): fp for fp in valid_images}

                for future in concurrent.futures.as_completed(future_map):
                    if not check_pause_cancel_state():
                        executor.shutdown(wait=False, cancel_futures=True)
                        was_stopped = True
                        break

                    try:
                        file_name, success, error_msg, item_manifest = future.result(timeout=120)
                    except concurrent.futures.TimeoutError:
                        processed_count += 1
                        log("⚠️ Timeout — bỏ qua 1 ảnh")
                        progress_bar.progress(processed_count / total_images)
                        continue
                    except Exception as exc:
                        processed_count += 1
                        log(f"⚠️ Lỗi thread: {exc}")
                        progress_bar.progress(processed_count / total_images)
                        continue

                    processed_count += 1

                    if success and item_manifest:
                        manifest_items.append(item_manifest)

                    status_icon = "✅" if success else "⚠️"
                    log_line = f"{status_icon} {file_name}"
                    if error_msg:
                        log_line += f" — {error_msg}"
                    log(log_line)

                    progress_bar.progress(processed_count / total_images)
        except MemoryError:
            st.error("❌ Hết bộ nhớ RAM — giảm số luồng xử lý hoặc chọn file ZIP nhỏ hơn.")
            st.session_state.download_status = "idle"
            return
        except Exception as exc:
            st.error(f"❌ Lỗi nghiêm trọng khi resize: {exc}")
            st.session_state.download_status = "idle"
            return

        if was_stopped:
            status_placeholder.warning(f"🚫 Đã hủy — {processed_count}/{total_images} ảnh.")
        else:
            status_placeholder.info(
                f"✔️ {processed_count}/{total_images} ảnh xong — Đang đóng gói ZIP..."
            )

        duration = time.time() - start_time
        all_output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

        if all_output_files:
            renamed = batch_rename_with_template(final_dir, template)
            if renamed:
                log(f"✏️ Đổi tên {renamed} ảnh")

            # Preview ở tab đã bị tắt để giảm tải RAM — xem ảnh trong Studio

            zip_output_path = temp_path / f"Local_Done_{workspace['batch_id']}.zip"
            make_zip(final_dir, zip_output_path,
                     compresslevel=int(cfg.get("zip_compression", 6)))

            if zip_output_path.exists() and zip_output_path.stat().st_size > 100:
                st.session_state.local_zip_path = str(zip_output_path)
                try:
                    st.session_state.local_zip_data = zip_output_path.read_bytes()
                except Exception:
                    st.session_state.local_zip_data = None
                zip_size_kb = zip_output_path.stat().st_size // 1024
                status_placeholder.success(
                    f"🎉 Hoàn tất — {len(all_output_files)} ảnh sẵn sàng!"
                )
                log(f"📦 ZIP: {zip_size_kb:,} KB")
            else:
                status_placeholder.error("❌ Tạo ZIP lỗi (giới hạn bộ nhớ).")

            batch_meta = {
                "batch_id": workspace["batch_id"],
                "root": str(temp_path),
                "final_dir": str(final_dir),
                "source_name": "Local ZIP",
                "source_count": len(manifest_items),
                "output_count": len(all_output_files),
                "zip_path": str(zip_output_path),
                "zip_size": readable_file_size(
                    zip_output_path.stat().st_size if zip_output_path.exists() else 0
                ),
            }
            render_batch_kpis(batch_meta)
            save_json(manifest_items, meta_dir / "manifest.json")
            save_json(batch_meta, meta_dir / "meta.json")

            st.session_state.last_batch_manifest = manifest_items
            st.session_state.last_batch_cfg = dict(cfg)
            st.session_state.last_batch_meta = batch_meta
            # Xóa ADJUSTED cũ + cache thumb cũ
            st.session_state.pop("_adjusted_root", None)
            st.session_state.pop("_studio_thumb_b64_cache", None)
            # Báo app.py auto-switch sang Studio
            st.session_state["_goto_studio"] = True

            size_label = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
            file_names = ", ".join([uf.name for uf in uploaded_files[:3]])
            add_to_history("Local", file_names, len(all_output_files), size_label, duration)

            st.success("🎯 Render xong! Đang chuyển sang **tab Studio** để bạn xem & chỉnh ảnh...")
        else:
            status_placeholder.error("❌ Không có file output (ảnh có thể bị lỗi cấu trúc).")

        st.session_state.download_status = "idle"

    # ── Tải ZIP — ưu tiên đọc từ disk, fallback bytes ──
    from utils import open_zip_for_download
    zip_handle = open_zip_for_download(st.session_state.get("local_zip_path", ""))
    if zip_handle:
        try:
            zp = Path(st.session_state.local_zip_path)
            size_text = readable_file_size(zp.stat().st_size)
            st.success(f"✅ ZIP Local đã sẵn sàng · {size_text}")
            st.download_button(
                label="📥 TẢI ZIP NGAY",
                data=zip_handle,
                file_name=zp.name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="download_local_zip",
            )
        finally:
            zip_handle.close()
    elif st.session_state.get("local_zip_data"):
        st.success("✅ ZIP Local đã sẵn sàng!")
        st.download_button(
            label="📥 TẢI ZIP NGAY",
            data=st.session_state.local_zip_data,
            file_name="Local_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_local_zip_bytes",
        )
