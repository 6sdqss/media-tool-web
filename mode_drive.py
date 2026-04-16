import streamlit as st
import os
import time
import shutil
import tempfile
import zipfile
from pathlib import Path
import gdown

from utils import (
    extract_drive_id_and_type, get_drive_name, download_direct_file,
    resize_image, check_pause_cancel_state, render_control_buttons,
)

IMAGE_EXTS      = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
MAX_IMG_FOLDER  = 7   # giới hạn ảnh/thư mục để tránh timeout


# ──────────────────────────────────────────────────────────────
def _try_download_folder(file_id: str, dest: Path) -> bool:
    """Tải thư mục Drive — 3 lần thử, trả True nếu có ít nhất 1 file."""
    folder_url = f"https://drive.google.com/drive/folders/{file_id}"
    for kwargs in [
        dict(use_cookies=False, remaining_ok=True),
        dict(use_cookies=True,  remaining_ok=True),
        dict(use_cookies=False, remaining_ok=False),
    ]:
        try:
            gdown.download_folder(url=folder_url, output=str(dest), quiet=True, **kwargs)
            if any(dest.rglob("*")):
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def _make_zip(final_dir: Path, zip_path: Path):
    """
    Tạo ZIP giữ đúng cấu trúc thư mục.
    Bỏ qua thư mục/file rỗng.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in final_dir.rglob("*"):
            if file.is_file() and file.stat().st_size > 0:
                arcname = file.relative_to(final_dir)
                zf.write(file, arcname)


# ──────────────────────────────────────────────────────────────
def run_mode_drive(w, h):
    if "drive_zip_data" not in st.session_state:
        st.session_state.drive_zip_data = None

    # ── INPUT ────────────────────────────────────────────────
    st.markdown('<div class="sec-title">📥 NGUỒN ẢNH — LINK GOOGLE DRIVE</div>', unsafe_allow_html=True)
    links_text = st.text_area(
        "Dán link (mỗi link 1 dòng):",
        height=130,
        placeholder=(
            "https://drive.google.com/drive/folders/ABC123...\n"
            "https://drive.google.com/file/d/XYZ456...\n"
            "https://drive.google.com/open?id=..."
        ),
        label_visibility="collapsed",
    )

    # ── NÚT BẮT ĐẦU ─────────────────────────────────────────
    if st.button("🚀  BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True, key="btn_drive"):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
            return

        st.session_state.download_status = "running"
        st.session_state.drive_zip_data  = None

        render_control_buttons()
        status_ph  = st.empty()
        prog_ph    = st.progress(0)
        log_ph     = st.empty()
        logs: list[str] = []

        def log(msg: str):
            logs.append(msg)
            log_ph.markdown(
                "<div class='log-box'>" + "<br>".join(logs[-25:]) + "</div>",
                unsafe_allow_html=True,
            )

        with tempfile.TemporaryDirectory() as td:
            temp   = Path(td)
            raw    = temp / "RAW"
            final  = temp / "FINAL"
            raw.mkdir();  final.mkdir()

            ok_count = 0

            for i, url in enumerate(links):
                if not check_pause_cancel_state():
                    break

                file_id, kind = extract_drive_id_and_type(url)
                if not file_id:
                    log(f"⚠️  Link không hợp lệ — bỏ qua: {url[:70]}")
                    prog_ph.progress((i + 1) / len(links))
                    continue

                drive_name = get_drive_name(file_id, kind)
                status_ph.info(f"⏳  [{i+1}/{len(links)}]  Đang xử lý: **{drive_name}**")
                log(f"▶  {drive_name}")

                curr_raw   = raw   / drive_name
                curr_final = final / drive_name
                curr_raw.mkdir(parents=True, exist_ok=True)

                try:
                    # ── FOLDER ──────────────────────────────
                    if kind == "folder":
                        ok = _try_download_folder(file_id, curr_raw)
                        if not ok:
                            log(f"  ❌ Không tải được '{drive_name}' — bỏ qua")
                            shutil.rmtree(curr_raw, ignore_errors=True)
                            prog_ph.progress((i + 1) / len(links))
                            continue

                        imgs = sorted(
                            [f for f in curr_raw.rglob("*") if f.suffix.lower() in IMAGE_EXTS],
                            key=lambda x: x.name,
                        )
                        if len(imgs) > MAX_IMG_FOLDER:
                            log(f"  ⚠️  {len(imgs)} ảnh — giới hạn {MAX_IMG_FOLDER}")
                            imgs = imgs[:MAX_IMG_FOLDER]

                        if not imgs:
                            log(f"  ❌ Không có ảnh hợp lệ — bỏ qua")
                            prog_ph.progress((i + 1) / len(links))
                            continue

                        curr_final.mkdir(parents=True, exist_ok=True)
                        done = 0
                        for img in imgs:
                            if not check_pause_cancel_state():
                                break
                            try:
                                out = curr_final / f"{img.stem}.jpg"
                                resize_image(img, out, w, h)
                                done += 1
                                log(f"  ✅  {img.name}")
                            except Exception as e:
                                log(f"  ⚠️  {img.name} — lỗi: {e}")

                        if done > 0:
                            ok_count += 1

                    # ── FILE ĐƠN ────────────────────────────
                    else:
                        fp = download_direct_file(file_id, curr_raw, drive_name)
                        if fp and fp.exists() and fp.stat().st_size > 2048:
                            curr_final.mkdir(parents=True, exist_ok=True)
                            out = curr_final / f"{fp.stem}.jpg"
                            resize_image(fp, out, w, h)
                            if out.exists() and out.stat().st_size > 0:
                                ok_count += 1
                                log(f"  ✅  {drive_name}")
                            else:
                                log(f"  ❌  Resize thất bại — bỏ qua")
                        else:
                            log(f"  ❌  Không tải được file — bỏ qua")

                except Exception as e:
                    log(f"  ❌  Lỗi '{drive_name}': {e} — bỏ qua")
                    shutil.rmtree(curr_raw, ignore_errors=True)

                prog_ph.progress((i + 1) / len(links))

            # ── ĐÓNG GÓI ZIP ────────────────────────────────
            # Kiểm tra có file nào trong final không
            all_output = [f for f in final.rglob("*") if f.is_file() and f.stat().st_size > 0]

            if all_output:
                if st.session_state.download_status == "cancelled":
                    status_ph.warning(f"🚫  Đã hủy — đã xử lý {ok_count} thư mục/file, vẫn có thể tải ZIP.")
                else:
                    status_ph.success(f"🎉  HOÀN TẤT — {ok_count}/{len(links)} xử lý thành công!")

                zip_path = temp / "Drive_Images_Done.zip"
                _make_zip(final, zip_path)

                if zip_path.exists() and zip_path.stat().st_size > 100:
                    with open(zip_path, "rb") as f:
                        st.session_state.drive_zip_data = f.read()
                    log(f"📦  ZIP: {zip_path.stat().st_size // 1024} KB — {len(all_output)} file")
                else:
                    log("⚠️  ZIP rỗng bất thường")
            else:
                status_ph.error("❌  Không có ảnh nào xử lý được — kiểm tra quyền chia sẻ Drive.")

            st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ─────────────────────────────────────────
    if st.session_state.get("drive_zip_data"):
        st.success("✅  Sẵn sàng tải xuống!")
        st.download_button(
            label="📥  TẢI TOÀN BỘ ẢNH (FILE ZIP)",
            data=st.session_state.drive_zip_data,
            file_name="Drive_Images_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_drive",
        )
