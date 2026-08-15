"""
components/ui.py — thành phần UI dùng chung: sidebar, header, progress panel,
queue table. Thay thế ui/theme.py + ui/components.py (Streamlit) bằng
rx.* + Tailwind (Reflex build-in), không cần CSS injection thủ công.
"""
from __future__ import annotations

import reflex as rx

from ..backend.auth_state import AuthState
from ..backend.batch_state import BatchState
from ..backend.studio_state import StudioState
from . import bauhaus as bh


def status_color(status: str) -> str:
    return rx.match(
        status,
        ("SUCCESS", "green"),
        ("FAILED", "red"),
        ("RUNNING", "blue"),
        ("RETRYING", "amber"),
        ("CANCELLED", "gray"),
        ("SKIPPED", "gray"),
        "gray",
    )


_STAT_COLOR_MAP = {
    "gray": bh.MUTED, "blue": bh.BLUE, "green": "#2E8B3D", "red": bh.RED, "amber": bh.YELLOW,
}


def stat_pill(label: str, value: rx.Var, color: str = "gray") -> rx.Component:
    bg = _STAT_COLOR_MAP.get(color, bh.MUTED)
    text_color = bh.WHITE if color in ("blue", "green", "red") else bh.INK
    return rx.hstack(
        rx.text(label, size="1", color=bh.INK, font_weight="700", text_transform="uppercase"),
        rx.box(
            rx.text(value.to_string(), size="1", font_font_weight="900"),
            bg=bg, color=text_color, border=f"2px solid {bh.INK}", padding="0.1em 0.55em",
        ),
        spacing="1",
        align="center",
    )


def _geo_logo(size: str = "42px") -> rx.Component:
    """Logo hình học Bauhaus: hình tròn (đỏ) + hình vuông (vàng) chồng lên
    hình vuông nền xanh — thay cho chữ 'M' gradient trước đây."""
    return rx.box(
        rx.box(position="absolute", top="0", left="0", width="100%", height="100%",
               bg=bh.BLUE, border=f"2px solid {bh.INK}"),
        rx.box(position="absolute", bottom="-4px", right="-4px", width="52%", height="52%",
               bg=bh.YELLOW, border=f"2px solid {bh.INK}"),
        rx.box(position="absolute", top="-4px", left="-4px", width="46%", height="46%",
               bg=bh.RED, border=f"2px solid {bh.INK}", border_radius="9999px"),
        position="relative", width=size, height=size, margin="4px",
    )


def top_header() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            _geo_logo(),
            rx.vstack(
                rx.heading(
                    "MEDIA TOOL PRO",
                    size="4",
                    color=bh.INK,
                    font_font_weight="900",
                    letter_spacing="-0.02em",
                    text_transform="uppercase",
                ),
                rx.text("BATCH IMAGE PROCESSING", size="1", color=bh.INK,
                         font_weight="700", letter_spacing="0.08em"),
                spacing="0",
            ),
            spacing="3", align="center",
        ),
        rx.spacer(),
        rx.hstack(
            rx.color_mode.button(),
            rx.box(
                rx.text(AuthState.user_username, size="1", font_weight="700",
                         text_transform="uppercase"),
                bg=bh.YELLOW, border=f"2px solid {bh.INK}", padding="0.25em 0.7em",
            ),
            rx.box(
                rx.text(AuthState.user_role, size="1", font_weight="700",
                         text_transform="uppercase"),
                bg=bh.WHITE, border=f"2px solid {bh.INK}", padding="0.25em 0.7em",
            ),
            rx.button("ĐĂNG XUẤT", on_click=AuthState.do_logout, size="2",
                      **bh.bauhaus_button(bg=bh.RED, shadow_px=3)),
            spacing="3", align="center",
        ),
        width="100%", padding="0.85em 1.6em",
        bg=bh.BG,
        border_bottom=f"4px solid {bh.INK}",
        align="center",
        position="sticky", top="0", z_index="100",
    )


NAV_ITEMS = [
    ("home", "🏠 Home"),
    ("web", "🛒 Web/TGDD"),
    ("drive", "🌐 Drive"),
    ("local", "💻 Local"),
    ("studio", "🎨 Studio"),
    ("guide", "📚 Guide"),
]


