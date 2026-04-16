import streamlit as st
import os
import re
import time
import requests
import shutil
import tempfile
import concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from utils import (
    resize_image, create_drive_folder, upload_to_drive,
    check_pause_cancel_state, render_control_buttons
)

# ─────────────────────────────────────────────────────────────
# COOKIES & HEADERS CHUNG
# ─────────────────────────────────────────────────────────────
RAW_COOKIES = [
    {"domain": ".thegioididong.com", "name": "_ce.clock_data",  "value": "-110%2C113.161.59.60%2C1%2C91e1a2a41c0741f7f47615ab9de2fb8a%2CChrome%2CVN"},
    {"domain": ".thegioididong.com", "name": "_ce.s",            "value": "v~10b349a1bfb597f2fbfafdd33af1d88e35768560~lcw~1775808302291~vir~returning~lva~1775788787457~vpv~198~v11ls~8496c620-34b3-11f1-b933-8983fd7f9723"},
    {"domain": ".thegioididong.com", "name": "cebs",             "value": "1"},
    {"domain": ".thegioididong.com", "name": "cebsp_",           "value": "32"},
    {"domain": ".thegioididong.com", "name": "mwgsp",            "value": "1"},
    {"domain": "www.thegioididong.com", "name": "ASP.NET_SessionId", "value": "zgo0wxmkgvnqbqub0lkreuon"},
    {"domain": "www.thegioididong.com", "name": "SvID",          "value": "beline26122|adivM|adhi9"},
    {"domain": "www.thegioididong.com", "name": "TBMCookie_3209819802479625248", "value": "272331001775808103SbF4f4kGHIEXWQ8vk5fTCgPn/0Q="},
]
TGDD_COOKIES = {c["name"]: c["value"] for c in RAW_COOKIES}

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
SESSION = requests.Session()
SESSION.headers.update(BASE_HEADERS)


