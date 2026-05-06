"""
mode_web.py — Tab Web TGDD v9.3
─────────────────────────────────────────────────────────
v9.3 (giữ NGUYÊN logic crawl/parser cookie/parser màu/parser ảnh):
- THÊM `seq_in_folder` vào manifest item → Studio map đúng ảnh sau rename.
- ZIP path lưu vào last_batch_meta để Studio dùng làm "ZIP GỐC".
"""

from __future__ import annotations

import os
import re
import json
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
# ║  HTTP SESSION + COOKIE STORE                                 ║
# ╚══════════════════════════════════════════════════════════════╝
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.thegioididong.com/",
}

_HTTP_SESSION = requests.Session()
_HTTP_SESSION.headers.update(_HEADERS)

IMAGE_EXTENSIONS_WEB = (".jpg", ".jpeg", ".png", ".webp")
TGDD_HOSTS = {
    "www.thegioididong.com",
    "thegioididong.com",
    "m.thegioididong.com",
}

_COOKIE_STATE_KEY = "_tgdd_cookies_loaded"


def _load_cookies_from_json(cookies_json: str) -> tuple[bool, str, int]:
    """Nạp cookie từ chuỗi JSON (export từ EditThisCookie / Cookie-Editor)."""
    if not cookies_json or not cookies_json.strip():
        return False, "Cookie JSON rỗng.", 0
    try:
        data = json.loads(cookies_json)
        if not isinstance(data, list):
            return False, "JSON phải là một mảng các cookie.", 0

        _HTTP_SESSION.cookies.clear()
        loaded = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            domain = item.get("domain", ".thegioididong.com")
            path = item.get("path", "/")
            if not name or value is None:
                continue
            try:
                _HTTP_SESSION.cookies.set(
                    name=name,
                    value=str(value),
                    domain=domain,
                    path=path,
                )
                loaded += 1
            except Exception:
                continue
        return (loaded > 0), f"Đã nạp {loaded} cookie.", loaded
    except json.JSONDecodeError as exc:
        return False, f"JSON không hợp lệ: {exc}", 0
    except Exception as exc:
        return False, f"Lỗi đọc cookie: {exc}", 0


def _ensure_cookies_loaded():
    """Auto-load cookie từ session_state nếu đã có (giữ nguyên cookie mặc định)."""
    my_cookie_json = """[
{"domain":".thegioididong.com","name":"_ga","path":"/","value":"GA1.1.1348144808.1750172118"},
{"domain":".thegioididong.com","name":"_fbp","path":"/","value":"fb.1.1750172120680.10576193331080870"},
{"domain":".thegioididong.com","name":"mwgsp","path":"/","value":"1"},
{"domain":"www.thegioididong.com","name":"__IP","path":"/","value":"1906391868"},
{"domain":"www.thegioididong.com","name":"__R","path":"/","value":"3"},
{"domain":"www.thegioididong.com","name":"__RC","path":"/","value":"5"},
{"domain":"www.thegioididong.com","name":"__tb","path":"/","value":"0"},
{"domain":"www.thegioididong.com","name":"__uif","path":"/","value":"__uid%3A9050220803447467022%7C__ui%3A1%252C6%7C__create%3A1750220803"},
{"domain":"www.thegioididong.com","name":"_customerIdRecommend","path":"/","value":"39576f4b4f03cb8b"},
{"domain":"www.thegioididong.com","name":"offRemindLocation","path":"/","value":"1"},
{"domain":"www.thegioididong.com","name":"popup_banner_home","path":"/","value":"popup_banner_H_1days"},
{"domain":"www.thegioididong.com","name":"SvID","path":"/","value":"beline2682|afqtx|afqqk"},
{"domain":".www.thegioididong.com","name":"_uidcms","path":"/","value":"9050220803447467022"}
]"""
    cookies_text = st.session_state.get("tgdd_cookies_json", my_cookie_json)
    already = st.session_state.get(_COOKIE_STATE_KEY, False)
    if cookies_text and not already:
        ok, _msg, _n = _load_cookies_from_json(cookies_text)
        st.session_state[_COOKIE_STATE_KEY] = ok
        st.session_state["tgdd_cookies_json"] = cookies_text


