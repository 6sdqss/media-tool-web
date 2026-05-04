import streamlit as st
import re
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


def _clean_name(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return re.sub(r"\s+", "_", name).strip("_") or "Untitled"


def _make_zip(final_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in final_dir.rglob("*"):
            if f.is_file() and f.stat().st_size > 0:
                zf.write(f, f.relative_to(final_dir))


def run_mode_local(w, h, scale_pct=100, mode="letterbox", rename=False):
    if "local_zip_data" not in st.session_state:
        st.session_state.local_zip_data = None

    st.markdown("""
    <div class="guide-box" style="padding:12px 16px;font-size:.86rem">
        💡 <b>Cách dùng:</b> Nén thư mục ảnh thành <b>.zip</b> rồi upload.
        Có thể upload nhiều file ZIP cùng lúc.
    </div>""", unsafe_allow_html=True)

    # ── UPLOAD ───────────────────────────────────────────────
    st.markdown('<div class="sec-title">📦 UPLOAD FILE ZIP</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Chọn file ZIP:",
        type=["zip"],
        help="Hỗ trợ nhiều file .zip. Tối đa ~200MB/file.",
        label_visibility="collapsed",
        accept_multiple_files=True
    )

    # ── ĐẶT TÊN TÙY CHỈNH ──
    custom_names = {}
    if rename and uploaded:
        st.markdown('<div class="sec-title">✏️ TÊN TÙY CHỈNH CHO TỪNG FILE ZIP</div>',
                    unsafe_allow_html=True)
        st.caption("Điền tên mới cho folder output. Bỏ trống = dùng tên gốc của ZIP.")
        for idx, up_file in enumerate(uploaded):
            original_name = Path(up_file.name).stem
            custom = st.text_input(
                f"📦 {up_file.name}",
                value="",
                placeholder=f"{original_name}  (tên gốc)",
                key=f"local_name_{idx}_{up_file.name}",
            )
            if custom.strip():
                custom_names[idx] = _clean_name(custom.strip())

    # ── NÚT BẮT ĐẦU ─────────────────────────────────────────
    st.write("")
    if st.button("BẮT ĐẦU RESIZE", type="primary", use_container_width=True, key="btn_local"):
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
                unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as td:
            temp  = Path(td)
            raw   = temp / "RAW"
            final = temp / "FINAL"
            raw.mkdir(); final.mkdir()

            status_ph.info(f"⏳ Giải nén {len(uploaded)} file ZIP...")

            for idx, up_file in enumerate(uploaded):
                try:
                    zip_path = temp / up_file.name
                    with open(zip_path, "wb") as f:
                        f.write(up_file.getbuffer())

                    # Tên folder: custom nếu có, không thì dùng tên gốc
                    if idx in custom_names:
                        folder_name = custom_names[idx]
                    else:
                        folder_name = Path(up_file.name).stem

                    extract_path = raw / folder_name
                    extract_path.mkdir(parents=True, exist_ok=True)

                    with zipfile.ZipFile(zip_path, "r") as zf:
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

                    zip_path.unlink()
                    log(f"📂 {up_file.name} → {folder_name}/")
                except zipfile.BadZipFile:
                    st.error(f"❌ {up_file.name} bị hỏng!")
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

            status_ph.info(f"🖼️ {len(valid)} ảnh — đang resize...")
            log(f"Tổng: {len(valid)} ảnh")

            # ── RESIZE SONG SONG ─────────────────────────────
            done = 0
            stopped = False

            def _resize_one(fp: Path):
                try:
                    rel  = fp.relative_to(raw)
                    out  = final / rel.with_suffix(".jpg")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    resize_image(fp, out, w, h, scale_pct=scale_pct, mode=mode)
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
                status_ph.warning(f"🚫 Đã hủy — {done}/{len(valid)} ảnh")
            else:
                status_ph.info(f"✔️ Resize xong {done}/{len(valid)} — đóng gói...")

            # ── ĐÓNG GÓI ZIP ────────────────────────────────
            _duration = time.time() - _t_start
            all_out = [f for f in final.rglob("*") if f.is_file() and f.stat().st_size > 0]

            if all_out:
                if rename:
                    n_renamed = batch_rename_files(final)
                    if n_renamed:
                        log(f"✏️ Đổi tên {n_renamed} ảnh")

                show_preview(final)

                zip_path = temp / "Local_Images_Done.zip"
                _make_zip(final, zip_path)

                if zip_path.exists() and zip_path.stat().st_size > 100:
                    with open(zip_path, "rb") as f:
                        st.session_state.local_zip_data = f.read()
                    status_ph.success(f"🎉 Hoàn tất — {len(all_out)} ảnh!")
                    log(f"📦 ZIP: {zip_path.stat().st_size // 1024} KB")
                else:
                    status_ph.error("❌ ZIP lỗi bất thường.")

                names = [u.name for u in uploaded[:3]]
                add_to_history("Local", ", ".join(names), len(all_out),
                               get_size_label(w, h, mode), _duration)
            else:
                status_ph.error("❌ Không có ảnh nào xử lý được!")

            st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ─────────────────────────────────────────
    if st.session_state.get("local_zip_data"):
        st.success("✅ Sẵn sàng tải!")
        st.download_button(
            label="📥 TẢI FILE ZIP",
            data=st.session_state.local_zip_data,
            file_name="Local_Images_Done.zip",
            mime="application/zip",
            type="primary", use_container_width=True, key="dl_local")
