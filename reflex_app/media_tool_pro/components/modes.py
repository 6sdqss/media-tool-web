"""
components/modes.py — nội dung từng tab: Home / Web / Drive / Local / Studio /
Guide / Admin. Thay thế modes/*.py (phần UI Streamlit) + admin_panel.py UI +
mode_adjust.py UI.
"""
from __future__ import annotations

import reflex as rx

from ..backend.auth_state import AuthState
from ..backend.batch_state import BatchState
from ..backend.admin_state import AdminState, PERMISSION_LABELS
from ..backend.studio_state import StudioState
from .ui import (
    batch_progress_panel, batch_queue_view, error_banner, error_banner_studio,
    input_report_bar, preset_picker, run_outputs_panel, stat_pill,
)
from . import bauhaus as bh


_HERO_COLORS = [bh.YELLOW, bh.BLUE, bh.RED]
_hero_counter = {"i": 0}


def hero(title: str, subtitle: str, accent: str | None = None) -> rx.Component:
    """Section màu khối kiểu Bauhaus, xoay vòng 3 màu chính nếu không chỉ
    định — kèm hình khối trang trí góc trên-phải (đối lập điểm nhấn)."""
    if accent is None:
        accent = _HERO_COLORS[_hero_counter["i"] % 3]
        _hero_counter["i"] += 1
    text_color = bh.WHITE if accent in (bh.BLUE, bh.RED) else bh.INK
    return rx.box(
        rx.box(
            width="90px", height="90px", border_radius="9999px",
            bg=(bh.WHITE if accent != bh.WHITE else bh.INK),
            opacity="0.18",
            position="absolute", top="-30px", right="-20px",
        ),
        rx.box(
            width="46px", height="46px",
            bg=(bh.WHITE if accent != bh.WHITE else bh.INK),
            opacity="0.18", transform="rotate(20deg)",
            position="absolute", bottom="-14px", right="60px",
        ),
        rx.heading(title.upper(), size="6", color=text_color, font_font_weight="900",
                    letter_spacing="-0.01em", position="relative"),
        rx.text(subtitle, color=text_color, size="2", margin_top="0.35em",
                 font_weight="500", position="relative"),
        padding="1.4em 1.7em",
        bg=accent,
        border=f"4px solid {bh.INK}",
        box_shadow=bh.hard_shadow(8),
        margin_bottom="1.1em",
        width="100%",
        position="relative", overflow="hidden",
    )


def render_home() -> rx.Component:
    _PRESET_ACCENTS = [bh.RED, bh.BLUE, bh.YELLOW]

    def _preset_card(p, i) -> rx.Component:
        accent = rx.match(i % 3, (0, bh.RED), (1, bh.BLUE), (2, bh.YELLOW), bh.RED)
        return rx.box(
            rx.box(width="12px", height="12px", bg=accent, border_radius="9999px",
                    position="absolute", top="-6px", right="-6px"),
            rx.vstack(
                rx.text(p["name"], font_weight="900", size="2", text_transform="uppercase"),
                rx.text(p["description"], size="1", color=bh.INK),
                rx.text(f"📐 {p['sizes']}", size="1", font_weight="700"),
                rx.text(f"Q={p['quality']} · {p['format']}", size="1", color=bh.INK),
                spacing="1", align_items="start",
            ),
            position="relative", padding="1em",
            bg=bh.WHITE, border=f"3px solid {bh.INK}", box_shadow=bh.hard_shadow(5),
            style={"transition": "transform 0.15s ease-out",
                   "_hover": {"transform": "translateY(-3px)"}},
        )

    return rx.vstack(
        hero("Image Resizer Pro",
             "Batch image processing tự động — dán/upload → chọn preset → START."),
        rx.heading("PRESET CÓ SẴN", size="4", margin_top="1em", font_font_weight="900",
                    letter_spacing="-0.01em"),
        rx.grid(
            rx.foreach(BatchState.preset_options, _preset_card),
            columns="3", spacing="4", width="100%",
        ),
        rx.heading("BẮT ĐẦU NHANH", size="4", margin_top="1.2em", font_font_weight="900"),
        rx.hstack(
            rx.button("💻 LOCAL", on_click=BatchState.set_active_mode("local"), size="3",
                      **bh.bauhaus_button(bg=bh.BLUE, shadow_px=4)),
            rx.button("🌐 DRIVE", on_click=BatchState.set_active_mode("drive"), size="3",
                      **bh.bauhaus_button(bg=bh.YELLOW, color=bh.INK, shadow_px=4)),
            rx.button("🛒 WEB/TGDD", on_click=BatchState.set_active_mode("web"), size="3",
                      **bh.bauhaus_button(bg=bh.RED, shadow_px=4)),
            spacing="3",
        ),
        rx.cond(
            BatchState.history.length() > 0,
            rx.vstack(
                rx.heading("LỊCH SỬ BATCH", size="4", margin_top="1.2em", font_font_weight="900"),
                rx.box(
                    rx.foreach(
                        BatchState.history,
                        lambda h: rx.hstack(
                            rx.box(
                                rx.text(h["mode"], size="1", font_font_weight="900",
                                         text_transform="uppercase"),
                                bg=bh.BLUE, color=bh.WHITE, border=f"2px solid {bh.INK}",
                                padding="0.15em 0.6em",
                            ),
                            rx.text(f"{h['success']}/{h['total']}", size="2", font_weight="700"),
                            rx.text(f"{h['duration']}s", size="1", color=bh.INK),
                            rx.text(h["at"], size="1", color=bh.INK),
                            spacing="3", align="center",
                            padding="0.4em 0", border_bottom=f"1px solid {bh.MUTED}",
                        ),
                    ),
                    width="100%",
                ),
                width="100%", align_items="start",
            ),
        ),
        spacing="3", width="100%", padding="1em",
    )


