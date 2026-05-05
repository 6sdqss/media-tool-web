"""
mode_web.py — Tab Web (TGDD / DMX)
Tự động quét sản phẩm, phát hiện màu sắc, tải gallery ảnh,
resize multi-size, đóng gói ZIP.
"""

import streamlit as st
import os
import re
import time
import requests
import tempfile
import zipfile
import concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from utils import (
    resize_to_multi_sizes,
    check_pause_cancel_state,
    render_control_buttons,
    show_preview,
    show_processing_summary,
    batch_rename_with_template,
    add_to_history,
    get_size_label,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  HTTP SESSION & COOKIES                                      ║
# ╚══════════════════════════════════════════════════════════════╝

_COOKIES = {
    "_ce.clock_data": "-110%2C113.161.59.60%2C1%2C91e1a2a41c0741f7f47615ab9de2fb8a%2CChrome%2CVN",
    "_ce.s": "v~10b349a1bfb597f2fbfafdd33af1d88e35768560~lcw~1775808302291~vir~returning",
    "cebs": "1",
    "cebsp_": "32",
    "mwgsp": "1",
    "ASP.NET_SessionId": "zgo0wxmkgvnqbqub0lkreuon",
    "SvID": "beline26122|adivM|adhi9",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}

_HTTP_SESSION = requests.Session()
_HTTP_SESSION.headers.update(_HEADERS)

IMAGE_EXTENSIONS_WEB = (".jpg", ".jpeg", ".png", ".webp")


# ╔══════════════════════════════════════════════════════════════╗
# ║  HELPERS — Scraping TGDD / DMX                               ║
# ╚══════════════════════════════════════════════════════════════╝

def _clean_product_name(name: str) -> str:
    """Làm sạch tên sản phẩm."""
    name = re.sub(r'[\\/:\*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "San_pham"


def _http_get(url: str, timeout: int = 12):
    """GET request với cookies và headers đã cấu hình."""
    try:
        response = _HTTP_SESSION.get(
            url, cookies=_COOKIES, timeout=timeout, allow_redirects=True
        )
        if response.status_code == 200:
            return response
    except Exception:
        pass
    return None


def resolve_url(url: str) -> str:
    """Resolve URL thực (xử lý meta refresh redirect)."""
    try:
        response = _HTTP_SESSION.get(
            url, cookies=_COOKIES, allow_redirects=True, timeout=15
        )
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            meta = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta:
                content = meta.get("content", "")
                if "url=" in content.lower():
                    redirect_url = content.split("url=")[-1].strip("'\"")
                    return urljoin(url, redirect_url)
            return response.url
    except Exception:
        pass
    return url


def get_product_name(url: str) -> str:
    """Lấy tên sản phẩm từ trang web."""
    response = _http_get(url)
    if not response:
        return "San_pham_khong_ten"

    soup = BeautifulSoup(response.text, "html.parser")
    name = ""

    # Ưu tiên 1: Thẻ h1
    h1_tag = soup.find("h1")
    if h1_tag:
        name = h1_tag.get_text(strip=True)
    else:
        # Ưu tiên 2: JavaScript item_name
        match = re.search(r'item_name\s*:\s*"(.*?)"', soup.get_text())
        if match:
            name = match.group(1)
        else:
            # Ưu tiên 3: Thẻ title
            title_tag = soup.find("title")
            if title_tag:
                name = title_tag.text.split("|")[0].strip()

    # Loại bỏ hậu tố marketing
    name = re.sub(
        r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*|chính hãng.*|bảo hành.*))",
        "", name, flags=re.IGNORECASE,
    )

    return _clean_product_name(name) or "San_pham_khong_ten"


def get_colors(url: str) -> list[dict]:
    """Lấy danh sách biến thể màu sắc của sản phẩm."""
    response = _http_get(url)
    if not response:
        return [{"name": "Mac_dinh", "link": url}]

    soup = BeautifulSoup(response.text, "html.parser")
    base_path = urlparse(url).path
    seen_links = set()
    colors = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        # Tìm link cùng sản phẩm nhưng khác code (biến thể màu)
        if base_path in href and "?code=" in href:
            full_link = urljoin(url, href)
            color_name = _clean_product_name(anchor.get_text(strip=True))
            if full_link not in seen_links and color_name:
                colors.append({"name": color_name, "link": full_link})
                seen_links.add(full_link)

    return colors if colors else [{"name": "Mac_dinh", "link": url}]


