"""
mode_adjust.py — Studio Scale v9.8
─────────────────────────────────────────────────────────
NÂNG CẤP v9.8 — Tổng hợp đầy đủ, giữ 100% logic cũ:

★ FIX TRIỆT ĐỂ MẤT STATE KHI CHUYỂN TRANG:
  Dùng dict `_adj_values` trong session_state (không phải widget key).
  Widget key (ws_/wx_/wy_/wsel_) là tạm thời — Streamlit có thể xóa bất
  cứ lúc nào khi widget không được render. _adj_values KHÔNG BAO GIỜ bị xóa.
  → Chuyển trang bao nhiêu lần, giá trị vẫn nguyên vẹn 100%.

★ NÚT "💾 LƯU TRANG NÀY" — theo yêu cầu:
  Người dùng chỉnh trang 1 → bấm LƯU → chuyển sang trang 2 chỉnh → LƯU →
  Render sẽ đọc đúng thông số của tất cả các trang đã lưu.
  Widget keys được đồng bộ → _adj_values qua on_change tự động,
  nút LƯU là cơ chế backup/confirm rõ ràng.

★ LAYOUT LIST DÀI CHI TIẾT (MẶC ĐỊNH):
  Giữ nguyên list dài 1 item/row: preview 2-layer + slider Scale/X/Y +
  nút Reset/±5% + tải từng tấm. Đúng giao diện cũ, đủ chức năng.
  Grid nhỏ là chế độ phụ.

★ RAM SAFETY:
  - b64 cache giới hạn 60 entry / 20 MB
  - preview thumbnail 480px (tiết kiệm ~56% vs 720px)
  - gc.collect() sau render nặng
  - Không load ZIP bytes vào session_state

★ XUẤT FILE ĐÚNG TẤT CẢ ẢNH ĐÃ CHỈNH:
  selected_items đọc từ _adj_values (toàn bộ manifest, không phụ thuộc trang).
"""

from __future__ import annotations

import gc
import re
import shutil
import time
from pathlib import Path

import streamlit as st