# ╔══════════════════════════════════════════════════════════════╗
# ║  HELPERS                                                     ║
# ╚══════════════════════════════════════════════════════════════╝
def _is_tgdd_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host in TGDD_HOSTS:
            return True
        if not host and ("sp-" in url or url.startswith("/")):
            return True
        return False
    except Exception:
        return False


def _normalize_input_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("/"):
        return f"https://www.thegioididong.com{url}"
    if not url.startswith(("http://", "https://")):
        return f"https://www.thegioididong.com/{url.lstrip('/')}"
    return url


def _clean_product_name(name: str) -> str:
    name = html.unescape(name or "")
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "San_pham"


def _http_get(url: str, timeout: int = 25, extra_headers: dict | None = None):
    """GET có retry: thử www → m.thegioididong (mobile) → cookie session."""
    candidates = [url]
    parsed = urlparse(url)
    if parsed.netloc == "www.thegioididong.com":
        candidates.append(url.replace("www.thegioididong.com", "m.thegioididong.com"))
    elif parsed.netloc == "thegioididong.com":
        candidates.append(url.replace("thegioididong.com", "www.thegioididong.com"))

    for attempt_url in candidates:
        for retry in range(2):
            try:
                headers = dict(_HEADERS)
                if extra_headers:
                    headers.update(extra_headers)
                response = _HTTP_SESSION.get(
                    attempt_url, timeout=timeout,
                    allow_redirects=True, headers=headers,
                )
                if response.status_code == 200 and len(response.text) > 1500:
                    return response
                if response.status_code in (403, 404, 429):
                    time.sleep(0.8 + 0.4 * retry)
                    continue
            except Exception:
                time.sleep(0.5)
                continue
    return None


def resolve_url(url: str) -> str:
    """Resolve link rút gọn (sp-XXXXX) → link đầy đủ."""
    url = _normalize_input_url(url)
    response = _http_get(url)
    if not response:
        return url
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return urljoin(response.url, canonical["href"])
        og_url = soup.find("meta", attrs={"property": "og:url"})
        if og_url and og_url.get("content"):
            return urljoin(response.url, og_url["content"])
        return response.url
    except Exception:
        return response.url


def _get_html(url: str) -> tuple[str, str]:
    response = _http_get(url)
    if not response:
        return url, ""
    return response.url, response.text


# ── PARSER TÊN SẢN PHẨM v2026 ──
def get_product_name(url: str) -> str:
    real_url, html_text = _get_html(url)
    if not html_text:
        return "San_pham_khong_ten"

    soup = BeautifulSoup(html_text, "html.parser")
    name = ""

    for h1 in soup.find_all("h1"):
        text = h1.get_text(" ", strip=True)
        if text and len(text) >= 3:
            name = text
            break

    if not name:
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            name = og_title["content"]

    if not name:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "{}")
                if isinstance(data, dict) and data.get("name"):
                    name = data["name"]
                    break
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("name"):
                            name = item["name"]
                            break
                    if name:
                        break
            except Exception:
                continue

    if not name:
        title_tag = soup.find("title")
        if title_tag:
            name = title_tag.get_text(" ", strip=True).split("|")[0].split("-")[0].strip()

    if not name:
        path_name = unquote(Path(urlparse(real_url).path).name or "")
        name = path_name.replace("-", " ")

    name = re.sub(
        r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*|chính hãng.*|"
        r"bảo hành.*|khuyến mãi.*|trả góp.*))",
        "",
        name,
        flags=re.IGNORECASE,
    )
    return _clean_product_name(name) or "San_pham"


