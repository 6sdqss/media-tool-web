"""
mode_adjust.py — Studio Scale v9.3 (LIVE PREVIEW UPGRADE)
─────────────────────────────────────────────────────────
Nâng cấp v9.3 (giữ NGUYÊN logic cũ, CHỈ MỞ RỘNG):
- LIVE PREVIEW: kéo slider Scale/X/Y → ảnh GIÃN/DỊCH ngay tức thì bằng
  CSS transform (scale + translate) trên thumbnail base64 — không phải
  chờ render.
- Hiển thị ĐÚNG ảnh đã render (FINAL) hoặc đã sửa (ADJUSTED) — map qua
  seq_in_folder để chính xác sau khi đã đổi tên template.
- Bố cục TO RÕ: chữ ≥14px, ảnh max-height 500px, padding rộng.
- Dual ZIP: TẢI ZIP GỐC (FINAL ngay sau render) + TẢI ZIP GỘP (đã sửa).
- Banner "Vừa render xong" khi auto-switch.
- Sau khi Render-lại trong Studio: tự reload để cập nhật.
"""

from __future__ import annotations

import time
import shutil
from pathlib import Path

import streamlit as st

from utils import (
    add_to_history,
    batch_rename_with_template,
    build_live_preview_b64,
    estimate_default_scale_for_size,
    find_rendered_image_for_item,
    get_size_label,
    make_zip,
    merge_final_with_adjusted,
    open_zip_for_download,
    readable_file_size,
    render_batch_kpis,
    resize_to_multi_sizes,
    show_preview,
)


_SMALL_IMAGE_THRESHOLD = 600          # ảnh < 600px coi là nhỏ → cảnh báo
_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ═════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════
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
    """
    Render preview LIVE: ảnh đã render được nhúng base64, áp transform
    `scale + translate` để giả lập real-time hiệu ứng kéo slider.

    - target_w/target_h dùng để giữ aspect-ratio khung canvas (giống size đầu ra).
    - scale_pct: 60..150 → factor 0.6..1.5
    - offset_x/y: -100..100 → translate %  (chia 2 để hợp với engine resize)
    """
    if not image_b64:
        return (
            "<div class='live-frame live-frame--empty'>"
            "<span>⚠️ Không tìm thấy ảnh đã render.</span>"
            "</div>"
        )

    factor = max(60, min(150, int(scale_pct))) / 100.0
    tx = max(-100, min(100, int(offset_x_pct))) * 0.5   # %
    ty = max(-100, min(100, int(offset_y_pct))) * 0.5   # %

    # Aspect-ratio khung
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
    """Khởi tạo state slider/checkbox 1 lần, đề xuất scale tự động cho ảnh nhỏ."""
    item_id = item["id"]
    scale_key = f"adj_scale_{item_id}"
    x_key = f"adj_x_{item_id}"
    y_key = f"adj_y_{item_id}"
    sel_key = f"sel_{item_id}"

    if scale_key not in st.session_state:
        # Đề xuất scale dựa trên size đầu tiên + kích thước nguồn
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
        # Ưu tiên đề xuất nếu ảnh nhỏ (suggested > default), tránh giãn vỡ
        st.session_state[scale_key] = max(default_scale, suggested) if _is_small_image(item) else default_scale

    if x_key not in st.session_state:
        st.session_state[x_key] = 0
    if y_key not in st.session_state:
        st.session_state[y_key] = 0
    if sel_key not in st.session_state:
        st.session_state[sel_key] = _is_small_image(item)