def render_web() -> rx.Component:
    return rx.vstack(
        hero("🛒 Thegioididong — scrape sản phẩm",
             "Dán link sản phẩm TGDD → scraper lấy tên, màu, ảnh gallery → tải song song → resize → ZIP."),
        rx.accordion.root(
            rx.accordion.item(
                header="🍪 Cookie TGDD (tuỳ chọn)",
                content=rx.vstack(
                    rx.text_area(
                        placeholder='[{"name":"_ga","value":"...","domain":".thegioididong.com"}]',
                        value=BatchState.web_cookie_text,
                        on_change=BatchState.set_web_cookie_text,
                        height="100px", width="100%",
                    ),
                    rx.hstack(
                        rx.button("💾 Nạp cookie", on_click=BatchState.load_cookie, size="2"),
                        rx.text(BatchState.web_cookie_status, size="1", color="gray"),
                        spacing="2",
                    ),
                    width="100%",
                ),
            ),
            collapsible=True, width="100%",
        ),
        preset_picker(),
        rx.text_area(
            placeholder="https://www.thegioididong.com/dtdd/iphone-16-pro-max\nhttps://www.thegioididong.com/sp-321654",
            value=BatchState.web_links,
            on_change=BatchState.set_web_links,
            height="110px", width="100%",
        ),
        input_report_bar(),
        rx.hstack(
            rx.button("🚀 START — SCRAPE & XỬ LÝ", on_click=BatchState.start_web_batch,
                      size="3", disabled=BatchState.is_batch_running,
                      **bh.bauhaus_button(bg=bh.RED, shadow_px=4)),
            rx.cond(BatchState.is_batch_running,
                    rx.button("⏹ HUỶ", on_click=BatchState.cancel_batch, size="3", **bh.bauhaus_button(bg=bh.INK, shadow_px=4))),
            spacing="3",
        ),
        error_banner(),
        rx.cond(
            BatchState.web_scrape_log.length() > 0,
            rx.box(
                rx.foreach(BatchState.web_scrape_log, lambda l: rx.text(l, size="1")),
                max_height="150px", overflow_y="auto", width="100%",
                bg="var(--gray-2)", padding="0.5em", border_radius="6px",
            ),
        ),
        batch_progress_panel(),
        run_outputs_panel(),
        batch_queue_view(),
        spacing="3", width="100%", padding="1em",
    )