# ── PARSER MÀU v2026 ──
def get_colors(url: str) -> list[dict]:
    real_url, html_text = _get_html(url)
    if not html_text:
        return [{"name": "Mac_dinh", "link": url}]

    soup = BeautifulSoup(html_text, "html.parser")
    base_path = urlparse(real_url).path
    base_sp_id = ""
    sp_match = re.search(r"sp-(\d+)", base_path)
    if sp_match:
        base_sp_id = sp_match.group(1)

    seen_links = set()
    colors: list[dict] = []

    def add_color(name: str, link: str):
        name = _clean_product_name(name)
        if not name or name.lower() in {"giá tốt", "trang chủ", "tgdd"}:
            return
        full = urljoin(real_url, link)
        key = full.split("#")[0]
        if key in seen_links:
            return
        seen_links.add(key)
        colors.append({"name": name, "link": full})

    for box in soup.select(".box03.color, .box03 .item, .box-color, .box-color-list .item"):
        anchor = box.find("a", href=True)
        if not anchor:
            continue
        text = anchor.get("title") or anchor.get_text(" ", strip=True)
        href = anchor.get("href", "")
        if href and text:
            add_color(text, href)

    for tag in soup.find_all(attrs={"data-color": True}):
        name = tag.get("data-color") or tag.get_text(" ", strip=True)
        href = tag.get("href") or tag.get("data-href") or ""
        if href:
            add_color(name, href)

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = anchor.get("title") or anchor.get_text(" ", strip=True)
        if not text:
            continue
        text_lower = text.lower()
        href_lower = href.lower()

        is_color_link = (
            "?color=" in href_lower
            or "?code=" in href_lower
            or "/mau-" in href_lower
            or (base_sp_id and f"sp-{base_sp_id}" not in href_lower
                and re.search(r"sp-\d+", href_lower) and "màu" in text_lower)
        )
        same_product = (
            base_path and base_path in href
        ) or (base_sp_id and f"sp-{base_sp_id}" in href_lower)

        if is_color_link and (same_product or "?color=" in href_lower or "?code=" in href_lower):
            add_color(text, href)

    if not colors:
        for script in soup.find_all("script"):
            txt = script.string or ""
            if not txt or "color" not in txt.lower():
                continue
            for match in re.finditer(
                r'["\']?(?:name|color|colorName)["\']?\s*:\s*["\']([^"\']+)["\']'
                r'[^}]{0,200}["\']?(?:url|link|href)["\']?\s*:\s*["\']([^"\']+)["\']',
                txt, re.IGNORECASE,
            ):
                add_color(match.group(1), match.group(2))

    if not colors:
        colors = [{"name": "Mac_dinh", "link": real_url}]

    return colors


def _normalize_image_url(url: str) -> str:
    url = html.unescape(url or "").strip().strip("'\"")
    if not url:
        return ""
    url = url.replace("\\/", "/")
    if "%2F" in url and "http" not in url[:8]:
        url = url.replace("%2F", "/")
    if url.startswith("//"):
        url = "https:" + url
    return url.split("#")[0]