def get_images(url: str) -> list[str]:
    """Lấy danh sách URL ảnh sản phẩm từ gallery."""
    response = _http_get(url)
    if not response:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    found_urls = set()

    for img_tag in soup.find_all("img"):
        # Lấy src: ưu tiên data-src (lazy load) → data-original → src
        src = (
            img_tag.get("data-src")
            or img_tag.get("data-original")
            or img_tag.get("src")
            or ""
        )
        if not src:
            continue

        src = urljoin(url, src)

        # Chuẩn hóa: xóa suffix kích thước ("-750x500", "-800x800"...)
        src_cleaned = re.sub(r"-\d{3,4}x\d{3,4}", "", src)
        parsed = urlparse(src_cleaned)

        # Chỉ nhận file ảnh
        if not any(src_cleaned.lower().endswith(ext) for ext in IMAGE_EXTENSIONS_WEB):
            continue

        # Loại bỏ icon, logo, banner, placeholder
        skip_patterns = ["/icon/", "/logo/", "/banner/", "placeholder", "loading"]
        if any(pattern in parsed.path.lower() for pattern in skip_patterns):
            continue

        # Chỉ nhận ảnh sản phẩm (có chứa path đặc trưng)
        product_patterns = [
            "/product/", "/dien-thoai/", "/may-tinh-bang/",
            "/laptop/", "-750x500", "-800x800", "-1200x1200",
        ]
        if any(pattern in src for pattern in product_patterns):
            found_urls.add(src_cleaned)

    return list(found_urls)


def _download_single_image(image_url: str, save_path: Path, max_retries: int = 3) -> bool:
    """Tải 1 ảnh từ URL. Retry nếu thất bại. Trả về True nếu OK."""
    for attempt in range(max_retries):
        try:
            response = _HTTP_SESSION.get(
                image_url, cookies=_COOKIES, timeout=15, stream=True
            )
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                if save_path.exists() and save_path.stat().st_size > 512:
                    return True
        except Exception:
            time.sleep(0.8)

    return False