# ─────────────────────────────────────────────────────────────
# TIỆN ÍCH
# ─────────────────────────────────────────────────────────────
def clean_name(name: str) -> str:
    """Làm sạch tên tránh ký tự đặc biệt trong tên file/folder."""
    name = re.sub(r'[\\/:\*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "San_pham"


def _get(url: str, timeout=12) -> requests.Response | None:
    """GET an toàn với cookie TGDD."""
    try:
        resp = SESSION.get(url, cookies=TGDD_COOKIES, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────
# PHÂN TÍCH URL
# ─────────────────────────────────────────────────────────────
def resolve_redirect_url(url: str) -> str:
    """Theo redirect và trả về URL thực tế của sản phẩm."""
    try:
        resp = SESSION.get(
            url, headers=BASE_HEADERS, cookies=TGDD_COOKIES,
            allow_redirects=True, timeout=15
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            meta = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta:
                content = meta.get("content", "")
                if "url=" in content.lower():
                    return urljoin(url, content.split("url=")[-1].strip("'\""))
            return resp.url
    except Exception:
        pass
    return url


def get_item_name(main_url: str) -> str:
    """Lấy tên sản phẩm từ thẻ <h1> hoặc <title>."""
    resp = _get(main_url)
    if not resp:
        return "San_pham_khong_ten"
    soup = BeautifulSoup(resp.text, "html.parser")

    name = ""
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    else:
        m = re.search(r'item_name\s*:\s*"(.*?)"', soup.get_text())
        if m:
            name = m.group(1)
        else:
            title_tag = soup.find("title")
            name = title_tag.text.split("|")[0].strip() if title_tag else ""

    # Bỏ các cụm quảng cáo phổ biến
    name = re.sub(
        r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*|chính hãng.*|bảo hành.*))",
        "", name, flags=re.IGNORECASE
    )
    return clean_name(name) or "San_pham_khong_ten"


def get_color_links_and_names(main_url: str) -> list[dict]:
    """Trích xuất danh sách màu sắc và link tương ứng."""
    resp = _get(main_url)
    if not resp:
        return [{"name": "Mac_dinh", "link": main_url}]

    soup      = BeautifulSoup(resp.text, "html.parser")
    base_path = urlparse(main_url).path
    color_data = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Link màu thường chứa base path + ?code=
        if base_path in href and "?code=" in href:
            c_name = a.get_text(strip=True)
            c_link = urljoin(main_url, href)
            if c_link not in seen_links and c_name:
                color_data.append({"name": clean_name(c_name), "link": c_link})
                seen_links.add(c_link)

    return color_data if color_data else [{"name": "Mac_dinh", "link": main_url}]


def get_gallery_image_urls(product_url: str) -> list[str]:
    """
    Lấy danh sách URL ảnh gallery của sản phẩm.
    Ưu tiên ảnh độ phân giải cao nhất, loại bỏ ảnh trùng lặp.
    """
    resp = _get(product_url)
    if not resp:
        return []

    soup     = BeautifulSoup(resp.text, "html.parser")
    img_urls = set()

    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
        if not src:
            continue
        src = urljoin(product_url, src)

        # Chuẩn hóa: xóa suffix kích thước như -750x500, -800x800
        src_clean = re.sub(r"-\d{3,4}x\d{3,4}", "", src)

        # Chỉ lấy ảnh sản phẩm thật (lọc icon, logo, banner)
        parsed = urlparse(src_clean)
        if not any(ext in parsed.path.lower() for ext in IMAGE_EXTS):
            continue
        if any(skip in parsed.path.lower() for skip in ["/icon/", "/logo/", "/banner/", "placeholder"]):
            continue
        if (
            "/product/" in src_clean
            or "/dien-thoai/" in src_clean
            or "/may-tinh-bang/" in src_clean
            or "/laptop/" in src_clean
            or "-750x500" in src
            or "-800x800" in src
            or "-1200x1200" in src
        ):
            img_urls.add(src_clean)

    return list(img_urls)


# ─────────────────────────────────────────────────────────────
# MODE CHÍNH
# ─────────────────────────────────────────────────────────────
def run_mode_web(w, h, drive_service, extract_drive_id_and_type):
    st.info(
        "💡 **HƯỚNG DẪN:** Dán link sản phẩm từ TGDD hoặc DMX.\n"
        "Bấm **Quét** để lấy danh sách màu, sau đó chọn màu và bấm **Tải & Resize**."
    )

    if "web_scanned_data" not in st.session_state:
        st.session_state.web_scanned_data = []
    if "web_zip_data" not in st.session_state:
        st.session_state.web_zip_data = None

    links_text = st.text_area(
        "🔗 Dán link sản phẩm (mỗi link 1 dòng):",
        height=110,
        placeholder="https://www.thegioididong.com/dtdd/...\nhttps://www.dienmayxanh.com/..."
    )

    # ── NÚT QUÉT ─────────────────────────────────
    if st.button("🔍 QUÉT SẢN PHẨM & MÀU", use_container_width=True, key="btn_web_scan"):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
        else:
            st.session_state.web_scanned_data = []
            st.session_state.web_zip_data     = None

            with st.spinner("Đang quét sản phẩm và màu sắc..."):
                def scan_one(link: str) -> dict:
                    real = resolve_redirect_url(link)
                    return {
                        "original_link": link,
                        "real_link":     real,
                        "product_name":  get_item_name(real),
                        "colors":        get_color_links_and_names(real),
                    }

                results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {ex.submit(scan_one, l): l for l in links}
                    for f in concurrent.futures.as_completed(futs):
                        try:
                            results.append(f.result())
                        except Exception:
                            pass

                # Giữ thứ tự theo link gốc
                order = {l: i for i, l in enumerate(links)}
                results.sort(key=lambda r: order.get(r["original_link"], 999))
                st.session_state.web_scanned_data = results
                st.success(f"✅ Quét xong {len(results)} sản phẩm! Chọn màu bên dưới.")

    # ── HIỆN DANH SÁCH MÀU ───────────────────────
    if st.session_state.web_scanned_data:
        st.markdown("---")
        st.markdown("### 🎨 CHỌN MÀU CẦN TẢI")

        selected_tasks = []
        for idx_item, item in enumerate(st.session_state.web_scanned_data):
            with st.expander(f"📦 {item['product_name']}  ({len(item['colors'])} màu)", expanded=True):
                cols = st.columns(min(len(item["colors"]), 4))
                for idx_color, color in enumerate(item["colors"]):
                    key = f"cb_{idx_item}_{idx_color}_{hash(item['original_link'])}"
                    with cols[idx_color % len(cols)]:
                        if st.checkbox(color["name"], value=True, key=key):
                            selected_tasks.append({
                                "product_name": item["product_name"],
                                "color_name":   color["name"],
                                "link":         color["link"],
                            })

        st.markdown("---")
        upload_link_web = st.text_input(
            "📤 Link Thư mục Drive ĐÍCH *(tùy chọn)*:",
            placeholder="Bỏ trống nếu chỉ muốn tải ZIP về máy"
        )

        # ── NÚT TẢI & RESIZE ─────────────────────
        if st.button("🚀 BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True, key="btn_web_start"):
            if not selected_tasks:
                st.error("⚠️ Chưa chọn màu nào!")
            else:
                st.session_state.download_status = "running"
                st.session_state.web_zip_data    = None

                render_control_buttons()

                target_folder_id, _ = (
                    extract_drive_id_and_type(upload_link_web)
                    if upload_link_web else (None, None)
                )

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    raw_dir   = temp_path / "RAW"
                    final_dir = temp_path / "FINAL"

                    status_text  = st.empty()
                    progress_bar = st.progress(0)
                    log_box      = st.empty()
                    logs         = []

                    def add_log(msg: str):
                        logs.append(msg)
                        log_box.markdown(
                            "<div class='log-box'>" +
                            "<br>".join(logs[-20:]) +
                            "</div>",
                            unsafe_allow_html=True
                        )

                    total = len(selected_tasks)

                    def download_and_resize(img_url: str, c_raw: Path, c_final: Path):
                        """Tải 1 ảnh và resize — chạy trong thread pool."""
                        try:
                            img_name = os.path.basename(img_url.split("?")[0])
                            # Đảm bảo tên file có extension
                            if not any(img_name.lower().endswith(e) for e in IMAGE_EXTS):
                                img_name += ".jpg"
                            save_path = c_raw / img_name
                            out_file  = c_final / (save_path.stem + ".jpg")

                            # Tải ảnh với retry
                            for attempt in range(3):
                                try:
                                    data = SESSION.get(
                                        img_url, cookies=TGDD_COOKIES, timeout=15, stream=True
                                    )
                                    if data.status_code == 200:
                                        with open(save_path, "wb") as f:
                                            for chunk in data.iter_content(8192):
                                                f.write(chunk)
                                        break
                                except Exception:
                                    time.sleep(1)

                            if save_path.exists() and save_path.stat().st_size > 512:
                                resize_image(save_path, out_file, w, h)
                                return True
                        except Exception:
                            pass
                        return False

                    for i, task in enumerate(selected_tasks):
                        if not check_pause_cancel_state():
                            break

                        p_name = task["product_name"]
                        c_name = task["color_name"]
                        c_link = task["link"]

                        status_text.info(f"⏳ [{i+1}/{total}] Đang xử lý: **{p_name}** — *{c_name}*")

                        c_raw   = raw_dir   / p_name / c_name
                        c_final = final_dir / p_name / c_name
                        c_raw.mkdir(parents=True, exist_ok=True)
                        c_final.mkdir(parents=True, exist_ok=True)

                        img_urls = get_gallery_image_urls(c_link)
                        if not img_urls:
                            add_log(f"⚠️ Không tìm thấy ảnh: {p_name} / {c_name}")
                            progress_bar.progress((i + 1) / total)
                            continue

                        add_log(f"🔎 {p_name} / {c_name}: {len(img_urls)} ảnh")

                        ok_count = 0
                        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                            futs = {
                                ex.submit(download_and_resize, url, c_raw, c_final): url
                                for url in img_urls
                            }
                            for fut in concurrent.futures.as_completed(futs):
                                if not check_pause_cancel_state():
                                    break
                                if fut.result():
                                    ok_count += 1

                        add_log(f"✅ {p_name}/{c_name}: {ok_count}/{len(img_urls)} ảnh OK")
                        progress_bar.progress((i + 1) / total)

                    # ── UPLOAD DRIVE ──────────────────────
                    if target_folder_id and drive_service and check_pause_cancel_state():
                        status_text.info("📤 Đang upload lên Google Drive...")
                        try:
                            root_fid = create_drive_folder(
                                drive_service,
                                f"Web_Resized_{int(time.time())}",
                                target_folder_id
                            )
                            folder_cache = {"": root_fid, ".": root_fid}

                            for img in final_dir.rglob("*.jpg"):
                                if not check_pause_cancel_state():
                                    break
                                rel_dir = str(img.parent.relative_to(final_dir))
                                if rel_dir not in folder_cache:
                                    current_parent = root_fid
                                    current_path   = ""
                                    for part in Path(rel_dir).parts:
                                        current_path = (
                                            os.path.join(current_path, part)
                                            if current_path else part
                                        )
                                        if current_path not in folder_cache:
                                            folder_cache[current_path] = create_drive_folder(
                                                drive_service, part, current_parent
                                            )
                                        current_parent = folder_cache[current_path]
                                upload_to_drive(drive_service, img, folder_cache[rel_dir])
                                add_log(f"📤 {img.name}")
                        except Exception as ue:
                            add_log(f"⚠️ Upload lỗi: {ue}")

                    # ── KẾT THÚC & TẠO ZIP ───────────────
                    if st.session_state.download_status == "cancelled":
                        status_text.warning("🚫 Đã hủy! Ảnh đã xử lý vẫn có thể tải.")
                    else:
                        status_text.success("🎉 HOÀN TẤT toàn bộ!")

                    zip_base = str(temp_path / "Web_Images_Done")
                    shutil.make_archive(zip_base, "zip", final_dir)
                    zip_path = Path(zip_base + ".zip")

                    if zip_path.exists() and zip_path.stat().st_size > 22:
                        with open(zip_path, "rb") as f:
                            st.session_state.web_zip_data = f.read()

                    st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ──────────────────────────────
    if st.session_state.get("web_zip_data"):
        st.download_button(
            label="📥 TẢI KẾT QUẢ VỀ MÁY (FILE ZIP)",
            data=st.session_state.web_zip_data,
            file_name="Web_Images_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_web_zip"
        )