def sidebar_nav() -> rx.Component:
    def nav_btn(key: str, label: str, accent: str = bh.RED) -> rx.Component:
        on_click = (
            [BatchState.set_active_mode(key), StudioState.load_from_last_batch]
            if key == "studio" else BatchState.set_active_mode(key)
        )
        is_active = BatchState.active_mode == key
        return rx.button(
            label,
            on_click=on_click,
            variant="ghost",
            width="100%",
            justify="start",
            size="3",
            border_radius="0",
            font_weight="700",
            text_transform="uppercase",
            letter_spacing="0.02em",
            color=rx.cond(is_active, "white", bh.INK),
            bg=rx.cond(is_active, accent, "transparent"),
            border=rx.cond(is_active, f"2px solid {bh.INK}", "2px solid transparent"),
            box_shadow=rx.cond(is_active, bh.hard_shadow(3), "none"),
            style={"transition": "all 0.12s ease-out", "_hover": {
                "background": rx.cond(is_active, accent, bh.MUTED),
            }},
        )

    items = [nav_btn(k, v, bh.ACCENTS[i % 3]) for i, (k, v) in enumerate(NAV_ITEMS)]
    return rx.vstack(
        *items,
        rx.cond(
            AuthState.is_admin,
            nav_btn("admin", "🔐 Admin", bh.INK),
        ),
        rx.box(height="4px", width="100%", bg=bh.INK, margin_y="0.6em"),
        rx.text("CÀI ĐẶT", size="1", weight="bold", color=bh.INK,
                 letter_spacing="0.1em", text_transform="uppercase"),
        rx.box(
            rx.hstack(rx.text("⚡ ONE-CLICK", size="1", font_weight="700"),
                      rx.spacer(),
                      rx.switch(checked=BatchState.one_click_mode,
                                on_change=BatchState.set_one_click_mode, color_scheme="red"),
                      width="100%"),
            rx.hstack(rx.text("📦 AUTO ZIP", size="1", font_weight="700"),
                      rx.spacer(),
                      rx.switch(checked=BatchState.auto_zip, on_change=BatchState.set_auto_zip,
                                color_scheme="red"),
                      width="100%", margin_top="0.5em"),
            rx.hstack(rx.text("📊 AUTO REPORT", size="1", font_weight="700"),
                      rx.spacer(),
                      rx.switch(checked=BatchState.auto_report, on_change=BatchState.set_auto_report,
                                color_scheme="red"),
                      width="100%", margin_top="0.5em"),
            width="100%", padding="0.7em 0.6em",
            bg=bh.MUTED, border=f"2px solid {bh.INK}",
        ),
        rx.box(height="4px", width="100%", bg=bh.INK, margin_y="0.6em"),
        rx.button("🧹 DỌN WORKSPACE CŨ", on_click=BatchState.cleanup_workspace,
                  width="100%", size="2", **bh.bauhaus_button(bg=bh.WHITE, color=bh.INK, shadow_px=3)),
        rx.cond(BatchState.cleanup_msg != "", rx.text(BatchState.cleanup_msg, size="1", color="green")),
        spacing="2", width="228px", padding="1.1em",
        bg=bh.BG,
        border_right=f"4px solid {bh.INK}",
        min_height="100%",
        align_items="stretch",
    )


def preset_picker() -> rx.Component:
    """Multi-select preset — tick nhiều preset để 1 ảnh xuất ra NHIỀU
    kích thước khác nhau trong cùng 1 lần chạy (mỗi preset ra 1 zip riêng)."""
    return rx.vstack(
        rx.hstack(
            rx.text("PRESET (TICK ĐỂ CHẠY NHIỀU SIZE CÙNG LÚC)", font_weight="700", size="2",
                     text_transform="uppercase", letter_spacing="0.02em"),
            rx.spacer(),
            rx.box(
                rx.text(BatchState.selected_presets.length().to_string(), " ĐÃ CHỌN",
                         size="1", font_font_weight="900"),
                bg=bh.YELLOW, border=f"2px solid {bh.INK}", padding="0.15em 0.6em",
            ),
            width="100%", align="center",
        ),
        rx.box(
            rx.foreach(
                BatchState.preset_options,
                lambda p: rx.hstack(
                    rx.checkbox(
                        checked=BatchState.selected_presets.contains(p["name"]),
                        on_change=lambda _: BatchState.toggle_preset_selected(p["name"]),
                        color_scheme="red",
                    ),
                    rx.vstack(
                        rx.text(p["name"], size="2", font_weight="700"),
                        rx.text(f"{p['description']} · {p['sizes']}", size="1", color=bh.INK),
                        spacing="0", align="start",
                    ),
                    spacing="2", align="center", width="100%",
                    padding="0.4em 0.3em",
                    border_bottom=f"2px solid {bh.MUTED}",
                ),
            ),
            width="100%", max_height="220px", overflow_y="auto",
            bg=bh.WHITE, border=f"3px solid {bh.INK}", padding="0.25em 0.5em",
        ),
        scale_slider(),
        custom_size_form(),
        width="100%", spacing="2",
    )


