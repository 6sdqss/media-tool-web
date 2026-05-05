"""
mode_adjust.py — Studio chỉnh scale từng ảnh
Áp dụng cho batch gần nhất đã xử lý (Hỗ trợ cả TGDD, Drive và Local ZIP).
"""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from utils import (
    add_to_history,
    batch_rename_with_template,
    get_size_label,
    make_zip,
    open_zip_for_download,
    readable_file_size,
    render_batch_kpis,
    resize_to_multi_sizes,
    safe_image_meta,
    show_preview,
    show_processing_summary,
)


def _filtered_items(items: list[dict], keyword: str, product_filter: str) -> list[dict]:
    keyword = (keyword or "").strip().lower()
    output = []
    for item in items:
        haystack = " ".join([
            item.get("product", ""),
            item.get("color", ""),
            item.get("original_name", ""),
            item.get("folder_name", ""),
        ]).lower()
        if product_filter and product_filter != "Tất cả" and item.get("product") != product_filter:
            continue
        if keyword and keyword not in haystack:
            continue
        output.append(item)
    return output


def _apply_bulk_to_items(target_items: list[dict], scale_value: int, x_value: int, y_value: int):
    for item in target_items:
        item_id = item["id"]
        st.session_state[f"adj_scale_{item_id}"] = int(scale_value)
        st.session_state[f"adj_x_{item_id}"] = int(x_value)
        st.session_state[f"adj_y_{item_id}"] = int(y_value)


