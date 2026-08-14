"""
modes/web.py — Thegioididong.com adapter.
Dùng TGDDScraper (modes.tgdd_scraper) để lấy sản phẩm → màu → gallery ảnh,
sau đó ủy quyền toàn bộ pipeline cho BatchManager.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import streamlit as st

from core import state as sstate
from core.batch import BatchManager, DownloadResult, Workspace
from core.download import download_http
from core.memory import disk_ok_for_batch
from core.types import ErrorType, TaskItem, new_id
from core.validation import (
    clean_name, fingerprint, split_input_lines, validate_url_batch,
)
from ui import components as ui

from .tgdd_scraper import TGDDScraper, derive_filename


_log = logging.getLogger("modes.web")

# Cache scraper theo session để giữ HTTP session (keep-alive + cookies)
_SCRAPER_KEY = "_tgdd_scraper_v11"


def _get_scraper() -> TGDDScraper:
    """Trả scraper có sẵn hoặc tạo mới. Cookie giữ lại giữa các lần chạy."""
    sc = st.session_state.get(_SCRAPER_KEY)
    if sc is None:
        try:
            sc = TGDDScraper()
        except RuntimeError as exc:
            st.error(f"Thiếu thư viện: {exc}")
            raise
        st.session_state[_SCRAPER_KEY] = sc
    return sc


def _download_image_url(item: TaskItem, ws: Workspace) -> DownloadResult:
    """Adapter tải 1 URL ảnh trực tiếp về ws.raw."""
    img_url = item.payload.get("image_url", item.source)
    ext = Path(img_url.split("?")[0]).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
        ext = ".jpg"

    dest_dir = ws.raw / (item.group_name or "web")
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = clean_name(item.display_name)[:50] or "img"
    dest = dest_dir / f"{base}_{item.item_id[-6:]}{ext}"

    ok, err, msg = download_http(
        img_url, dest,
        timeout=(10, 30),
        headers={"Referer": "https://www.thegioididong.com/"},
    )
    if ok:
        return DownloadResult(True, dest)
    return DownloadResult(False, None, err or ErrorType.DOWNLOAD_FAILED, msg)


# ══════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════
def render(preset) -> None:
    ui.hero(
        "🛒 Thegioididong — scrape sản phẩm",
        "Dán link sản phẩm TGDD (link đầy đủ hoặc /sp-XXXXX) → scraper lấy "
        "tên sản phẩm, danh sách màu, gallery ảnh chất lượng cao → tải song song → "
        "resize theo preset → ZIP. Có thể dán nhiều link cùng lúc, mỗi dòng 1 link.",
    )

    # Cookie panel
    with st.expander("🍪 Cookie TGDD (tuỳ chọn — cần cho link `/sp-XXXXX` "
                     "và một số trang có bot check)", expanded=False):
        st.caption(
            "Dán JSON export từ **EditThisCookie** hoặc **Cookie-Editor**, "
            "hoặc raw string dạng `k1=v1; k2=v2`. Cookie được nạp vào HTTP session "
            "và tự động dùng cho mọi request tiếp theo."
        )
        cookie_txt = st.text_area(
            "Cookie",
            height=110,
            key="tgdd_cookie_input",
            placeholder='[{"name":"_ga","value":"GA1...","domain":".thegioididong.com","path":"/"}]',
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("💾 Nạp cookie", key="btn_load_cookie", use_container_width=True):
                sc = _get_scraper()
                n, msg = sc.set_cookies(cookie_txt)
                if n > 0:
                    st.success(f"✔ {msg}")
                else:
                    st.warning(f"⚠ {msg}")
        with c2:
            n_cookies = 0
            sc = st.session_state.get(_SCRAPER_KEY)
            if sc is not None:
                try:
                    n_cookies = len(list(sc._session.cookies))
                except Exception:
                    pass
            st.caption(f"Session hiện tại: {n_cookies} cookie")

    ui.section("Dán link sản phẩm")
    text = st.text_area(
        "Links",
        height=110,
        placeholder=(
            "https://www.thegioididong.com/dtdd/iphone-16-pro-max\n"
            "https://www.thegioididong.com/sp-321654"
        ),
        label_visibility="collapsed",
        key="web_links",
    )

    lines = split_input_lines(text)
    report = validate_url_batch(lines, allowed_kinds={"tgdd"})
    if lines:
        ui.input_report_bar(
            report.raw_count, report.valid_count,
            report.dup_count, report.invalid_count,
        )
        if report.invalid:
            with st.expander(f"Xem {len(report.invalid)} link không hỗ trợ"):
                for raw, reason in report.invalid[:20]:
                    st.caption(f"❌ {raw} — {reason}")

    ui.section("Chạy")
    col1, col2 = st.columns([3, 1])
    with col1:
        clicked = ui.start_button("🚀 START — scrape & xử lý", key="btn_web_start")
    with col2:
        if sstate.is_batch_active():
            if st.button("⏹ Huỷ", use_container_width=True, key="btn_web_cancel"):
                BatchManager.request_cancel()

    if clicked:
        _handle_start(report, preset)

    ui.batch_progress_panel()
    ui.batch_queue_view()
    ui.batch_result_panel()

    ui.auto_refresh_if_active(1.0)


def _handle_start(report, preset) -> None:
    if not report.valid:
        st.error("Không có link TGDD hợp lệ.")
        return
    if not sstate.acquire_batch_lock():
        st.warning("Batch khác đang chạy.")
        return

    ok, msg = disk_ok_for_batch()
    if not ok:
        sstate.release_batch_lock()
        st.error(f"⚠️ {msg}")
        return

    scraper = _get_scraper()

    # ── Stage 1: scrape các sản phẩm ────────────────────────
    items: list[TaskItem] = []
    seen_fps: set[str] = set()
    bid = f"web_{int(time.time())}"

    total_products = len(report.valid)
    prog_placeholder = st.empty()
    log_lines: list[str] = []

    for pidx, (norm_url, _kind) in enumerate(report.valid, 1):
        prog_placeholder.info(
            f"🔍 Scraping sản phẩm {pidx}/{total_products}: {norm_url[:70]}..."
        )
        try:
            prod = scraper.scrape(norm_url)
        except Exception as exc:
            _log.warning("scrape failed for %s: %s", norm_url, exc)
            log_lines.append(f"❌ {norm_url[:60]} — {exc}")
            continue

        product_name = clean_name(prod.get("name", "product"))[:40] or "product"
        colors = prod.get("colors", [])
        if not colors:
            log_lines.append(f"⚠ {product_name} — không tìm thấy ảnh")
            continue

        for color in colors:
            color_name = clean_name(color.get("name", "default"))[:30] or "default"
            imgs = color.get("images", [])
            if not imgs:
                continue

            group = (
                f"{product_name}/{color_name}"
                if color_name and color_name != "Mac_dinh"
                else product_name
            )

            for i, img_url in enumerate(imgs, 1):
                fp = fingerprint(img_url, "image_url")
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
                fname = derive_filename(img_url, i) or f"{color_name}_{i:02d}"
                items.append(TaskItem(
                    item_id=new_id("it"),
                    batch_id=bid,
                    source=img_url,
                    source_kind="image_url",
                    group_name=group,
                    display_name=fname,
                    fingerprint=fp,
                    payload={
                        "image_url": img_url,
                        "product_url": norm_url,
                        "product_name": product_name,
                        "color_name": color_name,
                    },
                ))
        log_lines.append(
            f"✔ {product_name} — {len(colors)} màu, "
            f"{sum(len(c.get('images', [])) for c in colors)} ảnh"
        )

    prog_placeholder.empty()

    if log_lines:
        with st.expander(f"Xem {len(log_lines)} log scrape", expanded=False):
            for ln in log_lines:
                st.caption(ln)

    if not items:
        sstate.release_batch_lock()
        st.error(
            "Không scrape được ảnh nào. Có thể do:\n"
            "- Link cần cookie đăng nhập (thử paste cookie ở panel trên)\n"
            "- Trang bị chặn crawler tạm thời\n"
            "- URL không tồn tại hoặc sản phẩm ngừng bán"
        )
        return

    st.info(f"✅ Đã scrape {len(items)} ảnh — bắt đầu tải & resize (chạy nền)...")

    BatchManager.start_background("web", preset, items, _download_image_url)
    st.rerun()