def render_drive() -> rx.Component:
    return rx.vstack(
        hero("🌐 Google Drive — Folder & File",
             "Dán link Drive (folder chia sẻ hoặc file đơn) → tải song song → resize → ZIP."),
        preset_picker(),
        rx.text_area(
            placeholder="https://drive.google.com/drive/folders/ABC123\nhttps://drive.google.com/file/d/XYZ789",
            value=BatchState.drive_links,
            on_change=BatchState.set_drive_links,
            height="110px", width="100%",
        ),
        input_report_bar(),
        rx.hstack(
            rx.button("🚀 START — TẢI & XỬ LÝ", on_click=BatchState.start_drive_batch,
                      size="3", disabled=BatchState.is_batch_running,
                      **bh.bauhaus_button(bg=bh.RED, shadow_px=4)),
            rx.cond(BatchState.is_batch_running,
                    rx.button("⏹ HUỶ", on_click=BatchState.cancel_batch, size="3", **bh.bauhaus_button(bg=bh.INK, shadow_px=4))),
            spacing="3",
        ),
        error_banner(),
        batch_progress_panel(),
        run_outputs_panel(),
        batch_queue_view(),
        spacing="3", width="100%", padding="1em",
    )


def render_local() -> rx.Component:
    return rx.vstack(
        hero("💻 Local — Upload ZIP hoặc ảnh",
             "Kéo/chọn file (nhiều file cùng lúc) → tự giải nén ZIP → resize theo preset → xuất ZIP."),
        preset_picker(),
        rx.upload(
            rx.vstack(
                rx.text("Kéo thả file vào đây, hoặc bấm để chọn"),
                rx.text("Chấp nhận: .zip, .jpg, .jpeg, .png, .webp, .bmp, .gif", size="1", color="gray"),
            ),
            id="local_upload",
            multiple=True,
            border="1px dashed var(--gray-8)",
            padding="2em",
            width="100%",
            on_drop=BatchState.handle_local_upload(rx.upload_files(upload_id="local_upload")),
        ),
        rx.cond(
            BatchState.local_upload_names.length() > 0,
            rx.box(
                rx.foreach(BatchState.local_upload_names, lambda n: rx.text(f"📄 {n}", size="1")),
                width="100%",
            ),
        ),
        rx.hstack(
            rx.button("🚀 START — XỬ LÝ & TẢI KẾT QUẢ", on_click=BatchState.start_local_batch,
                      size="3", disabled=BatchState.is_batch_running,
                      **bh.bauhaus_button(bg=bh.RED, shadow_px=4)),
            rx.cond(BatchState.is_batch_running,
                    rx.button("⏹ HUỶ", on_click=BatchState.cancel_batch, size="3", **bh.bauhaus_button(bg=bh.INK, shadow_px=4))),
            spacing="3",
        ),
        error_banner(),
        batch_progress_panel(),
        run_outputs_panel(),
        batch_queue_view(),
        spacing="3", width="100%", padding="1em",
    )


def _studio_status_badge(status) -> rx.Component:
    return rx.badge(
        rx.match(
            status,
            ("adjusted", "🎯 Đã chỉnh"),
            ("rendered", "✅ Đã render"),
            "📷 Chưa render",
        ),
        color_scheme=rx.match(
            status,
            ("adjusted", "pink"),
            ("rendered", "green"),
            "gray",
        ),
    )