def scale_slider() -> rx.Component:
    """Thanh 'Scale %' thủ công (60-200%, mặc định 100) — cho phép người
    dùng chủ động phóng to/thu nhỏ thêm mọi ảnh trong lượt chạy này, tương
    tự slider Scale % ở bản Streamlit cũ (mode_adjust.py). Độc lập với phần
    tự-phóng-to giới hạn 1.6x trong core/imaging.py — cái đó chỉ bù cho ảnh
    quá nhỏ so với khung, còn thanh này là điều chỉnh chủ động của người dùng."""
    return rx.box(
        rx.hstack(
            rx.text("🔍 SCALE % (PHÓNG/THU ẢNH THỦ CÔNG)", size="1", font_weight="700",
                     text_transform="uppercase"),
            rx.spacer(),
            rx.box(
                rx.text(BatchState.run_scale_pct.to_string(), "%", size="1", font_font_weight="900"),
                bg=bh.WHITE, border=f"2px solid {bh.INK}", padding="0.1em 0.5em",
            ),
            rx.button("RESET", on_click=BatchState.reset_run_scale_pct,
                      size="1", variant="ghost", color=bh.INK, font_weight="700"),
            width="100%", align="center",
        ),
        rx.slider(
            min=60, max=200, step=5,
            value=[BatchState.run_scale_pct],
            on_change=BatchState.set_run_scale_pct,
            color_scheme="red", width="100%", margin_top="0.4em",
        ),
        rx.hstack(
            rx.text("60%", size="1", color=bh.INK, font_weight="700"),
            rx.spacer(),
            rx.text("100%", size="1", color=bh.INK, font_weight="700"),
            rx.spacer(),
            rx.text("200%", size="1", color=bh.INK, font_weight="700"),
            width="100%",
        ),
        width="100%", padding="0.7em 0.9em", margin_top="0.3em",
        bg=bh.YELLOW, border=f"3px solid {bh.INK}", box_shadow=bh.hard_shadow(4),
    )


def custom_size_form() -> rx.Component:
    """Cho phép tự thêm 1 preset kích thước tuỳ ý (WxH + kiểu resize)."""
    return rx.accordion.root(
        rx.accordion.item(
            header="➕ TỰ THÊM SIZE MỚI",
            content=rx.vstack(
                rx.hstack(
                    rx.input(placeholder="Tên (tuỳ chọn)", value=BatchState.custom_name,
                              on_change=BatchState.set_custom_name, size="2", width="40%"),
                    rx.input(placeholder="Width", value=BatchState.custom_width,
                              on_change=BatchState.set_custom_width, size="2", width="20%",
                              type="number"),
                    rx.input(placeholder="Height", value=BatchState.custom_height,
                              on_change=BatchState.set_custom_height, size="2", width="20%",
                              type="number"),
                    spacing="2", width="100%",
                ),
                rx.select(
                    ["letterbox", "crop_1000", "keep"],
                    value=BatchState.custom_mode,
                    on_change=BatchState.set_custom_mode,
                    size="2",
                ),
                rx.text(
                    "letterbox = giữ nguyên tỉ lệ, thêm nền trắng · "
                    "crop_1000 = crop giữa thành hình vuông · keep = không resize",
                    size="1", color=bh.INK,
                ),
                rx.button("THÊM PRESET", on_click=BatchState.add_custom_preset, size="2",
                          **bh.bauhaus_button(bg=bh.BLUE, shadow_px=3)),
                rx.cond(BatchState.custom_msg != "",
                        rx.text(BatchState.custom_msg, size="1", color=bh.INK)),
                spacing="2", width="100%", padding_top="0.5em",
            ),
            border=f"2px solid {bh.INK}",
        ),
        collapsible=True, width="100%",
    )


