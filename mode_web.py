import streamlit as st
import os
import re
import time
import requests
import shutil
import tempfile
import zipfile
import concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from utils import (
    resize_image, check_pause_cancel_state, render_control_buttons,
    show_preview, batch_rename_files, add_to_history, get_size_label,
)

# ══════════════════════════════════════════════════════════════
# COOKIES & SESSION
# ══════════════════════════════════════════════════════════════
_COOKIES = {
    "_ce.clock_data": "-110%2C113.161.59.60%2C1%2C91e1a2a41c0741f7f47615ab9de2fb8a%2CChrome%2CVN",
    "_ce.s": "v~10b349a1bfb597f2fbfafdd33af1d88e35768560~lcw~1775808302291~vir~returning",
    "cebs": "1", "cebsp_": "32", "mwgsp": "1",
    "ASP.NET_SessionId": "zgo0wxmkgvnqbqub0lkreuon",
    "SvID": "beline26122|adivM|adhi9",
}
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}
_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)

IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def _clean(name: str) -> str:
    name = re.sub(r'[\\/:\*?"<>|]', "", name)
    return re.sub(r"\s+", " ", name).strip() or "San_pham"


def _get(url: str, timeout=12):
    try:
        r = _SESSION.get(url, cookies=_COOKIES, timeout=timeout, allow_redirects=True)
        return r if r.status_code == 200 else None
    except Exception:
        return None


def resolve_url(url: str) -> str:
    try:
        r = _SESSION.get(url, cookies=_COOKIES, allow_redirects=True, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            meta = soup.find("meta", attrs={"http-equiv": "refresh"})
            if meta:
                c = meta.get("content", "")
                if "url=" in c.lower():
                    return urljoin(url, c.split("url=")[-1].strip("'\""))
            return r.url
    except Exception:
        pass
    return url


def get_product_name(url: str) -> str:
    r = _get(url)
    if not r:
        return "San_pham_khong_ten"
    soup = BeautifulSoup(r.text, "html.parser")
    name = ""
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    else:
        m = re.search(r'item_name\s*:\s*"(.*?)"', soup.get_text())
        if m:
            name = m.group(1)
        else:
            t = soup.find("title")
            name = t.text.split("|")[0].strip() if t else ""
    name = re.sub(
        r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*|chính hãng.*|bảo hành.*))",
        "", name, flags=re.IGNORECASE)
    return _clean(name) or "San_pham_khong_ten"


def get_colors(url: str) -> list[dict]:
    r = _get(url)
    if not r:
        return [{"name": "Mac_dinh", "link": url}]
    soup = BeautifulSoup(r.text, "html.parser")
    base = urlparse(url).path
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if base in href and "?code=" in href:
            link = urljoin(url, href)
            nm = _clean(a.get_text(strip=True))
            if link not in seen and nm:
                out.append({"name": nm, "link": link})
                seen.add(link)
    return out if out else [{"name": "Mac_dinh", "link": url}]


def get_images(url: str) -> list[str]:
    r = _get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    found = set()
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
        if not src:
            continue
        src = urljoin(url, src)
        src_clean = re.sub(r"-\d{3,4}x\d{3,4}", "", src)
        p = urlparse(src_clean)
        if not any(src_clean.lower().endswith(e) for e in IMG_EXTS):
            continue
        if any(x in p.path.lower() for x in ["/icon/", "/logo/", "/banner/", "placeholder", "loading"]):
            continue
        if any(x in src for x in ["/product/", "/dien-thoai/", "/may-tinh-bang/",
                                   "/laptop/", "-750x500", "-800x800", "-1200x1200"]):
            found.add(src_clean)
    return list(found)


