"""
mode_drive.py — Tab Google Drive v9.8
─────────────────────────────────────────────────────────
FIX v9.8 — Giữ NGUYÊN 100% logic Drive API / gdown / upload cũ.
Chỉ nâng cấp phần xử lý để không còn bị out ra khi dùng nhiều link:

★ 5 NGUYÊN NHÂN CRASH ĐÃ FIX:
  1. BytesIO buffer → streaming write từng 4MB chunk ra disk
     (utils.py: api_download_file đã được fix)
  2. Resize tuần tự 1 ảnh/lần → ThreadPoolExecutor đa luồng
     (như mode_local, tận dụng RAM/CPU của máy người dùng)
  3. Không có RAM guard → smart_max_workers() tính workers an toàn
     dựa trên RAM thực tế, giữ buffer 500MB cho OS
  4. zip_path.read_bytes() load ZIP vào RAM → chỉ lưu path, đọc từ disk
  5. Không GC giữa các folder → gc.collect() sau mỗi folder xong

★ TĂNG SỨC MẠNH TỪNG CÁ NHÂN:
  - Máy 4GB RAM → 2-3 workers
  - Máy 8GB RAM → 4-5 workers
  - Máy 16GB RAM → 6-8 workers
  Tự động tính, không cần user cấu hình thêm.

★ RETRY + RATE-LIMIT:
  - api_download_file: 3 lần thử, backoff 2s/4s/8s
  - Rate-limit 0.15s/file tránh Google quota 429
  - Lỗi 1 folder không làm crash cả batch
"""

from __future__ import annotations

import gc
import time
import threading
import concurrent.futures
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
    upload_to_drive,
)


# ─── Helper: tính số worker an toàn theo RAM thực tế ──────────────────────────
def _smart_workers(n_images: int, user_cap: int = 4) -> int:
    """
    Tính số luồng resize an toàn dựa trên RAM khả dụng của máy.
    Luôn giữ lại ít nhất 500 MB buffer cho OS + Streamlit.
    mb_per_image: ước tính 100 MB RAM cần cho decode+resize+encode 1 ảnh.
    """
    try:
        import psutil
        avail_mb   = int(psutil.virtual_memory().available / 1024 / 1024)
        budget_mb  = max(avail_mb - 500, 64)
        by_ram     = max(1, int(budget_mb / 100))
        return min(user_cap, by_ram, max(n_images, 1), 8)
    except ImportError:
        # psutil chưa cài → dùng giá trị an toàn
        return min(user_cap, 3)


