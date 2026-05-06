"""
mode_adjust.py — Studio Scale v9.2 (UPGRADED)
─────────────────────────────────────────────────────────
Nâng cấp v9.2:
- HIỂN THỊ ĐÚNG ảnh đã render (FINAL) hoặc ảnh đã sửa (ADJUSTED), thay
  vì ảnh "góc" preview như trước.
- Thumbnail luôn căn giữa hoàn toàn (object-fit: contain, mọi tỉ lệ).
- Bố cục Studio: chữ to hơn, padding rộng, dễ nhìn trên cả desktop & mobile.
- Banner "Vừa render xong từ tab khác" khi auto-switch.
- Sau khi render lại trong Studio: tự reload để hiện ảnh mới.
"""

from __future__ import annotations

import time
import shutil
from pathlib import Path

import streamlit as st

from utils import (
    add_to_history,
    batch_rename_with_template,
    get_size_label,
    make_zip,
    merge_final_with_adjusted,
    open_zip_for_download,
    readable_file_size,
    render_batch_kpis,
    resize_to_multi_sizes,
    show_preview,
    show_processing_summary,
)


_SMALL_IMAGE_THRESHOLD = 600  # ảnh < 600px coi là nhỏ — cảnh báo bị giãn

# Phần mở rộng file ảnh hợp lệ
_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ╔══════════════════════════════════════════════════════════════╗
# ║  HELPER — TÌM ẢNH ĐÃ RENDER ĐỂ HIỂN THỊ                     ║
# ╚══════════════════════════════════════════════════════════════╝
def _find_rendered_image(item: dict, root: Path,
                         final_dir: Path, adjusted_dir: Path,
                         sizes: list) -> tuple[str, str]:
    """
    Tìm đường dẫn ảnh đã render thực tế để hiển thị trong Studio.
    Ưu tiên: ADJUSTED (đã sửa) → FINAL (đã render xong) → preview → source.
    Trả về: (path_str, status) với status ∈ {"adjusted", "rendered", "source"}.
    """
    folder_name = item.get("folder_name", "")
    original_name = item.get("original_name", "")
    is_multi = isinstance(sizes, list) and len(sizes) > 1

    # Ưu tiên size đầu tiên (thường là size chuẩn TGDD 1020×680)
    size_label = ""
    if sizes:
        try:
            w, h, m = sizes[0]
            size_label = get_size_label(w, h, m)
        except Exception:
            size_label = ""

    candidate_dirs = []
    # 1. ADJUSTED (đã chỉnh tay)
    if adjusted_dir and adjusted_dir.exists():
        if is_multi and size_label:
            candidate_dirs.append(("adjusted", adjusted_dir / size_label / folder_name))
        candidate_dirs.append(("adjusted", adjusted_dir / folder_name))
        candidate_dirs.append(("adjusted", adjusted_dir))
    # 2. FINAL (đã render xong từ batch gốc)
    if final_dir and final_dir.exists():
        if is_multi and size_label:
            candidate_dirs.append(("rendered", final_dir / size_label / folder_name))
        candidate_dirs.append(("rendered", final_dir / folder_name))
        candidate_dirs.append(("rendered", final_dir))

    for status, d in candidate_dirs:
        if not d.exists() or not d.is_dir():
            continue
        # 1. khớp tên gốc
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = d / f"{original_name}{ext}"
            if p.exists() and p.stat().st_size > 0:
                return str(p), status
        # 2. file đầu tiên chứa original_name (sau rename template)
        try:
            for f in sorted(d.iterdir()):
                if (f.is_file() and f.suffix.lower() in _IMG_EXT
                        and original_name and original_name in f.stem):
                    return str(f), status
        except Exception:
            pass
        # 3. file đầu tiên trong thư mục folder_name
        try:
            for f in sorted(d.rglob("*")):
                if f.is_file() and f.suffix.lower() in _IMG_EXT and f.stat().st_size > 0:
                    return str(f), status
        except Exception:
            pass

    # 4. Fallback cuối: preview hoặc source
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