def input_report_bar() -> rx.Component:
    r = BatchState.input_report

    def _pill(label: str, val, bg: str, color: str = bh.WHITE) -> rx.Component:
        return rx.box(
            rx.text(label, val.to_string(), size="1", font_font_weight="900",
                     text_transform="uppercase"),
            bg=bg, color=color, border=f"2px solid {bh.INK}", padding="0.2em 0.6em",
        )

    return rx.hstack(
        _pill("TỔNG ", r["raw"], bh.MUTED, bh.INK),
        _pill("HỢP LỆ ", r["valid"], "#2E8B3D"),
        _pill("TRÙNG ", r["dup"], bh.YELLOW, bh.INK),
        _pill("KHÔNG HỖ TRỢ ", r["invalid"], bh.RED),
        spacing="2", wrap="wrap",
    )


def batch_progress_panel() -> rx.Component:
    return rx.cond(
        BatchState.batch_total > 0,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.text("BATCH:", font_weight="900", size="2", text_transform="uppercase"),
                    rx.box(
                        rx.text(BatchState.batch_state_label, size="1", font_font_weight="900"),
                        bg=bh.BLUE, color=bh.WHITE, border=f"2px solid {bh.INK}", padding="0.15em 0.6em",
                    ),
                    rx.spacer(),
                    rx.text(f"{BatchState.batch_duration_s}s", size="2", color=bh.INK, font_weight="700"),
                    width="100%",
                ),
                rx.progress(value=BatchState.batch_progress_pct, max=100, width="100%",
                             color_scheme="red"),
                rx.hstack(
                    stat_pill("Tổng", BatchState.batch_total, "gray"),
                    stat_pill("Đang chạy", BatchState.batch_running_n, "blue"),
                    stat_pill("Thành công", BatchState.batch_success, "green"),
                    stat_pill("Thất bại", BatchState.batch_failed, "red"),
                    stat_pill("Retry", BatchState.batch_retrying, "amber"),
                    stat_pill("Huỷ", BatchState.batch_cancelled, "gray"),
                    stat_pill("Bỏ qua", BatchState.batch_skipped, "gray"),
                    spacing="4", wrap="wrap",
                ),
                rx.cond(
                    BatchState.batch_current_item != "",
                    rx.text(f"▶ {BatchState.batch_current_item} · {BatchState.batch_current_op}",
                            size="2", color=bh.INK, font_weight="700"),
                ),
                rx.cond(
                    BatchState.is_batch_running,
                    rx.button("⏹ HUỶ BATCH", on_click=BatchState.cancel_batch, size="2",
                              **bh.bauhaus_button(bg=bh.RED, shadow_px=3)),
                ),
                rx.hstack(
                    rx.cond(BatchState.batch_zip_ready,
                            rx.button("⬇ TẢI ZIP", on_click=BatchState.download_zip, size="2",
                                      **bh.bauhaus_button(bg=bh.BLUE, shadow_px=3))),
                    rx.cond(BatchState.batch_report_ready,
                            rx.button("⬇ TẢI REPORT CSV", on_click=BatchState.download_report, size="2",
                                      **bh.bauhaus_button(bg=bh.WHITE, color=bh.INK, shadow_px=3))),
                    spacing="2",
                ),
                rx.cond(
                    BatchState.batch_log_tail.length() > 0,
                    rx.box(
                        rx.foreach(BatchState.batch_log_tail,
                                   lambda ln: rx.text(ln, size="1", color=bh.INK, font_family="monospace")),
                        max_height="160px", overflow_y="auto", width="100%",
                        bg=bh.MUTED, padding="0.5em", border=f"2px solid {bh.INK}",
                    ),
                ),
                spacing="3", width="100%",
            ),
            width="100%", **bh.bauhaus_card(),
            padding="1.1em",
        ),
    )