def _make_zip(final_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in final_dir.rglob("*"):
            if f.is_file() and f.stat().st_size > 0:
                zf.write(f, f.relative_to(final_dir))


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def run_mode_web(w, h, scale_pct=100, mode="letterbox", rename=False):
    if "web_scanned" not in st.session_state:
        st.session_state.web_scanned = []
    if "web_zip_data" not in st.session_state:
        st.session_state.web_zip_data = None

    st.markdown("""
    <div class="guide-box" style="padding:12px 16px;font-size:.86rem">
        💡 <b>Cách dùng:</b> Dán link sản phẩm TGDD / DMX →
        <b>Quét màu</b> → Tick chọn → <b>Tải & Resize</b>
    </div>""", unsafe_allow_html=True)

    # ── INPUT LINKS ──────────────────────────────────────────
    st.markdown('<div class="sec-title">🔗 LINK SẢN PHẨM</div>', unsafe_allow_html=True)
    links_text = st.text_area(
        "Links:", height=110,
        placeholder="https://www.thegioididong.com/dtdd/samsung-galaxy-s25\nhttps://www.dienmayxanh.com/tivi/...",
        label_visibility="collapsed", key="web_links_input")

    # ── NÚT QUÉT ─────────────────────────────────────────────
    if st.button("🔍 QUÉT SẢN PHẨM & MÀU", use_container_width=True, key="btn_scan"):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links:
            st.error("⚠️ Dán ít nhất 1 link!")
        else:
            st.session_state.web_scanned = []
            st.session_state.web_zip_data = None

            with st.spinner("Đang quét..."):
                def _scan(link):
                    real = resolve_url(link)
                    return {
                        "original": link, "real": real,
                        "name": get_product_name(real),
                        "colors": get_colors(real),
                    }
                order = {l: i for i, l in enumerate(links)}
                results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                    futs = {ex.submit(_scan, l): l for l in links}
                    for f in concurrent.futures.as_completed(futs):
                        try:
                            results.append(f.result())
                        except Exception:
                            pass
                results.sort(key=lambda r: order.get(r["original"], 999))
                st.session_state.web_scanned = results

            st.success(f"✅ Quét xong {len(results)} sản phẩm!")

    # ── CHỌN MÀU + ĐẶT TÊN ─────────────────────────────────
    selected_tasks: list[dict] = []

    if st.session_state.web_scanned:
        st.markdown('<div class="sec-title">🎨 CHỌN MÀU & ĐẶT TÊN</div>', unsafe_allow_html=True)

        for idx_p, item in enumerate(st.session_state.web_scanned):
            with st.expander(f"📦  {item['name']}  —  {len(item['colors'])} màu", expanded=True):

                # Ô đặt tên tùy chỉnh cho sản phẩm
                if rename:
                    custom_product_name = st.text_input(
                        "✏️ Tên sản phẩm:",
                        value="",
                        placeholder=f"{item['name']}  (tên tự động)",
                        key=f"web_pname_{idx_p}_{hash(item['original'])}",
                    )
                    product_name = custom_product_name.strip() if custom_product_name.strip() else item['name']
                    product_name = re.sub(r'[\\/*?:"<>|]', "", product_name).strip() or item['name']
                else:
                    product_name = item['name']

                ncols = min(len(item["colors"]), 4)
                cols = st.columns(ncols)
                for idx_c, color in enumerate(item["colors"]):
                    key = f"cb_{idx_p}_{idx_c}_{hash(item['original'])}"
                    with cols[idx_c % ncols]:
                        if st.checkbox(color["name"], value=True, key=key):
                            selected_tasks.append({
                                "product": product_name,
                                "color":   color["name"],
                                "link":    color["link"],
                            })

        st.markdown(f"**Đã chọn: {len(selected_tasks)} màu**")

        # ── NÚT TẢI & RESIZE ──────────────────────────────
        if st.button("BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True, key="btn_web_go"):
            if not selected_tasks:
                st.error("⚠️ Chưa chọn màu!")
                return

            st.session_state.download_status = "running"
            st.session_state.web_zip_data = None

            render_control_buttons()
            _t_start = time.time()
            status_ph = st.empty()
            prog_ph = st.progress(0)
            log_ph = st.empty()
            logs: list[str] = []

            def log(msg: str):
                logs.append(msg)
                log_ph.markdown(
                    "<div class='log-box'>" + "<br>".join(logs[-25:]) + "</div>",
                    unsafe_allow_html=True)

            with tempfile.TemporaryDirectory() as td:
                temp = Path(td)
                raw = temp / "RAW"
                final = temp / "FINAL"
                raw.mkdir(); final.mkdir()

                total = len(selected_tasks)

                def _download_img(img_url: str, save_raw: Path, save_final: Path) -> bool:
                    try:
                        name = os.path.basename(img_url.split("?")[0])
                        if not any(name.lower().endswith(e) for e in IMG_EXTS):
                            name += ".jpg"
                        sp = save_raw / name
                        out = save_final / (sp.stem + ".jpg")

                        for _ in range(3):
                            try:
                                r = _SESSION.get(img_url, cookies=_COOKIES, timeout=15, stream=True)
                                if r.status_code == 200:
                                    with open(sp, "wb") as f:
                                        for chunk in r.iter_content(8192):
                                            if chunk:
                                                f.write(chunk)
                                    break
                            except Exception:
                                time.sleep(0.8)

                        if sp.exists() and sp.stat().st_size > 512:
                            resize_image(sp, out, w, h, scale_pct=scale_pct, mode=mode)
                            return out.exists() and out.stat().st_size > 0
                    except Exception:
                        pass
                    return False

                for i, task in enumerate(selected_tasks):
                    if not check_pause_cancel_state():
                        break

                    p_name = task["product"]
                    c_name = task["color"]
                    c_link = task["link"]

                    status_ph.info(f"⏳ [{i+1}/{total}] **{p_name}** — *{c_name}*")
                    log(f"▶ {p_name} / {c_name}")

                    c_raw = raw / p_name / c_name
                    c_final = final / p_name / c_name
                    c_raw.mkdir(parents=True, exist_ok=True)
                    c_final.mkdir(parents=True, exist_ok=True)

                    try:
                        img_urls = get_images(c_link)
                    except Exception:
                        img_urls = []

                    if not img_urls:
                        log(f"  ⚠️ Không tìm thấy ảnh")
                        prog_ph.progress((i + 1) / total)
                        continue

                    log(f"  🔎 {len(img_urls)} ảnh")

                    ok_imgs = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                        futs = {ex.submit(_download_img, u, c_raw, c_final): u for u in img_urls}
                        for fut in concurrent.futures.as_completed(futs):
                            if not check_pause_cancel_state():
                                break
                            if fut.result():
                                ok_imgs += 1

                    if ok_imgs > 0:
                        log(f"  ✅ {ok_imgs}/{len(img_urls)} OK")
                    else:
                        log(f"  ❌ Không tải được ảnh nào")

                    prog_ph.progress((i + 1) / total)

                # ── ĐÓNG GÓI ZIP ────────────────────────────
                _duration = time.time() - _t_start
                all_out = [f for f in final.rglob("*") if f.is_file() and f.stat().st_size > 0]

                if all_out:
                    if st.session_state.download_status == "cancelled":
                        status_ph.warning(f"🚫 Đã hủy — {len(all_out)} ảnh có thể tải")
                    else:
                        status_ph.success(f"🎉 Hoàn tất — {len(all_out)} ảnh!")

                    if rename:
                        n_renamed = batch_rename_files(final)
                        if n_renamed:
                            log(f"✏️ Đổi tên {n_renamed} ảnh")

                    show_preview(final)

                    zip_path = temp / "Web_Images_Done.zip"
                    _make_zip(final, zip_path)

                    if zip_path.exists() and zip_path.stat().st_size > 100:
                        with open(zip_path, "rb") as f:
                            st.session_state.web_zip_data = f.read()
                        log(f"📦 ZIP: {zip_path.stat().st_size // 1024} KB")
                    else:
                        log("⚠️ ZIP rỗng")

                    product_names = list({t["product"] for t in selected_tasks})
                    add_to_history("Web", ", ".join(product_names[:3]),
                                   len(all_out), get_size_label(w, h, mode), _duration)
                else:
                    status_ph.error("❌ Không có ảnh nào!")

                st.session_state.download_status = "idle"

    # ── NÚT TẢI ZIP ─────────────────────────────────────────
    if st.session_state.get("web_zip_data"):
        st.success("✅ Sẵn sàng tải!")
        st.download_button(
            label="📥 TẢI FILE ZIP",
            data=st.session_state.web_zip_data,
            file_name="Web_Images_Done.zip",
            mime="application/zip",
            type="primary", use_container_width=True, key="dl_web")