def _studio_item_card(item: rx.Var) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.checkbox(
                    checked=item["selected"],
                    on_change=lambda _: StudioState.toggle_select(item["id"]),
                ),
                rx.text(item["product"], weight="bold", size="2", no_of_lines=1),
                rx.text("·", color="gray"),
                rx.text(item["original_name"], size="2", color="gray", no_of_lines=1),
                rx.spacer(),
                _studio_status_badge(item["status"]),
                rx.cond(
                    item["is_small"],
                    rx.badge("⚠ Ảnh nhỏ", color_scheme="pink"),
                ),
                width="100%", spacing="2",
            ),
            rx.hstack(
                rx.vstack(
                    rx.cond(
                        item["preview_b64"] != "",
                        rx.image(src=rx.Var.create("data:image/jpeg;base64,") + item["preview_b64"].to(str),
                                  max_width="220px", border_radius="8px"),
                        rx.box(rx.text("⚠️ Không có preview", size="1", color="red"),
                               width="220px", height="140px"),
                    ),
                    rx.text(f"📐 {item['source_width']}×{item['source_height']} · "
                            f"💾 {item['source_size_bytes']}", size="1", color="gray"),
                    width="35%", spacing="1",
                ),
                rx.vstack(
                    rx.hstack(
                        rx.text("Scale", size="1"), rx.spacer(),
                        rx.text(item["scale"].to_string() + "%", size="1", weight="bold"),
                        width="100%",
                    ),
                    rx.slider(min=60, max=200, value=[item["scale"]],
                              on_change=lambda v: StudioState.set_item_scale(item["id"], v),
                              width="100%"),
                    rx.hstack(
                        rx.text("X", size="1"), rx.spacer(),
                        rx.text(item["offset_x"].to_string(), size="1", weight="bold"),
                        width="100%",
                    ),
                    rx.slider(min=-100, max=100, value=[item["offset_x"]],
                              on_change=lambda v: StudioState.set_item_x(item["id"], v),
                              width="100%"),
                    rx.hstack(
                        rx.text("Y", size="1"), rx.spacer(),
                        rx.text(item["offset_y"].to_string(), size="1", weight="bold"),
                        width="100%",
                    ),
                    rx.slider(min=-100, max=100, value=[item["offset_y"]],
                              on_change=lambda v: StudioState.set_item_y(item["id"], v),
                              width="100%"),
                    rx.hstack(
                        rx.button("↺ Reset", on_click=StudioState.reset_item(item["id"]),
                                  size="1", variant="soft"),
                        rx.button("➖5%", on_click=StudioState.nudge_item(item["id"], -5),
                                  size="1", variant="soft"),
                        rx.button("➕5%", on_click=StudioState.nudge_item(item["id"], 5),
                                  size="1", variant="soft"),
                        spacing="2",
                    ),
                    width="65%", spacing="2",
                ),
                width="100%", spacing="3",
            ),
            spacing="2", width="100%",
        ),
        border=rx.cond(item["selected"], "1.5px solid var(--violet-8)", "1px solid var(--gray-4)"),
        border_radius="12px",
        box_shadow="0 1px 3px rgba(0,0,0,0.04)",
        bg=rx.cond(item["selected"], "var(--violet-2)", "var(--gray-1)"),
        width="100%",
    )


def _studio_pagination() -> rx.Component:
    return rx.hstack(
        rx.button("⏮", on_click=StudioState.go_first_page,
                  disabled=StudioState.page <= 1, size="2", variant="soft"),
        rx.button("◀", on_click=StudioState.go_prev_page,
                  disabled=StudioState.page <= 1, size="2", variant="soft"),
        rx.text(f"Trang {StudioState.page} / {StudioState.total_pages}", size="2", weight="medium"),
        rx.button("▶", on_click=StudioState.go_next_page,
                  disabled=StudioState.page >= StudioState.total_pages, size="2", variant="soft"),
        rx.button("⏭", on_click=StudioState.go_last_page,
                  disabled=StudioState.page >= StudioState.total_pages, size="2", variant="soft"),
        rx.text(f"· {StudioState.filtered_count} ảnh · {StudioState.per_page}/trang",
                size="1", color="gray"),
        spacing="3", align="center", justify="center", wrap="wrap",
        padding="0.5em", bg="var(--gray-2)", border_radius="999px",
    )