def render_adjustment_studio():
    st.markdown(
        "<div class='hero-card'>"
        "<h2>🎚️ Studio Scale VIP Pro</h2>"
        "<p>Chỉnh riêng từng ảnh sau khi xử lý (Hỗ trợ TGDD, Drive, Local). Kéo thanh trượt để scale, canh trái/phải, lên/xuống và render lại toàn bộ.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    manifest: list[dict] = st.session_state.get("last_batch_manifest", [])
    cfg: dict = st.session_state.get("last_batch_cfg", {})
    meta: dict = st.session_state.get("last_batch_meta", {})

    if not manifest:
        st.info("⚠️ Chưa có batch nào để chỉnh tay. Hãy chạy xử lý ở tab Web TGDD, Google Drive hoặc Local ZIP trước.")
        return

    render_batch_kpis(meta)

    st.markdown(
        f"<div class='guide-box' style='margin-top:8px'>"
        f"<b>Batch hiện tại:</b> {meta.get('batch_id', '-')}<br>"
        f"<b>Nguồn:</b> {meta.get('source_name', 'Hệ thống')} &nbsp;·&nbsp; "
        f"<b>Số ảnh gốc:</b> {len(manifest)} &nbsp;·&nbsp; "
        f"<b>Scale mặc định:</b> {cfg.get('default_scale_pct', 100)}%"
        f"</div>",
        unsafe_allow_html=True,
    )

    product_names = sorted(list({item.get("product", "") for item in manifest if item.get("product")}))

    filter_col1, filter_col2, filter_col3 = st.columns([1.6, 1.1, 1])
    with filter_col1:
        keyword = st.text_input("🔍 Tìm nhanh", placeholder="Nhập tên ảnh, màu sắc...")
    with filter_col2:
        product_filter = st.selectbox("Lọc theo thư mục/sản phẩm", ["Tất cả", *product_names])
    with filter_col3:
        per_page = st.selectbox("Ảnh mỗi trang", [6, 10, 16, 24], index=1)

    filtered = _filtered_items(manifest, keyword, product_filter)
    if not filtered:
        st.warning("Không có ảnh phù hợp với bộ lọc hiện tại.")
        return

    total_pages = max((len(filtered) - 1) // per_page + 1, 1)
    page = st.number_input("Trang số", min_value=1, max_value=total_pages, value=1, step=1)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]

    # Bulk Control
    st.markdown("<div class='sec-title'>🧩 ÁP DỤNG NHANH CHO TRANG HIỆN TẠI</div>", unsafe_allow_html=True)
    with st.container(border=True):
        bulk_col1, bulk_col2, bulk_col3, bulk_col4 = st.columns([1, 1, 1, 1.2])
        with bulk_col1:
            bulk_scale = st.slider("Scale chung (%)", 60, 150, int(cfg.get("default_scale_pct", 100)), 1, key="bulk_scale")
        with bulk_col2:
            bulk_x = st.slider("Lệch ngang", -100, 100, 0, 1, key="bulk_x")
        with bulk_col3:
            bulk_y = st.slider("Lệch dọc", -100, 100, 0, 1, key="bulk_y")
        with bulk_col4:
            st.write("") 
            if st.button("⚡ ÁP DỤNG HÀNG LOẠT", use_container_width=True):
                _apply_bulk_to_items(page_items, bulk_scale, bulk_x, bulk_y)
                st.rerun()

    # Image List
    st.markdown(f"<div class='sec-title'>🖼️ ĐIỀU CHỈNH TỪNG ẢNH ({len(page_items)}/{len(filtered)} ĐANG HIỂN THỊ)</div>", unsafe_allow_html=True)

    for item in page_items:
        item_id = item["id"]
        default_scale = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
        
        scale_key = f"adj_scale_{item_id}"
        x_key = f"adj_x_{item_id}"
        y_key = f"adj_y_{item_id}"

        if scale_key not in st.session_state:
            st.session_state[scale_key] = default_scale
        if x_key not in st.session_state:
            st.session_state[x_key] = 0
        if y_key not in st.session_state:
            st.session_state[y_key] = 0

        with st.container(border=True):
            left_col, right_col = st.columns([1, 2.8])
            
            with left_col:
                st.image(item.get("preview_path") or item["source_path"], use_container_width=True)
                st.markdown(
                    f"<div style='text-align:center; font-size:0.75rem; color:#64748b'>"
                    f"📐 {item.get('source_width', 0)}×{item.get('source_height', 0)}<br>"
                    f"💾 {readable_file_size(item.get('source_size_bytes', 0))}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with right_col:
                display_name = item.get('original_name', '-')
                st.markdown(f"<b style='color:#1e1b4b; font-size:1.05rem'>{item.get('product', '-')}</b> &nbsp;·&nbsp; <span style='color:#4338ca'>{item.get('color', '-')}</span> &nbsp;·&nbsp; <code style='font-size:0.8rem'>{display_name}</code>", unsafe_allow_html=True)
                
                # Bố cục thanh trượt gọn gàng trên 1 hàng ngang
                sc_col, x_col, y_col = st.columns(3)
                with sc_col:
                    st.slider(
                        "Scale (%)", 60, 150, 
                        value=int(st.session_state[scale_key]), step=1, key=scale_key
                    )
                with x_col:
                    st.slider(
                        "Lệch ngang (X)", -100, 100, 
                        value=int(st.session_state[x_key]), step=1, key=x_key
                    )
                with y_col:
                    st.slider(
                        "Lệch dọc (Y)", -100, 100, 
                        value=int(st.session_state[y_key]), step=1, key=y_key
                    )

    st.divider()
    st.markdown("<div class='sec-title'>🚀 XUẤT FILE MỚI SAU KHI ĐÃ ĐIỀU CHỈNH</div>", unsafe_allow_html=True)

    if st.button("RENDER LẠI TOÀN BỘ BATCH NÀY", type="primary", use_container_width=True):
        root = Path(meta.get("root", ""))
        if not root.exists():
            st.error("❌ Thư mục làm việc của batch này đã bị xóa hoặc không tồn tại. Vui lòng chạy lại tiến trình quét mới.")
            return

        adjusted_root = root / "ADJUSTED"
        final_dir = adjusted_root / f"FINAL_{int(time.time())}"
        final_dir.mkdir(parents=True, exist_ok=True)
        zip_path = adjusted_root / f"Adjusted_{meta.get('batch_id', 'batch')}.zip"

        progress = st.progress(0)
        status = st.empty()
        start_time = time.time()

        for idx, item in enumerate(manifest, start=1):
            status.info(f"[{idx}/{len(manifest)}] Đang Render: {item.get('product', '-')} / {item.get('original_name', '-')}")
            settings = {
                "scale_pct": int(st.session_state.get(f"adj_scale_{item['id']}", item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))),
                "offset_x": int(st.session_state.get(f"adj_x_{item['id']}", 0)),
                "offset_y": int(st.session_state.get(f"adj_y_{item['id']}", 0)),
            }
            resize_to_multi_sizes(
                Path(item["source_path"]),
                final_dir,
                item["folder_name"],
                item["original_name"],
                cfg.get("sizes", []),
                scale_pct=int(cfg.get("default_scale_pct", 100)),
                quality=int(cfg.get("quality", 95)),
                export_format=cfg.get("export_format", "JPEG (.jpg)"),
                per_image_settings=settings,
                huge_image_mode=bool(cfg.get("huge_image_mode", True)),
            )
            progress.progress(idx / len(manifest))

        batch_rename_with_template(final_dir, cfg.get("template", "{name}_{nn}"))
        make_zip(final_dir, zip_path, compresslevel=int(cfg.get("zip_compression", 6)))
        duration = time.time() - start_time
        output_files = [f for f in final_dir.rglob("*") if f.is_file() and f.stat().st_size > 0]

        status.success(f"🎉 Render VIP Pro hoàn tất — Đã tạo thành công {len(output_files)} ảnh")
        show_preview(final_dir)
        show_processing_summary(final_dir, cfg.get("sizes", []), duration)

        st.session_state.adjust_zip_path = str(zip_path)
        add_to_history(
            "Adjust",
            meta.get("source_name", "Studio") + " / Tùy chỉnh",
            len(output_files),
            " + ".join([get_size_label(w, h, m) for w, h, m in cfg.get("sizes", [])]),
            duration,
        )

    zip_path = st.session_state.get("adjust_zip_path", "")
    download_handle = open_zip_for_download(zip_path)
    if download_handle:
        try:
            size_text = readable_file_size(Path(zip_path).stat().st_size)
            st.success(f"📦 File ZIP đã chỉnh sửa xong — Dung lượng: {size_text}")
            st.download_button(
                label="📥 TẢI XUỐNG ZIP ĐÃ CHỈNH",
                data=download_handle,
                file_name=Path(zip_path).name,
                mime="application/zip",
                type="primary",
                use_container_width=True,
                key="download_adjust_zip",
            )
        finally:
            download_handle.close()
