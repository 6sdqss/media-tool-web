"""
mode_web.py — Tab Web TGDD
Chỉ tập trung cho TheGioiDiDong:
- Quét sản phẩm
- Tự phát hiện màu
- Tải gallery ảnh
- Resize đa kích thước
- Lưu manifest để chỉnh scale từng ảnh ở tab Studio
"""

from __future__ import annotations

import os
import re
import time
import html
import requests
import concurrent.futures
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import streamlit as st
from bs4 import BeautifulSoup

from utils import (
    add_to_history,
    batch_rename_with_template,
    build_preview_image,
    check_pause_cancel_state,
    clean_name,
    create_batch_workspace,
    get_size_label,
    make_zip,
    open_zip_for_download,
    readable_file_size,
    render_batch_kpis,
    render_control_buttons,
    resize_to_multi_sizes,
    safe_image_meta,
    save_json,
    show_preview,
    show_processing_summary,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  HTTP SESSION                                                ║
# ╚══════════════════════════════════════════════════════════════╝

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

_HTTP_SESSION = requests.Session()
_HTTP_SESSION.headers.update(_HEADERS)

IMAGE_EXTENSIONS_WEB = (".jpg", ".jpeg", ".png", ".webp")
TGDD_HOSTS = {"www.thegioididong.com", "thegioididong.com", "m.thegioididong.com"}


# ╔══════════════════════════════════════════════════════════════╗
# ║  HELPERS                                                     ║
# ╚══════════════════════════════════════════════════════════════╝

def _is_tgdd_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return host in TGDD_HOSTS
    except Exception:
        return False


def _clean_product_name(name: str) -> str:
    name = html.unescape(name or "")
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "San_pham"


def _http_get(url: str, timeout: int = 18):
    try:
        response = _HTTP_SESSION.get(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return response
    except Exception:
        pass
    return None


def resolve_url(url: str) -> str:
    try:
        response = _HTTP_SESSION.get(url, allow_redirects=True, timeout=18)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
            if meta:
                content = meta.get("content", "")
                if "url=" in content.lower():
                    redirect_url = content.split("url=")[-1].strip("'\"")
                    return urljoin(url, redirect_url)
            return response.url
    except Exception:
        pass
    return url


def _get_html(url: str) -> tuple[str, str]:
    response = _http_get(url)
    if not response:
        return url, ""
    return response.url, response.text


def get_product_name(url: str) -> str:
    real_url, html_text = _get_html(url)
    if not html_text:
        return "San_pham_khong_ten"

    soup = BeautifulSoup(html_text, "html.parser")
    name = ""

    h1_tag = soup.find("h1")
    if h1_tag:
        name = h1_tag.get_text(" ", strip=True)

    if not name:
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title:
            name = og_title.get("content", "")

    if not name:
        title_tag = soup.find("title")
        if title_tag:
            name = title_tag.get_text(" ", strip=True).split("|")[0].strip()

    name = re.sub(
        r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*|chính hãng.*|bảo hành.*))",
        "",
        name,
        flags=re.IGNORECASE,
    )
    return _clean_product_name(name) or _clean_product_name(Path(urlparse(real_url).path).name)


def get_colors(url: str) -> list[dict]:
    real_url, html_text = _get_html(url)
    if not html_text:
        return [{"name": "Mac_dinh", "link": url}]

    soup = BeautifulSoup(html_text, "html.parser")
    base_path = urlparse(real_url).path
    seen_links = set()
    colors = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = _clean_product_name(anchor.get_text(" ", strip=True))
        if not text:
            continue
        if base_path in href and ("?code=" in href or "?color=" in href or "/mau-" in href):
            full_link = urljoin(real_url, href)
            if full_link not in seen_links:
                colors.append({"name": text, "link": full_link})
                seen_links.add(full_link)

    if not colors:
        colors = [{"name": "Mac_dinh", "link": real_url}]
    return colors


def _normalize_image_url(url: str) -> str:
    url = html.unescape(url or "").strip().strip("'\"")
    if not url:
        return ""
    url = url.replace("\\/", "/")
    url = url.replace("%2F", "/") if "%2F" in url and "http" not in url[:8] else url
    if url.startswith("//"):
        url = "https:" + url
    return url.split("#")[0]


def _extract_candidate_urls_from_text(text: str) -> list[str]:
    pattern = re.compile(r'https?://[^\s\"\'<>]+?(?:jpg|jpeg|png|webp)(?:\?[^\s\"\'<>]*)?', re.IGNORECASE)
    return [_normalize_image_url(match.group(0)) for match in pattern.finditer(text)]