def render_studio() -> rx.Component:
    return rx.vstack(
        hero("🎚 Studio Scale — chỉnh scale/pan hàng loạt",
             "Nạp batch vừa chạy → lọc/phân trang → chỉnh scale%/X/Y từng ảnh hoặc "
             "hàng loạt → render → xuất ZIP gộp (ảnh đã chỉnh + ảnh gốc)."),
        rx.hstack(
            rx.button("🔄 Nạp batch gần nhất", on_click=StudioState.load_from_last_batch,
                      color_scheme="red", size="2"),
            spacing="2",
        ),
        error_banner_studio(),
        rx.cond(
            StudioState.loaded & (StudioState.total_count > 0),
            rx.vstack(
                # ── KPI ──
                rx.hstack(
                    stat_pill("Batch", StudioState.meta["batch_id"], "gray"),
                    stat_pill("Tổng", StudioState.total_count, "gray"),
                    stat_pill("Đang chọn", StudioState.selected_count, "green"),
                    stat_pill("Ảnh nhỏ", StudioState.small_count, "pink"),
                    rx.hstack(
                        rx.text("Canvas", size="1", color="gray"),
                        rx.badge(StudioState.canvas_w.to_string() + "×" + StudioState.canvas_h.to_string(),
                                  color_scheme="red", variant="soft"),
                        spacing="1", align="center",
                    ),
                    spacing="4", wrap="wrap",
                    padding="0.75em 1em",
                    bg="var(--gray-2)",
                    border="1px solid var(--gray-4)",
                    border_radius="10px",
                    width="100%",
                ),
                # ── Filters ──
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.box(width="4px", height="18px", bg="var(--violet-9)", border_radius="2px"),
                            rx.text("Bộ lọc", weight="bold", size="2"),
                            spacing="2", align="center",
                        ),
                        rx.hstack(
                            rx.input(placeholder="Tìm nhanh (tên, màu...)",
                                      value=StudioState.search_kw,
                                      on_change=StudioState.set_search_kw, width="35%"),
                            rx.select(StudioState.product_names, value=StudioState.filter_product,
                                      on_change=StudioState.set_filter_product, width="20%"),
                            rx.select(
                                ["Tất cả", "Chỉ ảnh đã chọn sửa", "Chỉ ảnh chưa chọn",
                                 "Chỉ ảnh nhỏ (bị giãn)"],
                                value=StudioState.filter_status,
                                on_change=StudioState.set_filter_status, width="25%",
                            ),
                            rx.select(["6", "10", "16", "24"],
                                      value=StudioState.per_page.to_string(),
                                      on_change=StudioState.set_per_page, width="10%"),
                            spacing="2", width="100%", wrap="wrap",
                        ),
                        width="100%", spacing="2",
                    ),
                    border="1px solid var(--gray-4)", border_radius="12px", box_shadow="0 1px 4px rgba(0,0,0,0.05)", width="100%",
                ),
                # ── Bulk ops ──
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.box(width="4px", height="18px", bg="var(--pink-9)", border_radius="2px"),
                            rx.text("Thao tác hàng loạt", weight="bold", size="2"),
                            spacing="2", align="center",
                        ),
                        rx.hstack(
                            rx.button("☑️ Chọn tất cả (lọc)", on_click=StudioState.select_all_filtered, size="2"),
                            rx.button("⬜ Bỏ chọn tất cả (lọc)", on_click=StudioState.deselect_all_filtered, size="2"),
                            rx.button("⚠️ Chọn ảnh nhỏ", on_click=StudioState.select_all_small, size="2"),
                            rx.button("🧹 Xoá hết chọn", on_click=StudioState.clear_all_selection, size="2"),
                            spacing="2", wrap="wrap",
                        ),
                        rx.hstack(
                            rx.vstack(
                                rx.text(f"Scale {StudioState.bulk_scale}%", size="1"),
                                rx.slider(min=60, max=200, value=[StudioState.bulk_scale],
                                          on_change=StudioState.set_bulk_scale, width="100%"),
                                width="33%",
                            ),
                            rx.vstack(
                                rx.text(f"X {StudioState.bulk_x}", size="1"),
                                rx.slider(min=-100, max=100, value=[StudioState.bulk_x],
                                          on_change=StudioState.set_bulk_x, width="100%"),
                                width="33%",
                            ),
                            rx.vstack(
                                rx.text(f"Y {StudioState.bulk_y}", size="1"),
                                rx.slider(min=-100, max=100, value=[StudioState.bulk_y],
                                          on_change=StudioState.set_bulk_y, width="100%"),
                                width="33%",
                            ),
                            width="100%", spacing="3",
                        ),
                        rx.hstack(
                            rx.button("⚡ Áp dụng trang hiện tại", on_click=StudioState.apply_bulk_current_page,
                                      color_scheme="red", size="2"),
                            rx.button("⚡⚡ Áp dụng toàn bộ (lọc)", on_click=StudioState.apply_bulk_all_filtered,
                                      color_scheme="red", size="2"),
                            spacing="2",
                        ),
                        width="100%", spacing="3",
                    ),
                    border="1px solid var(--gray-4)", border_radius="12px", box_shadow="0 1px 4px rgba(0,0,0,0.05)", bg="var(--violet-2)",
                    width="100%",
                ),
                # ── Item grid + pagination ──
                _studio_pagination(),
                rx.vstack(
                    rx.foreach(StudioState.page_items, _studio_item_card),
                    width="100%", spacing="3",
                ),
                _studio_pagination(),
                # ── Export panel ──
                rx.card(
                    rx.vstack(
                        rx.heading("🚀 Xuất file & tải về", size="4", color="var(--violet-11)"),
                        rx.text("Bước 1: Render ảnh đã chọn → Bước 2: Tạo ZIP gộp → Bước 3: Tải về.",
                                size="2", color="gray"),
                        rx.hstack(
                            rx.button(
                                f"🎨 Render {StudioState.selected_count} ảnh đã chọn",
                                on_click=StudioState.render_selected, color_scheme="red", size="3",
                                disabled=(StudioState.selected_count == 0) | StudioState.is_rendering,
                                loading=StudioState.is_rendering,
                            ),
                            rx.button(
                                "📦 Tạo ZIP gộp (đã chỉnh + gốc)",
                                on_click=StudioState.export_zip, color_scheme="red", size="3",
                                loading=StudioState.is_exporting,
                            ),
                            spacing="3", wrap="wrap",
                        ),
                        rx.cond(
                            StudioState.is_rendering,
                            rx.vstack(
                                rx.progress(value=StudioState.render_progress_pct, max=100, width="100%"),
                                rx.text(f"▶ {StudioState.render_current_name}", size="1", color="gray"),
                                width="100%", spacing="1",
                            ),
                        ),
                        rx.cond(StudioState.render_done_msg != "",
                                rx.callout(StudioState.render_done_msg, color_scheme="green")),
                        rx.cond(
                            StudioState.render_errors.length() > 0,
                            rx.box(
                                rx.foreach(StudioState.render_errors,
                                           lambda e: rx.text(f"• {e}", size="1", color="red")),
                                max_height="150px", overflow_y="auto", width="100%",
                            ),
                        ),
                        rx.cond(StudioState.export_msg != "",
                                rx.callout(StudioState.export_msg, color_scheme="green")),
                        rx.hstack(
                            rx.button(
                                rx.cond(StudioState.zip_orig_size != "",
                                        f"⬇️ ZIP Gốc ({StudioState.zip_orig_size})", "⬇️ ZIP Gốc"),
                                on_click=StudioState.download_zip_original, size="2",
                                disabled=StudioState.zip_orig_path == "",
                            ),
                            rx.button(
                                rx.cond(StudioState.zip_merged_size != "",
                                        f"⬇️ ZIP Gộp — Đã chỉnh ({StudioState.zip_merged_size})",
                                        "⬇️ ZIP Gộp — Đã chỉnh"),
                                on_click=StudioState.download_zip_merged, color_scheme="red", size="2",
                                disabled=StudioState.zip_merged_path == "",
                            ),
                            spacing="3", wrap="wrap",
                        ),
                        width="100%", spacing="3",
                    ),
                    border="1px solid var(--gray-4)", border_radius="12px", box_shadow="0 1px 4px rgba(0,0,0,0.05)", bg="linear-gradient(135deg, var(--violet-2), var(--pink-2))",
                    width="100%",
                ),
                width="100%", spacing="4",
            ),
        ),
        spacing="3", width="100%", padding="1em",
    )

