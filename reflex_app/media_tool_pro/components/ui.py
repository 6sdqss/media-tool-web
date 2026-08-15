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


def stat_pill(label: str, value: rx.Var, color: str = "gray") -> rx.Component:
    return rx.hstack(
        rx.text(label, size="1", color="gray"),
        rx.badge(value.to_string(), color_scheme=color, variant="soft"),
        spacing="1",
        align="center",
    )


def top_header() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.box(
                rx.text("M", weight="bold", size="5", color="white"),
                bg="linear-gradient(135deg,#7c3aed,#ec4899)",
                border_radius="10px",
                width="38px", height="38px",
                display="flex", align_items="center", justify_content="center",
            ),
            rx.vstack(
                rx.heading("Media Tool Pro", size="4"),
                rx.text("Batch image processing · Reflex UI", size="1", color="gray"),
                spacing="0",
            ),
            spacing="3", align="center",
        ),
        rx.spacer(),
        rx.hstack(
            rx.color_mode.button(),
            rx.badge(AuthState.user_username, variant="soft", color_scheme="violet"),
            rx.badge(AuthState.user_role, variant="outline"),
            rx.button("Đăng xuất", on_click=AuthState.do_logout, variant="soft",
                      color_scheme="red", size="2"),
            spacing="3", align="center",
        ),
        width="100%", padding="1em 1.5em",
        border_bottom="1px solid var(--gray-5)",
        align="center",
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
    def nav_btn(key: str, label: str) -> rx.Component:
        on_click = (
            [BatchState.set_active_mode(key), StudioState.load_from_last_batch]
            if key == "studio" else BatchState.set_active_mode(key)
        )
        return rx.button(
            label,
            on_click=on_click,
            variant=rx.cond(BatchState.active_mode == key, "solid", "ghost"),
            color_scheme=rx.cond(BatchState.active_mode == key, "violet", "gray"),
            width="100%",
            justify="start",
            size="3",
        )

    items = [nav_btn(k, v) for k, v in NAV_ITEMS]
    return rx.vstack(
        *items,
        rx.cond(
            AuthState.is_admin,
            rx.button(
                "🔐 Admin",
                on_click=BatchState.set_active_mode("admin"),
                variant=rx.cond(BatchState.active_mode == "admin", "solid", "ghost"),
                color_scheme=rx.cond(BatchState.active_mode == "admin", "violet", "gray"),
                width="100%", justify="start", size="3",
            ),
        ),
        rx.divider(),
        rx.text("Cài đặt", size="1", weight="bold", color="gray"),
        rx.hstack(rx.text("⚡ One-Click", size="2"),
                  rx.spacer(),
                  rx.switch(checked=BatchState.one_click_mode,
                            on_change=BatchState.set_one_click_mode),
                  width="100%"),
        rx.hstack(rx.text("📦 Auto ZIP", size="2"),
                  rx.spacer(),
                  rx.switch(checked=BatchState.auto_zip, on_change=BatchState.set_auto_zip),
                  width="100%"),
        rx.hstack(rx.text("📊 Auto Report", size="2"),
                  rx.spacer(),
                  rx.switch(checked=BatchState.auto_report, on_change=BatchState.set_auto_report),
                  width="100%"),
        rx.divider(),
        rx.button("🧹 Dọn workspace cũ", on_click=BatchState.cleanup_workspace,
                  width="100%", variant="soft", size="2"),
        rx.cond(BatchState.cleanup_msg != "", rx.text(BatchState.cleanup_msg, size="1", color="green")),
        spacing="2", width="220px", padding="1em",
        border_right="1px solid var(--gray-5)",
        min_height="100%",
        align_items="stretch",
    )


def preset_picker() -> rx.Component:
    """Multi-select preset — tick nhiều preset để 1 ảnh xuất ra NHIỀU
    kích thước khác nhau trong cùng 1 lần chạy (mỗi preset ra 1 zip riêng)."""
    return rx.vstack(
        rx.hstack(
            rx.text("Preset (tick để chạy nhiều size cùng lúc)", weight="bold", size="3"),
            rx.spacer(),
            rx.badge(
                BatchState.selected_presets.length().to_string(), " đã chọn",
                color_scheme="violet", variant="soft",
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
                    ),
                    rx.vstack(
                        rx.text(p["name"], size="2", weight="medium"),
                        rx.text(f"{p['description']} · {p['sizes']}", size="1", color="gray"),
                        spacing="0", align="start",
                    ),
                    spacing="2", align="center", width="100%",
                    padding="0.35em 0.25em",
                    border_bottom="1px solid var(--gray-4)",
                ),
            ),
            width="100%", max_height="220px", overflow_y="auto",
            border="1px solid var(--gray-5)", border_radius="8px", padding="0.25em 0.5em",
        ),
        custom_size_form(),
        width="100%", spacing="2",
    )