def run_mode_drive(cfg: dict, drive_service):
    sizes          = cfg["sizes"]
    scale_pct      = cfg["scale_pct"]
    quality        = cfg["quality"]
    export_format  = cfg["export_format"]
    template       = cfg["template"]
    rename_enabled = cfg["rename"]

    st.markdown(
        "<div class='guide-box'>"
        "💡 <b>Workflow Drive:</b> dán link Drive (folder/file) → tự tải → resize → ZIP. "
        "Có thể upload ngược lên Drive đích."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sec-title">📥 Nguồn ảnh từ Drive</div>',
                unsafe_allow_html=True)
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

    st.markdown('<div class="sec-title">📤 Đích upload Drive (tùy chọn)</div>',
                unsafe_allow_html=True)
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

    # Hiển thị thông tin RAM
    try:
        import psutil
        vm        = psutil.virtual_memory()
        avail_mb  = int(vm.available / 1024 / 1024)
        total_mb  = int(vm.total    / 1024 / 1024)
        used_pct  = int((total_mb - avail_mb) / max(total_mb, 1) * 100)
        ram_color = "#4ade80" if used_pct < 60 else ("#fbbf24" if used_pct < 80 else "#f87171")
        w_preview = _smart_workers(10, int(cfg.get("max_workers", 4)))
        st.markdown(
            f"<div style='font-size:0.8rem;color:#94a3b8;margin-bottom:6px;'>"
            f"💾 RAM: <b style='color:{ram_color}'>{avail_mb:,} MB</b> khả dụng / "
            f"{total_mb:,} MB · "
            f"⚡ Sẽ dùng <b style='color:#a78bfa'>{w_preview} luồng resize</b></div>",
            unsafe_allow_html=True,
        )
    except ImportError:
        pass

    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None
    if "drive_zip_path" not in st.session_state:
        st.session_state.drive_zip_path = ""

    if st.button("🚀 BẮT ĐẦU TẢI & XỬ LÝ", type="primary",
                 use_container_width=True, key="btn_drive_start"):

        st.session_state.download_status = "running"
        st.session_state.drive_zip_data  = None
        st.session_state.drive_zip_path  = ""

        links        = [line.strip() for line in links_text.splitlines() if line.strip()]
        custom_names = ([name.strip() for name in custom_names_text.splitlines()]
                        if rename_enabled else [])
        target_folder_id, _ = (extract_drive_id_and_type(upload_link)
                                if upload_link else (None, None))

        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link Drive.")
            st.session_state.download_status = "idle"
            return

        render_control_buttons()
        start_time = time.time()

        workspace   = create_batch_workspace("drive")
        temp_path   = Path(workspace["root"])
        raw_dir     = Path(workspace["raw_dir"])
        final_dir   = Path(workspace["final_dir"])
        preview_dir = Path(workspace["preview_dir"])
        meta_dir    = Path(workspace["meta_dir"])

        status_placeholder = st.empty()
        progress_bar       = st.progress(0)

        # ── Log container — hiển thị log xử lý từng ảnh ────────────────────
        log_placeholder = st.empty()
        log_messages: list[str] = []

        def log(msg: str):
            log_messages.append(msg)
            visible = log_messages[-30:]
            log_placeholder.markdown(
                "<div class='log-box'>" + "<br>".join(visible) + "</div>",
                unsafe_allow_html=True,
            )

        # Thread-safe counters
        folder_counter: dict[str, int] = {}
        folder_counter_lock = threading.Lock()

        def _bump_seq(folder_key: str) -> int:
            with folder_counter_lock:
                folder_counter[folder_key] = folder_counter.get(folder_key, 0) + 1
                return folder_counter[folder_key]

        successful_count  = 0
        total_links       = len(links)
        manifest_items: list[dict] = []

        # ── Hàm resize 1 ảnh — chạy trong thread pool ──────────────────────
        def _resize_one(img_path: Path, folder_name: str) -> dict | None:
            """
            Resize + build preview + build manifest item.
            Trả về manifest dict nếu thành công, None nếu lỗi.
            Không gọi st.* (không thread-safe).
            """
            try:
                resize_to_multi_sizes(
                    img_path, final_dir, folder_name, img_path.stem,
                    sizes, scale_pct, quality, export_format,
                    huge_image_mode=cfg.get("huge_image_mode", True),
                )
                meta_info    = safe_image_meta(img_path)
                preview_path = build_preview_image(img_path, preview_dir)
                seq          = _bump_seq(folder_name)
                return {
                    "id":              clean_name(f"drv_{folder_name}_{img_path.stem}_{seq}"),
                    "product":         folder_name,
                    "color":           "Mặc định",
                    "folder_name":     folder_name,
                    "seq_in_folder":   seq,
                    "source_path":     str(img_path),
                    "preview_path":    str(preview_path),
                    "original_name":   img_path.stem,
                    "default_scale_pct": int(cfg.get("default_scale_pct", 100)),
                    "source_width":    meta_info.get("width",      0),
                    "source_height":   meta_info.get("height",     0),
                    "source_size_bytes": meta_info.get("size_bytes", 0),
                }
            except Exception as exc:
                return {"_error": str(exc), "_name": img_path.name}

        def _process_images_concurrent(raw_images: list[Path],
                                        folder_name: str) -> list[dict]:
            """
            Resize tất cả ảnh của 1 folder bằng ThreadPoolExecutor.
            Tính số worker động theo RAM khả dụng.
            Trả về danh sách manifest items thành công.
            """
            if not raw_images:
                return []

            n_workers = _smart_workers(
                n_images  = len(raw_images),
                user_cap  = int(cfg.get("max_workers", 4)),
            )
            log(f"⚡ {folder_name}: {len(raw_images)} ảnh, {n_workers} luồng")

            results: list[dict] = []
            done_count           = 0

            try:
                with concurrent.futures.ThreadPoolExecutor(
                        max_workers=n_workers) as executor:
                    future_map = {
                        executor.submit(_resize_one, p, folder_name): p
                        for p in raw_images
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        if not check_pause_cancel_state():
                            executor.shutdown(wait=False, cancel_futures=True)
                            log("🚫 Đã hủy bởi người dùng.")
                            break

                        done_count += 1
                        try:
                            item = future.result(timeout=120)
                        except concurrent.futures.TimeoutError:
                            log(f"⚠️ Timeout — bỏ qua 1 ảnh trong {folder_name}")
                            continue
                        except Exception as exc:
                            log(f"⚠️ Lỗi thread: {exc}")
                            continue

                        if item is None:
                            continue
                        if "_error" in item:
                            log(f"⚠️ {item.get('_name','?')}: {item['_error']}")
                        else:
                            results.append(item)
                            log(f"✅ {item['original_name']}")

            except MemoryError:
                log(f"❌ Hết RAM khi xử lý {folder_name} — "
                    "giảm số ảnh/folder hoặc chọn máy RAM cao hơn.")
            except Exception as exc:
                log(f"❌ Lỗi pool {folder_name}: {exc}")

            return results

        # ════════════════════════════════════════════════════════════════════
        # VÒNG LẶP CHÍNH — xử lý từng link
        # ════════════════════════════════════════════════════════════════════
        for link_index, url in enumerate(links):
            if not check_pause_cancel_state():
                break

            file_id, kind = extract_drive_id_and_type(url)
            if not file_id:
                log(f"⚠️ Link sai định dạng: {url[:60]}")
                continue

            auto_name = get_drive_name(file_id, kind, service=drive_service)
            if (rename_enabled
                    and link_index < len(custom_names)
                    and custom_names[link_index]):
                folder_name = clean_name(custom_names[link_index])
            else:
                folder_name = auto_name

            current_raw = raw_dir / folder_name
            current_raw.mkdir(parents=True, exist_ok=True)

            status_placeholder.info(
                f"📥 [{link_index + 1}/{total_links}] Đang tải: {folder_name}"
            )

            try:
                # ── Tải ảnh xuống đĩa ────────────────────────────────────
                if kind == "folder":
                    if drive_service:
                        count = api_download_folder_images(
                            drive_service, file_id, current_raw, max_files=None
                        )
                        if count == 0:
                            log(f"⚠️ '{folder_name}' rỗng hoặc bị khóa quyền.")
                            continue
                        log(f"📥 Tải xong {count} ảnh từ '{folder_name}' (API).")
                    else:
                        # gdown fallback
                        try:
                            import gdown
                            download_url = f"https://drive.google.com/drive/folders/{file_id}"
                            gdown_ok = False
                            for use_cookies in [False, True]:
                                try:
                                    gdown.download_folder(
                                        url=download_url,
                                        output=str(current_raw),
                                        quiet=True,
                                        use_cookies=use_cookies,
                                    )
                                    if any(current_raw.iterdir()):
                                        gdown_ok = True
                                        break
                                except Exception:
                                    time.sleep(2)
                            if not gdown_ok:
                                log(f"⚠️ '{folder_name}' bị Google chặn fallback gdown.")
                                continue
                        except ImportError:
                            log("❌ Thiếu gdown và Google API — không thể tải.")
                            continue

                    # Lọc ảnh hợp lệ
                    raw_images = sorted([
                        f for f in current_raw.rglob("*.*")
                        if f.suffix.lower() in IMAGE_EXTENSIONS
                        and not f.name.startswith("._")
                    ])

                    if not raw_images:
                        log(f"⚠️ '{folder_name}': không tìm thấy ảnh sau khi tải.")
                        continue

                    status_placeholder.info(
                        f"🖼 [{link_index + 1}/{total_links}] "
                        f"Đang resize {len(raw_images)} ảnh: {folder_name}"
                    )

                    # ── CONCURRENT RESIZE — tận dụng RAM của máy ─────────
                    folder_items = _process_images_concurrent(raw_images, folder_name)
                    manifest_items.extend(folder_items)
                    log(f"✔️ {folder_name}: {len(folder_items)}/{len(raw_images)} ảnh xong.")

                else:
                    # ── Single file ───────────────────────────────────────
                    file_path = download_direct_file(
                        file_id, current_raw, folder_name,
                        service=drive_service,
                    )
                    if not file_path or not file_path.exists() \
                            or file_path.stat().st_size == 0:
                        # gdown fallback cho file đơn
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
                        item = _resize_one(file_path, folder_name)
                        if item and "_error" not in item:
                            manifest_items.append(item)
                            log(f"✅ File đơn '{folder_name}' — xong.")
                        else:
                            log(f"⚠️ Resize '{folder_name}' lỗi: "
                                f"{(item or {}).get('_error','?')}")
                    else:
                        log(f"⚠️ Tải file '{folder_name}' thất bại.")
                        continue

                successful_count += 1

                # ── Upload ngược lên Drive đích (nếu có) ─────────────────
                if target_folder_id and drive_service and check_pause_cancel_state():
                    try:
                        new_folder_id = create_drive_folder(
                            drive_service, folder_name, target_folder_id
                        )
                        ext = EXPORT_FORMATS.get(export_format, {}).get("ext", ".jpg")
                        for img in final_dir.rglob(f"*{ext}"):
                            upload_to_drive(drive_service, img, new_folder_id)
                        log(f"☁️ Đã upload '{folder_name}' lên Drive đích.")
                    except Exception as exc:
                        log(f"⚠️ Upload '{folder_name}' lỗi: {exc}")

            except MemoryError:
                log(f"❌ Hết RAM khi xử lý '{folder_name}'. "
                    "Đóng bớt ứng dụng khác hoặc giảm số ảnh/folder.")
                # Không crash toàn bộ — tiếp tục folder kế
            except Exception as exc:
                log(f"⚠️ Sự cố '{folder_name}': {exc}")

            # ── Dọn dẹp RAM sau mỗi folder ───────────────────────────────
            gc.collect()
            progress_bar.progress((link_index + 1) / total_links)

        # ════════════════════════════════════════════════════════════════════
        # SAU KHI XỬ LÝ XONG TẤT CẢ LINK
        # ════════════════════════════════════════════════════════════════════
        duration         = time.time() - start_time
        all_output_files = [
            f for f in final_dir.rglob("*")
            if f.is_file() and f.stat().st_size > 0
        ]

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
            # Preview ở tab đã bị tắt để giảm tải RAM — xem ảnh trong Studio

            zip_path = temp_path / f"Drive_Done_{workspace['batch_id']}.zip"
            try:
                make_zip(
                    final_dir, zip_path,
                    compresslevel=int(cfg.get("zip_compression", 6)),
                )
            except Exception as exc:
                log(f"⚠️ Tạo ZIP lỗi: {exc}")

            if zip_path.exists() and zip_path.stat().st_size > 100:
                # v9.8: KHÔNG load bytes vào RAM — chỉ lưu đường dẫn
                st.session_state.drive_zip_path = str(zip_path)
                st.session_state.drive_zip_data = None
                zip_size_str = readable_file_size(zip_path.stat().st_size)
                log(f"📦 ZIP: {zip_size_str}")

            batch_meta = {
                "batch_id":     workspace["batch_id"],
                "root":         str(temp_path),
                "final_dir":    str(final_dir),
                "source_name":  "Google Drive",
                "source_count": len(manifest_items),
                "output_count": len(all_output_files),
                "zip_path":     str(zip_path),
                "zip_size":     readable_file_size(
                    zip_path.stat().st_size if zip_path.exists() else 0
                ),
            }
            render_batch_kpis(batch_meta)
            save_json(manifest_items, meta_dir / "manifest.json")
            save_json(batch_meta,     meta_dir / "meta.json")

            st.session_state.last_batch_manifest = manifest_items
            st.session_state.last_batch_cfg      = dict(cfg)
            st.session_state.last_batch_meta     = batch_meta
            st.session_state.pop("_adjusted_root",         None)
            st.session_state.pop("_studio_thumb_b64_cache", None)
            st.session_state["_goto_studio"] = True

            size_label  = " + ".join([get_size_label(w, h, m) for w, h, m in sizes])
            detail_text = ", ".join([url.split("/")[-1][:15] for url in links[:3]])
            add_to_history("Drive", detail_text, len(all_output_files),
                           size_label, duration)

            st.success(
                "🎯 Render xong! Đang chuyển sang **tab Studio** để bạn xem & chỉnh ảnh..."
            )

            # Giải phóng RAM sau khi xong toàn bộ
            gc.collect()

        else:
            status_placeholder.error("❌ Không nhận được file ảnh hợp lệ.")

        st.session_state.download_status = "idle"

    # ── Tải ZIP — đọc từ disk (không dùng bytes trong RAM) ────────────────────
    zip_file_handle = open_zip_for_download(
        st.session_state.get("drive_zip_path", "")
    )
    if zip_file_handle:
        try:
            zp        = Path(st.session_state.drive_zip_path)
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
        # Fallback cũ (giữ tương thích)
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