def render_guide() -> rx.Component:
    return rx.vstack(
        hero("📚 Hướng dẫn", ""),
        rx.markdown("""
### Nguyên tắc
1. **Chọn tab** phù hợp nguồn ảnh: Local (upload ZIP/ảnh), Drive (link Google Drive), Web (link TGDD).
2. **Chọn preset** — mọi cấu hình (kích thước, chất lượng, format, tên) đã gói sẵn.
3. Bấm **START**. Hệ thống chạy tự động ở nền: validate → dedup → download → retry (3 lần backoff) → resize → rename → ZIP → CSV report.

### Anti-OOM
- Ảnh > 120 MP hoặc > 60 MB bị từ chối thay vì làm crash app.
- Số worker resize/download tự điều chỉnh theo RAM còn trống.
- Nếu đĩa còn < 150 MB, batch mới sẽ bị chặn — dùng nút "Dọn workspace cũ" ở sidebar.

### Retry logic
- Timeout / connection error → retry 3 lần (1s, 3.5s, 6s).
- Permission denied, invalid URL, invalid image → KHÔNG retry.

### Report CSV
Sau mỗi batch có nút "Tải Report CSV" gồm mọi item: status, error_type, error_message, kích thước, thời gian xử lý.
        """),
        spacing="3", width="100%", padding="1em",
    )