def get_images(url: str) -> list[str]:
    real_url, html_text = _get_html(url)
    if not html_text:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    found_urls: dict[str, int] = {}

    def add(url_value: str, score: int = 0):
        src = _normalize_image_url(urljoin(real_url, url_value))
        if not src:
            return
        parsed = urlparse(src)
        lower = src.lower()
        if parsed.netloc and "tgdd" not in parsed.netloc and "cdn" not in parsed.netloc:
            return
        if not any(ext in lower for ext in IMAGE_EXTENSIONS_WEB):
            return
        if any(skip in lower for skip in ["icon", "logo", "banner", "avatar", "placeholder", "loading"]):
            return
        priority = score
        if "/products/" in lower:
            priority += 10
        if "/images/" in lower:
            priority += 4
        if "1200x" in lower or "1020x" in lower or "680x" in lower:
            priority += 1
        if src not in found_urls or priority > found_urls[src]:
            found_urls[src] = priority

    for tag in soup.find_all(["img", "source"]):
        for attr in ["data-src", "data-original", "data-lazy", "data-thumb", "src", "srcset"]:
            value = tag.get(attr)
            if not value:
                continue
            if attr == "srcset":
                for part in value.split(","):
                    add(part.strip().split(" ")[0], score=2)
            else:
                add(value, score=3)

    for meta_name in ["og:image", "twitter:image"]:
        meta = soup.find("meta", attrs={"property": meta_name}) or soup.find("meta", attrs={"name": meta_name})
        if meta and meta.get("content"):
            add(meta["content"], score=2)

    for script in soup.find_all("script"):
        script_text = script.get_text(" ", strip=False)
        if not script_text:
            continue
        for raw_url in _extract_candidate_urls_from_text(script_text):
            add(raw_url, score=5)

    sorted_urls = sorted(found_urls.items(), key=lambda x: (-x[1], x[0]))
    return [url for url, _ in sorted_urls]


def _derive_filename(image_url: str, index: int) -> str:
    parsed = urlparse(image_url)
    raw_name = os.path.basename(parsed.path)
    raw_name = unquote(raw_name)
    raw_name = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name)
    stem, ext = os.path.splitext(raw_name)
    if ext.lower() not in IMAGE_EXTENSIONS_WEB:
        ext = ".jpg"
    stem = stem.strip("._") or f"image_{index:03d}"
    return f"{index:03d}_{stem}{ext.lower()}"


def _download_single_image(image_url: str, save_path: Path, max_retries: int = 3) -> bool:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(max_retries):
        try:
            response = _HTTP_SESSION.get(image_url, timeout=25, stream=True)
            if response.status_code != 200:
                continue
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
            if save_path.exists() and save_path.stat().st_size > 1024:
                return True
        except Exception:
            time.sleep(0.6 + 0.4 * attempt)
    return False


