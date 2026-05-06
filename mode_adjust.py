"""
mode_adjust.py — Studio Scale v9.3.2 (CACHE & RENDER FIX)
─────────────────────────────────────────────────────────
- Tự động check "Cần sửa ảnh này" khi kéo slider.
- FIX: Trình duyệt lưu cache file ZIP cũ -> Đổi tên file ZIP bằng timestamp mỗi lần xuất.
- FIX: Nút disable sẽ hiển thị màu xám rõ ràng.
- Đảm bảo ghi đè chính xác (Exact Stem) 100% khớp với file xuất từ các tab trước.
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
    show_preview,
)


_SMALL_IMAGE_THRESHOLD = 600
_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ═════════════════════════════════════════════════════════════════════
# CSS FIX (Sửa lỗi nút Disable vẫn hiện màu tím)
# ═════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
.stButton > button:disabled, .stDownloadButton > button:disabled {
    background: rgba(255, 255, 255, 0.05) !important;
    color: #64748b !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    transform: none !important;
}
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════
def _get_exact_stem_for_item(item: dict, manifest: list, cfg: dict) -> str:
    """Tái tạo chính xác tên file đã được đổi tên theo template để ghi đè đúng ảnh."""
    folder_items = [it for it in manifest if it.get("folder_name") == item.get("folder_name")]
    folder_items.sort(key=lambda x: str(x.get("original_name", "")))
    
    true_idx = 1
    for i, it in enumerate(folder_items):
        if it["id"] == item["id"]:
            true_idx = i + 1
            break
            
    folder_parts = [p for p in Path(item.get("folder_name", "")).parts if p]
    product_part = folder_parts[0] if len(folder_parts) >= 1 else "image"
    color_part = folder_parts[1] if len(folder_parts) >= 2 else ""
    product_part = re.sub(r"\s+", "_", product_part).strip("_")
    color_part = re.sub(r"\s+", "_", color_part).strip("_")

    return apply_name_template(
        cfg.get("template", "{name}_{nn}"),
        name=product_part,
        color=color_part,
        index=true_idx,
        original=item.get("original_name", "")
    )


def _get_exact_display_path(item: dict, exact_stem: str, final_dir: Path, adjusted_dir: Path, sizes_cfg: list):
    """Tìm đúng file đã render (ADJUSTED hoặc FINAL) dựa trên exact_stem."""
    is_multi = isinstance(sizes_cfg, list) and len(sizes_cfg) > 1
    size_label = ""
    if sizes_cfg:
        try:
            w, h, m = sizes_cfg[0]
            size_label = get_size_label(w, h, m)
        except Exception:
            pass

    folder_name = item.get("folder_name", "")
    
    if adjusted_dir and adjusted_dir.exists():
        check_adj = adjusted_dir / size_label / folder_name if is_multi and size_label else adjusted_dir / folder_name
        if check_adj.exists():
            for ext in _IMG_EXT:
                p = check_adj / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "adjusted"
                    
    if final_dir and final_dir.exists():
        check_fin = final_dir / size_label / folder_name if is_multi and size_label else final_dir / folder_name
        if check_fin.exists():
            for ext in _IMG_EXT:
                p = check_fin / f"{exact_stem}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), "rendered"
                    
    fallback = item.get("preview_path") or item.get("source_path") or ""
    return fallback, "source"


def _filtered_items(items, keyword, product_filter, status_filter):
    keyword = (keyword or "").strip().lower()
    output = []
    for item in items:
        haystack = " ".join([
            item.get("product", ""), item.get("color", ""),
            item.get("original_name", ""), item.get("folder_name", ""),
        ]).lower()
        if product_filter and product_filter != "Tất cả" and item.get("product") != product_filter:
            continue
        if keyword and keyword not in haystack:
            continue

        is_selected = st.session_state.get(f"sel_{item['id']}", False)
        if status_filter == "Chỉ ảnh đã chọn sửa" and not is_selected:
            continue
        if status_filter == "Chỉ ảnh chưa chọn" and is_selected:
            continue
        if status_filter == "Chỉ ảnh nhỏ (bị giãn)":
            w = int(item.get("source_width", 0))
            h = int(item.get("source_height", 0))
            if w >= _SMALL_IMAGE_THRESHOLD and h >= _SMALL_IMAGE_THRESHOLD:
                continue

        output.append(item)
    return output


def _apply_bulk_to_items(target_items, scale_value, x_value, y_value, also_select=True):
    for item in target_items:
        item_id = item["id"]
        st.session_state[f"adj_scale_{item_id}"] = int(scale_value)
        st.session_state[f"adj_x_{item_id}"] = int(x_value)
        st.session_state[f"adj_y_{item_id}"] = int(y_value)
        if also_select:
            st.session_state[f"sel_{item_id}"] = True


def _is_small_image(item) -> bool:
    w = int(item.get("source_width", 0))
    h = int(item.get("source_height", 0))
    return (0 < w < _SMALL_IMAGE_THRESHOLD) or (0 < h < _SMALL_IMAGE_THRESHOLD)


def _live_preview_html(image_b64: str, target_w: int, target_h: int,
                       scale_pct: int, offset_x_pct: int, offset_y_pct: int,
                       status_pill_html: str, status_label: str) -> str:
    if not image_b64:
        return (
            "<div class='live-frame live-frame--empty'>"
            "<span>⚠️ Không tìm thấy ảnh đã render.</span>"
            "</div>"
        )

    factor = max(60, min(150, int(scale_pct))) / 100.0
    tx = max(-100, min(100, int(offset_x_pct))) * 0.5
    ty = max(-100, min(100, int(offset_y_pct))) * 0.5

    if target_w and target_h:
        aspect = f"{int(target_w)} / {int(target_h)}"
    else:
        aspect = "3 / 2"

    return (
        "<div class='live-frame' style='aspect-ratio:" + aspect + ";'>"
        "  <div class='live-canvas'>"
        "    <img class='live-img' src='" + image_b64 + "' "
        "         style='transform: translate(" + f"{tx:.1f}%, {ty:.1f}%" + ") "
        "                          scale(" + f"{factor:.3f}" + ");' "
        "         alt='live preview'/>"
        "  </div>"
        "  <div class='live-status'>" + status_pill_html + "</div>"
        "  <div class='live-overlay-info'>"
        f"    <span>Scale {int(scale_pct)}%</span>"
        f"    <span>X {int(offset_x_pct):+d}</span>"
        f"    <span>Y {int(offset_y_pct):+d}</span>"
        f"    <span class='live-overlay-status'>{status_label}</span>"
        "  </div>"
        "</div>"
    )


def _ensure_default_state(item: dict, cfg: dict):
    item_id = item["id"]
    scale_key = f"adj_scale_{item_id}"
    x_key = f"adj_x_{item_id}"
    y_key = f"adj_y_{item_id}"
    sel_key = f"sel_{item_id}"

    if scale_key not in st.session_state:
        sizes = cfg.get("sizes", [])
        target_w = target_h = 0
        if sizes:
            tw, th, _m = sizes[0]
            target_w = int(tw or 0)
            target_h = int(th or 0)
        suggested = estimate_default_scale_for_size(
            int(item.get("source_width", 0)),
            int(item.get("source_height", 0)),
            target_w, target_h,
        )
        default_scale = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
        st.session_state[scale_key] = max(default_scale, suggested) if _is_small_image(item) else default_scale

    if x_key not in st.session_state:
        st.session_state[x_key] = 0
    if y_key not in st.session_state:
        st.session_state[y_key] = 0
    if sel_key not in st.session_state:
        st.session_state[sel_key] = _is_small_image(item)


# Callbacks tự động tick vào ô Checkbox khi người dùng chạm vào Slider
def _mark_item_selected(item_id: str):
    st.session_state[f"sel_{item_id}"] = True


# ═════════════════════════════════════════════════════════════════════
# MAIN STUDIO
# ═════════════════════════════════════════════════════════════════════
def render_adjustment_studio():
    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2 style='font-size:1.25rem !important'>🎚 Studio Scale</h2>"
        "<p style='font-size:0.95rem !important;line-height:1.65 !important'>"
        "Chỉ cần <b>kéo Slider</b> để chỉnh ảnh, hệ thống sẽ tự chọn ảnh đó. "
        "Bấm <b>Tạo ZIP Gộp</b> để tự động Render và đóng gói chung với ảnh gốc."
        "</p></div>",
        unsafe_allow_html=True,
    )

    manifest = st.session_state.get("last_batch_manifest", [])
    cfg = st.session_state.get("last_batch_cfg", {})
    meta = st.session_state.get("last_batch_meta", {})

    if not manifest:
        st.info(
            "⚠️ Chưa có batch nào để chỉnh. Hãy chạy ở tab "
            "**Web TGDD**, **Drive** hoặc **Local ZIP** trước."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if st.session_state.pop("_studio_just_arrived", False):
        st.markdown(
            "<div class='studio-fresh-banner'>"
            "✅ <b>Vừa render xong</b> — đã chuyển bạn sang Studio để xem & chỉnh ảnh. "
            "Ảnh hiển thị bên dưới là <b>kết quả thực tế đã được resize</b>. "
            "Kéo slider để xem ảnh giãn/nở ngay."
            "</div>",
            unsafe_allow_html=True,
        )

    render_batch_kpis(meta)

    total = len(manifest)
    selected_count = sum(1 for it in manifest if st.session_state.get(f"sel_{it['id']}", False))
    small_count = sum(1 for it in manifest if _is_small_image(it))

    st.markdown(
        f"<div class='guide-box'>"
        f"<b>Batch:</b> {meta.get('batch_id', '-')} · "
        f"<b>Tổng ảnh:</b> {total} · "
        f"<b>Đã chọn sửa:</b> <span style='color:#fbbf24'>{selected_count}</span> · "
        f"<b>Ảnh nhỏ cảnh báo:</b> <span style='color:#f87171'>{small_count}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    root = Path(meta.get("root", "")) if meta.get("root") else None
    final_dir = Path(meta.get("final_dir", str((root or Path(".")) / "FINAL"))) if root else None
    adjusted_dir = Path(st.session_state.get(
        "_adjusted_root", str((root or Path(".")) / "ADJUSTED")
    )) if root else None
    sizes_cfg = cfg.get("sizes", [])

    main_target_w, main_target_h = 1020, 680
    if sizes_cfg:
        try:
            tw, th, _m = sizes_cfg[0]
            if tw and th:
                main_target_w = int(tw)
                main_target_h = int(th)
        except Exception:
            pass

    product_names = sorted(list({item.get("product", "") for item in manifest if item.get("product")}))

    # ═════ BỘ LỌC ═════
    fc1, fc2, fc3, fc4 = st.columns([1.4, 1.1, 1.2, 0.8])
    with fc1:
        keyword = st.text_input("🔍 Tìm nhanh", placeholder="Tên ảnh, màu...", key="adj_kw")
    with fc2:
        product_filter = st.selectbox("Lọc sản phẩm", ["Tất cả", *product_names], key="adj_pf")
    with fc3:
        status_filter = st.selectbox(
            "Lọc trạng thái",
            ["Tất cả", "Chỉ ảnh đã chọn sửa", "Chỉ ảnh chưa chọn", "Chỉ ảnh nhỏ (bị giãn)"],
            key="adj_status",
        )
    with fc4:
        per_page = st.selectbox("Mỗi trang", [6, 10, 16, 24], index=1, key="adj_pp")

    filtered = _filtered_items(manifest, keyword, product_filter, status_filter)
    if not filtered:
        st.warning("Không có ảnh phù hợp bộ lọc.")
        _render_zip_download_section(meta, root, final_dir)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    total_pages = max((len(filtered) - 1) // per_page + 1, 1)
    page = st.number_input("Trang", min_value=1, max_value=total_pages, value=1, step=1, key="adj_page")
    start = (page - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]

    # ═════ HÀNG LOẠT ═════
    st.markdown('<div class="sec-title">🧩 Thao tác hàng loạt</div>', unsafe_allow_html=True)
    with st.container(border=True):
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("☑️ Chọn cả trang", use_container_width=True, key="adj_sel_page"):
                for it in page_items:
                    st.session_state[f"sel_{it['id']}"] = True
                st.rerun()
        with b2:
            if st.button("⬜ Bỏ chọn trang", use_container_width=True, key="adj_unsel_page"):
                for it in page_items:
                    st.session_state[f"sel_{it['id']}"] = False
                st.rerun()
        with b3:
            if st.button("⚠️ Chọn tất cả ảnh nhỏ", use_container_width=True, key="adj_sel_small"):
                for it in manifest:
                    if _is_small_image(it):
                        st.session_state[f"sel_{it['id']}"] = True
                st.rerun()
        with b4:
            if st.button("🧹 Xóa toàn bộ chọn", use_container_width=True, key="adj_clear_all"):
                for it in manifest:
                    st.session_state[f"sel_{it['id']}"] = False
                st.rerun()

        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            bulk_scale = st.slider("Scale (%)", 60, 150,
                                   int(cfg.get("default_scale_pct", 100)), 1, key="bulk_scale")
        with bc2:
            bulk_x = st.slider("Lệch X", -100, 100, 0, 1, key="bulk_x")
        with bc3:
            bulk_y = st.slider("Lệch Y", -100, 100, 0, 1, key="bulk_y")
        if st.button("⚡ Áp dụng cho trang & tự tích chọn",
                     use_container_width=True, key="adj_bulk_btn"):
            _apply_bulk_to_items(page_items, bulk_scale, bulk_x, bulk_y, also_select=True)
            st.rerun()

    # ═════ TỪNG ẢNH ═════
    st.markdown(
        f'<div class="sec-title">🖼 Điều chỉnh từng ảnh '
        f'({len(page_items)}/{len(filtered)}) — Live Preview</div>',
        unsafe_allow_html=True,
    )

    for item in page_items:
        item_id = item["id"]
        _ensure_default_state(item, cfg)

        scale_key = f"adj_scale_{item_id}"
        x_key = f"adj_x_{item_id}"
        y_key = f"adj_y_{item_id}"
        sel_key = f"sel_{item_id}"

        small_warn = _is_small_image(item)

        exact_stem = _get_exact_stem_for_item(item, manifest, cfg)
        display_path, display_status = _get_exact_display_path(
            item, exact_stem, final_dir, adjusted_dir, sizes_cfg
        )
        image_b64 = build_live_preview_b64(display_path)

        pill_map = {
            "adjusted": ("pill-adjusted", "🎯 Đã chỉnh"),
            "rendered": ("pill-rendered", "✅ Đã render"),
            "source":   ("pill-source",   "📷 Ảnh gốc"),
        }
        pill_class, pill_label = pill_map.get(display_status, pill_map["source"])
        pill_html = f"<span class='studio-status-pill {pill_class}'>{pill_label}</span>"

        with st.container(border=True):
            top_cb, top_warn = st.columns([3, 2])
            with top_cb:
                st.checkbox(
                    "✏️ Cần sửa ảnh này",
                    value=st.session_state[sel_key],
                    key=sel_key,
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
                    target_w=main_target_w,
                    target_h=main_target_h,
                    scale_pct=int(st.session_state[scale_key]),
                    offset_x_pct=int(st.session_state[x_key]),
                    offset_y_pct=int(st.session_state[y_key]),
                    status_pill_html=pill_html,
                    status_label=pill_label,
                )
                st.markdown(live_html, unsafe_allow_html=True)

                st.markdown(
                    f"<div class='preview-meta'>"
                    f"📐 <b>{item.get('source_width', 0)}×{item.get('source_height', 0)}</b> "
                    f"&nbsp;·&nbsp; 💾 {readable_file_size(item.get('source_size_bytes', 0))} "
                    f"&nbsp;·&nbsp; 🎯 Đầu ra <b>{main_target_w}×{main_target_h}</b>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with right_col:
                display_name = item.get("original_name", "-")
                st.markdown(
                    f"<div class='studio-img-title'>"
                    f"<b>{item.get('product', '-')}</b> · "
                    f"<span style='color:#a78bfa'>{item.get('color', '-')}</span><br>"
                    f"<code>{display_name}</code>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                sc, xc, yc = st.columns(3)
                with sc:
                    st.slider("Scale (%)", 60, 150,
                              value=int(st.session_state[scale_key]), step=1, key=scale_key,
                              on_change=_mark_item_selected, args=(item_id,))
                with xc:
                    st.slider("Lệch X", -100, 100,
                              value=int(st.session_state[x_key]), step=1, key=x_key,
                              on_change=_mark_item_selected, args=(item_id,))
                with yc:
                    st.slider("Lệch Y", -100, 100,
                              value=int(st.session_state[y_key]), step=1, key=y_key,
                              on_change=_mark_item_selected, args=(item_id,))

                rb1, rb2, rb3 = st.columns(3)
                with rb1:
                    if st.button("↺ Reset", key=f"reset_{item_id}", use_container_width=True):
                        st.session_state[scale_key] = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
                        st.session_state[x_key] = 0
                        st.session_state[y_key] = 0
                        st.session_state[sel_key] = True
                        st.rerun()
                with rb2:
                    if st.button("➖ Thu nhỏ 5%", key=f"minus_{item_id}", use_container_width=True):
                        st.session_state[scale_key] = max(60, int(st.session_state[scale_key]) - 5)
                        st.session_state[sel_key] = True
                        st.rerun()
                with rb3:
                    if st.button("➕ Phóng 5%", key=f"plus_{item_id}", use_container_width=True):
                        st.session_state[scale_key] = min(150, int(st.session_state[scale_key]) + 5)
                        st.session_state[sel_key] = True
                        st.rerun()

    # ═════ RENDER & XUẤT ZIP ═════
    st.divider()
    st.markdown('<div class="sec-title">🚀 Render ảnh đã chọn & xuất ZIP</div>',
                unsafe_allow_html=True)

    selected_items = [it for it in manifest if st.session_state.get(f"sel_{it['id']}", False)]
    unselected_items = [it for it in manifest if not st.session_state.get(f"sel_{it['id']}", False)]

    st.caption(
        f"🎯 Đang chọn **{len(selected_items)}** ảnh để sửa · "
        f"giữ nguyên **{len(unselected_items)}** ảnh từ batch gốc."
    )

    cb1, cb2 = st.columns(2)
    with cb1:
        do_render = st.button(
            "🎨 1. CHỈ RENDER ẢNH ĐÃ CHỌN",
            type="primary",
            use_container_width=True,
            key="adj_render_selected",
            disabled=(len(selected_items) == 0),
        )
    with cb2:
        do_export_full = st.button(
            "📦 2. TẠO ZIP GỘP (Tự RENDER trước nếu có)",
            type="primary",
            use_container_width=True,
            key="adj_export_full",
        )

    if do_render or do_export_full:
        if not root or not root.exists():
            st.error("❌ Thư mục batch đã bị xóa. Vui lòng chạy batch mới.")
            _render_zip_download_section(meta, root, final_dir)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        adjusted_root = root / "ADJUSTED"
        
        # --- RENDER TRƯỚC (NẾU CÓ ẢNH ĐƯỢC CHỌN) ---
        if selected_items:
            if adjusted_root.exists():
                shutil.rmtree(adjusted_root, ignore_errors=True)
            adjusted_root.mkdir(parents=True, exist_ok=True)

            progress = st.progress(0)
            status = st.empty()
            start_time = time.time()

            for idx, item in enumerate(selected_items, start=1):
                status.info(
                    f"[{idx}/{len(selected_items)}] Đang xử lý: {item.get('original_name', '-')}"
                )
                settings = {
                    "scale_pct": int(st.session_state.get(f"adj_scale_{item['id']}", 100)),
                    "offset_x": int(st.session_state.get(f"adj_x_{item['id']}", 0)),
                    "offset_y": int(st.session_state.get(f"adj_y_{item['id']}", 0)),
                }

                exact_stem = _get_exact_stem_for_item(item, manifest, cfg)

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
                    status.warning(f"⚠️ Lỗi render {item.get('original_name', '-')}: {exc}")
                progress.progress(idx / max(len(selected_items), 1))

            duration = time.time() - start_time
            adjusted_files = [f for f in adjusted_root.rglob("*") if f.is_file() and f.stat().st_size > 0]

            status.success(f"🎉 Đã Render xong {len(adjusted_files)} ảnh được chọn.")
            
            st.session_state.pop("_studio_thumb_b64_cache", None)
            st.session_state["_adjust_render_done"] = True
            st.session_state["_adjusted_root"] = str(adjusted_root)

            add_to_history(
                "Adjust",
                f"Studio · {len(selected_items)} ảnh",
                len(adjusted_files),
                " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])]),
                duration,
            )

        # --- GỘP & TẠO ZIP VỚI TÊN FILE MỚI CHỐNG CACHE ---
        if do_export_full:
            final_p = Path(meta.get("final_dir", str(root / "FINAL")))
            adjusted_p = Path(st.session_state.get("_adjusted_root", str(root / "ADJUSTED")))

            if not final_p.exists():
                st.error("❌ Thư mục FINAL gốc không tồn tại.")
            else:
                with st.spinner("Đang gộp ảnh đã chỉnh + ảnh gốc..."):
                    # Luôn tạo một folder gộp và một file ZIP mang tên duy nhất (timestamp)
                    unique_id = int(time.time())
                    merged_dir = root / f"MERGED_{unique_id}"
                    merged_dir.mkdir(parents=True, exist_ok=True)
                    stats = merge_final_with_adjusted(final_p, adjusted_p, merged_dir)

                    zip_path = root / f"FullExport_{meta.get('batch_id', 'batch')}_{unique_id}.zip"
                    make_zip(merged_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))

                st.session_state.adjust_zip_path = str(zip_path)
                st.success(
                    f"📦 ZIP gộp đã sẵn sàng — "
                    f"giữ nguyên: **{stats['kept']}** · ghi đè: **{stats['overridden']}** ảnh."
                )

        st.rerun()

    # ═════ KHU VỰC TẢI ZIP (LUÔN HIỂN THỊ TRONG STUDIO) ═════
    _render_zip_download_section(meta, root, final_dir)

    st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# ZIP DOWNLOADS
# ═════════════════════════════════════════════════════════════════════
def _render_zip_download_section(meta: dict, root: Path | None, final_dir: Path | None):
    st.markdown(
        '<div class="sec-title">📥 Tải ZIP (cả khi chưa chỉnh)</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='guide-box' style='font-size:0.95rem !important'>"
        "🔵 <b>ZIP GỐC</b> = tải ngay batch vừa render xong (chưa qua Studio).<br>"
        "🟢 <b>ZIP GỘP</b> = tải sau khi nhấn nút <b>TẠO ZIP GỘP</b> ở trên — "
        "ảnh đã chỉnh sẽ ghi đè ảnh gốc, ảnh chưa chỉnh giữ nguyên."
        "</div>",
        unsafe_allow_html=True,
    )

    col_orig, col_merged = st.columns(2)

    with col_orig:
        zip_path_orig = meta.get("zip_path", "") if isinstance(meta, dict) else ""
        if (not zip_path_orig or not Path(zip_path_orig).exists()) and root and final_dir and final_dir.exists():
            try:
                fallback_zip = root / f"OriginalExport_{meta.get('batch_id', 'batch')}.zip"
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
                st.markdown(
                    f"<div class='summary-card' style='border-color:rgba(99,102,241,0.4)'>"
                    f"📦 <b>ZIP GỐC</b> · {size_text}</div>",
                    unsafe_allow_html=True,
                )
                st.download_button(
                    label="📥 TẢI ZIP GỐC (FINAL)",
                    data=handle_orig,
                    file_name=Path(zip_path_orig).name,
                    mime="application/zip",
                    use_container_width=True,
                    key="dl_studio_orig_zip",
                )
            finally:
                handle_orig.close()
        else:
            st.info("Chưa có ZIP gốc — vào tab nguồn (Web/Drive/Local) tải lại để tạo.")

    with col_merged:
        zip_path_merged = st.session_state.get("adjust_zip_path", "")
        handle_merged = open_zip_for_download(zip_path_merged)
        if handle_merged:
            try:
                size_text = readable_file_size(Path(zip_path_merged).stat().st_size)
                st.markdown(
                    f"<div class='summary-card'>"
                    f"📦 <b>ZIP GỘP</b> · {size_text}</div>",
                    unsafe_allow_html=True,
                )
                st.download_button(
                    label="📥 TẢI ZIP GỘP (đã sửa + chưa sửa)",
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
            st.info("Chưa có ZIP gộp — bấm **TẠO ZIP GỘP** sau khi render ảnh đã chọn.")
