import streamlit as st
import shutil
import time
import tempfile
import zipfile
import concurrent.futures
from pathlib import Path

from utils import (
    resize_image, ignore_system_files,
    check_pause_cancel_state, render_control_buttons,
    show_preview, batch_rename_files, add_to_history, get_size_label,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def _make_zip(final_dir: Path, zip_path: Path):
    """Tạo ZIP giữ đúng cấu trúc thư mục, bỏ qua file rỗng."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in final_dir.rglob("*"):
            if f.is_file() and f.stat().st_size > 0:
                zf.write(f, f.relative_to(final_dir))


def run_mode_local(w, h, scale_pct=100, mode="letterbox", rename=False):
    if "local_zip_data" not in st.session_state:
        st.session_state.local_zip_data = None

    # ── INFO ─────────────────────────────────────────────────
    st.markdown("""
    <div class="guide-box" style="padding:12px 16px;font-size:.86rem">
        💡 <b>Cách dùng:</b> Nén thư mục ảnh thành <b>.zip</b> rồi upload lên đây.<br>
        <i>Có thể upload nhiều file ZIP cùng lúc.</i>
    </div>""", unsafe_allow_html=True)

    # ── UPLOAD ───────────────────────────────────────────────
    st.markdown('<div class="sec-title">📦 UPLOAD FILE ZIP</div>', unsafe_allow_html=True)
    
    # === NÂNG CẤP: Cho phép upload nhiều file ZIP ===
    uploaded = st.file_uploader(
        "Chọn file ZIP:",
        type=["zip"],
        help="Hỗ trợ chọn nhiều file .zip. Kích thước tối đa ~200MB/file.",
        label_visibility="collapsed",
        accept_multiple_files=True
    )

    # ── NÚT BẮT ĐẦU ─────────────────────────────────────────
    if st.button("🚀  BẮT ĐẦU RESIZE", type="primary", use_container_width=True, key="btn_local"):
        if not uploaded:
            st.error("⚠️ Chưa tải file nào lên!")
            return

        st.session_state.download_status = "running"
        st.session_state.local_zip_data  = None

        render_control_buttons()
        _t_start = time.time()
        status_ph = st.empty()
        prog_ph   = st.progress(0)
        log_ph    = st.empty()
        logs: list[str] = []

        def log(msg: str):
            logs.append(msg)
            log_ph.markdown(
                "<div class='log-box'>" + "<br>".join(logs[-25:]) + "</div>",
                unsafe_allow_html=True,
            )

        with tempfile.TemporaryDirectory() as td:
            temp  = Path(td)
            raw   = temp / "RAW"
            final = temp / "FINAL"
            raw.mkdir();  final.mkdir()

            # === NÂNG CẤP: Xử lý ghi luồng đĩa chống văng app & Giải nén nhiều file ===
            status_ph.info(f"⏳ Đang giải nén {len(uploaded)} file ZIP...")
            
            for up_file in uploaded:
                try:
                    # Ghi trực tiếp xuống ổ đĩa thay vì đọc trên RAM
                    zip_path = temp / up_file.name
                    with open(zip_path, "wb") as f:
                        f.write(up_file.getbuffer())

                    # Tạo thư mục giải nén trùng với tên file ZIP
                    folder_name = Path(up_file.name).stem
                    extract_path = raw / folder_name
                    extract_path.mkdir(parents=True, exist_ok=True)

                    with zipfile.ZipFile(zip_path, "r") as zf:
                        members = [
                            m for m in zf.namelist()
                            if not m.startswith("__MACOSX")
                            and "/.DS_Store" not in m
                            and not m.startswith(".")
                            and not "/._" in m
                        ]
                        if not members:
                            members = zf.namelist()
                        zf.extractall(extract_path, members=members)
                        
                    # Giải nén xong thì xóa file ZIP tạm đi cho nhẹ
                    zip_path.unlink()
                except zipfile.BadZipFile:
                    st.error(f"❌ File ZIP {up_file.name} bị hỏng hoặc không đúng định dạng!")
                except Exception as e:
                    st.error(f"❌ Lỗi giải nén {up_file.name}: {e}")

            # ── TÌM ẢNH ─────────────────────────────────────
            valid = [
                f for f in raw.rglob("*")
                if f.is_file()
                and f.suffix.lower() in IMAGE_EXTS
                and not ignore_system_files(f)
            ]

            if not valid:
                st.error("⚠️ Không tìm thấy ảnh hợp lệ trong ZIP!")
                st.session_state.download_status = "idle"
                return

            status_ph.info(f"🖼️ Tìm thấy **{len(valid)}** ảnh — đang resize...")
            log(f"Tổng: {len(valid)} ảnh")

            # ── RESIZE SONG SONG ─────────────────────────────
            done = 0
            stopped = False

            def _resize_one(fp: Path):
                """Chạy trong thread — không gọi Streamlit ở đây."""
                try:
                    rel  = fp.relative_to(raw)
                    out  = final / rel.with_suffix(".jpg")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    resize_image(fp, out, w, h,
                                 scale_pct=scale_pct, mode=mode)
                    return (fp.name, True, "")
                except Exception as e:
                    return (fp.name, False, str(e))

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
                futs = {ex.submit(_resize_one, fp): fp for fp in valid}
                for fut in concurrent.futures.as_completed(futs):
                    if not check_pause_cancel_state():
                        ex.shutdown(wait=False, cancel_futures=True)
                        stopped = True
                        break
                    name, ok, err = fut.result()
                    done += 1
                    log(f"{'✅' if ok else '⚠️'}  {name}" + (f"  —  {err}" if err else ""))
                    prog_ph.progress(done / len(valid))

            if stopped:
                status_ph.warning(f"🚫 Đã hủy — đã xử lý {done}/{len(valid)} ảnh")
            else:
                status_ph.info(f"✔️  Resize xong {done}/{len(valid)} ảnh — đang đóng gói...")

            # ── ĐÓNG GÓI ZIP ────────────────────────────────
            _duration = time.time() - _t_start
            all_out = [f for f in final.rglob("*") if f.is_file() and f.stat().st_size > 0]

            if all_out:
                # Đặt tên hàng loạt nếu bật
                if rename:
                    n_renamed = batch_rename_files(final)
                    if n_renamed:
                        log(f"✏️  Đã đổi tên {n_renamed} ảnh")

                # Xem trước
                show_preview(final)

                zip_path = temp / "Local_Images_Done.zip"
                _make_zip(final, zip_path)

                if zip_path.exists() and zip_path.stat().st_size > 100:
                    with open(zip_path, "rb") as f:
                        st.session_state.local_zip_data = f.read()
                    status_ph.success(f"🎉  HOÀN TẤT — {len(all_out)} ảnh trong ZIP!")
                    log(f"📦  ZIP: {zip_path.stat().st_size // 1024} KB")
                else:
                    status_ph.error("❌ ZIP không tạo được — lỗi bất thường.")

                # Lưu lịch sử
                names = [u.name for u in uploaded[:3]]
                detail = ", ".join(names)
                add_to_history("Local", detail, len(all_out),
                               get_size_label(w, h, mode), _duration)
            else:
                status_ph.error("❌ Không có ảnh nào xử lý được!")

            st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ─────────────────────────────────────────
    if st.session_state.get("local_zip_data"):
        st.success("✅  Sẵn sàng tải xuống!")
        st.download_button(
            label="📥  TẢI KẾT QUẢ (FILE ZIP)",
            data=st.session_state.local_zip_data,
            file_name="Local_Images_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_local",
        )