from utils import (
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


# ─── Hằng số ──────────────────────────────────────────────────────────
_SMALL_IMAGE_THRESHOLD = 600
_IMG_EXT               = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ══════════════════════════════════════════════════════════════════════
# CSS — Giữ nguyên style gốc + thêm lớp mới
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Disabled buttons ── */
.stButton > button:disabled,
.stDownloadButton > button:disabled {
    background: rgba(255,255,255,0.05) !important;
    color: #64748b !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    transform: none !important;
}

/* ── Export panel ── */
.export-panel {
    background: rgba(21,21,31,0.7);
    border: 1px solid rgba(139,92,246,0.3);
    border-radius: 12px;
    padding: 20px;
    margin-top: 10px;
}

/* ── Save-page banner ── */
.save-banner {
    background: linear-gradient(90deg,
        rgba(251,191,36,0.12) 0%, rgba(245,158,11,0.08) 100%);
    border: 1px solid rgba(251,191,36,0.4);
    border-radius: 10px;
    padding: 10px 16px;
    margin: 8px 0 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.88rem;
    color: #fde68a;
}
.save-banner b { color: #fbbf24; }

/* ── Compact grid card ── */
.gc-wrap {
    border: 1.5px solid rgba(139,92,246,0.22);
    border-radius: 9px;
    overflow: hidden;
    background: rgba(15,15,23,0.9);
    margin-bottom: 6px;
}
.gc-wrap.gc-sel  { border-color: #fbbf24 !important;
                   box-shadow: 0 0 0 2px rgba(251,191,36,0.22); }
.gc-wrap.gc-warn { border-color: rgba(248,113,113,0.55) !important; }
.gc-thumb        { width:100%; max-height:128px; object-fit:contain;
                   background:#fff; display:block; }
.gc-thumb-empty  { width:100%; height:80px; background:#0f172a;
                   display:flex; align-items:center; justify-content:center;
                   color:#475569; font-size:0.72rem; }
.gc-body  { padding:5px 7px 4px; }
.gc-name  { font-size:0.73rem; color:#c4b5fd; font-weight:700;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.gc-sub   { font-size:0.67rem; color:#64748b; white-space:nowrap;
             overflow:hidden; text-overflow:ellipsis; margin-top:1px; }
.gc-vals  { display:flex; gap:7px; margin-top:3px;
             font-size:0.72rem; font-weight:600; }
.gc-s { color:#4ade80; } .gc-x { color:#60a5fa; } .gc-y { color:#f472b6; }
.gc-sa{ color:#fbbf24; font-size:0.67rem; margin-top:2px; }
.gc-sr{ color:#4ade80; font-size:0.67rem; margin-top:2px; }
.gc-ss{ color:#94a3b8; font-size:0.67rem; margin-top:2px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# PERSISTENT ADJUSTMENT STORE  (_adj_values)
# ══════════════════════════════════════════════════════════════════════

def _astore() -> dict:
    """Kho lưu trữ bền vững — không bao giờ bị Streamlit xóa."""
    return st.session_state.setdefault("_adj_values", {})


def _aget(item_id: str, field: str, default=None):
    """Đọc 1 field của item_id từ kho bền vững."""
    return _astore().get(item_id, {}).get(field, default)


def _aset(item_id: str, **kwargs):
    """Ghi vào kho bền vững (idempotent nếu cùng giá trị)."""
    store = _astore()
    if item_id not in store:
        store[item_id] = {}
    store[item_id].update(kwargs)


def _ainit(item_id: str, scale: int, sel: bool):
    """Khởi tạo entry CHƯA tồn tại — không ghi đè."""
    if item_id not in _astore():
        _aset(item_id, scale=scale, x=0, y=0, sel=sel)


def _wkeys(iid: str) -> tuple[str, str, str, str]:
    """4 widget keys tạm thời (Streamlit có thể xóa khi widget không render)."""
    return f"ws_{iid}", f"wx_{iid}", f"wy_{iid}", f"wsel_{iid}"


def _restore_wkeys_from_store(iid: str):
    """
    Tái khởi tạo widget keys từ _adj_values.
    Gọi ngay trước khi render widget — đảm bảo giá trị đúng sau chuyển trang.
    """
    wsk, wxk, wyk, wselk = _wkeys(iid)
    if wsk   not in st.session_state: st.session_state[wsk]   = _aget(iid, "scale", 100)
    if wxk   not in st.session_state: st.session_state[wxk]   = _aget(iid, "x",     0)
    if wyk   not in st.session_state: st.session_state[wyk]   = _aget(iid, "y",     0)
    if wselk not in st.session_state: st.session_state[wselk] = _aget(iid, "sel",   False)


def _invalidate_wkeys(iid: str):
    """Xóa widget keys để ép Streamlit tái khởi từ _adj_values lần sau."""
    for k in _wkeys(iid):
        st.session_state.pop(k, None)


def _sync_widget_to_store(iid: str, field: str, widget_key: str):
    """
    on_change callback: đồng bộ widget → _adj_values ngay khi user kéo slider.
    Đây là đồng bộ tự động theo thời gian thực.
    """
    val = st.session_state.get(widget_key)
    if val is None:
        return
    if field == "sel":
        _aset(iid, sel=bool(val))
    elif field == "scale":
        _aset(iid, scale=int(val), sel=True)
    elif field in ("x", "y"):
        _aset(iid, sel=True, **{field: int(val)})


def _save_page_to_store(page_items: list):
    """
    Đồng bộ TOÀN BỘ widget hiện trên trang vào _adj_values.
    Gọi khi user bấm nút "💾 LƯU TRANG NÀY".
    Đây là cơ chế backup chắc chắn — kể cả khi on_change bị miss.
    """
    saved = 0
    for item in page_items:
        iid = item["id"]
        wsk, wxk, wyk, wselk = _wkeys(iid)
        scale_val = st.session_state.get(wsk)
        x_val     = st.session_state.get(wxk)
        y_val     = st.session_state.get(wyk)
        sel_val   = st.session_state.get(wselk)
        updates = {}
        if scale_val is not None: updates["scale"] = int(scale_val)
        if x_val     is not None: updates["x"]     = int(x_val)
        if y_val     is not None: updates["y"]     = int(y_val)
        if sel_val   is not None: updates["sel"]   = bool(sel_val)
        if updates:
            _aset(iid, **updates)
            saved += 1
    return saved


def _apply_bulk_to_items(target_items: list,
                          scale_value: int, x_value: int, y_value: int,
                          also_select: bool = True):
    """Áp scale/x/y hàng loạt → _adj_values + xóa widget keys để tái khởi."""
    for item in target_items:
        iid = item["id"]
        _aset(iid, scale=int(scale_value), x=int(x_value), y=int(y_value))
        if also_select:
            _aset(iid, sel=True)
        _invalidate_wkeys(iid)


# ══════════════════════════════════════════════════════════════════════
# HELPERS — GIỮ NGUYÊN LOGIC GỐC
# ══════════════════════════════════════════════════════════════════════

def _is_small_image(item: dict) -> bool:
    w = int(item.get("source_width",  0))
    h = int(item.get("source_height", 0))
    return (0 < w < _SMALL_IMAGE_THRESHOLD) or (0 < h < _SMALL_IMAGE_THRESHOLD)


def _ensure_default_state(item: dict, cfg: dict):
    """
    Khởi tạo _adj_values cho item nếu chưa có (idempotent).
    Gọi một lần duy nhất ngay đầu hàm cho toàn bộ manifest.
    """
    iid = item["id"]
    if iid in _astore():
        return  # đã có, không ghi đè
    sizes    = cfg.get("sizes", [])
    tgt_w = tgt_h = 0
    if sizes:
        try:
            tw, th, _m = sizes[0]
            tgt_w, tgt_h = int(tw or 0), int(th or 0)
        except Exception:
            pass
    suggested     = estimate_default_scale_for_size(
        int(item.get("source_width",  0)),
        int(item.get("source_height", 0)),
        tgt_w, tgt_h,
    )
    default_scale = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
    init_scale    = max(default_scale, suggested) if _is_small_image(item) else default_scale
    _ainit(iid, scale=init_scale, sel=_is_small_image(item))


def _get_exact_stem_for_item(item: dict, final_dir: Path,
                              sizes_cfg: list, cfg: dict) -> str:
    """Đọc thẳng vào thư mục FINAL để lấy ĐÚNG tên file đã xuất."""
    folder_name = item.get("folder_name", "")
    seq         = int(item.get("seq_in_folder", 1))

    if final_dir and final_dir.exists():
        is_multi  = isinstance(sizes_cfg, list) and len(sizes_cfg) > 1
        check_dir = final_dir
        if is_multi and sizes_cfg:
            try:
                w, h, m   = sizes_cfg[0]
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

    product_part = re.sub(r"\s+", "_", item.get("product", "image")).strip("_")
    color_part   = re.sub(r"\s+", "_", item.get("color",   "")).strip("_")
    return apply_name_template(
        cfg.get("template", "{name}_{nn}"),
        name=product_part, color=color_part,
        index=seq, original=item.get("original_name", ""),
    )


def _get_exact_display_path(item: dict, final_dir: Path, adjusted_dir: Path,
                             sizes_cfg: list, cfg: dict):
    """Ưu tiên ADJUSTED → FINAL → Source."""
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

    if adjusted_dir and adjusted_dir.exists():
        d = (adjusted_dir / size_label / folder_name
             if is_multi and size_label else adjusted_dir / folder_name)
        if d.exists():
            for ext in _IMG_EXT:
                p = d / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "adjusted"

    if final_dir and final_dir.exists():
        d = (final_dir / size_label / folder_name
             if is_multi and size_label else final_dir / folder_name)
        if d.exists():
            for ext in _IMG_EXT:
                p = d / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "rendered"

    fallback = item.get("preview_path") or item.get("source_path") or ""
    return fallback, "source"


def _filtered_items(items: list, keyword: str, product_filter: str,
                    status_filter: str) -> list:
    keyword = (keyword or "").strip().lower()
    output  = []
    for item in items:
        haystack = " ".join([
            item.get("product", ""), item.get("color", ""),
            item.get("original_name", ""), item.get("folder_name", ""),
        ]).lower()
        if (product_filter and product_filter != "Tất cả"
                and item.get("product") != product_filter):
            continue
        if keyword and keyword not in haystack:
            continue
        is_sel = _aget(item["id"], "sel", False)
        if status_filter == "Chỉ ảnh đã chọn sửa" and not is_sel: continue
        if status_filter == "Chỉ ảnh chưa chọn"   and is_sel:     continue
        if status_filter == "Chỉ ảnh nhỏ (bị giãn)":
            if (int(item.get("source_width",  0)) >= _SMALL_IMAGE_THRESHOLD
                    and int(item.get("source_height", 0)) >= _SMALL_IMAGE_THRESHOLD):
                continue
        output.append(item)
    return output


def _live_preview_html(image_b64: str, target_w: int, target_h: int,
                       scale_pct: int, offset_x_pct: int, offset_y_pct: int,
                       status_pill_html: str) -> str:
    """2-Layer canvas preview — canvas cố định, product layer phóng to bên trong."""
    if not image_b64:
        return ("<div class='live-frame live-frame--empty'>"
                "<span>⚠️ Không tìm thấy ảnh.</span></div>")
    factor = max(60, min(200, int(scale_pct))) / 100.0
    tx     = max(-100, min(100, int(offset_x_pct))) * 0.5
    ty     = max(-100, min(100, int(offset_y_pct))) * 0.5
    aspect = f"{int(target_w)} / {int(target_h)}" if target_w and target_h else "3 / 2"
    return (
        f"<div class='live-frame' style='aspect-ratio:{aspect};overflow:hidden;"
        f"position:relative;background:#fff;border-radius:8px;"
        f"border:1px solid rgba(139,92,246,0.3);box-shadow:0 4px 6px rgba(0,0,0,0.1);'>"
        f"  <div style='position:absolute;inset:0;display:flex;"
        f"       align-items:center;justify-content:center;'>"
        f"    <img src='{image_b64}' "
        f"         style='max-width:100%;max-height:100%;object-fit:contain;"
        f"                transform:translate({tx:.1f}%,{ty:.1f}%) scale({factor:.3f});"
        f"                transition:transform 0.1s ease-out;' alt=''/>"
        f"  </div>"
        f"  <div style='position:absolute;top:10px;left:10px;z-index:10;'>"
        f"    {status_pill_html}</div>"
        f"  <div style='position:absolute;bottom:10px;left:10px;right:10px;display:flex;"
        f"       justify-content:space-between;background:rgba(15,23,42,0.75);"
        f"       padding:6px 12px;border-radius:6px;font-size:0.85rem;color:#fff;"
        f"       z-index:10;backdrop-filter:blur(4px);'>"
        f"    <span>🔍 Scale: <b>{int(scale_pct)}%</b></span>"
        f"    <span>↔️ X: <b>{int(offset_x_pct):+d}</b></span>"
        f"    <span>↕️ Y: <b>{int(offset_y_pct):+d}</b></span>"
        f"  </div>"
        f"</div>"
    )


# ══════════════════════════════════════════════════════════════════════
# COMPACT GRID CARD (chế độ phụ)
# ══════════════════════════════════════════════════════════════════════

def _render_grid_card(item: dict, final_dir: Path, adjusted_dir: Path,
                      sizes_cfg: list, cfg: dict,
                      main_target_w: int, main_target_h: int):
    iid       = item["id"]
    scale_val = _aget(iid, "scale", 100)
    x_val     = _aget(iid, "x",     0)
    y_val     = _aget(iid, "y",     0)
    is_sel    = _aget(iid, "sel",   False)
    small_w   = _is_small_image(item)

    display_path, display_status = _get_exact_display_path(
        item, final_dir, adjusted_dir, sizes_cfg, cfg
    )
    src_path     = str(item.get("source_path", ""))
    preview_base = src_path if (src_path and Path(src_path).exists()) else display_path
    image_b64    = build_live_preview_b64(preview_base, max_size=200)

    _ico = {"adjusted": "🎯", "rendered": "✅", "source": "📷"}.get(display_status, "📷")
    _cls = {"adjusted": "gc-sa", "rendered": "gc-sr", "source": "gc-ss"}.get(display_status, "gc-ss")
    _lbl = {"adjusted": "Đã chỉnh", "rendered": "Đã render", "source": "Ảnh nguồn"}.get(display_status, "Ảnh nguồn")

    border_cls = "gc-sel" if is_sel else ("gc-warn" if small_w else "")
    name_s     = (item.get("product") or "-")[:22]
    orig_s     = (item.get("original_name") or "-")[:22]
    warn_txt   = "&nbsp;⚠️" if small_w else ""

    img_html = (
        f"<img class='gc-thumb' src='{image_b64}' alt=''/>"
        if image_b64 else
        "<div class='gc-thumb-empty'>Không có ảnh</div>"
    )
    st.markdown(f"""
<div class='gc-wrap {border_cls}'>
    {img_html}
    <div class='gc-body'>
        <div class='gc-name'>{_ico} {name_s}{warn_txt}</div>
        <div class='gc-sub'>{orig_s}</div>
        <div class='gc-vals'>
            <span class='gc-s'>S:{scale_val}%</span>
            <span class='gc-x'>X:{x_val:+d}</span>
            <span class='gc-y'>Y:{y_val:+d}</span>
        </div>
        <div class='{_cls}'>{_lbl}</div>
    </div>
</div>""", unsafe_allow_html=True)

    _, _, _, wselk = _wkeys(iid)
    if wselk not in st.session_state:
        st.session_state[wselk] = is_sel
    st.checkbox("✏️ Chọn", key=wselk,
                on_change=_sync_widget_to_store, args=(iid, "sel", wselk))

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("−5%", key=f"gm_{iid}", use_container_width=True):
            _aset(iid, scale=max(60, int(scale_val) - 5), sel=True)
            _invalidate_wkeys(iid)
            st.rerun()
    with b2:
        if st.button("↺", key=f"gr_{iid}", use_container_width=True):
            _aset(iid, scale=int(item.get("default_scale_pct",
                                          cfg.get("default_scale_pct", 100))),
                  x=0, y=0)
            _invalidate_wkeys(iid)
            st.rerun()
    with b3:
        if st.button("+5%", key=f"gp_{iid}", use_container_width=True):
            _aset(iid, scale=min(200, int(scale_val) + 5), sel=True)
            _invalidate_wkeys(iid)
            st.rerun()

    if display_path and Path(display_path).exists():
        try:
            with open(display_path, "rb") as fh:
                fbytes = fh.read()
            st.download_button(
                "📥 Tải tấm này",
                data=fbytes,
                file_name=Path(display_path).name,
                mime="image/jpeg",
                use_container_width=True,
                type="primary" if display_status == "adjusted" else "secondary",
                key=f"gdl_{iid}",
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# DETAIL ROW — list dài 1 item/row (chế độ mặc định)
# ══════════════════════════════════════════════════════════════════════

def _render_detail_row(item: dict, final_dir: Path, adjusted_dir: Path,
                       sizes_cfg: list, cfg: dict,
                       main_target_w: int, main_target_h: int):
    """
    Render 1 ảnh theo kiểu list dài chi tiết:
    - Preview 2-layer (live CSS transform)
    - Slider Scale / Lệch X / Lệch Y
    - Nút Reset / Thu nhỏ 5% / Phóng 5%
    - Checkbox "Cần sửa ảnh này"
    - Nút tải từng tấm
    Tất cả widget đều dùng widget key tạm thời, đồng bộ → _adj_values qua on_change.
    """
    iid = item["id"]

    # Tái khởi widget keys từ _adj_values (an toàn sau chuyển trang)
    _restore_wkeys_from_store(iid)
    wsk, wxk, wyk, wselk = _wkeys(iid)

    small_warn = _is_small_image(item)

    display_path, display_status = _get_exact_display_path(
        item, final_dir, adjusted_dir, sizes_cfg, cfg
    )
    src_path     = str(item.get("source_path", ""))
    preview_base = src_path if (src_path and Path(src_path).exists()) else display_path
    image_b64    = build_live_preview_b64(preview_base)

    pill_map = {
        "adjusted": ("pill-adjusted", "🎯 Đã chỉnh"),
        "rendered": ("pill-rendered", "✅ Đã render (Gốc)"),
        "source":   ("pill-source",   "📷 Ảnh nguồn"),
    }
    pill_class, pill_label = pill_map.get(display_status, pill_map["source"])
    pill_html = f"<span class='studio-status-pill {pill_class}'>{pill_label}</span>"

    # Đọc giá trị hiện tại từ widget (hoặc store nếu widget chưa render)
    cur_scale = int(st.session_state.get(wsk,   _aget(iid, "scale", 100)))
    cur_x     = int(st.session_state.get(wxk,   _aget(iid, "x",     0)))
    cur_y     = int(st.session_state.get(wyk,   _aget(iid, "y",     0)))

    with st.container(border=True):
        # ── Header: checkbox + cảnh báo ảnh nhỏ ──────────────────
        hdr_cb, hdr_warn = st.columns([3, 2])
        with hdr_cb:
            st.checkbox(
                "✏️ Cần sửa ảnh này",
                key=wselk,
                on_change=_sync_widget_to_store, args=(iid, "sel", wselk),
            )
        with hdr_warn:
            if small_warn:
                st.markdown(
                    "<span style='color:#f87171;font-size:0.95rem;font-weight:700'>"
                    "⚠️ ẢNH NHỎ — DỄ BỊ GIÃN</span>",
                    unsafe_allow_html=True,
                )

        # ── 2 cột: preview trái | điều chỉnh phải ─────────────────
        left_col, right_col = st.columns([1.05, 1.6])

        with left_col:
            live_html = _live_preview_html(
                image_b64=image_b64,
                target_w=main_target_w, target_h=main_target_h,
                scale_pct=cur_scale,
                offset_x_pct=cur_x,
                offset_y_pct=cur_y,
                status_pill_html=pill_html,
            )
            st.markdown(live_html, unsafe_allow_html=True)
            st.markdown(
                f"<div class='preview-meta'>"
                f"📐 <b>{item.get('source_width',0)}×{item.get('source_height',0)}</b>"
                f" · 💾 {readable_file_size(item.get('source_size_bytes',0))}"
                f" · 🎯 Canvas <b>{main_target_w}×{main_target_h}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with right_col:
            st.markdown(
                f"<div class='studio-img-title'>"
                f"<b>{item.get('product', '-')}</b>"
                f"&nbsp;·&nbsp;<span style='color:#a78bfa'>"
                f"{item.get('color', '-')}</span><br>"
                f"<code>{item.get('original_name', '-')}</code>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # ── Sliders ───────────────────────────────────────────
            sc, xc, yc = st.columns(3)
            with sc:
                st.slider(
                    "Scale (%)", 60, 200, step=1,
                    key=wsk,
                    on_change=_sync_widget_to_store, args=(iid, "scale", wsk),
                )
            with xc:
                st.slider(
                    "Lệch X", -100, 100, step=1,
                    key=wxk,
                    on_change=_sync_widget_to_store, args=(iid, "x", wxk),
                )
            with yc:
                st.slider(
                    "Lệch Y", -100, 100, step=1,
                    key=wyk,
                    on_change=_sync_widget_to_store, args=(iid, "y", wyk),
                )

            # ── Nút điều chỉnh nhanh ─────────────────────────────
            rb1, rb2, rb3 = st.columns(3)
            with rb1:
                if st.button("↺ Reset", key=f"reset_{iid}",
                             use_container_width=True):
                    _aset(iid,
                          scale=int(item.get("default_scale_pct",
                                             cfg.get("default_scale_pct", 100))),
                          x=0, y=0, sel=True)
                    _invalidate_wkeys(iid)
                    st.rerun()
            with rb2:
                if st.button("➖ Thu nhỏ 5%", key=f"minus_{iid}",
                             use_container_width=True):
                    new_s = max(60, _aget(iid, "scale", 100) - 5)
                    _aset(iid, scale=new_s, sel=True)
                    _invalidate_wkeys(iid)
                    st.rerun()
            with rb3:
                if st.button("➕ Phóng 5%", key=f"plus_{iid}",
                             use_container_width=True):
                    new_s = min(200, _aget(iid, "scale", 100) + 5)
                    _aset(iid, scale=new_s, sel=True)
                    _invalidate_wkeys(iid)
                    st.rerun()

            # ── Tải từng tấm ──────────────────────────────────────
            st.markdown(
                "<hr style='margin:10px 0;border-color:rgba(139,92,246,0.15);'>",
                unsafe_allow_html=True,
            )
            if display_path and Path(display_path).exists():
                try:
                    with open(display_path, "rb") as fh:
                        fbytes = fh.read()
                    st.download_button(
                        label="📥 TẢI TẤM NÀY",
                        data=fbytes,
                        file_name=Path(display_path).name,
                        mime="image/jpeg",
                        use_container_width=True,
                        type="primary" if display_status == "adjusted" else "secondary",
                        key=f"dl_single_{iid}",
                    )
                except Exception:
                    pass


# ══════════════════════════════════════════════════════════════════════
# MAIN STUDIO
# ══════════════════════════════════════════════════════════════════════

def render_adjustment_studio():
    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2 style='font-size:1.25rem !important'>🎚 Studio Scale v9.8</h2>"
        "<p style='font-size:0.95rem !important;line-height:1.65 !important'>"
        "<b>Fix v9.8</b>: Điều chỉnh trang 1 → bấm <b>💾 LƯU TRANG NÀY</b> → sang trang 2 → "
        "LƯU → Render sẽ đọc đúng thông số tất cả trang. "
        "Giá trị được lưu vào kho bền vững <code>_adj_values</code> — "
        "không bao giờ bị Streamlit xóa dù chuyển trang bao nhiêu lần."
        "</p></div>",
        unsafe_allow_html=True,
    )

    manifest = st.session_state.get("last_batch_manifest", [])
    cfg      = st.session_state.get("last_batch_cfg",      {})
    meta     = st.session_state.get("last_batch_meta",     {})

    if not manifest:
        st.info("⚠️ Chưa có batch. Hãy chạy ở tab Web, Drive hoặc Local ZIP trước.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── INIT: Khởi tạo _adj_values cho TẤT CẢ manifest ngay đầu hàm ──
    # Đảm bảo mọi item đều có entry → selected_items & filter đọc được.
    for _item in manifest:
        _ensure_default_state(_item, cfg)

    render_batch_kpis(meta)

    total          = len(manifest)
    selected_count = sum(1 for it in manifest if _aget(it["id"], "sel", False))
    small_count    = sum(1 for it in manifest if _is_small_image(it))
    saved_pages    = st.session_state.get("_studio_saved_pages", set())

    st.markdown(
        f"<div class='guide-box'>"
        f"<b>Batch:</b> {meta.get('batch_id', '-')} &nbsp;·&nbsp; "
        f"<b>Tổng ảnh:</b> {total} &nbsp;·&nbsp; "
        f"<b>Đã chọn sửa:</b> "
        f"<span style='color:#fbbf24;font-weight:700'>{selected_count}</span>"
        f" &nbsp;·&nbsp; "
        f"<b>Ảnh nhỏ ⚠️:</b> <span style='color:#f87171'>{small_count}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    root         = Path(meta.get("root", "")) if meta.get("root") else None
    final_dir    = (Path(meta.get("final_dir",
                              str((root or Path(".")) / "FINAL")))
                    if root else None)
    adjusted_dir = (Path(st.session_state.get(
                        "_adjusted_root",
                        str((root or Path(".")) / "ADJUSTED")))
                    if root else None)
    sizes_cfg = cfg.get("sizes", [])

    main_target_w, main_target_h = 1020, 680
    if sizes_cfg:
        try:
            tw, th, _m = sizes_cfg[0]
            if tw and th:
                main_target_w, main_target_h = int(tw), int(th)
        except Exception:
            pass

    product_names = sorted({it.get("product", "")
                             for it in manifest if it.get("product")})

    # ══ BỘ LỌC + CHẾ ĐỘ XEM ════════════════════════════════════════
    r1, r2, r3, r4 = st.columns([1.5, 1.3, 1.5, 1.2])
    with r1:
        keyword = st.text_input(
            "🔍 Tìm nhanh", placeholder="Tên ảnh, màu...", key="adj_kw"
        )
    with r2:
        product_filter = st.selectbox(
            "Lọc SP", ["Tất cả", *product_names], key="adj_pf"
        )
    with r3:
        status_filter = st.selectbox(
            "Lọc trạng thái",
            ["Tất cả", "Chỉ ảnh đã chọn sửa",
             "Chỉ ảnh chưa chọn", "Chỉ ảnh nhỏ (bị giãn)"],
            key="adj_status",
        )
    with r4:
        view_mode = st.radio(
            "Chế độ xem",
            ["📋 Chi tiết", "🔲 Lưới nhỏ"],
            horizontal=True,
            key="studio_view_mode",
        )

    # Số ảnh/trang theo mode
    if view_mode == "📋 Chi tiết":
        _opts   = [6, 10, 16, 24, 50, 100, 10000]
        _labels = ["6", "10", "16", "24", "50", "100", "Tất cả"]
        _sel    = st.selectbox("Mỗi trang", _labels, index=1, key="adj_pp")
    else:
        _opts   = [20, 40, 60, 100, 200, 10000]
        _labels = ["20", "40", "60", "100", "200", "Tất cả"]
        _sel    = st.selectbox("Mỗi trang (lưới)", _labels, index=1, key="adj_gp")
    per_page = _opts[_labels.index(_sel)]

    filtered = _filtered_items(manifest, keyword, product_filter, status_filter)
    if not filtered:
        st.warning("Không có ảnh phù hợp bộ lọc.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    total_pages = max((len(filtered) - 1) // per_page + 1, 1)

    # ── Điều hướng trang ────────────────────────────────────────────
    nav_l, nav_c, nav_r = st.columns([1, 3, 1])
    with nav_l:
        page_val = st.number_input(
            "Trang", min_value=1, max_value=total_pages,
            value=1, step=1, key="adj_page",
        )
    page = int(page_val)
    with nav_c:
        # Hiển thị trạng thái đã lưu từng trang
        saved_indicator = ""
        if saved_pages:
            saved_indicator = (
                f" &nbsp;·&nbsp; ✅ Đã lưu trang: "
                f"<b style='color:#4ade80'>"
                f"{', '.join(str(p) for p in sorted(saved_pages))}</b>"
            )
        st.markdown(
            f"<div style='padding-top:28px;font-size:0.82rem;color:#94a3b8;'>"
            f"Trang {page}/{total_pages} · {len(filtered)} ảnh · "
            f"Manifest: {total}{saved_indicator}</div>",
            unsafe_allow_html=True,
        )
    with nav_r:
        # Nút prev/next
        pn1, pn2 = st.columns(2)
        with pn1:
            if st.button("◀", key="pg_prev", use_container_width=True,
                         disabled=(page <= 1)):
                st.session_state["adj_page"] = page - 1
                st.rerun()
        with pn2:
            if st.button("▶", key="pg_next", use_container_width=True,
                         disabled=(page >= total_pages)):
                st.session_state["adj_page"] = page + 1
                st.rerun()

    start      = (page - 1) * per_page
    end        = min(start + per_page, len(filtered))
    page_items = filtered[start:end]

    # ══ THAO TÁC HÀNG LOẠT ══════════════════════════════════════════
    st.markdown(
        '<div class="sec-title">🧩 Thao tác hàng loạt</div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        # Hàng 1 — chọn / bỏ chọn
        sb1, sb2, sb3, sb4, sb5 = st.columns(5)
        with sb1:
            if st.button("☑️ Chọn trang này",
                         use_container_width=True, key="adj_sel_page"):
                for it in page_items:
                    _aset(it["id"], sel=True)
                    _invalidate_wkeys(it["id"])
                st.rerun()
        with sb2:
            if st.button("☑️ Chọn TẤT CẢ đã lọc",
                         use_container_width=True, key="adj_sel_all"):
                for it in filtered:
                    _aset(it["id"], sel=True)
                    _invalidate_wkeys(it["id"])
                st.rerun()
        with sb3:
            if st.button("⬜ Bỏ chọn trang",
                         use_container_width=True, key="adj_unsel_page"):
                for it in page_items:
                    _aset(it["id"], sel=False)
                    _invalidate_wkeys(it["id"])
                st.rerun()
        with sb4:
            if st.button("⚠️ Chọn ảnh nhỏ",
                         use_container_width=True, key="adj_sel_small"):
                for it in manifest:
                    if _is_small_image(it):
                        _aset(it["id"], sel=True)
                        _invalidate_wkeys(it["id"])
                st.rerun()
        with sb5:
            if st.button("🧹 Bỏ tất cả",
                         use_container_width=True, key="adj_clear_all"):
                for it in manifest:
                    _aset(it["id"], sel=False)
                    _invalidate_wkeys(it["id"])
                st.rerun()

        # Hàng 2 — sliders bulk
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            bulk_scale = st.slider(
                "Scale (%)", 60, 200,
                int(cfg.get("default_scale_pct", 100)), 1,
                key="bulk_scale",
            )
        with bc2:
            bulk_x = st.slider("Lệch X", -100, 100, 0, 1, key="bulk_x")
        with bc3:
            bulk_y = st.slider("Lệch Y", -100, 100, 0, 1, key="bulk_y")

        # Hàng 3 — áp dụng bulk
        ba1, ba2 = st.columns(2)
        with ba1:
            if st.button("⚡ Áp dụng TRANG này + tích chọn",
                         use_container_width=True, key="adj_bulk_page"):
                _apply_bulk_to_items(page_items, bulk_scale, bulk_x, bulk_y)
                st.rerun()
        with ba2:
            if st.button("⚡⚡ Áp dụng TẤT CẢ đã lọc + tích chọn",
                         use_container_width=True, key="adj_bulk_all"):
                _apply_bulk_to_items(filtered, bulk_scale, bulk_x, bulk_y)
                st.rerun()

    # ══ NÚT LƯU TRANG — trái tim của fix v9.8 ══════════════════════
    # Banner giải thích quy trình
    st.markdown(
        "<div class='save-banner'>"
        "💾 <b>QUAN TRỌNG:</b> Sau khi chỉnh xong trang này, bấm nút "
        "<b>LƯU TRANG NÀY</b> trước khi chuyển sang trang khác. "
        "Thao tác lưu đảm bảo 100% giá trị được giữ nguyên."
        "</div>",
        unsafe_allow_html=True,
    )

    sv1, sv2, sv3 = st.columns([2, 2, 1])
    with sv1:
        page_is_saved = page in saved_pages
        save_label    = (f"✅ Trang {page} đã được lưu"
                         if page_is_saved else
                         f"💾 LƯU TRANG {page} NÀY")
        save_type     = "secondary" if page_is_saved else "primary"
        if st.button(save_label, key="btn_save_page",
                     use_container_width=True, type=save_type):
            n = _save_page_to_store(page_items)
            saved_set = st.session_state.setdefault("_studio_saved_pages", set())
            saved_set.add(page)
            st.success(
                f"✅ Đã lưu {n} ảnh của trang {page} vào kho bền vững! "
                f"Bạn có thể an toàn chuyển sang trang khác."
            )
            st.rerun()
    with sv2:
        if st.button("💾💾 LƯU TẤT CẢ CÁC TRANG",
                     key="btn_save_all_pages", use_container_width=True):
            # Lưu tất cả widget hiện có trong session_state cho toàn manifest
            saved_total = 0
            for it in manifest:
                iid = it["id"]
                wsk, wxk, wyk, wselk = _wkeys(iid)
                updates = {}
                if wsk   in st.session_state: updates["scale"] = int(st.session_state[wsk])
                if wxk   in st.session_state: updates["x"]     = int(st.session_state[wxk])
                if wyk   in st.session_state: updates["y"]     = int(st.session_state[wyk])
                if wselk in st.session_state: updates["sel"]   = bool(st.session_state[wselk])
                if updates:
                    _aset(iid, **updates)
                    saved_total += 1
            saved_set = st.session_state.setdefault("_studio_saved_pages", set())
            saved_set.update(range(1, total_pages + 1))
            st.success(f"✅ Đã lưu {saved_total} ảnh trên tất cả trang!")
            st.rerun()
    with sv3:
        sel_now = sum(1 for it in manifest if _aget(it["id"], "sel", False))
        st.markdown(
            f"<div style='padding-top:10px;text-align:center;"
            f"font-size:0.82rem;color:#fbbf24;font-weight:700;'>"
            f"✏️ Chọn sửa: {sel_now}/{total}</div>",
            unsafe_allow_html=True,
        )

    # ══ HIỂN THỊ ẢNH ════════════════════════════════════════════════
    st.markdown(
        f'<div class="sec-title">🖼 {view_mode} &nbsp;—&nbsp; '
        f'Trang {page}: ảnh {start+1}~{end} / {len(filtered)} &nbsp;|&nbsp; '
        f'<span style="color:#fbbf24">Đã chọn sửa: {sel_now}</span></div>',
        unsafe_allow_html=True,
    )

    # ─── CHI TIẾT (MẶC ĐỊNH) ──────────────────────────────────────
    if view_mode == "📋 Chi tiết":
        for item in page_items:
            _render_detail_row(
                item, final_dir, adjusted_dir, sizes_cfg, cfg,
                main_target_w, main_target_h,
            )

    # ─── LƯỚI NHỎ ─────────────────────────────────────────────────
    else:
        COLS = 4
        rows = [page_items[i : i + COLS] for i in range(0, len(page_items), COLS)]
        for row_items in rows:
            cols = st.columns(COLS)
            for ci, item in enumerate(row_items):
                with cols[ci]:
                    _render_grid_card(
                        item, final_dir, adjusted_dir, sizes_cfg, cfg,
                        main_target_w, main_target_h,
                    )

    # Nút prev/next lần 2 ở dưới (tiện dụng cho list dài)
    bot_l, bot_c, bot_r = st.columns([1, 3, 1])
    with bot_l:
        if st.button("◀ Trang trước", key="pg_prev_bot",
                     use_container_width=True, disabled=(page <= 1)):
            _save_page_to_store(page_items)  # auto-save khi next/prev
            saved_set = st.session_state.setdefault("_studio_saved_pages", set())
            saved_set.add(page)
            st.session_state["adj_page"] = page - 1
            st.rerun()
    with bot_c:
        st.markdown(
            f"<div style='text-align:center;padding-top:10px;"
            f"font-size:0.82rem;color:#64748b;'>"
            f"Trang {page} / {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with bot_r:
        if st.button("Trang sau ▶", key="pg_next_bot",
                     use_container_width=True, disabled=(page >= total_pages)):
            _save_page_to_store(page_items)  # auto-save khi next/prev
            saved_set = st.session_state.setdefault("_studio_saved_pages", set())
            saved_set.add(page)
            st.session_state["adj_page"] = page + 1
            st.rerun()

    # ══ XUẤT FILE & TẢI VỀ ══════════════════════════════════════════
    st.markdown("""
<div class="export-panel">
    <h2 style="margin-top:0;color:#fff;font-size:1.4rem;">
        🚀 BƯỚC CUỐI: XUẤT FILE & TẢI VỀ
    </h2>
    <p style="color:#cbd5e1;font-size:0.95rem;">
        <b>Bước 1</b>: Chỉnh từng trang → bấm <b>💾 LƯU TRANG NÀY</b> cho từng trang.
        &nbsp;<b>Bước 2</b>: Bấm <b>ÁP DỤNG ĐIỀU CHỈNH</b> — render toàn bộ ảnh đã chọn
        (đọc từ kho bền vững, không phụ thuộc trang đang xem).
        &nbsp;<b>Bước 3</b>: Đóng gói ZIP. &nbsp;<b>Bước 4</b>: Tải về.
    </p>
</div>""", unsafe_allow_html=True)

    # selected_items đọc từ _adj_values — TOÀN BỘ manifest
    selected_items = [it for it in manifest if _aget(it["id"], "sel", False)]

    col_step1, col_step2 = st.columns(2)
    with col_step1:
        st.markdown(
            "<h4 style='color:#a78bfa;margin-bottom:5px;'>▶ BƯỚC 1+2: RENDER</h4>",
            unsafe_allow_html=True,
        )
        do_render = st.button(
            f"🎨 ÁP DỤNG ĐIỀU CHỈNH ({len(selected_items)} ảnh đang chọn)",
            type="primary",
            use_container_width=True,
            key="adj_render_selected",
            disabled=(len(selected_items) == 0),
        )
    with col_step2:
        st.markdown(
            "<h4 style='color:#a78bfa;margin-bottom:5px;'>▶ BƯỚC 3: TẠO ZIP GỘP</h4>",
            unsafe_allow_html=True,
        )
        do_export_full = st.button(
            "📦 ĐÓNG GÓI ZIP (Tất cả ảnh đã sửa + chưa sửa)",
            type="primary",
            use_container_width=True,
            key="adj_export_full",
        )

    if do_render or do_export_full:
        if not root or not root.exists():
            st.error("❌ Thư mục batch đã bị xóa. Vui lòng chạy batch mới.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        adjusted_root = root / "ADJUSTED"

        # ── RENDER TẤT CẢ ẢNH ĐÃ CHỌN (toàn bộ manifest, không giới hạn trang) ──
        if selected_items:
            if adjusted_root.exists():
                shutil.rmtree(adjusted_root, ignore_errors=True)
            adjusted_root.mkdir(parents=True, exist_ok=True)

            progress   = st.progress(0)
            status_box = st.empty()
            t0         = time.time()

            for idx, item in enumerate(selected_items, start=1):
                iid    = item["id"]
                status_box.info(
                    f"[{idx}/{len(selected_items)}] "
                    f"Đang xử lý: {item.get('original_name', '-')}"
                )
                # ĐỌC TỪ _adj_values — KHÔNG từ widget key
                settings = {
                    "scale_pct": _aget(iid, "scale", 100),
                    "offset_x":  _aget(iid, "x",     0),
                    "offset_y":  _aget(iid, "y",     0),
                }
                exact_stem = _get_exact_stem_for_item(item, final_dir, sizes_cfg, cfg)
                try:
                    resize_to_multi_sizes(
                        Path(item["source_path"]),
                        adjusted_root,
                        item["folder_name"],
                        exact_stem,
                        cfg.get("sizes", []),
                        scale_pct=int(cfg.get("default_scale_pct", 100)),
                        quality=int(cfg.get("quality", 95)),
                        export_format=cfg.get("export_format", "JPEG (.jpg)"),
                        per_image_settings=settings,
                        huge_image_mode=bool(cfg.get("huge_image_mode", True)),
                    )
                except Exception as exc:
                    status_box.warning(
                        f"⚠️ Lỗi render {item.get('original_name', '-')}: {exc}"
                    )
                progress.progress(idx / max(len(selected_items), 1))

            duration       = time.time() - t0
            adjusted_files = [
                f for f in adjusted_root.rglob("*")
                if f.is_file() and f.stat().st_size > 0
            ]
            status_box.success(f"🎉 Render xong {len(adjusted_files)} ảnh.")

            # Giải phóng RAM sau render nặng
            try:
                gc.collect()
            except Exception:
                pass

            st.session_state.pop("_studio_thumb_b64_cache", None)
            st.session_state["_adjust_render_done"] = True
            st.session_state["_adjusted_root"]      = str(adjusted_root)

            add_to_history(
                "Adjust",
                f"Studio · {len(selected_items)} ảnh",
                len(adjusted_files),
                " + ".join([get_size_label(w, h, m)
                            for w, h, m in cfg.get("sizes", [])]),
                duration,
            )

        # ── TẠO ZIP GỘP ─────────────────────────────────────────────
        if do_export_full:
            final_p    = Path(meta.get("final_dir", str(root / "FINAL")))
            adjusted_p = Path(
                st.session_state.get("_adjusted_root", str(root / "ADJUSTED"))
            )
            if not final_p.exists():
                st.error("❌ Thư mục FINAL gốc không tồn tại.")
            else:
                with st.spinner("Đang gộp ảnh đã chỉnh + ảnh gốc..."):
                    uid        = int(time.time())
                    merged_dir = root / f"MERGED_{uid}"
                    merged_dir.mkdir(parents=True, exist_ok=True)
                    stats    = merge_final_with_adjusted(final_p, adjusted_p,
                                                         merged_dir)
                    zip_path = (root /
                                f"FullExport_{meta.get('batch_id','batch')}_{uid}.zip")
                    make_zip(merged_dir, zip_path,
                             compresslevel=int(cfg.get("zip_compression", 6)))
                    # Không load bytes vào RAM — chỉ lưu đường dẫn
                    st.session_state.adjust_zip_path = str(zip_path)
                st.success(
                    f"📦 ZIP gộp sẵn sàng — "
                    f"Ghi đè: **{stats['overridden']}** ảnh đã sửa | "
                    f"Giữ nguyên: **{stats['kept']}** ảnh gốc."
                )
                try:
                    gc.collect()
                except Exception:
                    pass

        st.rerun()

    # ─── BƯỚC 4: TẢI FILE ZIP ────────────────────────────────────
    st.markdown(
        "<h4 style='color:#a78bfa;margin-top:20px;margin-bottom:5px;'>"
        "▶ BƯỚC 4: TẢI FILE ZIP</h4>",
        unsafe_allow_html=True,
    )
    col_orig, col_merged = st.columns(2)

    with col_orig:
        zip_path_orig = (meta.get("zip_path", "")
                         if isinstance(meta, dict) else "")
        # Fallback: tạo zip gốc nếu chưa có
        if (not zip_path_orig or not Path(zip_path_orig).exists()):
            if root and final_dir and final_dir.exists():
                try:
                    fallback_zip = (
                        root / f"OriginalExport_{meta.get('batch_id','batch')}.zip"
                    )
                    if not fallback_zip.exists():
                        make_zip(final_dir, fallback_zip, compresslevel=6)
                    if fallback_zip.exists():
                        zip_path_orig = str(fallback_zip)
                except Exception:
                    pass

        handle_orig = open_zip_for_download(zip_path_orig)
        if handle_orig:
            try:
                size_text = readable_file_size(
                    Path(zip_path_orig).stat().st_size
                )
                st.download_button(
                    label=f"⬇️ TẢI ZIP GỐC (Ảnh mặc định — {size_text})",
                    data=handle_orig,
                    file_name=Path(zip_path_orig).name,
                    mime="application/zip",
                    use_container_width=True,
                    key="dl_studio_orig_zip",
                )
            finally:
                handle_orig.close()
        else:
            st.info("ZIP gốc chưa có — chạy batch để tạo.")

    with col_merged:
        zip_path_merged = st.session_state.get("adjust_zip_path", "")
        handle_merged   = open_zip_for_download(zip_path_merged)
        if handle_merged:
            try:
                size_text = readable_file_size(
                    Path(zip_path_merged).stat().st_size
                )
                st.download_button(
                    label=f"⬇️ TẢI ZIP GỘP (Đã điều chỉnh — {size_text})",
                    data=handle_merged,
                    file_name=Path(zip_path_merged).name,
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    key="dl_studio_merged_zip",
                )
            finally:
                handle_merged.close()
        else:
            st.info(
                "💡 Bấm [BƯỚC 3: TẠO ZIP GỘP] để phần mềm xuất "
                "và cung cấp file tải về."
            )

    st.markdown("</div>", unsafe_allow_html=True)