def custom_size_form() -> rx.Component:
    """Cho phép tự thêm 1 preset kích thước tuỳ ý (WxH + kiểu resize)."""
    return rx.accordion.root(
        rx.accordion.item(
            header="➕ Tự thêm size mới",
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
                    size="1", color="gray",
                ),
                rx.button("Thêm preset", on_click=BatchState.add_custom_preset,
                          size="2", variant="soft", color_scheme="violet"),
                rx.cond(BatchState.custom_msg != "",
                        rx.text(BatchState.custom_msg, size="1", color="gray")),
                spacing="2", width="100%", padding_top="0.5em",
            ),
        ),
        collapsible=True, width="100%",
    )


def input_report_bar() -> rx.Component:
    r = BatchState.input_report
    return rx.hstack(
        rx.badge("Tổng: ", r["raw"].to_string(), color_scheme="gray"),
        rx.badge("Hợp lệ: ", r["valid"].to_string(), color_scheme="green"),
        rx.badge("Trùng: ", r["dup"].to_string(), color_scheme="amber"),
        rx.badge("Không hỗ trợ: ", r["invalid"].to_string(), color_scheme="red"),
        spacing="2", wrap="wrap",
    )


def batch_progress_panel() -> rx.Component:
    return rx.cond(
        BatchState.batch_total > 0,
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.text(f"Batch: ", weight="bold"),
                    rx.badge(BatchState.batch_state_label, color_scheme="violet"),
                    rx.spacer(),
                    rx.text(f"{BatchState.batch_duration_s}s", size="2", color="gray"),
                    width="100%",
                ),
                rx.progress(value=BatchState.batch_progress_pct, max=100, width="100%"),
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
                            size="2", color="gray"),
                ),
                rx.cond(
                    BatchState.is_batch_running,
                    rx.button("⏹ Huỷ batch", on_click=BatchState.cancel_batch,
                              color_scheme="red", variant="soft", size="2"),
                ),
                rx.hstack(
                    rx.cond(BatchState.batch_zip_ready,
                            rx.button("⬇ Tải ZIP", on_click=BatchState.download_zip, size="2")),
                    rx.cond(BatchState.batch_report_ready,
                            rx.button("⬇ Tải Report CSV", on_click=BatchState.download_report,
                                      size="2", variant="soft")),
                    spacing="2",
                ),
                rx.cond(
                    BatchState.batch_log_tail.length() > 0,
                    rx.box(
                        rx.foreach(BatchState.batch_log_tail,
                                   lambda ln: rx.text(ln, size="1", color="gray", font_family="monospace")),
                        max_height="160px", overflow_y="auto", width="100%",
                        bg="var(--gray-2)", padding="0.5em", border_radius="6px",
                    ),
                ),
                spacing="3", width="100%",
            ),
            width="100%",
        ),
    )


def run_outputs_panel() -> rx.Component:
    """Danh sách zip/report của TỪNG preset (hoặc từng đợt-chunk drive) đã
    xong trong lượt chạy vừa rồi — quan trọng khi chạy multi-preset vì nút
    "Tải ZIP" ở batch_progress_panel chỉ giữ file của lượt CUỐI CÙNG."""
    return rx.cond(
        BatchState.run_outputs.length() > 1,
        rx.card(
            rx.vstack(
                rx.text("Kết quả theo từng preset", weight="bold", size="3"),
                rx.foreach(
                    BatchState.run_outputs,
                    lambda o, i: rx.hstack(
                        rx.vstack(
                            rx.text(o["label"], size="2", weight="medium"),
                            rx.text(f"{o['success']}/{o['total']} ảnh thành công",
                                    size="1", color="gray"),
                            spacing="0", align="start",
                        ),
                        rx.spacer(),
                        rx.button("⬇ ZIP", on_click=BatchState.download_output_zip(i),
                                  size="1", variant="soft"),
                        rx.button("⬇ CSV", on_click=BatchState.download_output_report(i),
                                  size="1", variant="soft"),
                        width="100%", align="center", spacing="2",
                        padding="0.35em 0.25em", border_bottom="1px solid var(--gray-4)",
                    ),
                ),
                width="100%", spacing="2",
            ),
            width="100%",
        ),
    )


def batch_queue_view() -> rx.Component:
    return rx.cond(
        BatchState.queue_rows.length() > 0,
        rx.card(
            rx.vstack(
                rx.text("Queue", weight="bold"),
                rx.box(
                    rx.foreach(
                        BatchState.queue_rows,
                        lambda row: rx.hstack(
                            rx.text(row["name"], size="2", no_of_lines=1, width="35%"),
                            rx.text(row["group"], size="1", color="gray", width="25%"),
                            rx.badge(row["status"], size="1"),
                            rx.cond(row["error"] != "", rx.text(row["error"], size="1", color="red")),
                            width="100%", spacing="2",
                        ),
                    ),
                    max_height="300px", overflow_y="auto", width="100%",
                ),
                width="100%", spacing="2",
            ),
            width="100%",
        ),
    )


def error_banner() -> rx.Component:
    return rx.cond(
        BatchState.batch_error_msg != "",
        rx.callout(BatchState.batch_error_msg, color_scheme="red", icon="triangle_alert"),
    )


def error_banner_studio() -> rx.Component:
    return rx.cond(
        StudioState.error_msg != "",
        rx.callout(StudioState.error_msg, color_scheme="red", icon="triangle_alert"),
    )