def _make_zip(source_dir: Path, zip_path: Path):
    """Tạo ZIP từ thư mục."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_size > 0:
                zf.write(file_path, file_path.relative_to(source_dir))


# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN — Giao diện Tab Web                                    ║
# ╚══════════════════════════════════════════════════════════════╝

def run_mode_web(cfg: dict):
    """
    Giao diện và logic xử lý tab Web (TGDD / DMX).

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

    # Session state
    if "web_scanned" not in st.session_state:
        st.session_state.web_scanned = []
    if "web_zip_data" not in st.session_state:
        st.session_state.web_zip_data = None

    # ── HƯỚNG DẪN ──
    st.markdown("""
    <div class="guide-box" style="padding:10px 14px;font-size:.84rem; background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; margin-bottom:15px;">
        💡 <b>Cách dùng:</b> Dán link sản phẩm TGDD / DMX →
        Bấm <b>Quét</b> → Tick chọn màu → <b>Tải & Resize</b>
    </div>
    """, unsafe_allow_html=True)

    # ── INPUT: Link sản phẩm ──
    st.markdown(
        '<div class="sec-title">🔗 LINK SẢN PHẨM</div>',
        unsafe_allow_html=True,
    )
    links_text = st.text_area(
        "Links sản phẩm:",
        height=100,
        placeholder=(
            "https://www.thegioididong.com/dtdd/samsung-galaxy-s25\n"
            "https://www.dienmayxanh.com/tivi/..."
        ),
        label_visibility="collapsed",
        key="web_links_input",
    )

    # ══════════════════════════════════════════════════════════
    # NÚT QUÉT SẢN PHẨM & MÀU
    # ══════════════════════════════════════════════════════════
    if st.button("🔍 QUÉT SẢN PHẨM & MÀU", use_container_width=True, key="btn_web_scan"):
        links = [line.strip() for line in links_text.splitlines() if line.strip()]
        if not links:
            st.error("⚠️ Vui lòng dán ít nhất 1 link!")
        else:
            st.session_state.web_scanned = []
            st.session_state.web_zip_data = None

            with st.spinner("Đang quét sản phẩm và màu sắc..."):
                def scan_product(link):
                    real_url = resolve_url(link)
                    return {
                        "original": link,
                        "real": real_url,
                        "name": get_product_name(real_url),
                        "colors": get_colors(real_url),
                    }

                # Quét song song
                link_order = {link: idx for idx, link in enumerate(links)}
                scan_results = []

                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    future_map = {
                        executor.submit(scan_product, link): link
                        for link in links
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        try:
                            scan_results.append(future.result())
                        except Exception:
                            pass

                # Sắp xếp lại theo thứ tự link gốc
                scan_results.sort(
                    key=lambda r: link_order.get(r["original"], 999)
                )
                st.session_state.web_scanned = scan_results

            st.success(f"✅ Quét xong {len(scan_results)} sản phẩm!")

    # ══════════════════════════════════════════════════════════
    # CHỌN MÀU & ĐẶT TÊN
    # ══════════════════════════════════════════════════════════
    selected_tasks: list[dict] = []

    if st.session_state.web_scanned:
        st.markdown(
            '<div class="sec-title">🎨 CHỌN MÀU & ĐẶT TÊN</div>',
            unsafe_allow_html=True,
        )

        for product_idx, product_item in enumerate(st.session_state.web_scanned):
            auto_name = product_item["name"]
            num_colors = len(product_item["colors"])

            with st.expander(f"📦 {auto_name} — {num_colors} màu", expanded=True):

                # Ô đặt tên tùy chỉnh cho sản phẩm
                if rename_enabled:
                    custom_product_name = st.text_input(
                        "✏️ Tên sản phẩm:",
                        value="",
                        placeholder=f"{auto_name}  (tên tự động)",
                        key=f"web_product_name_{product_idx}_{hash(product_item['original'])}",
                    )
                    display_name = custom_product_name.strip() if custom_product_name.strip() else auto_name
                    display_name = re.sub(r'[\\/*?:"<>|]', "", display_name).strip() or auto_name
                else:
                    display_name = auto_name

                # Grid checkbox cho các màu
                num_cols = min(num_colors, 4)
                columns = st.columns(num_cols)

                for color_idx, color_info in enumerate(product_item["colors"]):
                    checkbox_key = (
                        f"web_color_{product_idx}_{color_idx}"
                        f"_{hash(product_item['original'])}"
                    )
                    with columns[color_idx % num_cols]:
                        if st.checkbox(color_info["name"], value=True, key=checkbox_key):
                            selected_tasks.append({
                                "product": display_name,
                                "color": color_info["name"],
                                "link": color_info["link"],
                            })

        st.markdown(f"**Đã chọn: {len(selected_tasks)} màu**")

        # ══════════════════════════════════════════════════════
        # NÚT TẢI & RESIZE
        # ══════════════════════════════════════════════════════
        if st.button("BẮT ĐẦU TẢI & RESIZE", type="primary",
                     use_container_width=True, key="btn_web_process"):
            if not selected_tasks:
                st.error("⚠️ Chưa chọn màu nào!")
                return

            st.session_state.download_status = "running"
            st.session_state.web_zip_data = None

            render_control_buttons()
            start_time = time.time()

            # UI elements
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            log_placeholder = st.empty()
            log_messages: list[str] = []

            def log(message: str):
                log_messages.append(message)
                visible = log_messages[-25:]
                log_placeholder.markdown(
                    "<div class='log-box'>" + "<br>".join(visible) + "</div>",
                    unsafe_allow_html=True,
                )

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                raw_dir = temp_path / "RAW"
                final_dir = temp_path / "FINAL"
                raw_dir.mkdir()
                final_dir.mkdir()

                total_tasks = len(selected_tasks)

                # ── XỬ LÝ TỪNG MÀU ──
                for task_idx, task in enumerate(selected_tasks):
                    if not check_pause_cancel_state():
                        break

                    product_name = task["product"]
                    color_name = task["color"]
                    color_link = task["link"]

                    status_placeholder.info(
                        f"⏳ [{task_idx + 1}/{total_tasks}] "
                        f"**{product_name}** — *{color_name}*"
                    )
                    log(f"▶ {product_name} / {color_name}")

                    # Tạo thư mục raw & final cho màu này
                    color_raw_dir = raw_dir / product_name / color_name
                    color_raw_dir.mkdir(parents=True, exist_ok=True)

                    # Lấy danh sách URL ảnh
                    try:
                        image_urls = get_images(color_link)
                    except Exception:
                        image_urls = []

                    if not image_urls:
                        log(f"  ⚠️ Không tìm thấy ảnh — bỏ qua")
                        progress_bar.progress((task_idx + 1) / total_tasks)
                        continue

                    log(f"  🔎 {len(image_urls)} ảnh tìm thấy")

                    # Tải & resize từng ảnh
                    successful_images = 0
                    folder_path = f"{product_name}/{color_name}"

                    for image_url in image_urls:
                        if not check_pause_cancel_state():
                            break

                        # Xác định tên file từ URL
                        url_filename = os.path.basename(image_url.split("?")[0])
                        if not any(url_filename.lower().endswith(ext)
                                   for ext in IMAGE_EXTENSIONS_WEB):
                            url_filename += ".jpg"

                        save_path = color_raw_dir / url_filename

                        # Tải ảnh
                        download_ok = _download_single_image(image_url, save_path)

                        if download_ok:
                            # Resize sang multi-size
                            resize_to_multi_sizes(
                                save_path, final_dir, folder_path, save_path.stem,
                                sizes, scale_pct, quality, export_format,
                            )
                            successful_images += 1

                    # Log kết quả
                    if successful_images > 0:
                        log(f"  ✅ {successful_images}/{len(image_urls)} ảnh OK")
                    else:
                        log(f"  ❌ Không tải được ảnh nào")

                    progress_bar.progress((task_idx + 1) / total_tasks)

                # ══════════════════════════════════════════════
                # KẾT THÚC — ĐÓNG GÓI ZIP
                # ══════════════════════════════════════════════
                duration = time.time() - start_time
                all_output_files = [
                    f for f in final_dir.rglob("*")
                    if f.is_file() and f.stat().st_size > 0
                ]

                if all_output_files:
                    if st.session_state.download_status == "cancelled":
                        status_placeholder.warning(
                            f"🚫 Đã hủy — {len(all_output_files)} ảnh có thể tải"
                        )
                    else:
                        status_placeholder.success(
                            f"🎉 Hoàn tất — {len(all_output_files)} ảnh!"
                        )

                    # Đổi tên theo template
                    renamed = batch_rename_with_template(final_dir, template)
                    if renamed:
                        log(f"✏️ Đã đổi tên {renamed} ảnh")

                    # Preview + Summary
                    show_preview(final_dir)
                    show_processing_summary(final_dir, sizes, duration)

                    # Đóng gói ZIP
                    zip_path = temp_path / "Web_Done.zip"
                    _make_zip(final_dir, zip_path)

                    if zip_path.exists() and zip_path.stat().st_size > 100:
                        st.session_state.web_zip_data = zip_path.read_bytes()
                        zip_size_kb = zip_path.stat().st_size // 1024
                        log(f"📦 ZIP: {zip_size_kb:,} KB")

                    # Lưu lịch sử
                    size_label = " + ".join([
                        get_size_label(w, h, m) for w, h, m in sizes
                    ])
                    product_names = list({t["product"] for t in selected_tasks})
                    add_to_history(
                        "Web",
                        ", ".join(product_names[:3]),
                        len(all_output_files),
                        size_label,
                        duration,
                    )
                else:
                    status_placeholder.error("❌ Không có ảnh nào tải được!")

                st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ──
    if st.session_state.get("web_zip_data"):
        st.success("✅ Sẵn sàng tải xuống!")
        st.download_button(
            label="📥 TẢI FILE ZIP",
            data=st.session_state.web_zip_data,
            file_name="Web_Done.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="download_web_zip",
        )