# ═════════════════════════════════════════════════════════════════════
# MAIN STUDIO
# ═════════════════════════════════════════════════════════════════════
def render_adjustment_studio():
    # Wrap toàn bộ Studio để CSS .studio-wrap có hiệu lực
    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2 style='font-size:1.25rem !important'>🎚 Studio Scale</h2>"
        "<p style='font-size:0.95rem !important;line-height:1.65 !important'>"
        "Tích chọn ảnh cần sửa · Scale + offset X/Y · "
        "<b style='color:#fde68a'>Live Preview</b> giãn/nở theo slider · "
        "Xuất ZIP gộp đầy đủ. Ảnh hiển thị bên dưới là "
        "<b>ảnh đã render xong</b> (hoặc ảnh đã chỉnh nếu có)."
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

    # Banner "vừa render xong" nếu được auto-redirect tới
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

    # Đếm trạng thái
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

    # Thư mục FINAL & ADJUSTED
    root = Path(meta.get("root", "")) if meta.get("root") else None
    final_dir = Path(meta.get("final_dir", str((root or Path(".")) / "FINAL"))) if root else None
    adjusted_dir = Path(st.session_state.get(
        "_adjusted_root", str((root or Path(".")) / "ADJUSTED")
    )) if root else None
    sizes_cfg = cfg.get("sizes", [])

    # Size đầu tiên — dùng để render khung Live Preview giữ aspect-ratio
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
        # Vẫn hiện khu vực ZIP gốc kể cả khi lọc rỗng
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

        # Tìm ảnh ĐÃ RENDER thật để live-preview
        display_path, display_status = find_rendered_image_for_item(
            item, root, final_dir, adjusted_dir, sizes_cfg
        )
        image_b64 = build_live_preview_b64(display_path)

        pill_map = {
            "adjusted": ("pill-adjusted", "🎯 Đã chỉnh"),
            "rendered": ("pill-rendered", "✅ Đã render"),
            "source":   ("pill-source",   "📷 Ảnh gốc"),
        }
        pill_class, pill_label = pill_map.get(display_status, pill_map["source"])
        pill_html = (
            f"<span class='studio-status-pill {pill_class}'>{pill_label}</span>"
        )

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

            # ───── LIVE PREVIEW (TRÁI) ─────
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

            # ───── SLIDERS (PHẢI) ─────
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
                              value=int(st.session_state[scale_key]), step=1, key=scale_key)
                with xc:
                    st.slider("Lệch X", -100, 100,
                              value=int(st.session_state[x_key]), step=1, key=x_key)
                with yc:
                    st.slider("Lệch Y", -100, 100,
                              value=int(st.session_state[y_key]), step=1, key=y_key)

                # Hàng nút mini per-item: reset / +/-5
                rb1, rb2, rb3 = st.columns(3)
                with rb1:
                    if st.button("↺ Reset", key=f"reset_{item_id}", use_container_width=True):
                        st.session_state[scale_key] = int(item.get(
                            "default_scale_pct", cfg.get("default_scale_pct", 100)
                        ))
                        st.session_state[x_key] = 0
                        st.session_state[y_key] = 0
                        st.rerun()
                with rb2:
                    if st.button("➖ Thu nhỏ 5%", key=f"minus_{item_id}", use_container_width=True):
                        st.session_state[scale_key] = max(60, int(st.session_state[scale_key]) - 5)
                        st.rerun()
                with rb3:
                    if st.button("➕ Phóng 5%", key=f"plus_{item_id}", use_container_width=True):
                        st.session_state[scale_key] = min(150, int(st.session_state[scale_key]) + 5)
                        st.rerun()

    # ═════ RENDER & XUẤT ZIP ═════
    st.divider()
    st.markdown('<div class="sec-title">🚀 Render ảnh đã chọn & xuất ZIP</div>',
                unsafe_allow_html=True)

    selected_items = [it for it in manifest if st.session_state.get(f"sel_{it['id']}", False)]
    unselected_items = [it for it in manifest if not st.session_state.get(f"sel_{it['id']}", False)]

    st.caption(
        f"🎯 Sẽ render lại **{len(selected_items)}** ảnh đã chọn · "
        f"giữ nguyên **{len(unselected_items)}** ảnh từ batch gốc."
    )

    cb1, cb2 = st.columns(2)
    with cb1:
        do_render = st.button(
            "🎨 RENDER ẢNH ĐÃ CHỌN",
            type="primary",
            use_container_width=True,
            key="adj_render_selected",
            disabled=(len(selected_items) == 0),
        )
    with cb2:
        do_export_full = st.button(
            "📦 TẠO ZIP GỘP (đã sửa + chưa sửa)",
            use_container_width=True,
            key="adj_export_full",
        )

    # ───── RENDER ─────
    if do_render and selected_items:
        if not root or not root.exists():
            st.error("❌ Thư mục batch đã bị xóa. Vui lòng chạy batch mới.")
            _render_zip_download_section(meta, root, final_dir)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        adjusted_root = root / "ADJUSTED"
        if adjusted_root.exists():
            shutil.rmtree(adjusted_root, ignore_errors=True)
        adjusted_root.mkdir(parents=True, exist_ok=True)

        progress = st.progress(0)
        status = st.empty()
        start_time = time.time()

        for idx, item in enumerate(selected_items, start=1):
            status.info(
                f"[{idx}/{len(selected_items)}] {item.get('product', '-')} / "
                f"{item.get('original_name', '-')}"
            )
            settings = {
                "scale_pct": int(st.session_state.get(
                    f"adj_scale_{item['id']}",
                    item.get("default_scale_pct", cfg.get("default_scale_pct", 100)),
                )),
                "offset_x": int(st.session_state.get(f"adj_x_{item['id']}", 0)),
                "offset_y": int(st.session_state.get(f"adj_y_{item['id']}", 0)),
            }
            try:
                resize_to_multi_sizes(
                    Path(item["source_path"]),
                    adjusted_root,
                    item["folder_name"],
                    item["original_name"],
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

        try:
            batch_rename_with_template(adjusted_root, cfg.get("template", "{name}_{nn}"))
        except Exception:
            pass

        duration = time.time() - start_time
        adjusted_files = [
            f for f in adjusted_root.rglob("*")
            if f.is_file() and f.stat().st_size > 0
        ]

        status.success(f"🎉 Render xong {len(adjusted_files)} file đã chỉnh.")
        show_preview(adjusted_root)

        # Xóa cache thumbnail để buộc Studio đọc lại ảnh ADJUSTED mới
        st.session_state.pop("_studio_thumb_b64_cache", None)
        st.session_state["_adjust_render_done"] = True
        st.session_state["_adjusted_root"] = str(adjusted_root)

        add_to_history(
            "Adjust",
            f"{meta.get('source_name', 'Studio')} · {len(selected_items)} ảnh",
            len(adjusted_files),
            " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])]),
            duration,
        )
        st.rerun()

    # ───── ZIP GỘP ─────
    if do_export_full:
        if not root or not root.exists():
            st.error("❌ Thư mục batch đã bị xóa.")
        else:
            final_p = Path(meta.get("final_dir", str(root / "FINAL")))
            adjusted_p = Path(st.session_state.get("_adjusted_root", str(root / "ADJUSTED")))

            if not final_p.exists():
                st.error("❌ Thư mục FINAL gốc không tồn tại.")
            else:
                with st.spinner("Đang gộp ảnh đã chỉnh + ảnh gốc..."):
                    merged_dir = root / f"MERGED_{int(time.time())}"
                    merged_dir.mkdir(parents=True, exist_ok=True)
                    stats = merge_final_with_adjusted(final_p, adjusted_p, merged_dir)

                    zip_path = root / f"FullExport_{meta.get('batch_id', 'batch')}.zip"
                    make_zip(merged_dir, zip_path,
                             compresslevel=int(cfg.get("zip_compression", 6)))

                st.session_state.adjust_zip_path = str(zip_path)
                st.success(
                    f"📦 ZIP gộp đã sẵn sàng — "
                    f"giữ nguyên: **{stats['kept']}** · ghi đè: **{stats['overridden']}** · "
                    f"tổng: **{stats['total']}** file."
                )

    # ═════ KHU VỰC TẢI ZIP (LUÔN HIỂN THỊ TRONG STUDIO) ═════
    _render_zip_download_section(meta, root, final_dir)

    st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# ZIP DOWNLOADS — luôn hiển thị trong Studio (cả ZIP gốc & ZIP gộp)
# ═════════════════════════════════════════════════════════════════════
def _render_zip_download_section(meta: dict, root: Path | None, final_dir: Path | None):
    """Hiển thị 2 nút TẢI ZIP trong Studio: ZIP gốc (FINAL) + ZIP gộp (đã chỉnh)."""
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

    # ── ZIP GỐC (FINAL) ──
    with col_orig:
        zip_path_orig = meta.get("zip_path", "") if isinstance(meta, dict) else ""
        # Nếu zip_path không có, thử tự tạo từ final_dir
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

    # ── ZIP GỘP (sau khi user bấm TẠO ZIP GỘP) ──
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