def render_adjustment_studio():
    # Wrap toàn bộ Studio để CSS .studio-wrap có hiệu lực (chữ to, layout rộng)
    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2 style='font-size:1.15rem !important'>🎚 Studio Scale</h2>"
        "<p style='font-size:0.86rem !important'>"
        "Tích chọn ảnh cần sửa · Scale + offset X/Y · Xuất ZIP gộp đầy đủ. "
        "Ảnh hiển thị bên dưới là <b>ảnh đã render xong</b> (hoặc ảnh đã chỉnh nếu có)."
        "</p></div>",
        unsafe_allow_html=True,
    )

    manifest = st.session_state.get("last_batch_manifest", [])
    cfg = st.session_state.get("last_batch_cfg", {})
    meta = st.session_state.get("last_batch_meta", {})

    if not manifest:
        st.info("⚠️ Chưa có batch nào để chỉnh. Hãy chạy ở tab Web TGDD, Drive hoặc Local ZIP trước.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Banner "vừa render xong" nếu được auto-redirect tới
    if st.session_state.pop("_studio_just_arrived", False):
        st.markdown(
            "<div class='studio-fresh-banner'>"
            "✅ <b>Vừa render xong</b> — đã chuyển bạn sang Studio để chỉnh ảnh nếu cần. "
            "Ảnh hiển thị bên dưới là kết quả thực tế đã được resize."
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

    # Thư mục FINAL & ADJUSTED — dùng để tìm ảnh đã render
    root = Path(meta.get("root", ""))
    final_dir = Path(meta.get("final_dir", str(root / "FINAL"))) if meta.get("root") else None
    adjusted_dir = Path(st.session_state.get("_adjusted_root", str(root / "ADJUSTED"))) \
        if meta.get("root") else None
    sizes_cfg = cfg.get("sizes", [])

    product_names = sorted(list({item.get("product", "") for item in manifest if item.get("product")}))

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
        f'<div class="sec-title">🖼 Điều chỉnh từng ảnh ({len(page_items)}/{len(filtered)})</div>',
        unsafe_allow_html=True
    )

    for item in page_items:
        item_id = item["id"]
        default_scale = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))

        scale_key = f"adj_scale_{item_id}"
        x_key = f"adj_x_{item_id}"
        y_key = f"adj_y_{item_id}"
        sel_key = f"sel_{item_id}"

        if scale_key not in st.session_state:
            st.session_state[scale_key] = default_scale
        if x_key not in st.session_state:
            st.session_state[x_key] = 0
        if y_key not in st.session_state:
            st.session_state[y_key] = 0
        if sel_key not in st.session_state:
            st.session_state[sel_key] = _is_small_image(item)  # auto-tick ảnh nhỏ

        small_warn = _is_small_image(item)

        # Tìm ảnh thực tế đã render để hiển thị
        display_path, display_status = _find_rendered_image(
            item, root, final_dir, adjusted_dir, sizes_cfg
        )

        with st.container(border=True):
            top_cb, top_warn = st.columns([3, 2])
            with top_cb:
                st.checkbox(
                    f"✏️ Cần sửa ảnh này",
                    value=st.session_state[sel_key],
                    key=sel_key,
                )
            with top_warn:
                if small_warn:
                    st.markdown(
                        "<span style='color:#f87171;font-size:0.8rem;font-weight:700'>"
                        "⚠️ ẢNH NHỎ — DỄ BỊ GIÃN</span>",
                        unsafe_allow_html=True,
                    )

            left_col, right_col = st.columns([1, 2.2])

            with left_col:
                # Pill trạng thái: rendered / adjusted / source
                pill_class = {
                    "adjusted": ("pill-adjusted", "🎯 Đã chỉnh"),
                    "rendered": ("pill-rendered", "✅ Đã render"),
                    "source":   ("pill-source",   "📷 Ảnh gốc"),
                }[display_status]

                st.markdown(
                    f"<div style='text-align:center;margin-bottom:6px'>"
                    f"<span class='studio-status-pill {pill_class[0]}'>{pill_class[1]}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if display_path and Path(display_path).exists():
                    st.image(display_path, use_container_width=True)
                else:
                    st.warning("⚠️ Không tìm thấy ảnh hiển thị.")

                st.markdown(
                    f"<div class='preview-meta'>"
                    f"📐 {item.get('source_width', 0)}×{item.get('source_height', 0)}<br>"
                    f"💾 {readable_file_size(item.get('source_size_bytes', 0))}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with right_col:
                display_name = item.get('original_name', '-')
                st.markdown(
                    f"<div class='studio-img-title'>"
                    f"<b>{item.get('product', '-')}</b> · "
                    f"<span style='color:#a78bfa'>{item.get('color', '-')}</span><br>"
                    f"<code>{display_name}</code>"
                    f"</div>",
                    unsafe_allow_html=True
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

    # ═════ RENDER & XUẤT ZIP GỘP ═════
    st.divider()
    st.markdown('<div class="sec-title">🚀 Render ảnh đã chọn & xuất ZIP gộp</div>',
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
            "📦 XUẤT ZIP GỘP (đã sửa + chưa sửa)",
            use_container_width=True,
            key="adj_export_full",
        )

    # ───────── RENDER PHẦN ĐÃ CHỌN ─────────
    if do_render and selected_items:
        root_p = Path(meta.get("root", ""))
        if not root_p.exists():
            st.error("❌ Thư mục batch đã bị xóa. Vui lòng chạy batch mới.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        adjusted_root = root_p / "ADJUSTED"
        # Reset ADJUSTED để tránh lẫn ảnh cũ
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
                    item.get("default_scale_pct", cfg.get("default_scale_pct", 100))
                )),
                "offset_x": int(st.session_state.get(f"adj_x_{item['id']}", 0)),
                "offset_y": int(st.session_state.get(f"adj_y_{item['id']}", 0)),
            }
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
            progress.progress(idx / len(selected_items))

        batch_rename_with_template(adjusted_root, cfg.get("template", "{name}_{nn}"))

        duration = time.time() - start_time
        adjusted_files = [f for f in adjusted_root.rglob("*")
                          if f.is_file() and f.stat().st_size > 0]

        status.success(f"🎉 Render xong {len(adjusted_files)} file đã chỉnh.")
        show_preview(adjusted_root)

        st.session_state["_adjust_render_done"] = True
        st.session_state["_adjusted_root"] = str(adjusted_root)

        add_to_history(
            "Adjust",
            f"{meta.get('source_name', 'Studio')} · {len(selected_items)} ảnh",
            len(adjusted_files),
            " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])]),
            duration,
        )
        # Reload để các thumbnail trên hiện ngay ảnh ADJUSTED mới
        st.rerun()

    # ───────── XUẤT ZIP GỘP ─────────
    if do_export_full:
        root_p = Path(meta.get("root", ""))
        final_p = Path(meta.get("final_dir", str(root_p / "FINAL")))
        adjusted_p = Path(st.session_state.get("_adjusted_root", str(root_p / "ADJUSTED")))

        if not final_p.exists():
            st.error("❌ Thư mục FINAL gốc không tồn tại.")
        else:
            with st.spinner("Đang gộp ảnh đã chỉnh + ảnh gốc..."):
                merged_dir = root_p / f"MERGED_{int(time.time())}"
                merged_dir.mkdir(parents=True, exist_ok=True)
                stats = merge_final_with_adjusted(final_p, adjusted_p, merged_dir)

                zip_path = root_p / f"FullExport_{meta.get('batch_id', 'batch')}.zip"
                make_zip(merged_dir, zip_path,
                         compresslevel=int(cfg.get("zip_compression", 6)))

            st.session_state.adjust_zip_path = str(zip_path)
            st.success(
                f"📦 ZIP gộp đã sẵn sàng — "
                f"giữ nguyên: **{stats['kept']}** · ghi đè: **{stats['overridden']}** · "
                f"tổng: **{stats['total']}** file."
            )

    # ───────── DOWNLOAD ZIP ─────────
    zip_path = st.session_state.get("adjust_zip_path", "")
    download_handle = open_zip_for_download(zip_path)
    if download_handle:
        try:
            size_text = readable_file_size(Path(zip_path).stat().st_size)
            st.markdown(f"<div class='summary-card'>"
                        f"📦 <b>ZIP gộp</b> · {size_text}</div>",
                        unsafe_allow_html=True)
            st.download_button(
                label="📥 TẢI ZIP ĐẦY ĐỦ (đã sửa + chưa sửa)",
                data=download_handle,
                file_name=Path(zip_path).name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="download_adjust_zip",
            )
        finally:
            download_handle.close()

    st.markdown("</div>", unsafe_allow_html=True)
