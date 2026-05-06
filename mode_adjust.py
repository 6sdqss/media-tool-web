"""
mode_adjust.py — Studio Scale v9.7 (PERSISTENT STATE + COMPACT GRID)
─────────────────────────────────────────────────────────
FIXED v9.7 — Root cause: Streamlit tự xóa widget keys (adj_scale_xxx,
sel_xxx) khỏi session_state khi widget không được render (chuyển trang).
→ Mọi điều chỉnh ở trang 1 bị mất khi qua trang 2.

GIẢI PHÁP: Dùng một dict DUY NHẤT `_adj_values` trong session_state
(không phải widget key) làm nguồn lưu trữ bền vững:
    st.session_state["_adj_values"][item_id] = {scale, x, y, sel}

Widget keys tạm thời (ws_/wx_/wy_/wsel_) được tái khởi tạo từ
_adj_values mỗi khi re-render. on_change callback đồng bộ ngược lại.
Kết quả: chuyển trang bất kỳ, giá trị KHÔNG bao giờ bị mất.

Giữ NGUYÊN 100% logic resize/export/merge/zip cũ.
"""

from __future__ import annotations

import time
import shutil
import re
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


_SMALL_IMAGE_THRESHOLD = 600
_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ═════════════════════════════════════════════════════════════════════
# CSS
# ═════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
.stButton > button:disabled, .stDownloadButton > button:disabled {
    background: rgba(255,255,255,0.05) !important; color: #64748b !important;
    cursor: not-allowed !important; box-shadow: none !important;
    border: 1px solid rgba(255,255,255,0.1) !important; transform: none !important;
}
.export-panel {
    background: rgba(21,21,31,0.7); border: 1px solid rgba(139,92,246,0.3);
    border-radius: 12px; padding: 20px; margin-top: 10px;
}
.gc-wrap {
    border: 1.5px solid rgba(139,92,246,0.22); border-radius: 9px;
    overflow: hidden; background: rgba(15,15,23,0.9); margin-bottom: 6px;
}
.gc-wrap.gc-sel  { border-color: #fbbf24 !important; box-shadow: 0 0 0 2px rgba(251,191,36,0.22); }
.gc-wrap.gc-warn { border-color: rgba(248,113,113,0.55) !important; }
.gc-thumb        { width:100%; max-height:128px; object-fit:contain; background:#fff; display:block; }
.gc-thumb-empty  { width:100%; height:80px; background:#0f172a; display:flex;
                    align-items:center; justify-content:center;
                    color:#475569; font-size:0.72rem; }
.gc-body  { padding: 5px 7px 4px; }
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
.gc-sw{ color:#f87171; font-size:0.67rem; font-weight:700; margin-top:1px; }
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# PERSISTENT ADJUSTMENT STORE  ← trái tim của fix v9.7
# Lưu trữ bền vững, KHÔNG phụ thuộc widget keys → không bao giờ mất
# khi chuyển trang hay bất kỳ re-render nào.
# ═════════════════════════════════════════════════════════════════════

def _astore() -> dict:
    """Trả về dict trung tâm lưu giá trị điều chỉnh."""
    return st.session_state.setdefault("_adj_values", {})


def _aget(item_id: str, field: str, default=None):
    return _astore().get(item_id, {}).get(field, default)


def _aset(item_id: str, **kwargs):
    store = _astore()
    if item_id not in store:
        store[item_id] = {}
    store[item_id].update(kwargs)


def _ainit(item_id: str, scale: int, sel: bool):
    """Khởi tạo entry nếu chưa có (idempotent)."""
    if item_id not in _astore():
        _aset(item_id, scale=scale, x=0, y=0, sel=sel)


def _sync_adj(item_id: str, field: str, widget_key: str):
    """on_change callback: widget → _adj_values."""
    val = st.session_state.get(widget_key)
    if val is None:
        return
    if field == "sel":
        _aset(item_id, sel=bool(val))
    elif field == "scale":
        _aset(item_id, scale=int(val), sel=True)
    elif field in ("x", "y"):
        _aset(item_id, sel=True, **{field: int(val)})


def _wkeys(item_id: str) -> tuple[str, str, str, str]:
    """Trả về 4 widget keys tạm thời cho item."""
    return (
        f"ws_{item_id}",    # scale slider
        f"wx_{item_id}",    # x slider
        f"wy_{item_id}",    # y slider
        f"wsel_{item_id}",  # sel checkbox
    )


def _init_wkeys(item_id: str):
    """
    Khởi tạo widget keys từ _adj_values NẾU chúng chưa tồn tại
    (Streamlit đã xóa chúng khi widget không được render → chuyển trang).
    """
    wsk, wxk, wyk, wselk = _wkeys(item_id)
    if wsk   not in st.session_state: st.session_state[wsk]   = _aget(item_id, "scale", 100)
    if wxk   not in st.session_state: st.session_state[wxk]   = _aget(item_id, "x", 0)
    if wyk   not in st.session_state: st.session_state[wyk]   = _aget(item_id, "y", 0)
    if wselk not in st.session_state: st.session_state[wselk] = _aget(item_id, "sel", False)


def _clear_wkeys(item_id: str):
    """Xóa widget keys sau khi bulk-apply / reset → widget tái khởi từ store."""
    for k in _wkeys(item_id):
        st.session_state.pop(k, None)


# ═════════════════════════════════════════════════════════════════════
# HELPERS (logic gốc giữ nguyên)
# ═════════════════════════════════════════════════════════════════════

def _get_exact_stem_for_item(item: dict, final_dir: Path, sizes_cfg: list, cfg: dict) -> str:
    folder_name = item.get("folder_name", "")
    seq = int(item.get("seq_in_folder", 1))
    if final_dir and final_dir.exists():
        is_multi  = isinstance(sizes_cfg, list) and len(sizes_cfg) > 1
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
    product_part = re.sub(r"\s+", "_", item.get("product", "image")).strip("_")
    color_part   = re.sub(r"\s+", "_", item.get("color",   "")).strip("_")
    return apply_name_template(
        cfg.get("template", "{name}_{nn}"),
        name=product_part, color=color_part,
        index=seq, original=item.get("original_name", ""),
    )


def _get_exact_display_path(item: dict, final_dir: Path, adjusted_dir: Path,
                             sizes_cfg: list, cfg: dict):
    exact_stem = _get_exact_stem_for_item(item, final_dir, sizes_cfg, cfg)
    is_multi   = isinstance(sizes_cfg, list) and len(sizes_cfg) > 1
    size_label = ""
    if sizes_cfg:
        try:
            w, h, m = sizes_cfg[0]; size_label = get_size_label(w, h, m)
        except Exception:
            pass
    folder_name = item.get("folder_name", "")

    if adjusted_dir and adjusted_dir.exists():
        d = adjusted_dir / size_label / folder_name if (is_multi and size_label) else adjusted_dir / folder_name
        if d.exists():
            for ext in _IMG_EXT:
                p = d / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "adjusted"

    if final_dir and final_dir.exists():
        d = final_dir / size_label / folder_name if (is_multi and size_label) else final_dir / folder_name
        if d.exists():
            for ext in _IMG_EXT:
                p = d / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "rendered"

    fallback = item.get("preview_path") or item.get("source_path") or ""
    return fallback, "source"


def _filtered_items(items, keyword, product_filter, status_filter):
    keyword = (keyword or "").strip().lower()
    output  = []
    for item in items:
        haystack = " ".join([
            item.get("product", ""), item.get("color", ""),
            item.get("original_name", ""), item.get("folder_name", ""),
        ]).lower()
        if product_filter and product_filter != "Tất cả" and item.get("product") != product_filter:
            continue
        if keyword and keyword not in haystack:
            continue
        is_sel = _aget(item["id"], "sel", False)
        if status_filter == "Chỉ ảnh đã chọn sửa" and not is_sel: continue
        if status_filter == "Chỉ ảnh chưa chọn"   and is_sel:     continue
        if status_filter == "Chỉ ảnh nhỏ (bị giãn)":
            w = int(item.get("source_width",  0))
            h = int(item.get("source_height", 0))
            if w >= _SMALL_IMAGE_THRESHOLD and h >= _SMALL_IMAGE_THRESHOLD:
                continue
        output.append(item)
    return output


def _apply_bulk_to_items(target_items, scale_value, x_value, y_value, also_select=True):
    for item in target_items:
        iid = item["id"]
        _aset(iid, scale=int(scale_value), x=int(x_value), y=int(y_value))
        if also_select:
            _aset(iid, sel=True)
        _clear_wkeys(iid)  # buộc widget tái khởi từ store khi render lại


def _is_small_image(item) -> bool:
    w = int(item.get("source_width",  0))
    h = int(item.get("source_height", 0))
    return (0 < w < _SMALL_IMAGE_THRESHOLD) or (0 < h < _SMALL_IMAGE_THRESHOLD)


def _ensure_default_state(item: dict, cfg: dict):
    """Khởi tạo _adj_values cho item nếu chưa có (idempotent)."""
    iid = item["id"]
    if iid in _astore():
        return  # đã có, không ghi đè
    sizes    = cfg.get("sizes", [])
    tgt_w = tgt_h = 0
    if sizes:
        try:
            tw, th, _m = sizes[0]; tgt_w, tgt_h = int(tw or 0), int(th or 0)
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


def _live_preview_html(image_b64: str, target_w: int, target_h: int,
                       scale_pct: int, offset_x_pct: int, offset_y_pct: int,
                       status_pill_html: str, status_label: str) -> str:
    if not image_b64:
        return "<div class='live-frame live-frame--empty'><span>⚠️ Không tìm thấy ảnh.</span></div>"
    factor = max(60, min(200, int(scale_pct))) / 100.0
    tx     = max(-100, min(100, int(offset_x_pct))) * 0.5
    ty     = max(-100, min(100, int(offset_y_pct))) * 0.5
    aspect = f"{int(target_w)} / {int(target_h)}" if target_w and target_h else "3 / 2"
    return (
        f"<div class='live-frame' style='aspect-ratio:{aspect};overflow:hidden;position:relative;"
        f"background:#fff;border-radius:8px;border:1px solid rgba(139,92,246,0.3);"
        f"box-shadow:0 4px 6px rgba(0,0,0,0.1);'>"
        f"  <div class='live-canvas' style='position:absolute;inset:0;display:flex;"
        f"       align-items:center;justify-content:center;'>"
        f"    <img src='{image_b64}' style='max-width:100%;max-height:100%;object-fit:contain;"
        f"         transform:translate({tx:.1f}%,{ty:.1f}%) scale({factor:.3f});"
        f"         transition:transform 0.1s ease-out;' alt=''/>"
        f"  </div>"
        f"  <div style='position:absolute;top:10px;left:10px;z-index:10;'>{status_pill_html}</div>"
        f"  <div style='position:absolute;bottom:10px;left:10px;right:10px;display:flex;"
        f"       justify-content:space-between;background:rgba(15,23,42,0.75);padding:6px 12px;"
        f"       border-radius:6px;font-size:0.85rem;color:#fff;z-index:10;backdrop-filter:blur(4px);'>"
        f"    <span>🔍 Scale:<b>{int(scale_pct)}%</b></span>"
        f"    <span>↔️ X:<b>{int(offset_x_pct):+d}</b></span>"
        f"    <span>↕️ Y:<b>{int(offset_y_pct):+d}</b></span>"
        f"  </div>"
        f"</div>"
    )


# ═════════════════════════════════════════════════════════════════════
# COMPACT GRID CARD
# ═════════════════════════════════════════════════════════════════════
def _render_grid_card(item: dict, final_dir, adjusted_dir,
                      sizes_cfg, cfg, main_target_w: int, main_target_h: int):
    iid       = item["id"]
    scale_val = _aget(iid, "scale", 100)
    x_val     = _aget(iid, "x",     0)
    y_val     = _aget(iid, "y",     0)
    is_sel    = _aget(iid, "sel",   False)
    small_w   = _is_small_image(item)

    display_path, display_status = _get_exact_display_path(
        item, final_dir, adjusted_dir, sizes_cfg, cfg
    )
    source_path  = str(item.get("source_path", ""))
    preview_base = source_path if (source_path and Path(source_path).exists()) else display_path
    image_b64    = build_live_preview_b64(preview_base, max_size=200)

    _status_cls = {"adjusted": "gc-sa", "rendered": "gc-sr", "source": "gc-ss"}
    _status_ico = {"adjusted": "🎯",    "rendered": "✅",     "source": "📷"}
    _status_lbl = {"adjusted": "Đã chỉnh", "rendered": "Đã render", "source": "Ảnh nguồn"}

    s_cls = _status_cls.get(display_status, "gc-ss")
    s_ico = _status_ico.get(display_status, "📷")
    s_lbl = _status_lbl.get(display_status, "Ảnh nguồn")

    border_cls = "gc-sel" if is_sel else ("gc-warn" if small_w else "")
    name_short = (item.get("product") or "-")[:22]
    orig_short = (item.get("original_name") or "-")[:22]

    img_html = (
        f"<img class='gc-thumb' src='{image_b64}' alt=''/>"
        if image_b64 else
        "<div class='gc-thumb-empty'>Không có ảnh</div>"
    )
    warn_txt = "&nbsp;⚠️" if small_w else ""

    st.markdown(f"""
<div class='gc-wrap {border_cls}'>
    {img_html}
    <div class='gc-body'>
        <div class='gc-name'>{s_ico} {name_short}{warn_txt}</div>
        <div class='gc-sub'>{orig_short}</div>
        <div class='gc-vals'>
            <span class='gc-s'>S:{scale_val}%</span>
            <span class='gc-x'>X:{x_val:+d}</span>
            <span class='gc-y'>Y:{y_val:+d}</span>
        </div>
        <div class='{s_cls}'>{s_lbl}</div>
    </div>
</div>""", unsafe_allow_html=True)

    # Checkbox — dùng wsel_ key, sync → _adj_values
    _, _, _, wselk = _wkeys(iid)
    if wselk not in st.session_state:
        st.session_state[wselk] = is_sel
    st.checkbox("✏️ Chọn", key=wselk,
                on_change=_sync_adj, args=(iid, "sel", wselk))

    # Nút ±5% / Reset (trực tiếp cập nhật _adj_values, xóa widget key)
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("−5%", key=f"gm_{iid}", use_container_width=True):
            _aset(iid, scale=max(60, int(scale_val) - 5), sel=True)
            _clear_wkeys(iid)
            st.rerun()
    with b2:
        if st.button("↺", key=f"gr_{iid}", use_container_width=True):
            _aset(iid, scale=int(item.get("default_scale_pct",
                                          cfg.get("default_scale_pct", 100))),
                  x=0, y=0)
            _clear_wkeys(iid)
            st.rerun()
    with b3:
        if st.button("+5%", key=f"gp_{iid}", use_container_width=True):
            _aset(iid, scale=min(200, int(scale_val) + 5), sel=True)
            _clear_wkeys(iid)
            st.rerun()

    # Tải ảnh đã render (nếu có)
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


# ═════════════════════════════════════════════════════════════════════
# MAIN STUDIO
# ═════════════════════════════════════════════════════════════════════
def render_adjustment_studio():
    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2 style='font-size:1.25rem !important'>🎚 Studio Scale v9.7</h2>"
        "<p style='font-size:0.95rem !important;line-height:1.65 !important'>"
        "<b>Fix v9.7</b>: Điều chỉnh trang 1 KHÔNG bị mất khi sang trang 2/3. "
        "Lưu bền vững trong <code>_adj_values</code> — hoàn toàn độc lập với pagination. "
        "Lưới nhỏ: 4 cột, xem 40–60 ảnh cùng lúc. Chi tiết: slider live-preview."
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

    # ── INIT TẤT CẢ MANIFEST vào _adj_values (idempotent) ──
    for _item in manifest:
        _ensure_default_state(_item, cfg)

    render_batch_kpis(meta)

    total          = len(manifest)
    selected_count = sum(1 for it in manifest if _aget(it["id"], "sel", False))
    small_count    = sum(1 for it in manifest if _is_small_image(it))

    st.markdown(
        f"<div class='guide-box'>"
        f"<b>Batch:</b> {meta.get('batch_id', '-')} &nbsp;·&nbsp; "
        f"<b>Tổng ảnh:</b> {total} &nbsp;·&nbsp; "
        f"<b>Đã chọn sửa:</b> <span style='color:#fbbf24;font-weight:700'>{selected_count}</span>"
        f" &nbsp;·&nbsp; "
        f"<b>Ảnh nhỏ ⚠️:</b> <span style='color:#f87171'>{small_count}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    root         = Path(meta.get("root", ""))        if meta.get("root")      else None
    final_dir    = Path(meta.get("final_dir", str((root or Path(".")) / "FINAL"))) if root else None
    adjusted_dir = Path(st.session_state.get(
        "_adjusted_root", str((root or Path(".")) / "ADJUSTED"))) if root else None
    sizes_cfg    = cfg.get("sizes", [])

    main_target_w, main_target_h = 1020, 680
    if sizes_cfg:
        try:
            tw, th, _m = sizes_cfg[0]
            if tw and th:
                main_target_w, main_target_h = int(tw), int(th)
        except Exception:
            pass

    product_names = sorted({it.get("product", "") for it in manifest if it.get("product")})

    # ═══ BỘ LỌC + CHẾ ĐỘ XEM ═══════════════════════════════════════
    r1, r2, r3, r4 = st.columns([1.5, 1.3, 1.5, 1.2])
    with r1:
        keyword = st.text_input("🔍 Tìm nhanh", placeholder="Tên ảnh, màu...", key="adj_kw")
    with r2:
        product_filter = st.selectbox("Lọc SP", ["Tất cả", *product_names], key="adj_pf")
    with r3:
        status_filter = st.selectbox(
            "Lọc trạng thái",
            ["Tất cả", "Chỉ ảnh đã chọn sửa", "Chỉ ảnh chưa chọn", "Chỉ ảnh nhỏ (bị giãn)"],
            key="adj_status",
        )
    with r4:
        view_mode = st.radio(
            "Chế độ xem",
            ["🔲 Lưới nhỏ", "📋 Chi tiết"],
            horizontal=True,
            key="studio_view_mode",
        )

    # Số ảnh mỗi trang
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
    pc, ic = st.columns([1, 4])
    with pc:
        page = st.number_input(
            "Trang", min_value=1, max_value=total_pages, value=1, step=1, key="adj_page"
        )
    with ic:
        st.markdown(
            f"<div style='padding-top:28px;font-size:0.82rem;color:#94a3b8;'>"
            f"Trang {int(page)}/{total_pages} · {len(filtered)} ảnh khớp · Manifest: {total}"
            f"</div>",
            unsafe_allow_html=True,
        )

    start      = (int(page) - 1) * per_page
    end        = min(start + per_page, len(filtered))
    page_items = filtered[start:end]

    # ═══ THAO TÁC HÀNG LOẠT ════════════════════════════════════════
    st.markdown('<div class="sec-title">🧩 Thao tác hàng loạt</div>', unsafe_allow_html=True)
    with st.container(border=True):
        s1, s2, s3, s4, s5 = st.columns(5)
        with s1:
            if st.button("☑️ Chọn trang này", use_container_width=True, key="adj_sel_page"):
                for it in page_items:
                    _aset(it["id"], sel=True); _clear_wkeys(it["id"])
                st.rerun()
        with s2:
            if st.button("☑️ Chọn TẤT CẢ đã lọc", use_container_width=True, key="adj_sel_all"):
                for it in filtered:
                    _aset(it["id"], sel=True); _clear_wkeys(it["id"])
                st.rerun()
        with s3:
            if st.button("⬜ Bỏ chọn trang", use_container_width=True, key="adj_unsel_page"):
                for it in page_items:
                    _aset(it["id"], sel=False); _clear_wkeys(it["id"])
                st.rerun()
        with s4:
            if st.button("⚠️ Chọn ảnh nhỏ", use_container_width=True, key="adj_sel_small"):
                for it in manifest:
                    if _is_small_image(it):
                        _aset(it["id"], sel=True); _clear_wkeys(it["id"])
                st.rerun()
        with s5:
            if st.button("🧹 Bỏ tất cả", use_container_width=True, key="adj_clear_all"):
                for it in manifest:
                    _aset(it["id"], sel=False); _clear_wkeys(it["id"])
                st.rerun()

        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            bulk_scale = st.slider(
                "Scale (%)", 60, 200,
                int(cfg.get("default_scale_pct", 100)), 1, key="bulk_scale"
            )
        with bc2:
            bulk_x = st.slider("Lệch X", -100, 100, 0, 1, key="bulk_x")
        with bc3:
            bulk_y = st.slider("Lệch Y", -100, 100, 0, 1, key="bulk_y")

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

    # ═══ HIỂN THỊ ẢNH ═══════════════════════════════════════════════
    _sel_now = sum(1 for it in manifest if _aget(it["id"], "sel", False))
    st.markdown(
        f'<div class="sec-title">🖼 {view_mode} &nbsp;—&nbsp; '
        f'Trang {int(page)}: {len(page_items)} ảnh ({start+1}~{end}/{len(filtered)}) &nbsp;|&nbsp; '
        f'<span style="color:#fbbf24">Đã chọn sửa: {_sel_now} / {total}</span></div>',
        unsafe_allow_html=True,
    )

    # ─── LƯỚI NHỎ ─────────────────────────────────────────────────
    if view_mode == "🔲 Lưới nhỏ":
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

    # ─── CHI TIẾT ─────────────────────────────────────────────────
    else:
        for item in page_items:
            iid = item["id"]
            # Khởi tạo widget keys từ _adj_values (tái khởi sau chuyển trang)
            _init_wkeys(iid)
            wsk, wxk, wyk, wselk = _wkeys(iid)

            small_warn   = _is_small_image(item)
            display_path, display_status = _get_exact_display_path(
                item, final_dir, adjusted_dir, sizes_cfg, cfg
            )
            source_path  = str(item.get("source_path", ""))
            preview_base = source_path if (source_path and Path(source_path).exists()) else display_path
            image_b64    = build_live_preview_b64(preview_base)

            pill_map = {
                "adjusted": ("pill-adjusted", "🎯 Đã chỉnh"),
                "rendered": ("pill-rendered", "✅ Đã render (Gốc)"),
                "source":   ("pill-source",   "📷 Ảnh nguồn"),
            }
            pill_class, pill_label = pill_map.get(display_status, pill_map["source"])
            pill_html = f"<span class='studio-status-pill {pill_class}'>{pill_label}</span>"

            with st.container(border=True):
                top_cb, top_warn = st.columns([3, 2])
                with top_cb:
                    st.checkbox(
                        "✏️ Cần sửa ảnh này",
                        key=wselk,
                        on_change=_sync_adj, args=(iid, "sel", wselk),
                    )
                with top_warn:
                    if small_warn:
                        st.markdown(
                            "<span style='color:#f87171;font-size:0.95rem;font-weight:700'>"
                            "⚠️ ẢNH NHỎ — DỄ BỊ GIÃN</span>",
                            unsafe_allow_html=True,
                        )

                left_col, right_col = st.columns([1.05, 1.6])

                with left_col:
                    live_html = _live_preview_html(
                        image_b64=image_b64,
                        target_w=main_target_w,  target_h=main_target_h,
                        scale_pct=st.session_state.get(wsk, 100),
                        offset_x_pct=st.session_state.get(wxk, 0),
                        offset_y_pct=st.session_state.get(wyk, 0),
                        status_pill_html=pill_html, status_label=pill_label,
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
                        f"<b>{item.get('product','-')}</b>"
                        f" · <span style='color:#a78bfa'>{item.get('color','-')}</span><br>"
                        f"<code>{item.get('original_name','-')}</code>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    sc, xc, yc = st.columns(3)
                    with sc:
                        st.slider(
                            "Scale (%)", 60, 200, step=1,
                            key=wsk,
                            on_change=_sync_adj, args=(iid, "scale", wsk),
                        )
                    with xc:
                        st.slider(
                            "Lệch X", -100, 100, step=1,
                            key=wxk,
                            on_change=_sync_adj, args=(iid, "x", wxk),
                        )
                    with yc:
                        st.slider(
                            "Lệch Y", -100, 100, step=1,
                            key=wyk,
                            on_change=_sync_adj, args=(iid, "y", wyk),
                        )

                    rb1, rb2, rb3 = st.columns(3)
                    with rb1:
                        if st.button("↺ Reset", key=f"reset_{iid}", use_container_width=True):
                            _aset(iid,
                                  scale=int(item.get("default_scale_pct",
                                                     cfg.get("default_scale_pct", 100))),
                                  x=0, y=0, sel=True)
                            _clear_wkeys(iid)
                            st.rerun()
                    with rb2:
                        if st.button("➖ Thu nhỏ 5%", key=f"minus_{iid}", use_container_width=True):
                            _aset(iid,
                                  scale=max(60, _aget(iid, "scale", 100) - 5),
                                  sel=True)
                            _clear_wkeys(iid)
                            st.rerun()
                    with rb3:
                        if st.button("➕ Phóng 5%", key=f"plus_{iid}", use_container_width=True):
                            _aset(iid,
                                  scale=min(200, _aget(iid, "scale", 100) + 5),
                                  sel=True)
                            _clear_wkeys(iid)
                            st.rerun()

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

    # ═══ XUẤT FILE ══════════════════════════════════════════════════
    st.markdown("""
<div class="export-panel">
    <h2 style="margin-top:0;color:#fff;font-size:1.4rem;">🚀 BƯỚC CUỐI: XUẤT FILE & TẢI VỀ</h2>
    <p style="color:#cbd5e1;font-size:0.95rem;">
        <b>Bước 1</b>: Render → áp dụng toàn bộ ảnh đã tích chọn (từ mọi trang, không giới hạn).
        <b>Bước 2</b>: Đóng gói ZIP gộp (ảnh đã sửa ghi đè gốc).
        <b>Bước 3</b>: Tải về.
    </p>
</div>""", unsafe_allow_html=True)

    # Đọc từ _adj_values — TOÀN BỘ manifest, không phụ thuộc trang
    selected_items = [it for it in manifest if _aget(it["id"], "sel", False)]

    col_step1, col_step2 = st.columns(2)
    with col_step1:
        st.markdown(
            "<h4 style='color:#a78bfa;margin-bottom:5px;'>▶ BƯỚC 1: RENDER</h4>",
            unsafe_allow_html=True,
        )
        do_render = st.button(
            f"🎨 ÁP DỤNG ĐIỀU CHỈNH ({len(selected_items)} ảnh đang chọn)",
            type="primary", use_container_width=True,
            key="adj_render_selected",
            disabled=(len(selected_items) == 0),
        )
    with col_step2:
        st.markdown(
            "<h4 style='color:#a78bfa;margin-bottom:5px;'>▶ BƯỚC 2: TẠO ZIP GỘP</h4>",
            unsafe_allow_html=True,
        )
        do_export_full = st.button(
            "📦 ĐÓNG GÓI ZIP (Tất cả ảnh đã sửa + chưa sửa)",
            type="primary", use_container_width=True,
            key="adj_export_full",
        )

    if do_render or do_export_full:
        if not root or not root.exists():
            st.error("❌ Thư mục batch đã bị xóa. Vui lòng chạy batch mới.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        adjusted_root = root / "ADJUSTED"

        # --- RENDER TẤT CẢ ẢNH ĐƯỢC CHỌN (toàn manifest) ---
        if selected_items:
            if adjusted_root.exists():
                shutil.rmtree(adjusted_root, ignore_errors=True)
            adjusted_root.mkdir(parents=True, exist_ok=True)

            progress   = st.progress(0)
            status     = st.empty()
            start_time = time.time()

            for idx, item in enumerate(selected_items, start=1):
                iid = item["id"]
                status.info(f"[{idx}/{len(selected_items)}] {item.get('original_name', '-')}")
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
                    status.warning(f"⚠️ Lỗi render {item.get('original_name','-')}: {exc}")
                progress.progress(idx / max(len(selected_items), 1))

            duration       = time.time() - start_time
            adjusted_files = [
                f for f in adjusted_root.rglob("*")
                if f.is_file() and f.stat().st_size > 0
            ]
            status.success(f"🎉 Render xong {len(adjusted_files)} ảnh.")
            st.session_state.pop("_studio_thumb_b64_cache", None)
            st.session_state["_adjust_render_done"] = True
            st.session_state["_adjusted_root"]      = str(adjusted_root)
            add_to_history(
                "Adjust", f"Studio · {len(selected_items)} ảnh", len(adjusted_files),
                " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])]),
                duration,
            )

        # --- TẠO ZIP GỘP ---
        if do_export_full:
            final_p    = Path(meta.get("final_dir", str(root / "FINAL")))
            adjusted_p = Path(st.session_state.get("_adjusted_root", str(root / "ADJUSTED")))
            if not final_p.exists():
                st.error("❌ Thư mục FINAL gốc không tồn tại.")
            else:
                with st.spinner("Đang gộp ảnh đã chỉnh + ảnh gốc..."):
                    uid        = int(time.time())
                    merged_dir = root / f"MERGED_{uid}"
                    merged_dir.mkdir(parents=True, exist_ok=True)
                    stats    = merge_final_with_adjusted(final_p, adjusted_p, merged_dir)
                    zip_path = root / f"FullExport_{meta.get('batch_id','batch')}_{uid}.zip"
                    make_zip(merged_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))
                st.session_state.adjust_zip_path = str(zip_path)
                st.success(
                    f"📦 ZIP gộp sẵn sàng — "
                    f"Ghi đè: **{stats['overridden']}** | Giữ nguyên: **{stats['kept']}**"
                )

        st.rerun()

    # ─── BƯỚC 3: TẢI FILE ────────────────────────────────────────
    st.markdown(
        "<h4 style='color:#a78bfa;margin-top:20px;margin-bottom:5px;'>"
        "▶ BƯỚC 3: TẢI FILE ZIP</h4>",
        unsafe_allow_html=True,
    )
    col_orig, col_merged = st.columns(2)

    with col_orig:
        zip_path_orig = meta.get("zip_path", "") if isinstance(meta, dict) else ""
        if (not zip_path_orig or not Path(zip_path_orig).exists()) and root and final_dir and final_dir.exists():
            try:
                fallback_zip = root / f"OriginalExport_{meta.get('batch_id','batch')}.zip"
                if not fallback_zip.exists():
                    make_zip(final_dir, fallback_zip, compresslevel=6)
                if fallback_zip.exists():
                    zip_path_orig = str(fallback_zip)
            except Exception:
                pass
        handle_orig = open_zip_for_download(zip_path_orig)
        if handle_orig:
            try:
                size_text = readable_file_size(Path(zip_path_orig).stat().st_size)
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

    with col_merged:
        zip_path_merged = st.session_state.get("adjust_zip_path", "")
        handle_merged   = open_zip_for_download(zip_path_merged)
        if handle_merged:
            try:
                size_text = readable_file_size(Path(zip_path_merged).stat().st_size)
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
            st.info("💡 Bấm [BƯỚC 2: TẠO ZIP GỘP] để phần mềm xuất và cung cấp file tải về.")

    st.markdown("</div>", unsafe_allow_html=True)
