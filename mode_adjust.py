"""
mode_adjust.py — Studio Scale v10.0 (PRODUCTION REWRITE)
══════════════════════════════════════════════════════════════════════
ROOT CAUSE ANALYSIS & FIXES:

[BUG 1 — CRITICAL] Studio hiện ảnh GỐC thay vì ảnh đã resize
  Nguyên nhân: preview_base = source_path (luôn ưu tiên ảnh gốc)
               ngay cả sau khi đã render xong → user thấy ảnh gốc mãi.
  Fix: Phân biệt rõ 3 trạng thái:
    • source  → Chưa render: Dùng 2-layer CSS preview với source_path
    • rendered → Đã có trong FINAL: Hiển thị ảnh từ FINAL
    • adjusted → Đã render qua Studio: Hiển thị ảnh từ ADJUSTED

[BUG 2 — CRASH] CSS injection ở module level (ngoài function)
  Nguyên nhân: st.markdown(...) chạy ngay khi import module
               → Streamlit "Oh no!" error trên một số phiên bản
  Fix: Inject CSS một lần duy nhất qua session_state flag

[BUG 3 — PERFORMANCE] Tất cả thumbnail được build đồng thời
  Nguyên nhân: Vòng lặp build tất cả build_live_preview_b64() cùng lúc
               → RAM spike khi có 100+ ảnh → crash
  Fix: Chỉ build thumbnail cho items đang visible trên trang

[BUG 4 — STATE] Xóa toàn bộ thumb cache sau mỗi render
  Nguyên nhân: st.session_state.pop("_studio_thumb_b64_cache")
               → Tất cả thumbs phải build lại → chậm + RAM spike
  Fix: Chỉ invalidate cache của items được render

[BUG 5 — UX] Không distinguish Live Preview vs Rendered Preview
  Nguyên nhân: Dùng cùng một HTML template cho cả 2 trạng thái
  Fix: Live Preview (source + CSS) vs Rendered Preview (st.image actual)

[BUG 6 — CRASH] Không có per-item error boundary
  Nguyên nhân: Một ảnh lỗi trong loop render → exception → toàn bộ
               progress bị dừng + Streamlit hiện traceback
  Fix: try/except per item, log lỗi, tiếp tục các ảnh còn lại
"""
from __future__ import annotations

import time
import shutil
import re
import logging
from pathlib import Path
from typing import Optional

import streamlit as st

from utils import (
    EXPORT_FORMATS,
    add_to_history,
    apply_name_template,
    build_live_preview_b64,
    estimate_default_scale_for_size,
    get_size_label,
    make_zip,
    merge_final_with_adjusted,
    open_zip_for_download,
    readable_file_size,
    render_batch_kpis,
    resize_to_multi_sizes,
)

_log = logging.getLogger("mode_adjust")

# ── Hằng số ──────────────────────────────────────────────────────
_SMALL_IMAGE_THRESHOLD = 600
_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_DEFAULT_PER_PAGE = 10
_MAX_INMEM_ZIP_BYTES = 50 * 1024 * 1024  # 50MB