def _user_card(u) -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.text(u["username"], weight="bold"),
                    rx.badge(u["role"], color_scheme=rx.cond(u["role"] == "admin", "violet", "gray")),
                    rx.badge(u["status"], color_scheme=rx.match(
                        u["status"], ("approved", "green"), ("pending", "amber"), ("banned", "red"), "gray")),
                ),
                rx.text(f"Quyền: {u['permissions_label']}", size="1", color="gray"),
                rx.text(f"Ghi chú: {u['note']}", size="1", color="gray"),
                rx.text(f"Tạo lúc: {u['created_at']}", size="1", color="gray"),
                align_items="start", spacing="1",
            ),
            rx.spacer(),
            rx.cond(
                u["username"] != "ducpro",
                rx.button("Sửa", on_click=AdminState.start_edit(u["username"]), size="2"),
            ),
            width="100%",
        ),
        width="100%",
    )


def render_admin() -> rx.Component:
    return rx.vstack(
        hero("👑 Admin Panel", "Duyệt, phân quyền, khóa/mở/xóa tài khoản."),
        rx.hstack(
            rx.button("🔄 Pull GitHub", on_click=AdminState.pull_github, size="2"),
            rx.button("⬆️ Push GitHub", on_click=AdminState.push_github, size="2", variant="soft"),
            spacing="2",
        ),
        rx.cond(AdminState.sync_msg != "", rx.text(AdminState.sync_msg, size="2", color="green")),
        rx.input(placeholder="🔍 Tìm tài khoản...", value=AdminState.search,
                  on_change=AdminState.set_search, width="100%"),
        rx.foreach(AdminState.users, _user_card),
        rx.cond(
            AdminState.edit_username != "",
            rx.card(
                rx.vstack(
                    rx.heading(f"Sửa: {AdminState.edit_username}", size="3"),
                    rx.select(["approved", "pending", "banned"], value=AdminState.edit_status,
                              on_change=AdminState.set_edit_status),
                    rx.hstack(
                        rx.foreach(
                            AdminState.all_permissions,
                            lambda perm: rx.checkbox(
                                perm,
                                checked=AdminState.edit_permissions.contains(perm),
                                on_change=lambda _: AdminState.toggle_edit_permission(perm),
                            ),
                        ),
                        spacing="3", wrap="wrap",
                    ),
                    rx.input(placeholder="Ghi chú", value=AdminState.edit_note,
                              on_change=AdminState.set_edit_note, width="100%"),
                    rx.hstack(
                        rx.button("💾 Lưu", on_click=AdminState.save_edit, color_scheme="red"),
                        rx.button("🗑 Xoá", on_click=AdminState.delete_edit_user, color_scheme="red",
                                  variant="soft"),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.input(placeholder="Mật khẩu mới (>= 4 ký tự)", type="password",
                                  value=AdminState.edit_new_password,
                                  on_change=AdminState.set_edit_new_password),
                        rx.button("🔑 Reset mật khẩu", on_click=AdminState.reset_edit_password),
                        spacing="2",
                    ),
                    spacing="3", width="100%",
                ),
                width="100%",
            ),
        ),
        spacing="3", width="100%", padding="1em",
        on_mount=AdminState.load_users,
    )