def _extract_candidate_urls_from_text(text: str) -> list[str]:
    pattern = re.compile(
        r'https?://[^\s\"\'<>]+?(?:jpg|jpeg|png|webp)(?:\?[^\s\"\'<>]*)?',
        re.IGNORECASE,
    )
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
        if parsed.netloc and "tgdd" not in parsed.netloc and "cdn" not in parsed.netloc \
                and "thegioididong" not in parsed.netloc:
            return
        if not any(ext in lower for ext in IMAGE_EXTENSIONS_WEB):
            return
        if any(skip in lower for skip in [
            "icon", "logo-", "/logo.", "banner", "avatar", "placeholder",
            "loading", "/sprite", "/svg/", "_thumb-",
        ]):
            return
        priority = score
        if "/products/" in lower:
            priority += 12
        if "/images/" in lower:
            priority += 4
        if any(s in lower for s in ["1200x", "1020x", "680x", "800x", "1000x"]):
            priority += 2
        if src not in found_urls or priority > found_urls[src]:
            found_urls[src] = priority

    for tag in soup.find_all(["img", "source"]):
        for attr in ["data-src", "data-original", "data-lazy", "data-thumb",
                     "data-zoom-image", "data-large", "src", "srcset"]:
            value = tag.get(attr)
            if not value:
                continue
            if attr == "srcset":
                for part in value.split(","):
                    add(part.strip().split(" ")[0], score=2)
            else:
                add(value, score=3)

    for meta_name in ["og:image", "twitter:image", "og:image:secure_url"]:
        meta = soup.find("meta", attrs={"property": meta_name}) \
            or soup.find("meta", attrs={"name": meta_name})
        if meta and meta.get("content"):
            add(meta["content"], score=2)

    for script in soup.find_all("script"):
        script_text = script.get_text(" ", strip=False)
        if not script_text:
            continue
        for raw_url in _extract_candidate_urls_from_text(script_text):
            add(raw_url, score=5)

    sorted_urls = sorted(found_urls.items(), key=lambda x: (-x[1], x[0]))
    return [u for u, _ in sorted_urls]


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
            response = _HTTP_SESSION.get(image_url, timeout=30, stream=True)
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


# ╔══════════════════════════════════════════════════════════════╗
# ║  COOKIE PANEL UI                                             ║
# ╚══════════════════════════════════════════════════════════════╝
def _render_cookie_panel():
    with st.expander("🍪 Cookie TGDD (bắt buộc cho link sp-XXXXX)", expanded=False):
        st.caption(
            "Dán JSON cookie export từ extension **Cookie-Editor** / **EditThisCookie** "
            "trên trình duyệt đã đăng nhập trang TheGioiDiDong. "
            "Cookie giúp vượt qua chặn 404/anti-bot khi truy cập link rút gọn."
        )
        cookies_input = st.text_area(
            "Cookie JSON",
            value=st.session_state.get("tgdd_cookies_json", ""),
            height=130,
            placeholder='[{"domain":".thegioididong.com","name":"_ga","value":"..."}, ...]',
            label_visibility="collapsed",
            key="tgdd_cookies_input_area",
        )
        cc1, cc2, cc3 = st.columns([1, 1, 1])
        with cc1:
            if st.button("💾 Lưu & Nạp", use_container_width=True, key="btn_save_cookie"):
                ok, msg, n = _load_cookies_from_json(cookies_input)
                if ok:
                    st.session_state["tgdd_cookies_json"] = cookies_input
                    st.session_state[_COOKIE_STATE_KEY] = True
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
        with cc2:
            if st.button("🧪 Test", use_container_width=True, key="btn_test_cookie"):
                _ensure_cookies_loaded()
                test_resp = _http_get("https://www.thegioididong.com/")
                if test_resp and test_resp.status_code == 200:
                    st.success(f"✅ Kết nối OK ({len(test_resp.text):,} bytes)")
                else:
                    st.error("❌ Kết nối thất bại — kiểm tra cookie.")
        with cc3:
            if st.button("🗑 Xóa", use_container_width=True, key="btn_clear_cookie"):
                _HTTP_SESSION.cookies.clear()
                st.session_state.pop("tgdd_cookies_json", None)
                st.session_state[_COOKIE_STATE_KEY] = False
                st.info("🗑 Đã xóa cookie.")

        cookie_count = len(_HTTP_SESSION.cookies)
        if cookie_count > 0:
            st.caption(f"🟢 Phiên hiện tại: **{cookie_count} cookie** đã nạp.")
        else:
            st.caption("⚪ Chưa có cookie — link `/sp-XXXXX` có thể bị 404.")


# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN UI                                                     ║
# ╚══════════════════════════════════════════════════════════════╝
def run_mode_web(cfg: dict):
    _ensure_cookies_loaded()

    st.markdown(
        "<div class='guide-box'>"
        "💡 <b>Workflow TGDD:</b> (1) Nạp cookie → (2) dán link → (3) quét → "
        "(4) chọn màu → (5) resize → (6) sang <b>Studio</b> chỉnh ảnh nhỏ bị giãn."
        "</div>",
        unsafe_allow_html=True,
    )

    _render_cookie_panel()

    if "web_scanned" not in st.session_state:
        st.session_state.web_scanned = []
    if "web_zip_path" not in st.session_state:
        st.session_state.web_zip_path = ""

    st.markdown('<div class="sec-title">🔗 Link sản phẩm TGDD</div>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        links_text = st.text_area(
            "Links",
            height=85,
            placeholder=(
                "https://www.thegioididong.com/sp-366648\n"
                "https://www.thegioididong.com/dtdd/iphone-16-pro-max"
            ),
            label_visibility="collapsed",
            key="web_links_input",
        )
    with col_btn:
        st.write("")
        scan_clicked = st.button("🔍 QUÉT", use_container_width=True, key="btn_web_scan")

    if scan_clicked:
        links = [_normalize_input_url(l) for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("Vui lòng dán ít nhất 1 link TGDD.")
        else:
            invalid_links = [u for u in links if not _is_tgdd_url(u)]
            if invalid_links:
                st.error("Chỉ hỗ trợ link TheGioiDiDong.")
            else:
                with st.spinner("Đang quét sản phẩm và màu..."):
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
                    workers = min(6, max(2, int(cfg.get("max_workers", 4))))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                        future_map = {executor.submit(scan_product, link): link for link in links}
                        for future in concurrent.futures.as_completed(future_map):
                            try:
                                scan_results.append(future.result())
                            except Exception:
                                pass
                    scan_results.sort(key=lambda item: order_map.get(item["original"], 9999))
                    st.session_state.web_scanned = scan_results
                    st.session_state.web_zip_path = ""

                ok_cnt = sum(1 for r in st.session_state.web_scanned
                             if r["name"] != "San_pham_khong_ten")
                if ok_cnt == 0:
                    st.error(
                        "⚠️ Không quét được sản phẩm nào. "
                        "Hãy nạp **Cookie JSON** ở panel phía trên rồi thử lại."
                    )
                else:
                    st.success(f"Quét xong {ok_cnt}/{len(links)} sản phẩm.")

    selected_tasks: list[dict] = []
    rename_enabled = bool(cfg.get("rename", True))

    if st.session_state.web_scanned:
        st.markdown('<div class="sec-title">🎨 Chọn màu & tên xuất</div>', unsafe_allow_html=True)

        for product_idx, product_item in enumerate(st.session_state.web_scanned):
            auto_name = product_item["name"]
            colors = product_item.get("colors", [])
            with st.expander(f"📦 {auto_name} — {len(colors)} màu", expanded=True):
                if rename_enabled:
                    custom_product_name = st.text_input(
                        "Tên xuất ra",
                        value="",
                        placeholder=f"{auto_name} (trống = tự động)",
                        key=f"web_product_name_{product_idx}_{hash(product_item['original'])}",
                    )
                    display_name = custom_product_name.strip() if custom_product_name.strip() else auto_name
                    display_name = clean_name(display_name).replace("_", " ")
                else:
                    display_name = auto_name

                num_cols = min(max(len(colors), 1), 3)
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

        st.caption(f"Đã chọn {len(selected_tasks)} biến thể màu.")

        if st.button("🚀 TẢI ẢNH & RESIZE", type="primary",
                     use_container_width=True, key="btn_web_process"):
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

            def log(message: str):
                logs.append(message)
                visible = logs[-25:]
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
                    f"[{task_idx}/{len(selected_tasks)}] {product_name} / {color_name}"
                )
                log(f"▶ {product_name} / {color_name}")

                try:
                    image_urls = get_images(task["link"])
                except Exception:
                    image_urls = []

                if not image_urls:
                    log("⚠️ Không tìm được gallery")
                    progress_bar.progress(task_idx / len(selected_tasks))
                    continue

                log(f"🔎 Tìm thấy {len(image_urls)} URL ảnh")
                color_raw_dir = raw_dir / clean_name(product_name) / clean_name(color_name)
                color_raw_dir.mkdir(parents=True, exist_ok=True)

                # Theo dõi seq trong CÙNG folder_path để Studio map ảnh chính xác
                folder_counter = {}

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
                    # Sắp xếp kết quả theo image_index để giữ thứ tự ổn định
                    raw_results = []
                    for future in concurrent.futures.as_completed(future_map):
                        if not check_pause_cancel_state():
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                        raw_results.append(future.result())
                    raw_results.sort(key=lambda r: r[0])

                    for image_index, image_url, save_path, ok in raw_results:
                        if not ok:
                            log(f"⚠️ Lỗi tải #{image_index}")
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

                        # seq trong folder_path
                        folder_counter[folder_path] = folder_counter.get(folder_path, 0) + 1
                        seq_in_folder = folder_counter[folder_path]

                        successful_items.append(save_path)
                        manifest_items.append({
                            "id": clean_name(f"{product_name}_{color_name}_{save_path.stem}"),
                            "product": product_name,
                            "color": color_name,
                            "folder_name": folder_path,
                            "seq_in_folder": seq_in_folder,
                            "source_path": str(save_path),
                            "preview_path": preview_path,
                            "original_name": save_path.stem,
                            "default_scale_pct": int(cfg.get("default_scale_pct", 100)),
                            "source_width": meta_info.get("width", 0),
                            "source_height": meta_info.get("height", 0),
                            "source_size_bytes": meta_info.get("size_bytes", 0),
                        })
                        log(
                            f"✅ #{image_index} {save_path.name} · "
                            f"{meta_info.get('width', 0)}×{meta_info.get('height', 0)} · "
                            f"{readable_file_size(meta_info.get('size_bytes', 0))}"
                        )

                if successful_items:
                    log(f"📦 {len(successful_items)}/{len(image_urls)} ảnh OK")
                else:
                    log(f"❌ Không tải được ảnh nào cho {product_name} / {color_name}")

                progress_bar.progress(task_idx / len(selected_tasks))

            duration = time.time() - start_time
            output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

            if output_files:
                renamed_count = batch_rename_with_template(final_dir, cfg.get("template", "{name}_{nn}"))
                if renamed_count:
                    log(f"✏️ Đã đổi tên {renamed_count} ảnh")

                make_zip(final_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))
                st.session_state.web_zip_path = str(zip_path)
                status_placeholder.success(f"🎉 Hoàn tất — {len(output_files)} ảnh output")
                show_preview(final_dir)
                show_processing_summary(final_dir, cfg.get("sizes", []), duration)

                batch_meta = {
                    "batch_id": workspace["batch_id"],
                    "root": str(root),
                    "final_dir": str(final_dir),
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
                st.session_state.pop("_adjusted_root", None)
                st.session_state.pop("_studio_thumb_b64_cache", None)
                st.session_state["_goto_studio"] = True

                size_label = " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])])
                product_names = list({t["product"] for t in selected_tasks})
                add_to_history("Web", ", ".join(product_names[:3]), len(output_files), size_label, duration)
                st.success("🎯 Render xong! Đang chuyển sang **tab Studio** để bạn xem & chỉnh ảnh...")
            else:
                status_placeholder.error("Không có ảnh nào tải/xử lý thành công.")

            st.session_state.download_status = "idle"

    zip_file = open_zip_for_download(st.session_state.get("web_zip_path", ""))
    if zip_file:
        try:
            zip_path = Path(st.session_state.web_zip_path)
            size_text = readable_file_size(zip_path.stat().st_size)
            st.success(f"📦 ZIP sẵn sàng · {size_text}")
            st.download_button(
                label="📥 TẢI ZIP",
                data=zip_file,
                file_name=zip_path.name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="download_web_zip",
            )
        finally:
            zip_file.close()