# ══════════════════════════════════════════════════════════════════
# CSS — Inject 1 lần duy nhất qua session_state flag
# ══════════════════════════════════════════════════════════════════
def _inject_studio_css():
    """
    [FIX BUG 2] CSS không inject ở module level nữa.
    Dùng session_state flag để chỉ inject 1 lần/session.
    """
    if st.session_state.get("_studio_css_injected"):
        return
    st.session_state["_studio_css_injected"] = True
    st.markdown("""
<style>
/* ── Disabled buttons ── */
.stButton>button:disabled,.stDownloadButton>button:disabled{
    background:rgba(255,255,255,0.05)!important;color:#64748b!important;
    cursor:not-allowed!important;box-shadow:none!important;
    border:1px solid rgba(255,255,255,0.1)!important;transform:none!important;
}
/* ── Export panel ── */
.export-panel{
    background:rgba(21,21,31,0.7);border:1px solid rgba(139,92,246,0.3);
    border-radius:12px;padding:20px;margin-top:10px;
}
/* ── Studio card ── */
.studio-card{
    border:1.5px solid rgba(139,92,246,0.22);border-radius:10px;
    background:rgba(15,15,23,0.88);padding:14px;margin-bottom:12px;
    transition:border-color .18s;
}
.studio-card.card-adjusted{border-color:#fbbf24!important;
    box-shadow:0 0 0 2px rgba(251,191,36,0.18);}
.studio-card.card-small{border-color:rgba(248,113,113,0.55)!important;}
/* ── Status pills ── */
.spill{display:inline-block;font-size:.78rem;font-weight:700;
    padding:3px 10px;border-radius:999px;letter-spacing:.3px;}
.spill-r{background:rgba(34,197,94,.85);color:#fff;}
.spill-a{background:rgba(251,191,36,.9);color:#1f2937;}
.spill-s{background:rgba(148,163,184,.85);color:#fff;}
/* ── Rendered preview frame ── */
.rendered-frame{
    background:#fff;border-radius:8px;
    border:1px solid rgba(139,92,246,0.3);
    overflow:hidden;display:flex;align-items:center;
    justify-content:center;padding:4px;
}
.rendered-frame img{max-width:100%;max-height:260px;
    object-fit:contain;display:block;margin:0 auto;}
/* ── Live-preview frame (2-layer CSS) ── */
.live-frame{position:relative;width:100%;background:#fff;
    border-radius:8px;border:1px solid rgba(139,92,246,0.3);
    overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.25);}
.live-canvas{position:absolute;inset:0;display:flex;
    align-items:center;justify-content:center;overflow:hidden;}
.live-img{width:100%;height:100%;object-fit:contain;
    transform-origin:center center;
    transition:transform .12s cubic-bezier(.4,.7,.2,1);
    will-change:transform;user-select:none;}
.live-overlay{position:absolute;bottom:0;left:0;right:0;
    display:flex;flex-wrap:wrap;gap:4px 12px;padding:5px 10px;
    background:linear-gradient(180deg,rgba(0,0,0,0)0%,rgba(0,0,0,.55)100%);
    color:#e2e8f0;font-size:.78rem!important;font-weight:600;z-index:2;}
/* ── Size info ── */
.size-info{font-size:.78rem;color:#94a3b8;margin-top:4px;line-height:1.6;}
/* ── Pagination ── */
.pg-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
    padding:8px 0;border-top:1px solid rgba(139,92,246,0.12);margin-top:8px;}
/* ── Skeleton ── */
.skeleton{background:linear-gradient(90deg,rgba(139,92,246,.08) 25%,
    rgba(139,92,246,.18) 50%,rgba(139,92,246,.08) 75%);
    background-size:200% 100%;animation:shimmer 1.4s infinite;
    border-radius:6px;height:120px;}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# HELPERS — Path resolution
# ══════════════════════════════════════════════════════════════════
def _get_exact_stem_for_item(
    item: dict, final_dir: Optional[Path],
    sizes_cfg: list, cfg: dict,
) -> str:
    """
    Đọc thẳng thư mục FINAL để lấy đúng tên file đã xuất.
    Dùng seq_in_folder để map đúng file sau khi rename template.
    """
    folder_name = item.get("folder_name", "")
    seq = int(item.get("seq_in_folder", 1))

    if final_dir and final_dir.exists():
        is_multi = isinstance(sizes_cfg, list) and len(sizes_cfg) > 1
        check_dir = final_dir
        if is_multi and sizes_cfg:
            try:
                w, h, m = sizes_cfg[0]
                check_dir = final_dir / get_size_label(w, h, m)
            except Exception:
                pass
        check_dir = check_dir / folder_name

        if check_dir.exists():
            files = sorted([
                f for f in check_dir.iterdir()
                if f.is_file() and not f.name.startswith("__tmp_")
            ])
            if 1 <= seq <= len(files):
                return files[seq - 1].stem

    # Fallback: tính tên theo template
    pname = re.sub(r"\s+", "_", item.get("product", "image")).strip("_")
    cname = re.sub(r"\s+", "_", item.get("color", "")).strip("_")
    return apply_name_template(
        cfg.get("template", "{name}_{nn}"),
        name=pname, color=cname,
        index=seq, original=item.get("original_name", ""),
    )


def _get_display_path(
    item: dict,
    final_dir: Optional[Path],
    adjusted_dir: Optional[Path],
    sizes_cfg: list,
    cfg: dict,
) -> tuple[str, str]:
    """
    [FIX BUG 1] Tìm đúng ảnh để hiển thị.
    Ưu tiên: ADJUSTED → FINAL → fallback source/preview.

    Returns: (path_str, status)
      status ∈ {"adjusted", "rendered", "source"}
    """
    exact_stem = _get_exact_stem_for_item(item, final_dir, sizes_cfg, cfg)
    is_multi   = isinstance(sizes_cfg, list) and len(sizes_cfg) > 1
    size_label = ""
    if sizes_cfg:
        try:
            w, h, m    = sizes_cfg[0]
            size_label = get_size_label(w, h, m)
        except Exception:
            pass

    folder_name = item.get("folder_name", "")

    # ── Tìm trong ADJUSTED (ảnh đã qua Studio render) ──────────
    if adjusted_dir and adjusted_dir.exists():
        adj_sub = (
            adjusted_dir / size_label / folder_name
            if is_multi and size_label
            else adjusted_dir / folder_name
        )
        if adj_sub.exists():
            for ext in _IMG_EXT:
                p = adj_sub / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "adjusted"

    # ── Tìm trong FINAL (ảnh đã resize nhưng chưa qua Studio) ──
    if final_dir and final_dir.exists():
        fin_sub = (
            final_dir / size_label / folder_name
            if is_multi and size_label
            else final_dir / folder_name
        )
        if fin_sub.exists():
            for ext in _IMG_EXT:
                p = fin_sub / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "rendered"

    # ── Fallback ────────────────────────────────────────────────
    fallback = item.get("preview_path") or item.get("source_path") or ""
    return fallback, "source"


def _is_small_image(item: dict) -> bool:
    w = int(item.get("source_width", 0))
    h = int(item.get("source_height", 0))
    return (0 < w < _SMALL_IMAGE_THRESHOLD) or (0 < h < _SMALL_IMAGE_THRESHOLD)


def _ensure_item_state(item: dict, cfg: dict):
    """Khởi tạo slider defaults cho 1 item — chỉ khi chưa có."""
    iid = item["id"]
    if f"adj_scale_{iid}" in st.session_state:
        return  # Đã khởi tạo → bỏ qua

    sizes = cfg.get("sizes", [])
    tw = th = 0
    if sizes:
        try:
            tw, th, _ = sizes[0]
            tw, th = int(tw or 0), int(th or 0)
        except Exception:
            pass

    suggested = estimate_default_scale_for_size(
        int(item.get("source_width", 0)),
        int(item.get("source_height", 0)),
        tw, th,
    )
    default = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
    st.session_state[f"adj_scale_{iid}"] = (
        max(default, suggested) if _is_small_image(item) else default
    )
    st.session_state[f"adj_x_{iid}"]     = 0
    st.session_state[f"adj_y_{iid}"]     = 0
    st.session_state[f"sel_{iid}"]       = _is_small_image(item)


def _mark_selected(item_id: str):
    st.session_state[f"sel_{item_id}"] = True


def _invalidate_thumb(item_id: str):
    """Xóa cache thumb chỉ của item cụ thể — không flush toàn bộ cache."""
    cache = st.session_state.get("_studio_thumb_b64_cache", {})
    keys_to_del = [k for k in cache if item_id in k]
    for k in keys_to_del:
        del cache[k]


# ══════════════════════════════════════════════════════════════════
# FILTER & PAGINATION
# ══════════════════════════════════════════════════════════════════
def _filter_items(
    items: list, keyword: str,
    product_filter: str, status_filter: str,
) -> list:
    kw = (keyword or "").strip().lower()
    out = []
    for item in items:
        hay = " ".join([
            item.get("product", ""), item.get("color", ""),
            item.get("original_name", ""), item.get("folder_name", ""),
        ]).lower()
        if product_filter and product_filter != "Tất cả":
            if item.get("product") != product_filter:
                continue
        if kw and kw not in hay:
            continue
        is_sel = st.session_state.get(f"sel_{item['id']}", False)
        if status_filter == "Chỉ ảnh đã chọn sửa" and not is_sel:
            continue
        if status_filter == "Chỉ ảnh chưa chọn" and is_sel:
            continue
        if status_filter == "Chỉ ảnh nhỏ (bị giãn)" and not _is_small_image(item):
            continue
        out.append(item)
    return out


def _render_pagination(total_items: int, per_page: int, page_key: str) -> tuple[int, int, int]:
    """
    Hiển thị pagination bar.
    Returns: (current_page, start_idx, end_idx)
    """
    total_pages = max((total_items - 1) // per_page + 1, 1)
    current     = int(st.session_state.get(page_key, 1))
    current     = max(1, min(current, total_pages))

    pc1, pc2, pc3, pc4, pc5 = st.columns([1, 1, 2, 1, 1])
    with pc1:
        if st.button("⏮ Đầu", use_container_width=True, key=f"{page_key}_first",
                     disabled=current <= 1):
            st.session_state[page_key] = 1
            st.rerun()
    with pc2:
        if st.button("◀ Trước", use_container_width=True, key=f"{page_key}_prev",
                     disabled=current <= 1):
            st.session_state[page_key] = current - 1
            st.rerun()
    with pc3:
        new_page = st.number_input(
            f"Trang / {total_pages}",
            min_value=1, max_value=total_pages,
            value=current, step=1,
            key=f"{page_key}_input",
            label_visibility="collapsed",
        )
        if new_page != current:
            st.session_state[page_key] = int(new_page)
            st.rerun()
    with pc4:
        if st.button("Tiếp ▶", use_container_width=True, key=f"{page_key}_next",
                     disabled=current >= total_pages):
            st.session_state[page_key] = current + 1
            st.rerun()
    with pc5:
        if st.button("Cuối ⏭", use_container_width=True, key=f"{page_key}_last",
                     disabled=current >= total_pages):
            st.session_state[page_key] = total_pages
            st.rerun()

    st.caption(
        f"Trang **{current}** / {total_pages} "
        f"· {total_items} ảnh · {per_page} ảnh/trang"
    )

    start = (current - 1) * per_page
    end   = start + per_page
    return current, start, end


# ══════════════════════════════════════════════════════════════════
# PREVIEW HTML (Live 2-layer CSS — dùng cho ảnh chưa render)
# ══════════════════════════════════════════════════════════════════
def _live_preview_html(
    image_b64: str, target_w: int, target_h: int,
    scale_pct: int, offset_x: int, offset_y: int,
) -> str:
    """
    2-Layer CSS preview: Chỉ dùng khi status == "source" (chưa render).
    Layer 1 = Canvas cố định (trắng, overflow:hidden)
    Layer 2 = Ảnh nguồn với CSS transform theo slider
    """
    if not image_b64:
        return (
            "<div class='live-frame' style='aspect-ratio:3/2;min-height:140px;"
            "display:flex;align-items:center;justify-content:center;'>"
            "<span style='color:#f87171'>⚠️ Không tìm thấy ảnh nguồn</span></div>"
        )

    f  = max(60, min(200, int(scale_pct))) / 100.0
    tx = max(-100, min(100, int(offset_x)))  * 0.5
    ty = max(-100, min(100, int(offset_y)))  * 0.5
    ar = f"{int(target_w)} / {int(target_h)}" if target_w and target_h else "3 / 2"

    return (
        f"<div class='live-frame' style='aspect-ratio:{ar};'>"
        f"  <div class='live-canvas'>"
        f"    <img class='live-img' src='{image_b64}' "
        f"         style='transform:translate({tx:.1f}%,{ty:.1f}%) scale({f:.3f})' "
        f"         alt='preview'/>"
        f"  </div>"
        f"  <div class='live-overlay'>"
        f"    <span>🔍 {int(scale_pct)}%</span>"
        f"    <span>↔ X:{int(offset_x):+d}</span>"
        f"    <span>↕ Y:{int(offset_y):+d}</span>"
        f"    <span style='margin-left:auto;color:#fde68a'>⚡ Live Preview</span>"
        f"  </div>"
        f"</div>"
    )


# ══════════════════════════════════════════════════════════════════
# SINGLE ITEM CARD
# ══════════════════════════════════════════════════════════════════
def _render_item_card(
    item: dict, cfg: dict,
    final_dir: Optional[Path],
    adjusted_dir: Optional[Path],
    target_w: int, target_h: int,
    sizes_cfg: list,
):
    """
    Render 1 item card với đầy đủ: preview, controls, download.

    [FIX BUG 1] Logic hiển thị ảnh:
      • status="adjusted"  → st.image() với ảnh từ ADJUSTED (ảnh đã render qua Studio)
      • status="rendered"  → st.image() với ảnh từ FINAL (ảnh đã resize nhưng chưa chỉnh)
      • status="source"    → 2-layer CSS preview với source_path (chưa render lần nào)
    """
    iid        = item["id"]
    sel_key    = f"sel_{iid}"
    scale_key  = f"adj_scale_{iid}"
    x_key      = f"adj_x_{iid}"
    y_key      = f"adj_y_{iid}"

    _ensure_item_state(item, cfg)
    small_flag = _is_small_image(item)

    # ── Tìm ảnh đúng trạng thái ─────────────────────────────────
    display_path, display_status = _get_display_path(
        item, final_dir, adjusted_dir, sizes_cfg, cfg
    )

    # ── Tính card CSS class ──────────────────────────────────────
    card_cls = "studio-card"
    if display_status == "adjusted":
        card_cls += " card-adjusted"
    elif small_flag:
        card_cls += " card-small"

    # ── Status pill ──────────────────────────────────────────────
    pill_map = {
        "adjusted": ("spill spill-a", "🎯 Đã chỉnh"),
        "rendered": ("spill spill-r", "✅ Đã render"),
        "source":   ("spill spill-s", "📷 Chưa render"),
    }
    pill_cls, pill_lbl = pill_map.get(display_status, pill_map["source"])
    pill_html = f"<span class='{pill_cls}'>{pill_lbl}</span>"

    with st.container(border=True):
        # ── Header row ──────────────────────────────────────────
        hc1, hc2, hc3 = st.columns([2.5, 1.5, 1])
        with hc1:
            st.checkbox(
                f"✏️ {item.get('product', '-')} · "
                f"{item.get('original_name', '-')}",
                key=sel_key,
            )
        with hc2:
            st.markdown(pill_html, unsafe_allow_html=True)
            if small_flag:
                st.markdown(
                    "<span style='color:#f87171;font-size:.8rem'>⚠️ Ảnh nhỏ</span>",
                    unsafe_allow_html=True,
                )
        with hc3:
            src_size = readable_file_size(item.get("source_size_bytes", 0))
            sw, sh   = item.get("source_width", 0), item.get("source_height", 0)
            st.markdown(
                f"<div class='size-info'>"
                f"📐 {sw}×{sh}<br>💾 {src_size}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Main layout: Preview | Controls ─────────────────────
        left_col, right_col = st.columns([1.1, 1.6])

        with left_col:
            # [FIX BUG 1] Phân biệt rõ preview vs rendered display
            if display_status in ("adjusted", "rendered"):
                # ─── Hiển thị ảnh ĐÃ RENDER thật sự ────────────
                dp = Path(display_path)
                if dp.exists() and dp.stat().st_size > 0:
                    # Build thumbnail từ ảnh đã render
                    b64 = build_live_preview_b64(display_path, max_size=480)
                    if b64:
                        st.markdown(
                            f"<div class='rendered-frame'>"
                            f"<img src='{b64}' alt='rendered'/>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        # Fallback: dùng st.image trực tiếp
                        try:
                            st.image(str(dp), use_container_width=True)
                        except Exception:
                            st.caption("⚠ Không đọc được ảnh")
                    # Hiển thị size ảnh output
                    try:
                        out_size = readable_file_size(dp.stat().st_size)
                        st.markdown(
                            f"<div class='size-info' style='color:#86efac'>"
                            f"📦 Output: {out_size} · "
                            f"🎯 {target_w}×{target_h}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        pass
                else:
                    st.markdown(
                        "<div style='color:#f87171;font-size:.85rem'>"
                        "⚠️ File render không tồn tại</div>",
                        unsafe_allow_html=True,
                    )
            else:
                # ─── Live Preview 2-layer (chưa render) ─────────
                source_path = str(item.get("source_path", ""))
                preview_b64 = ""
                if source_path and Path(source_path).exists():
                    preview_b64 = build_live_preview_b64(source_path, max_size=360)
                if not preview_b64 and display_path:
                    preview_b64 = build_live_preview_b64(display_path, max_size=360)

                live_html = _live_preview_html(
                    image_b64=preview_b64,
                    target_w=target_w, target_h=target_h,
                    scale_pct=int(st.session_state[scale_key]),
                    offset_x=int(st.session_state[x_key]),
                    offset_y=int(st.session_state[y_key]),
                )
                st.markdown(live_html, unsafe_allow_html=True)
                st.markdown(
                    f"<div class='size-info'>"
                    f"🎯 Canvas {target_w}×{target_h}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with right_col:
            # ── Sliders ────────────────────────────────────────
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.slider(
                    "Scale %", 60, 200,
                    value=int(st.session_state[scale_key]),
                    step=1, key=scale_key,
                    on_change=_mark_selected, args=(iid,),
                )
            with sc2:
                st.slider(
                    "X", -100, 100,
                    value=int(st.session_state[x_key]),
                    step=1, key=x_key,
                    on_change=_mark_selected, args=(iid,),
                )
            with sc3:
                st.slider(
                    "Y", -100, 100,
                    value=int(st.session_state[y_key]),
                    step=1, key=y_key,
                    on_change=_mark_selected, args=(iid,),
                )

            # ── Quick buttons ──────────────────────────────────
            qb1, qb2, qb3 = st.columns(3)
            with qb1:
                if st.button("↺ Reset", key=f"rst_{iid}", use_container_width=True):
                    default = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
                    st.session_state[scale_key] = default
                    st.session_state[x_key]     = 0
                    st.session_state[y_key]     = 0
                    st.session_state[sel_key]   = True
                    _invalidate_thumb(iid)
                    st.rerun()
            with qb2:
                if st.button("➖ 5%", key=f"min_{iid}", use_container_width=True):
                    st.session_state[scale_key] = max(60, int(st.session_state[scale_key]) - 5)
                    st.session_state[sel_key]   = True
                    st.rerun()
            with qb3:
                if st.button("➕ 5%", key=f"pls_{iid}", use_container_width=True):
                    st.session_state[scale_key] = min(200, int(st.session_state[scale_key]) + 5)
                    st.session_state[sel_key]   = True
                    st.rerun()

            # ── Download single image ──────────────────────────
            st.markdown(
                "<hr style='margin:8px 0;border-color:rgba(139,92,246,.15)'>",
                unsafe_allow_html=True,
            )
            if display_path and Path(display_path).exists():
                try:
                    file_bytes = Path(display_path).read_bytes()
                    btn_type   = "primary" if display_status == "adjusted" else "secondary"
                    label      = "📥 Tải ảnh đã chỉnh" if display_status == "adjusted" else "📥 Tải ảnh"
                    st.download_button(
                        label=label,
                        data=file_bytes,
                        file_name=Path(display_path).name,
                        mime="image/jpeg",
                        use_container_width=True,
                        type=btn_type,
                        key=f"dl_{iid}",
                    )
                except Exception as exc:
                    _log.warning("Download button error [%s]: %s", iid, exc)
                    st.caption("⚠ Không đọc được file")
            else:
                st.caption("— Chưa có file output —")


# ══════════════════════════════════════════════════════════════════
# RENDER ENGINE — Per-item error boundary
# ══════════════════════════════════════════════════════════════════
def _run_render(
    selected_items: list,
    adjusted_root: Path,
    final_dir: Optional[Path],
    sizes_cfg: list,
    cfg: dict,
) -> tuple[int, list[str]]:
    """
    [FIX BUG 6] Per-item try/except — 1 ảnh lỗi không crash toàn bộ.
    Returns: (success_count, error_list)
    """
    if adjusted_root.exists():
        shutil.rmtree(adjusted_root, ignore_errors=True)
    adjusted_root.mkdir(parents=True, exist_ok=True)

    progress_bar = st.progress(0)
    status_ph    = st.empty()
    errors: list[str] = []
    success      = 0
    total        = len(selected_items)

    for idx, item in enumerate(selected_items, start=1):
        item_name = item.get("original_name", item.get("product", f"item_{idx}"))
        status_ph.info(f"[{idx}/{total}] Đang render: **{item_name}**")

        settings = {
            "scale_pct": int(st.session_state.get(f"adj_scale_{item['id']}", 100)),
            "offset_x":  int(st.session_state.get(f"adj_x_{item['id']}", 0)),
            "offset_y":  int(st.session_state.get(f"adj_y_{item['id']}", 0)),
        }

        exact_stem = _get_exact_stem_for_item(item, final_dir, sizes_cfg, cfg)

        src = Path(item.get("source_path", ""))
        if not src.exists():
            err_msg = f"{item_name}: source_path không tồn tại ({src})"
            errors.append(err_msg)
            _log.warning("[render] %s", err_msg)
            progress_bar.progress(idx / total)
            continue

        try:
            resize_to_multi_sizes(
                src, adjusted_root,
                item["folder_name"], exact_stem,
                cfg.get("sizes", []),
                scale_pct=int(cfg.get("default_scale_pct", 100)),
                quality=int(cfg.get("quality", 95)),
                export_format=cfg.get("export_format", "JPEG (.jpg)"),
                per_image_settings=settings,
                huge_image_mode=bool(cfg.get("huge_image_mode", True)),
            )
            success += 1
            # [FIX BUG 4] Chỉ invalidate cache của item này
            _invalidate_thumb(item["id"])
            _log.info("[render] OK: %s", item_name)

        except Exception as exc:
            err_msg = f"{item_name}: {exc}"
            errors.append(err_msg)
            _log.error("[render] FAILED %s: %s", item_name, exc)

        progress_bar.progress(idx / total)

    status_ph.empty()
    progress_bar.empty()
    return success, errors


# ══════════════════════════════════════════════════════════════════
# MAIN STUDIO FUNCTION
# ══════════════════════════════════════════════════════════════════
def render_adjustment_studio():
    """
    Studio Scale v10.0 — Production-ready.

    Signature không đổi để tương thích với app.py cũ.
    """
    # [FIX BUG 2] CSS inject trong function, không ở module level
    _inject_studio_css()

    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2 style='font-size:1.2rem!important'>🎚 Studio Scale v10.0</h2>"
        "<p style='font-size:.9rem!important;line-height:1.6'>"
        "Điều chỉnh scale + vị trí từng ảnh. Ảnh <b>chưa render</b> hiển thị "
        "Live Preview (CSS). Sau khi bấm <b>Render</b>, Studio sẽ hiển thị "
        "<b>ảnh output thật sự</b> từ đĩa."
        "</p></div>",
        unsafe_allow_html=True,
    )

    # ── Lấy state từ session ─────────────────────────────────────
    manifest  = st.session_state.get("last_batch_manifest", [])
    cfg       = st.session_state.get("last_batch_cfg", {})
    meta      = st.session_state.get("last_batch_meta", {})

    if not manifest:
        st.info(
            "⚠️ Chưa có batch. Chạy tab **Web / Drive / Local ZIP** trước."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    render_batch_kpis(meta)

    root = Path(meta["root"]) if meta.get("root") else None
    if root and not root.exists():
        st.error(
            "❌ Workspace batch đã bị xóa (Streamlit Cloud reset container). "
            "Vui lòng chạy lại batch."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    final_dir    = Path(meta["final_dir"]) if meta.get("final_dir") else (
        root / "FINAL" if root else None
    )
    adjusted_dir = Path(
        st.session_state.get("_adjusted_root", str(root / "ADJUSTED"))
    ) if root else None
    sizes_cfg    = cfg.get("sizes", [])

    # Canvas size
    main_tw, main_th = 1020, 680
    if sizes_cfg:
        try:
            tw, th, _ = sizes_cfg[0]
            if tw and th:
                main_tw, main_th = int(tw), int(th)
        except Exception:
            pass

    # ── Init state toàn bộ manifest (một lần) ───────────────────
    init_key = f"_studio_init_{meta.get('batch_id', 'x')}"
    if not st.session_state.get(init_key):
        for item in manifest:
            _ensure_item_state(item, cfg)
        st.session_state[init_key] = True

    total     = len(manifest)
    sel_count = sum(1 for it in manifest if st.session_state.get(f"sel_{it['id']}", False))
    sml_count = sum(1 for it in manifest if _is_small_image(it))

    st.markdown(
        f"<div class='guide-box'>"
        f"<b>Batch:</b> {meta.get('batch_id', '-')[:20]} · "
        f"<b>Tổng ảnh:</b> {total} · "
        f"<b>Đang chọn:</b> <span style='color:#fbbf24'>{sel_count}</span> · "
        f"<b>Ảnh nhỏ:</b> <span style='color:#f87171'>{sml_count}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ══════ BỘ LỌC ══════════════════════════════════════════════
    st.markdown(
        '<div class="sec-title">🔍 Bộ lọc & Phân trang</div>',
        unsafe_allow_html=True,
    )
    product_names = sorted({it.get("product", "") for it in manifest if it.get("product")})

    fc1, fc2, fc3, fc4 = st.columns([1.5, 1.1, 1.3, 0.9])
    with fc1:
        keyword = st.text_input(
            "Tìm nhanh", placeholder="Tên ảnh, màu...", key="adj_kw",
            label_visibility="collapsed",
        )
    with fc2:
        product_filter = st.selectbox(
            "Sản phẩm", ["Tất cả", *product_names], key="adj_pf",
            label_visibility="collapsed",
        )
    with fc3:
        status_filter = st.selectbox(
            "Trạng thái",
            ["Tất cả", "Chỉ ảnh đã chọn sửa", "Chỉ ảnh chưa chọn", "Chỉ ảnh nhỏ (bị giãn)"],
            key="adj_sf",
            label_visibility="collapsed",
        )
    with fc4:
        per_page = st.selectbox(
            "Trang", [6, 10, 16, 24], index=1, key="adj_pp",
            label_visibility="collapsed",
        )

    filtered = _filter_items(manifest, keyword, product_filter, status_filter)

    if not filtered:
        st.warning("Không có ảnh phù hợp bộ lọc.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ══════ THAO TÁC HÀNG LOẠT ══════════════════════════════════
    st.markdown('<div class="sec-title">🧩 Thao tác hàng loạt</div>', unsafe_allow_html=True)
    with st.container(border=True):
        ba1, ba2, ba3, ba4 = st.columns(4)
        with ba1:
            if st.button("☑️ Chọn tất cả bộ lọc", use_container_width=True, key="adj_sel_all"):
                for it in filtered:
                    st.session_state[f"sel_{it['id']}"] = True
                st.rerun()
        with ba2:
            if st.button("⬜ Bỏ chọn tất cả", use_container_width=True, key="adj_unsel_all"):
                for it in filtered:
                    st.session_state[f"sel_{it['id']}"] = False
                st.rerun()
        with ba3:
            if st.button("⚠️ Chọn ảnh nhỏ", use_container_width=True, key="adj_sel_small"):
                for it in manifest:
                    if _is_small_image(it):
                        st.session_state[f"sel_{it['id']}"] = True
                st.rerun()
        with ba4:
            if st.button("🧹 Xóa toàn bộ", use_container_width=True, key="adj_clear"):
                for it in manifest:
                    st.session_state[f"sel_{it['id']}"] = False
                st.rerun()

        bs1, bs2, bs3 = st.columns(3)
        with bs1:
            bulk_scale = st.slider(
                "Scale (%)", 60, 200,
                int(cfg.get("default_scale_pct", 100)),
                key="bulk_sc",
            )
        with bs2:
            bulk_x = st.slider("X", -100, 100, 0, key="bulk_x")
        with bs3:
            bulk_y = st.slider("Y", -100, 100, 0, key="bulk_y")

        bapp1, bapp2 = st.columns(2)
        with bapp1:
            if st.button(
                "⚡ Áp dụng trang hiện tại",
                use_container_width=True, key="adj_bulk_page",
            ):
                # Áp dụng cho page items — lấy sau khi tính pagination
                page_key = "adj_page_num"
                pg       = int(st.session_state.get(page_key, 1))
                pg_start = (pg - 1) * per_page
                pg_end   = pg_start + per_page
                for it in filtered[pg_start:pg_end]:
                    iid = it["id"]
                    st.session_state[f"adj_scale_{iid}"] = int(bulk_scale)
                    st.session_state[f"adj_x_{iid}"]     = int(bulk_x)
                    st.session_state[f"adj_y_{iid}"]     = int(bulk_y)
                    st.session_state[f"sel_{iid}"]       = True
                st.rerun()
        with bapp2:
            if st.button(
                "⚡⚡ Áp dụng TOÀN BỘ bộ lọc",
                use_container_width=True, key="adj_bulk_all",
            ):
                for it in filtered:
                    iid = it["id"]
                    st.session_state[f"adj_scale_{iid}"] = int(bulk_scale)
                    st.session_state[f"adj_x_{iid}"]     = int(bulk_x)
                    st.session_state[f"adj_y_{iid}"]     = int(bulk_y)
                    st.session_state[f"sel_{iid}"]       = True
                st.rerun()

    # ══════ PAGINATION + ITEM LIST ═══════════════════════════════
    st.markdown(
        f'<div class="sec-title">🖼 Ảnh ({len(filtered)} phù hợp) — '
        f'Canvas {main_tw}×{main_th}</div>',
        unsafe_allow_html=True,
    )

    _, start, end = _render_pagination(len(filtered), per_page, "adj_page_num")
    page_items    = filtered[start:end]

    for item in page_items:
        _render_item_card(
            item=item, cfg=cfg,
            final_dir=final_dir, adjusted_dir=adjusted_dir,
            target_w=main_tw, target_h=main_th,
            sizes_cfg=sizes_cfg,
        )

    # ══════ XUẤT FILE ═══════════════════════════════════════════
    selected_items = [it for it in manifest if st.session_state.get(f"sel_{it['id']}", False)]

    st.markdown("""
        <div class="export-panel">
            <h2 style="margin-top:0;color:#fff;font-size:1.3rem">
                🚀 BƯỚC CUỐI: XUẤT FILE & TẢI VỀ
            </h2>
            <p style="color:#cbd5e1;font-size:.9rem">
                <b>Bước 1</b>: Render ảnh đã chọn (áp dụng scale/vị trí) →
                <b>Bước 2</b>: Đóng gói ZIP →
                <b>Bước 3</b>: Tải về máy.
            </p>
        </div>
    """, unsafe_allow_html=True)

    col_r, col_z = st.columns(2)

    with col_r:
        st.markdown(
            "<h4 style='color:#a78bfa;margin-bottom:4px'>▶ BƯỚC 1: RENDER</h4>",
            unsafe_allow_html=True,
        )
        do_render = st.button(
            f"🎨 Render {len(selected_items)} ảnh đã chọn",
            type="primary", use_container_width=True,
            key="adj_render",
            disabled=(len(selected_items) == 0),
        )

    with col_z:
        st.markdown(
            "<h4 style='color:#a78bfa;margin-bottom:4px'>▶ BƯỚC 2: TẠO ZIP</h4>",
            unsafe_allow_html=True,
        )
        do_export = st.button(
            "📦 ZIP gộp (ảnh đã chỉnh + ảnh gốc)",
            type="primary", use_container_width=True,
            key="adj_export",
        )

    # ── Xử lý render ─────────────────────────────────────────────
    if do_render:
        if not root:
            st.error("❌ Workspace batch không tồn tại.")
        else:
            adjusted_root = root / "ADJUSTED"
            start_time    = time.time()

            success_n, errors = _run_render(
                selected_items, adjusted_root,
                final_dir, sizes_cfg, cfg,
            )
            duration = time.time() - start_time

            st.session_state["_adjusted_root"]    = str(adjusted_root)
            st.session_state["_adjust_render_done"] = True

            if success_n > 0:
                st.success(
                    f"✅ Render xong **{success_n}/{len(selected_items)}** ảnh "
                    f"trong {duration:.1f}s"
                )
                add_to_history(
                    "Adjust",
                    f"Studio · {success_n} ảnh",
                    success_n,
                    " + ".join([get_size_label(w, h, m) for w, h, m in sizes_cfg]),
                    duration,
                )

            if errors:
                with st.expander(f"⚠️ {len(errors)} ảnh bị lỗi — Xem chi tiết"):
                    for e in errors:
                        st.caption(f"• {e}")

            st.rerun()

    # ── Xử lý export ZIP ─────────────────────────────────────────
    if do_export:
        if not root:
            st.error("❌ Workspace batch không tồn tại.")
        elif not final_dir or not final_dir.exists():
            st.error("❌ Thư mục FINAL không tồn tại.")
        else:
            adj_p = Path(
                st.session_state.get("_adjusted_root", str(root / "ADJUSTED"))
            )
            uid   = int(time.time())

            with st.spinner("Đang gộp ảnh đã chỉnh + ảnh gốc..."):
                merged_dir = root / f"MERGED_{uid}"
                merged_dir.mkdir(parents=True, exist_ok=True)
                stats = merge_final_with_adjusted(final_dir, adj_p, merged_dir)

                zip_path = root / f"FullExport_{meta.get('batch_id','batch')}_{uid}.zip"
                make_zip(merged_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))

            if zip_path.exists() and zip_path.stat().st_size > 0:
                st.session_state["adjust_zip_path"] = str(zip_path)
                st.success(
                    f"📦 ZIP sẵn sàng · Ghi đè: **{stats['overridden']}** · "
                    f"Giữ nguyên: **{stats['kept']}** ảnh"
                )
                st.rerun()
            else:
                st.error("❌ Tạo ZIP thất bại.")

    # ══════ TẢI ZIP ══════════════════════════════════════════════
    st.markdown(
        "<h4 style='color:#a78bfa;margin-top:20px;margin-bottom:4px'>"
        "▶ BƯỚC 3: TẢI FILE ZIP</h4>",
        unsafe_allow_html=True,
    )

    dz1, dz2 = st.columns(2)

    with dz1:
        # ZIP gốc (FINAL)
        zip_orig = meta.get("zip_path", "")
        if not zip_orig or not Path(zip_orig).exists():
            # Tạo fallback ZIP từ FINAL
            if root and final_dir and final_dir.exists():
                try:
                    fb_zip = root / f"OrigExport_{meta.get('batch_id','b')}.zip"
                    if not fb_zip.exists():
                        make_zip(final_dir, fb_zip, compresslevel=6)
                    if fb_zip.exists():
                        zip_orig = str(fb_zip)
                except Exception:
                    pass

        h = open_zip_for_download(zip_orig)
        if h:
            try:
                sz = readable_file_size(Path(zip_orig).stat().st_size)
                st.download_button(
                    f"⬇️ ZIP Gốc ({sz})",
                    data=h,
                    file_name=Path(zip_orig).name,
                    mime="application/zip",
                    use_container_width=True,
                    key="dl_orig_zip",
                )
            finally:
                h.close()
        else:
            st.caption("ZIP gốc chưa có.")

    with dz2:
        # ZIP gộp (FINAL + ADJUSTED)
        zip_merged = st.session_state.get("adjust_zip_path", "")
        hm = open_zip_for_download(zip_merged)
        if hm:
            try:
                sz = readable_file_size(Path(zip_merged).stat().st_size)
                st.download_button(
                    f"⬇️ ZIP Gộp — Đã chỉnh ({sz})",
                    data=hm,
                    file_name=Path(zip_merged).name,
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    key="dl_merged_zip",
                )
            finally:
                hm.close()
        else:
            st.info("💡 Bấm **[Bước 2: Tạo ZIP]** để tạo file gộp.")

    st.markdown("</div>", unsafe_allow_html=True)
