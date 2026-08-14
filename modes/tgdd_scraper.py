"""
modes/tgdd_scraper.py — TGDD product page scraper.

Trích từ mode_web.py v10.2 sang module riêng để `modes/web.py` giữ được
tính chất "adapter mỏng" — chỉ điều phối BatchManager.

API công khai:
    class TGDDScraper:
        set_cookies(json_or_str)   → nạp cookie user paste (không hardcode)
        scrape(product_url)        → dict {name, colors:[{name, link, images:[...]}]}
        resolve(product_url)       → follow link rút gọn /sp-XXXXX

Scraper KHÔNG dùng streamlit — hoàn toàn thuần Python để có thể unit test.
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, unquote


_log = logging.getLogger("modes.tgdd_scraper")


# ══════════════════════════════════════════════════════════════
# HTTP CONFIG
# ══════════════════════════════════════════════════════════════
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

TGDD_HOSTS = {
    "www.thegioididong.com",
    "thegioididong.com",
    "m.thegioididong.com",
}

IMAGE_EXTENSIONS_WEB = (".jpg", ".jpeg", ".png", ".webp")


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def _clean_text(name: str) -> str:
    """Clean tên sản phẩm/màu — bỏ ký tự nguy hiểm cho path."""
    name = html.unescape(name or "")
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _normalize_input_url(url: str) -> str:
    """Chuyển link rút gọn hoặc path-only về URL đầy đủ."""
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("/"):
        return f"https://www.thegioididong.com{url}"
    if not url.startswith(("http://", "https://")):
        return f"https://www.thegioididong.com/{url.lstrip('/')}"
    return url


def is_tgdd_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host in TGDD_HOSTS:
            return True
        if not host and ("sp-" in url or url.startswith("/")):
            return True
        return False
    except Exception:
        return False


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
    """Regex tìm mọi URL ảnh trong 1 đoạn JS/JSON."""
    pattern = re.compile(
        r'https?://[^\s\"\'<>]+?(?:jpg|jpeg|png|webp)(?:\?[^\s\"\'<>]*)?',
        re.IGNORECASE,
    )
    return [_normalize_image_url(m.group(0)) for m in pattern.finditer(text)]


def derive_filename(image_url: str, index: int) -> str:
    """Sinh tên file từ URL ảnh."""
    parsed = urlparse(image_url)
    raw_name = Path(unquote(parsed.path)).name or f"image_{index:02d}"
    stem = Path(raw_name).stem
    return _clean_text(stem)[:60] or f"image_{index:02d}"


# ══════════════════════════════════════════════════════════════
# COOKIE PARSING
# ══════════════════════════════════════════════════════════════
def parse_cookies(cookie_txt: str) -> tuple[dict, str]:
    """
    Nhận string:
      • JSON export từ EditThisCookie/Cookie-Editor: [{"name","value","domain",...}, ...]
      • Raw string "k1=v1; k2=v2"
    Trả (dict, message).
    """
    cookie_txt = (cookie_txt or "").strip()
    if not cookie_txt:
        return {}, "Cookie rỗng"

    # JSON array
    if cookie_txt.startswith("["):
        try:
            data = json.loads(cookie_txt)
            if not isinstance(data, list):
                return {}, "JSON phải là array"
            out = {}
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("value")
                if not name or value is None:
                    continue
                out[str(name)] = str(value)
            return out, f"Đã nạp {len(out)} cookie từ JSON"
        except json.JSONDecodeError as exc:
            return {}, f"JSON không hợp lệ: {exc}"

    # JSON object
    if cookie_txt.startswith("{"):
        try:
            data = json.loads(cookie_txt)
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items() if v is not None}, \
                       f"Đã nạp {len(data)} cookie từ dict"
        except json.JSONDecodeError:
            pass

    # Raw "k=v; k=v"
    out = {}
    for part in re.split(r";\s*", cookie_txt):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            if k:
                out[k] = v.strip()
    return out, f"Đã parse {len(out)} cookie từ raw string" if out else "Không nhận diện được cookie"


# ══════════════════════════════════════════════════════════════
# SCRAPER CLASS
# ══════════════════════════════════════════════════════════════
class TGDDScraper:
    """Wrap 1 requests.Session có cookie đã nạp + methods scrape."""

    def __init__(self, cookies: dict | None = None):
        try:
            import requests
        except ImportError:
            raise RuntimeError("Thư viện `requests` không có sẵn.")
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        if cookies:
            self.set_cookies_dict(cookies)

    def set_cookies_dict(self, cookies: dict) -> int:
        """Nạp dict cookie vào session, trả số lượng."""
        self._session.cookies.clear()
        n = 0
        for k, v in (cookies or {}).items():
            try:
                self._session.cookies.set(
                    name=str(k), value=str(v),
                    domain=".thegioididong.com", path="/",
                )
                n += 1
            except Exception:
                continue
        return n

    def set_cookies(self, cookie_txt: str) -> tuple[int, str]:
        """Nạp cookie từ string (JSON hoặc raw). Trả (count, message)."""
        cookies, msg = parse_cookies(cookie_txt)
        n = self.set_cookies_dict(cookies) if cookies else 0
        return n, msg

    # ── HTTP GET với fallback www ↔ m ────────────────────────
    def http_get(self, url: str, timeout: int = 25):
        """
        GET có retry: thử www trước, fallback m.thegioididong nếu fail.
        Trả requests.Response hoặc None.
        """
        candidates = [url]
        try:
            parsed = urlparse(url)
            if parsed.netloc == "www.thegioididong.com":
                candidates.append(url.replace("www.thegioididong.com",
                                              "m.thegioididong.com"))
            elif parsed.netloc == "thegioididong.com":
                candidates.append(url.replace("thegioididong.com",
                                              "www.thegioididong.com"))
        except Exception:
            pass

        for attempt_url in candidates:
            for retry in range(2):
                try:
                    resp = self._session.get(
                        attempt_url, timeout=timeout, allow_redirects=True,
                    )
                    if resp.status_code == 200 and len(resp.text) > 1500:
                        return resp
                    if resp.status_code in (403, 404, 429):
                        time.sleep(0.8 + 0.4 * retry)
                        continue
                except Exception as exc:
                    _log.debug("http_get retry: %s", exc)
                    time.sleep(0.5)
                    continue
        return None

    def _get_html(self, url: str) -> tuple[str, str]:
        resp = self.http_get(url)
        if not resp:
            return url, ""
        return resp.url, resp.text

    # ── Public: resolve, name, colors, images ────────────────
    def resolve(self, url: str) -> str:
        """Follow link rút gọn /sp-XXXXX → URL đầy đủ."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return _normalize_input_url(url)

        url = _normalize_input_url(url)
        resp = self.http_get(url)
        if not resp:
            return url
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                return urljoin(resp.url, canonical["href"])
            og_url = soup.find("meta", attrs={"property": "og:url"})
            if og_url and og_url.get("content"):
                return urljoin(resp.url, og_url["content"])
            return resp.url
        except Exception:
            return resp.url

    def get_product_name(self, url: str) -> str:
        """Parse tên sản phẩm — H1 → og:title → LD-JSON → title → path."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return "San_pham"

        real_url, html_text = self._get_html(url)
        if not html_text:
            return "San_pham_khong_ten"

        soup = BeautifulSoup(html_text, "html.parser")
        name = ""

        # 1) H1
        for h1 in soup.find_all("h1"):
            text = h1.get_text(" ", strip=True)
            if text and len(text) >= 3:
                name = text
                break

        # 2) og:title
        if not name:
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title and og_title.get("content"):
                name = og_title["content"]

        # 3) LD-JSON
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

        # 4) <title>
        if not name:
            title_tag = soup.find("title")
            if title_tag:
                name = title_tag.get_text(" ", strip=True).split("|")[0].split("-")[0].strip()

        # 5) path
        if not name:
            path_name = unquote(Path(urlparse(real_url).path).name or "")
            name = path_name.replace("-", " ")

        # Lọc noise
        name = re.sub(
            r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*|chính hãng.*|"
            r"bảo hành.*|khuyến mãi.*|trả góp.*))",
            "",
            name,
            flags=re.IGNORECASE,
        )
        # Strip trailing dashes / punctuation còn lại sau khi bỏ noise
        name = re.sub(r"[\s\-–—_·,.:;/]+$", "", name).strip()
        return _clean_text(name) or "San_pham"

    def get_colors(self, url: str) -> list[dict]:
        """
        Parse danh sách màu. Trả list [{"name": str, "link": str}].
        Nếu không tìm thấy màu nào, trả 1 màu "Mac_dinh" trỏ về URL gốc.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return [{"name": "Mac_dinh", "link": url}]

        real_url, html_text = self._get_html(url)
        if not html_text:
            return [{"name": "Mac_dinh", "link": url}]

        soup = BeautifulSoup(html_text, "html.parser")
        base_path = urlparse(real_url).path
        base_sp_id = ""
        sp_match = re.search(r"sp-(\d+)", base_path)
        if sp_match:
            base_sp_id = sp_match.group(1)

        seen_links: set[str] = set()
        colors: list[dict] = []

        def add_color(name: str, link: str) -> None:
            name = _clean_text(name)
            if not name or name.lower() in {"giá tốt", "trang chủ", "tgdd"}:
                return
            full = urljoin(real_url, link)
            key = full.split("#")[0]
            if key in seen_links:
                return
            seen_links.add(key)
            colors.append({"name": name, "link": full})

        # 1) Selector .box03.color, .box-color, ...
        for box in soup.select(".box03.color, .box03 .item, .box-color, .box-color-list .item"):
            anchor = box.find("a", href=True)
            if not anchor:
                continue
            text = anchor.get("title") or anchor.get_text(" ", strip=True)
            href = anchor.get("href", "")
            if href and text:
                add_color(text, href)

        # 2) data-color attribute
        for tag in soup.find_all(attrs={"data-color": True}):
            name = tag.get("data-color") or tag.get_text(" ", strip=True)
            href = tag.get("href") or tag.get("data-href") or ""
            if href:
                add_color(name, href)

        # 3) Anchor với ?color=/?code=/mau-/sp-XXX
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

        # 4) Fallback: parse JS/JSON trong <script>
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

        # 5) Không có màu → 1 màu mặc định
        if not colors:
            colors = [{"name": "Mac_dinh", "link": real_url}]

        return colors

    def get_images(self, url: str) -> list[str]:
        """
        Parse URL ảnh chất lượng cao từ trang. Trả list ưu tiên theo priority.
        Filter: chỉ giữ CDN TGDD, bỏ icon/logo/banner/thumb.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        real_url, html_text = self._get_html(url)
        if not html_text:
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        found: dict[str, int] = {}

        def add(url_value: str, score: int = 0) -> None:
            src = _normalize_image_url(urljoin(real_url, url_value))
            if not src:
                return
            parsed = urlparse(src)
            lower = src.lower()
            # Chỉ giữ ảnh của CDN TGDD
            if parsed.netloc and "tgdd" not in parsed.netloc \
                    and "cdn" not in parsed.netloc \
                    and "thegioididong" not in parsed.netloc:
                return
            if not any(ext in lower for ext in IMAGE_EXTENSIONS_WEB):
                return
            # Loại thumbnail/icon
            if any(skip in lower for skip in [
                "icon", "logo-", "/logo.", "banner", "avatar", "placeholder",
                "loading", "/sprite", "/svg/", "_thumb-",
            ]):
                return
            # Priority
            priority = score
            if "/products/" in lower:
                priority += 12
            if "/images/" in lower:
                priority += 4
            if any(s in lower for s in ["1200x", "1020x", "680x", "800x", "1000x"]):
                priority += 2
            if src not in found or priority > found[src]:
                found[src] = priority

        # 1) img/source tags — data-src / srcset / src
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

        # 2) og:image meta
        for meta_name in ["og:image", "twitter:image", "og:image:secure_url"]:
            meta = soup.find("meta", attrs={"property": meta_name}) \
                or soup.find("meta", attrs={"name": meta_name})
            if meta and meta.get("content"):
                add(meta["content"], score=2)

        # 3) URL ảnh trong <script>
        for script in soup.find_all("script"):
            script_text = script.get_text(" ", strip=False)
            if not script_text:
                continue
            for raw_url in _extract_candidate_urls_from_text(script_text):
                add(raw_url, score=5)

        # Sort priority DESC
        sorted_urls = sorted(found.items(), key=lambda x: (-x[1], x[0]))
        return [u for u, _ in sorted_urls]

    # ── Main entry ───────────────────────────────────────────
    def scrape(self, product_url: str) -> dict:
        """
        Scrape 1 sản phẩm trả:
          {
            "name": str,
            "url":  str (resolved),
            "colors": [
              {"name": str, "link": str, "images": [url1, url2, ...]},
              ...
            ]
          }
        Nếu có nhiều màu, mỗi màu có gallery riêng.
        Nếu chỉ 1 màu, gallery từ trang gốc.
        """
        product_url = _normalize_input_url(product_url)
        real_url = self.resolve(product_url)
        name = self.get_product_name(real_url)
        colors = self.get_colors(real_url)

        result_colors: list[dict] = []
        for color in colors:
            imgs = self.get_images(color["link"])
            if imgs:
                result_colors.append({
                    "name": color["name"],
                    "link": color["link"],
                    "images": imgs,
                })

        # Fallback: nếu không màu nào có ảnh, thử lấy ảnh từ trang gốc
        if not result_colors:
            imgs = self.get_images(real_url)
            if imgs:
                result_colors.append({
                    "name": "Mac_dinh",
                    "link": real_url,
                    "images": imgs,
                })

        return {
            "name": name,
            "url": real_url,
            "colors": result_colors,
        }