def run_outputs_panel() -> rx.Component:
    """Danh sách zip/report của TỪNG preset (hoặc từng đợt-chunk drive) đã
    xong trong lượt chạy vừa rồi — quan trọng khi chạy multi-preset vì nút
    "Tải ZIP" ở batch_progress_panel chỉ giữ file của lượt CUỐI CÙNG."""
    return rx.cond(
        BatchState.run_outputs.length() > 1,
        rx.box(
            rx.vstack(
                rx.text("KẾT QUẢ THEO TỪNG PRESET", font_weight="900", size="2",
                         text_transform="uppercase"),
                rx.foreach(
                    BatchState.run_outputs,
                    lambda o, i: rx.hstack(
                        rx.vstack(
                            rx.text(o["label"], size="2", font_weight="700"),
                            rx.text(f"{o['success']}/{o['total']} ảnh thành công",
                                    size="1", color=bh.INK),
                            spacing="0", align="start",
                        ),
                        rx.spacer(),
                        rx.button("⬇ ZIP", on_click=BatchState.download_output_zip(i), size="1",
                                  **bh.bauhaus_button(bg=bh.BLUE, shadow_px=2)),
                        rx.button("⬇ CSV", on_click=BatchState.download_output_report(i), size="1",
                                  **bh.bauhaus_button(bg=bh.WHITE, color=bh.INK, shadow_px=2)),
                        width="100%", align="center", spacing="2",
                        padding="0.4em 0.3em", border_bottom=f"2px solid {bh.MUTED}",
                    ),
                ),
                width="100%", spacing="2",
            ),
            width="100%", **bh.bauhaus_card(),
            padding="1.1em",
        ),
    )


def batch_queue_view() -> rx.Component:
    def _status_box(status: rx.Var) -> rx.Component:
        return rx.box(
            rx.text(status, size="1", font_font_weight="900"),
            bg=rx.match(
                status,
                ("SUCCESS", "#2E8B3D"), ("FAILED", bh.RED), ("RUNNING", bh.BLUE),
                ("RETRYING", bh.YELLOW), bh.MUTED,
            ),
            color=rx.match(
                status,
                ("SUCCESS", bh.WHITE), ("FAILED", bh.WHITE), ("RUNNING", bh.WHITE),
                ("RETRYING", bh.INK), bh.INK,
            ),
            border=f"2px solid {bh.INK}", padding="0.1em 0.5em", display="inline-block",
        )

    return rx.cond(
        BatchState.queue_rows.length() > 0,
        rx.box(
            rx.vstack(
                rx.text("QUEUE", font_weight="900", size="2", text_transform="uppercase"),
                rx.box(
                    rx.foreach(
                        BatchState.queue_rows,
                        lambda row: rx.hstack(
                            rx.text(row["name"], size="2", no_of_lines=1, width="35%", font_weight="500"),
                            rx.text(row["group"], size="1", color=bh.INK, width="25%"),
                            _status_box(row["status"]),
                            rx.cond(row["error"] != "", rx.text(row["error"], size="1", color=bh.RED)),
                            width="100%", spacing="2", align="center",
                            padding="0.3em 0",
                            border_bottom=f"1px solid {bh.MUTED}",
                        ),
                    ),
                    max_height="300px", overflow_y="auto", width="100%",
                ),
                width="100%", spacing="2",
            ),
            width="100%", **bh.bauhaus_card(),
            padding="1.1em",
        ),
    )


def error_banner() -> rx.Component:
    return rx.cond(
        BatchState.batch_error_msg != "",
        rx.box(
            rx.hstack(
                rx.text("⚠", size="4"),
                rx.text(BatchState.batch_error_msg, size="2", font_weight="700"),
                spacing="2", align="center",
            ),
            bg=bh.RED, color=bh.WHITE, border=f"3px solid {bh.INK}",
            box_shadow=bh.hard_shadow(4), padding="0.7em 1em", width="100%",
        ),
    )


def error_banner_studio() -> rx.Component:
    return rx.cond(
        StudioState.error_msg != "",
        rx.box(
            rx.hstack(
                rx.text("⚠", size="4"),
                rx.text(StudioState.error_msg, size="2", font_weight="700"),
                spacing="2", align="center",
            ),
            bg=bh.RED, color=bh.WHITE, border=f"3px solid {bh.INK}",
            box_shadow=bh.hard_shadow(4), padding="0.7em 1em", width="100%",
        ),
    )