def run_mode_web(cfg: dict):
    st.markdown(
        "<div class='guide-box'>"
        "💡 <b>Workflow VIP Pro TGDD:</b> dán link sản phẩm TGDD → quét màu → tải gallery → resize → sang tab <b>Studio Scale</b> để chỉnh riêng từng ảnh nếu bị zoom lố."
        "</div>",
        unsafe_allow_html=True,
    )

    if "web_scanned" not in st.session_state:
        st.session_state.web_scanned = []
    if "web_zip_path" not in st.session_state:
        st.session_state.web_zip_path = ""

    st.markdown('<div class="sec-title">🔗 LINK SẢN PHẨM TGDD</div>', unsafe_allow_html=True)
    
    # Chia 2 cột để nút quét nằm kế bên text_area cho gọn
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        links_text = st.text_area(
            "Links sản phẩm TGDD",
            height=100,
            placeholder=(
                "https://www.thegioididong.com/dtdd/iphone-16-pro-max\n"
                "https://www.thegioididong.com/laptop/abc..."
            ),
            label_visibility="collapsed",
            key="web_links_input",
        )
    with col_btn:
        st.write("") # Căn chỉnh độ cao
        scan_clicked = st.button("🔍 QUÉT", use_container_width=True, key="btn_web_scan")

    if scan_clicked:
        links = [line.strip() for line in links_text.splitlines() if line.strip()]
        if not links:
            st.error("Vui lòng dán ít nhất 1 link TGDD.")
        else:
            invalid_links = [url for url in links if not _is_tgdd_url(url)]
            if invalid_links:
                st.error("Chỉ hỗ trợ link TheGioiDiDong. Hãy bỏ các link ngoài TGDD rồi quét lại.")
            else:
                with st.spinner("Đang quét sản phẩm, tên và màu sắc từ TGDD..."):
                    def scan_product(link: str):
                        real_url = resolve_url(link)
                        return {
                            "original": link,
                            "real": real_url,
                            "name": get_product_name(real_url),
                            "colors": get_colors(real_url),
                        }

                    scan_results = []
                    order_map = {link: idx for idx, link in enumerate(links)}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, max(2, int(cfg.get("max_workers", 4))))) as executor:
                        future_map = {executor.submit(scan_product, link): link for link in links}
                        for future in concurrent.futures.as_completed(future_map):
                            try:
                                scan_results.append(future.result())
                            except Exception:
                                pass
                    scan_results.sort(key=lambda item: order_map.get(item["original"], 9999))
                    st.session_state.web_scanned = scan_results
                    st.session_state.web_zip_path = ""
                st.success(f"Quét xong {len(st.session_state.web_scanned)} sản phẩm TGDD.")

    selected_tasks: list[dict] = []
    rename_enabled = bool(cfg.get("rename", True))

    if st.session_state.web_scanned:
        st.markdown('<div class="sec-title">🎨 CHỌN MÀU & TÊN SẢN PHẨM</div>', unsafe_allow_html=True)

        for product_idx, product_item in enumerate(st.session_state.web_scanned):
            auto_name = product_item["name"]
            colors = product_item.get("colors", [])
            with st.expander(f"📦 {auto_name} — {len(colors)} màu", expanded=True):
                if rename_enabled:
                    custom_product_name = st.text_input(
                        "Tên sản phẩm xuất ra",
                        value="",
                        placeholder=f"{auto_name} (để trống = dùng tên tự động)",
                        key=f"web_product_name_{product_idx}_{hash(product_item['original'])}",
                    )
                    display_name = custom_product_name.strip() if custom_product_name.strip() else auto_name
                    display_name = clean_name(display_name).replace("_", " ")
                else:
                    display_name = auto_name

                num_cols = min(max(len(colors), 1), 4)
                columns = st.columns(num_cols)
                for color_idx, color_info in enumerate(colors):
                    checkbox_key = f"web_color_{product_idx}_{color_idx}_{hash(product_item['original'])}"
                    with columns[color_idx % num_cols]:
                        if st.checkbox(color_info["name"], value=True, key=checkbox_key):
                            selected_tasks.append({
                                "product": display_name,
                                "color": color_info["name"],
                                "link": color_info["link"],
                            })

        st.caption(f"Đã chọn {len(selected_tasks)} biến thể màu để tải và resize.")

        if st.button("🚀 TẢI ẢNH TGDD & RESIZE", type="primary", use_container_width=True, key="btn_web_process"):
            if not selected_tasks:
                st.error("Bạn chưa chọn màu nào.")
                return

            st.session_state.download_status = "running"
            st.session_state.web_zip_path = ""
            render_control_buttons()

            workspace = create_batch_workspace("tgdd")
            root = Path(workspace["root"])
            raw_dir = Path(workspace["raw_dir"])
            final_dir = Path(workspace["final_dir"])
            preview_dir = Path(workspace["preview_dir"])
            meta_dir = Path(workspace["meta_dir"])
            zip_path = root / f"TGDD_{workspace['batch_id']}.zip"

            start_time = time.time()
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            log_placeholder = st.empty()
            logs: list[str] = []
            manifest_items: list[dict] = []
            total_downloaded = 0

            def log(message: str):
                logs.append(message)
                visible = logs[-30:]
                log_placeholder.markdown(
                    "<div class='log-box'>" + "<br>".join(visible) + "</div>",
                    unsafe_allow_html=True,
                )

            for task_idx, task in enumerate(selected_tasks, start=1):
                if not check_pause_cancel_state():
                    break

                product_name = clean_name(task["product"]).replace("_", " ")
                color_name = clean_name(task["color"]).replace("_", " ")
                folder_path = f"{clean_name(product_name)}/{clean_name(color_name)}"

                status_placeholder.info(
                    f"[{task_idx}/{len(selected_tasks)}] Đang tải TGDD: {product_name} / {color_name}"
                )
                log(f"▶ {product_name} / {color_name}")

                try:
                    image_urls = get_images(task["link"])
                except Exception:
                    image_urls = []

                if not image_urls:
                    log("⚠️ Không tìm được gallery ảnh từ trang màu này")
                    progress_bar.progress(task_idx / len(selected_tasks))
                    continue

                log(f"🔎 Tìm thấy {len(image_urls)} URL ảnh")
                color_raw_dir = raw_dir / clean_name(product_name) / clean_name(color_name)
                color_raw_dir.mkdir(parents=True, exist_ok=True)

                successful_items = []
                max_workers = min(8, max(1, int(cfg.get("max_workers", 4))))

                def download_job(payload):
                    image_index, image_url = payload
                    filename = _derive_filename(image_url, image_index)
                    save_path = color_raw_dir / filename
                    ok = _download_single_image(image_url, save_path)
                    return image_index, image_url, save_path, ok

                jobs = list(enumerate(image_urls, start=1))
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {executor.submit(download_job, payload): payload for payload in jobs}
                    for future in concurrent.futures.as_completed(future_map):
                        if not check_pause_cancel_state():
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        image_index, image_url, save_path, ok = future.result()
                        if not ok:
                            log(f"⚠️ Lỗi tải ảnh #{image_index}")
                            continue

                        meta_info = safe_image_meta(save_path)
                        preview_path = build_preview_image(save_path, preview_dir)
                        resize_to_multi_sizes(
                            save_path,
                            final_dir,
                            folder_path,
                            save_path.stem,
                            cfg.get("sizes", []),
                            scale_pct=int(cfg.get("default_scale_pct", 100)),
                            quality=int(cfg.get("quality", 95)),
                            export_format=cfg.get("export_format", "JPEG (.jpg)"),
                            huge_image_mode=bool(cfg.get("huge_image_mode", True)),
                        )
                        successful_items.append(save_path)
                        manifest_items.append({
                            "id": clean_name(f"{product_name}_{color_name}_{save_path.stem}"),
                            "product": product_name,
                            "color": color_name,
                            "folder_name": folder_path,
                            "source_path": str(save_path),
                            "preview_path": preview_path,
                            "original_name": save_path.stem,
                            "default_scale_pct": int(cfg.get("default_scale_pct", 100)),
                            "source_width": meta_info.get("width", 0),
                            "source_height": meta_info.get("height", 0),
                            "source_size_bytes": meta_info.get("size_bytes", 0),
                        })
                        total_downloaded += 1
                        log(
                            f"✅ #{image_index} {save_path.name} · "
                            f"{meta_info.get('width', 0)}×{meta_info.get('height', 0)} · "
                            f"{readable_file_size(meta_info.get('size_bytes', 0))}"
                        )

                if successful_items:
                    log(f"📦 Hoàn tất {len(successful_items)}/{len(image_urls)} ảnh cho {product_name} / {color_name}")
                else:
                    log(f"❌ Không tải được ảnh nào cho {product_name} / {color_name}")

                progress_bar.progress(task_idx / len(selected_tasks))

            duration = time.time() - start_time
            output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

            if output_files:
                renamed_count = batch_rename_with_template(final_dir, cfg.get("template", "{name}_{nn}"))
                if renamed_count:
                    log(f"✏️ Đã đổi tên {renamed_count} ảnh theo template")

                make_zip(final_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))
                st.session_state.web_zip_path = str(zip_path)
                status_placeholder.success(f"VIP Pro hoàn tất — {len(output_files)} ảnh output")
                show_preview(final_dir)
                show_processing_summary(final_dir, cfg.get("sizes", []), duration)

                batch_meta = {
                    "batch_id": workspace["batch_id"],
                    "root": str(root),
                    "source_name": "Web TGDD",
                    "source_count": len(manifest_items),
                    "output_count": len(output_files),
                    "zip_path": str(zip_path),
                    "zip_size": readable_file_size(zip_path.stat().st_size if zip_path.exists() else 0),
                }
                render_batch_kpis(batch_meta)

                save_json(manifest_items, meta_dir / "manifest.json")
                save_json(batch_meta, meta_dir / "meta.json")
                st.session_state.last_batch_manifest = manifest_items
                st.session_state.last_batch_cfg = dict(cfg)
                st.session_state.last_batch_meta = batch_meta

                size_label = " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])])
                product_names = list({t["product"] for t in selected_tasks})
                add_to_history("Web", ", ".join(product_names[:3]), len(output_files), size_label, duration)
                st.info("Nếu có ảnh nào zoom bị lố, sang tab ‘Studio Scale’ để chỉnh riêng từng ảnh rồi render lại batch.")
            else:
                status_placeholder.error("Không có ảnh nào tải và xử lý thành công.")

            st.session_state.download_status = "idle"

    zip_file = open_zip_for_download(st.session_state.get("web_zip_path", ""))
    if zip_file:
        try:
            zip_path = Path(st.session_state["web_zip_path"])
            st.success(f"ZIP TGDD sẵn sàng — {readable_file_size(zip_path.stat().st_size)}")
            st.download_button(
                label="📥 TẢI ZIP TGDD",
                data=zip_file,
                file_name=zip_path.name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="download_web_zip",
            )
        finally:
            zip_file.close()
