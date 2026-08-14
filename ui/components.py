"""
ui/components.py — reusable UI widgets.
"""
from __future__ import annotations

import html
import time
from pathlib import Path

import streamlit as st

from core import state as sstate
from core.archive import readable_size
from core.batch import BatchManager, is_thread_alive
from core.memory import (
    DISK_WARNING_MB, disk_free_mb, memory_pressure_high, available_memory_mb,
)
from core.presets import load_all as load_presets
from core.types import BatchState, ErrorType, ItemState, TaskItem
from core.types import ERROR_LABEL_VI


# ══════════════════════════════════════════════════════════════
# HEADER / HERO
# ══════════════════════════════════════════════════════════════
def app_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"""
    <div class="mtp-header">
      <div class="brand">M</div>
      <div>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(subtitle)}</p>
      </div>
    </div>
    """, unsafe_allow_html=True)


def hero(title: str, description: str = "") -> None:
    st.markdown(f"""
    <div class="mtp-hero">
      <h2>{html.escape(title)}</h2>
      <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)


def section(label: str) -> None:
    st.markdown(f"<div class='mtp-sec-title'>{html.escape(label)}</div>",
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# INPUT REPORT (validation counters)
# ══════════════════════════════════════════════════════════════
def input_report_bar(raw: int, valid: int, dup: int, invalid: int) -> None:
    """Thanh tóm tắt sau khi validate URL/upload input."""
    parts = [
        f"<span class='mtp-pill muted'>{raw} input</span>",
        f"<span class='mtp-pill ok'>✓ {valid} valid</span>",
    ]
    if dup:
        parts.append(f"<span class='mtp-pill warn'>⚠ {dup} duplicate</span>")
    if invalid:
        parts.append(f"<span class='mtp-pill err'>✗ {invalid} invalid</span>")
    st.markdown(
        f"<div class='mtp-input-report'>{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════
# PRESET PICKER
# ══════════════════════════════════════════════════════════════
def preset_picker(mode: str) -> "core.types.Preset":
    """Chọn preset. Trả về đối tượng Preset."""
    from core.types import Preset
    presets = load_presets()
    names = [p.name for p in presets]

    current = sstate.batch().preset_name or st.session_state.get("current_preset", names[0])
    if current not in names:
        current = names[0]

    idx = names.index(current)
    selected = st.selectbox(
        "Preset xử lý",
        names,
        index=idx,
        key=f"preset_pick_{mode}",
        help="Chọn 1 preset — toàn bộ cấu hình resize / format / template được áp dụng tự động.",
    )
    st.session_state["current_preset"] = selected

    p = next((pp for pp in presets if pp.name == selected), presets[0])
    st.markdown(
        f"<div class='mtp-input-report' style='margin-top:4px'>"
        f"<span class='mtp-pill info'>{len(p.sizes)} kích thước</span>"
        f"<span class='mtp-pill muted'>Q={p.quality}</span>"
        f"<span class='mtp-pill muted'>{p.export_format}</span>"
        f"<span class='mtp-pill muted'>{'no-upscale' if p.no_upscale else 'upscale-ok'}</span>"
        f"<span class='mtp-pill muted'>tpl: <code>{html.escape(p.template)}</code></span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if p.description:
        st.caption(p.description)
    return p


# ══════════════════════════════════════════════════════════════
# ONE-CLICK BANNER
# ══════════════════════════════════════════════════════════════
def one_click_banner() -> None:
    if sstate.settings().get("one_click_mode"):
        st.markdown(
            "<div class='mtp-oneclick'>⚡ <b>One-Click mode ON</b> — "
            "dán/upload xong rồi bấm START là xong, "
            "hệ thống tự chạy toàn bộ pipeline.</div>",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════
# BATCH STATUS
# ══════════════════════════════════════════════════════════════
def batch_progress_panel() -> None:
    """Panel realtime — chỉ hiển thị khi batch không IDLE."""
    bi = sstate.batch()
    if bi.state == BatchState.IDLE:
        return

    # Header pill
    label_map = {
        BatchState.PREPARING: ("info",       "Chuẩn bị"),
        BatchState.RUNNING:   ("info",       "Đang chạy"),
        BatchState.PAUSED:    ("warn",       "Tạm dừng"),
        BatchState.CANCELLING:("warn",       "Đang huỷ"),
        BatchState.DONE:      ("ok",         "Hoàn tất"),
        BatchState.FAILED:    ("err",        "Lỗi"),
    }
    color, label = label_map.get(bi.state, ("muted", bi.state.value))
    st.markdown(
        f"<div class='mtp-input-report'>"
        f"<span class='mtp-pill {color}'>● {label}</span>"
        f"<span class='mtp-pill muted'>Batch <code>{bi.batch_id[-10:]}</code></span>"
        f"<span class='mtp-pill muted'>Preset: {html.escape(bi.preset_name or '')}</span>"
        f"<span class='mtp-pill muted'>Duration: {bi.duration:.1f}s</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Progress bar
    st.progress(bi.progress_ratio)

    # Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", bi.total)
    c2.metric("Success", bi.success)
    c3.metric("Failed", bi.failed)
    c4.metric("Retry", bi.retrying)
    c5.metric("Queued", bi.queued + bi.running)

    # Current item hint
    if bi.current_item_name:
        st.caption(
            f"⏳ Đang xử lý: **{html.escape(bi.current_item_name)}** "
            f"({html.escape(bi.current_operation)})"
        )

    # Control buttons — chỉ khi batch đang active
    if bi.state in (BatchState.RUNNING, BatchState.PAUSED, BatchState.PREPARING):
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            if bi.state == BatchState.RUNNING:
                if st.button("⏸ Pause", key=f"ctl_pause_{bi.batch_id}",
                             use_container_width=True):
                    BatchManager.request_pause()
                    st.rerun()
            elif bi.state == BatchState.PAUSED:
                if st.button("▶ Resume", key=f"ctl_resume_{bi.batch_id}",
                             use_container_width=True, type="primary"):
                    BatchManager.request_resume()
                    st.rerun()
            else:
                st.button("⏸ Pause", disabled=True,
                         key=f"ctl_pause_disabled_{bi.batch_id}",
                         use_container_width=True)
        with cc2:
            if st.button("⏹ Cancel", key=f"ctl_cancel_{bi.batch_id}",
                         use_container_width=True):
                BatchManager.request_cancel()
                st.rerun()
        with cc3:
            if st.button("🔄 Refresh", key=f"ctl_refresh_{bi.batch_id}",
                         use_container_width=True):
                st.rerun()

    if bi.log_tail:
        st.markdown(
            "<div class='mtp-log'>" +
            html.escape("\n".join(bi.log_tail[-24:])) +
            "</div>",
            unsafe_allow_html=True,
        )


def auto_refresh_if_active(interval_sec: float = 1.0) -> None:
    """
    Gọi ở CUỐI trang khi batch đang active — sleep rồi rerun.
    Nếu không active thì return ngay.

    Streamlit sẽ block ở time.sleep() nhưng nút widgets đã được đăng ký
    trước đó, user click sẽ trigger rerun mới (Streamlit break sleep bằng
    cách restart script). Interval nhỏ (~1s) giữ trải nghiệm mượt.
    """
    bi = sstate.batch()
    # Chỉ refresh khi worker thread còn sống HOẶC state đang active
    if bi.state in (BatchState.RUNNING, BatchState.PAUSED, BatchState.PREPARING,
                    BatchState.CANCELLING):
        # Nếu worker đã die nhưng state vẫn active → có thể pipeline crash
        # trước khi kịp cập nhật state. Force finalize.
        if bi.batch_id and not is_thread_alive(bi.batch_id):
            # Đợi 1 chút cho finalize xong trước khi rerun
            time.sleep(0.3)
            st.rerun()
            return
        time.sleep(interval_sec)
        st.rerun()


def batch_result_panel() -> None:
    """Sau khi batch xong: nút download ZIP + report + retry failed."""
    bi = sstate.batch()
    if bi.state not in (BatchState.DONE, BatchState.FAILED):
        return

    st.markdown("---")
    cols = st.columns([1, 1, 1])

    with cols[0]:
        if bi.zip_path and Path(bi.zip_path).exists():
            zp = Path(bi.zip_path)
            size = readable_size(zp.stat().st_size)
            with open(zp, "rb") as f:
                st.download_button(
                    f"📥 Tải ZIP · {size}",
                    data=f.read() if zp.stat().st_size < 50 * 1024 * 1024 else f,
                    file_name=zp.name,
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    key="dl_zip_" + bi.batch_id,
                )

    with cols[1]:
        if bi.report_path and Path(bi.report_path).exists():
            rp = Path(bi.report_path)
            st.download_button(
                "📊 Tải Report CSV",
                data=rp.read_bytes(),
                file_name=f"report_{bi.batch_id}.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_csv_" + bi.batch_id,
            )

    with cols[2]:
        failed_count = bi.failed
        if failed_count > 0:
            if st.button(
                f"🔁 Retry {failed_count} failed",
                use_container_width=True,
                key="retry_failed_" + bi.batch_id,
            ):
                st.session_state["_retry_failed"] = True
                st.rerun()


def batch_queue_view(max_rows: int = 30) -> None:
    """Bảng liệt kê item + status. Không load ảnh — chỉ text."""
    items: list[TaskItem] = sstate.items()
    if not items:
        return

    with st.expander(f"📋 Chi tiết {len(items)} item", expanded=False):
        rows = ["<div class='mtp-queue'>",
                "<div class='mtp-queue-row head'>"
                "<div>#</div><div>Item</div><div>Group</div>"
                "<div>Status</div><div>Attempt</div>"
                "</div>"]

        state_pill = {
            ItemState.QUEUED:    ("muted", "queued"),
            ItemState.RUNNING:   ("info", "running"),
            ItemState.RETRYING:  ("warn", "retry"),
            ItemState.SUCCESS:   ("ok",   "success"),
            ItemState.FAILED:    ("err",  "failed"),
            ItemState.CANCELLED: ("muted","cancel"),
            ItemState.SKIPPED:   ("muted","skip"),
        }
        for i, it in enumerate(items[:max_rows], 1):
            color, label = state_pill.get(it.status, ("muted", "?"))
            name_html = html.escape(it.display_name or it.source[:80])
            group_html = html.escape(it.group_name or "-")
            err_line = ""
            if it.status == ItemState.FAILED and it.error_type != ErrorType.NONE:
                err_line = (f"<div class='mtp-queue-err'>"
                            f"{html.escape(ERROR_LABEL_VI.get(it.error_type, it.error_type.value))} — "
                            f"{html.escape(it.error_message[:120])}</div>")
            rows.append(
                f"<div class='mtp-queue-row'>"
                f"<div>{i}</div>"
                f"<div><div class='mtp-queue-name'>{name_html}</div>{err_line}</div>"
                f"<div>{group_html}</div>"
                f"<div><span class='mtp-pill {color}'>{label}</span></div>"
                f"<div>{it.attempt}/{it.max_attempts}</div>"
                f"</div>"
            )
        if len(items) > max_rows:
            rows.append(
                f"<div class='mtp-queue-row'><div></div>"
                f"<div>... còn {len(items)-max_rows} item nữa</div>"
                f"<div></div><div></div><div></div></div>"
            )
        rows.append("</div>")
        st.markdown("".join(rows), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# SIDEBAR SYSTEM STATUS
# ══════════════════════════════════════════════════════════════
def system_status_sidebar() -> None:
    ram = available_memory_mb()
    disk = disk_free_mb("/tmp")
    ram_color = "err" if 0 < ram < 250 else ("warn" if 0 < ram < 400 else "ok")
    disk_color = "err" if 0 < disk < 150 else ("warn" if 0 < disk < DISK_WARNING_MB else "ok")

    st.markdown(
        f"<div style='display:flex;flex-direction:column;gap:4px'>"
        f"<span class='mtp-pill {ram_color}'>RAM · "
        f"{'?' if ram < 0 else f'{ram:.0f} MB'}</span>"
        f"<span class='mtp-pill {disk_color}'>Disk · "
        f"{'?' if disk < 0 else f'{disk:.0f} MB'}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════
# START BUTTON — with double-click guard
# ══════════════════════════════════════════════════════════════
def start_button(label: str = "🚀 START", key: str = "btn_start", disabled: bool = False) -> bool:
    """
    Nút START chống double-click.
    Tự disable khi batch đang chạy (sstate.is_batch_active()).
    """
    active = sstate.is_batch_active()
    return st.button(
        label,
        key=key,
        type="primary",
        use_container_width=True,
        disabled=disabled or active,
    )
