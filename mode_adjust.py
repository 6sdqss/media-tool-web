"""
mode_adjust.py — Studio Scale v10.2 (WHITE PROFESSIONAL UI)
══════════════════════════════════════════════════════════════
CHANGELOG v10.2 (nâng từ v10.0):

[FIX]  Download nút đơn per-ảnh: dùng open(dp, "rb") thay vì read_bytes()
       cho file > _MAX_INMEM_IMG_BYTES (50MB). Tránh OOM khi ảnh gốc lớn.
[UI]   CSS inject guard dùng key '_studio_css_v102' (thay vì '_studio_css_v10').
[COMPAT] Đồng bộ version với toàn bộ hệ thống v10.2.

GIỮ NGUYÊN TỪ v10.0:
[UI]  Giao diện Modern White Professional (Canva/Figma style).
[FIX] Dynamic canvas aspect ratio — canvas preview thay đổi theo output size thật.
[FIX] CSS inject đúng vị trí (trong function, không ở module level).
[FIX] Hiển thị ảnh ĐÃ RENDER thay vì luôn dùng source_path.
[PERF] Lazy thumbnail, per-item cache invalidation.
[FIX] Per-item error boundary trong _run_render().
[UX]  Pagination ⏮ ◀ [page] ▶ ⏭; Bulk operations cho toàn bộ filtered items.
"""
from __future__ import annotations

import time
import shutil
import re
import logging
from pathlib import Path
from typing import Optional

import streamlit as st

from utils import (
    EXPORT_FORMATS,
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

_log = logging.getLogger("mode_adjust")

_SMALL_THR = 600
_IMG_EXT   = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# [v10.2 FIX] Ngưỡng Anti-OOM cho download nút đơn — file lớn dùng open() stream
_MAX_INMEM_IMG_BYTES = 50 * 1024 * 1024  # 50 MB


# ══════════════════════════════════════════════════════════════
# CSS — inject once per session, trong function body
# ══════════════════════════════════════════════════════════════
def _inject_css():
    # [v10.2] Guard key '_studio_css_v102' — đồng bộ với phiên bản mới
    if st.session_state.get("_studio_css_v102"):
        return
    st.session_state["_studio_css_v102"] = True
    # CSS chính đã được inject bởi app.py (live-frame, rendered-frame, etc.)
    # Chỉ thêm Studio-specific overrides không có trong app.py
    st.markdown("""
<style>
/* Studio container max-width override on large screens */
@media (min-width:1200px) {
    .studio-wrap .block-container { max-width:1380px!important; }
}
/* Slider value display */
.studio-wrap .stSlider [data-testid="stTickBarMin"],
.studio-wrap .stSlider [data-testid="stTickBarMax"] {
    display:none!important;
}
/* Compact number display beside slider */
.slider-val {
    display:inline-block;
    background:#f5f3ff;
    color:#7c3aed;
    font-size:0.78rem;
    font-weight:700;
    padding:1px 7px;
    border-radius:5px;
    min-width:38px;
    text-align:center;
    border:1px solid #ddd6fe;
}
/* Info pill row */
.info-pills {
    display:flex;
    flex-wrap:wrap;
    gap:4px;
    margin:4px 0;
}
.info-pill {
    font-size:0.74rem;
    color:#64748b;
    background:#f8fafc;
    border:1px solid #e2e8f0;
    border-radius:5px;
    padding:2px 8px;
    white-space:nowrap;
}
.info-pill b { color:#374151; }
/* Adjust section header */
.adj-section-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:6px;
}
.adj-section-head span { font-size:0.82rem;color:#94a3b8; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def _stem(item: dict, final_dir: Optional[Path], sizes: list, cfg: dict) -> str:
    """Lấy đúng tên file stem từ FINAL dir theo seq_in_folder."""
    folder = item.get("folder_name", "")
    seq    = int(item.get("seq_in_folder", 1))

    if final_dir and final_dir.exists():
        is_multi = len(sizes) > 1
        check    = final_dir
        if is_multi and sizes:
            try:
                w, h, m = sizes[0]; check = final_dir / get_size_label(w, h, m)
            except Exception:
                pass
        check = check / folder
        if check.exists():
            files = sorted(f for f in check.iterdir()
                           if f.is_file() and not f.name.startswith("__tmp_"))
            if 1 <= seq <= len(files):
                return files[seq - 1].stem

    pn = re.sub(r"\s+", "_", item.get("product", "image")).strip("_")
    cn = re.sub(r"\s+", "_", item.get("color", "")).strip("_")
    return apply_name_template(
        cfg.get("template", "{name}_{nn}"),
        name=pn, color=cn,
        index=seq, original=item.get("original_name", ""),
    )


def _display_path(
    item: dict,
    final_dir: Optional[Path], adjusted_dir: Optional[Path],
    sizes: list, cfg: dict,
) -> tuple[str, str]:
    """
    [FIX] Ưu tiên ADJUSTED → FINAL → source fallback.
    Returns (path_str, status: "adjusted"|"rendered"|"source")
    """
    es       = _stem(item, final_dir, sizes, cfg)
    is_multi = len(sizes) > 1
    sl       = ""
    if sizes:
        try:
            w, h, m = sizes[0]; sl = get_size_label(w, h, m)
        except Exception:
            pass
    folder = item.get("folder_name", "")

    for base, status in [
        (adjusted_dir, "adjusted"),
        (final_dir,    "rendered"),
    ]:
        if not base or not base.exists():
            continue
        sub = (base / sl / folder) if (is_multi and sl) else (base / folder)
        if sub.exists():
            for ext in _IMG_EXT:
                p = sub / f"{es}{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return str(p), status

    return item.get("preview_path") or item.get("source_path") or "", "source"


def _is_small(item: dict) -> bool:
    w = int(item.get("source_width", 0))
    h = int(item.get("source_height", 0))
    return (0 < w < _SMALL_THR) or (0 < h < _SMALL_THR)


def _init_item(item: dict, cfg: dict):
    iid = item["id"]
    if f"adj_scale_{iid}" in st.session_state:
        return
    sizes = cfg.get("sizes", [])
    tw = th = 0
    if sizes:
        try:
            tw, th, _ = sizes[0]; tw, th = int(tw or 0), int(th or 0)
        except Exception:
            pass
    sug     = estimate_default_scale_for_size(
        int(item.get("source_width", 0)), int(item.get("source_height", 0)), tw, th
    )
    default = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
    st.session_state[f"adj_scale_{iid}"] = max(default, sug) if _is_small(item) else default
    st.session_state[f"adj_x_{iid}"]     = 0
    st.session_state[f"adj_y_{iid}"]     = 0
    st.session_state[f"sel_{iid}"]       = _is_small(item)


def _mark(iid: str):
    st.session_state[f"sel_{iid}"] = True


def _del_thumb(iid: str):
    """Per-item cache invalidation — không flush toàn bộ cache."""
    cache = st.session_state.get("_studio_thumb_b64_cache", {})
    for k in [k for k in cache if iid in k]:
        del cache[k]


def _filter(items: list, kw: str, pf: str, sf: str) -> list:
    kw = (kw or "").strip().lower()
    out = []
    for it in items:
        hay = " ".join([it.get("product",""), it.get("color",""),
                        it.get("original_name",""), it.get("folder_name","")]).lower()
        if pf and pf != "Tất cả" and it.get("product") != pf:
            continue
        if kw and kw not in hay:
            continue
        sel = st.session_state.get(f"sel_{it['id']}", False)
        if sf == "Chỉ ảnh đã chọn sửa" and not sel:   continue
        if sf == "Chỉ ảnh chưa chọn"   and sel:        continue
        if sf == "Chỉ ảnh nhỏ (bị giãn)" and not _is_small(it): continue
        out.append(it)
    return out


# ══════════════════════════════════════════════════════════════
# DYNAMIC CANVAS PREVIEW HTML
# Key insight: aspect-ratio được set INLINE theo output size thật
# ══════════════════════════════════════════════════════════════
def _live_preview_html(
    b64: str, tw: int, th: int,
    scale: int, ox: int, oy: int,
    label: str = "",
) -> str:
    """
    [FIX] Canvas aspect-ratio = tw/th thật sự thay vì hardcode 3/2.
    CSS transform scale + translate — không cần page rerun.
    """
    if not b64:
        return (
            "<div class='live-frame live-frame--empty'>"
            "⚠️ Không tìm thấy ảnh nguồn</div>"
        )
    f  = max(60, min(200, int(scale))) / 100.0
    tx = max(-100, min(100, int(ox)))  * 0.5
    ty = max(-100, min(100, int(oy)))  * 0.5
    # aspect-ratio theo output THẬT — đây là key fix
    ar = f"{int(tw)} / {int(th)}" if tw and th else "3 / 2"
    return (
        f"<div class='live-frame' style='aspect-ratio:{ar};'>"
        f"  <div class='live-canvas'>"
        f"    <img class='live-img' src='{b64}'"
        f"         style='transform:translate({tx:.1f}%,{ty:.1f}%) scale({f:.3f})'"
        f"         alt='preview' loading='eager'/>"
        f"  </div>"
        f"  <div class='live-overlay'>"
        f"    <span>🔍 {int(scale)}%</span>"
        f"    <span>↔ X:{int(ox):+d}</span>"
        f"    <span>↕ Y:{int(oy):+d}</span>"
        f"    <span style='margin-left:auto;color:#fde68a;font-size:.7rem'>⚡ Live</span>"
        f"  </div>"
        f"</div>"
    )


def _rendered_html(b64: str) -> str:
    """Hiển thị ảnh ĐÃ RENDER — không dùng CSS transform."""
    if not b64:
        return "<div style='color:#f87171;font-size:.85rem'>⚠ Không đọc được file</div>"
    return (
        f"<div class='rendered-frame'>"
        f"<img src='{b64}' alt='rendered' loading='lazy'/>"
        f"</div>"
    )


# ══════════════════════════════════════════════════════════════
# PAGINATION
# ══════════════════════════════════════════════════════════════
def _paginate(total: int, per_page: int, key: str) -> tuple[int, int, int]:
    n_pages = max((total - 1) // per_page + 1, 1)
    cur     = max(1, min(int(st.session_state.get(key, 1)), n_pages))

    pc = st.columns([1, 1, 2, 1, 1])
    with pc[0]:
        if st.button("⏮", key=f"{key}_f", disabled=cur <= 1, use_container_width=True):
            st.session_state[key] = 1; st.rerun()
    with pc[1]:
        if st.button("◀", key=f"{key}_p", disabled=cur <= 1, use_container_width=True):
            st.session_state[key] = cur - 1; st.rerun()
    with pc[2]:
        np_ = st.number_input(
            f"/{n_pages}", min_value=1, max_value=n_pages,
            value=cur, step=1, key=f"{key}_i",
            label_visibility="visible",
        )
        if int(np_) != cur:
            st.session_state[key] = int(np_); st.rerun()
    with pc[3]:
        if st.button("▶", key=f"{key}_n", disabled=cur >= n_pages, use_container_width=True):
            st.session_state[key] = cur + 1; st.rerun()
    with pc[4]:
        if st.button("⏭", key=f"{key}_l", disabled=cur >= n_pages, use_container_width=True):
            st.session_state[key] = n_pages; st.rerun()

    st.caption(f"Trang **{cur}** / {n_pages} · {total} ảnh · {per_page}/trang")
    s = (cur - 1) * per_page
    return cur, s, s + per_page


# ══════════════════════════════════════════════════════════════
# RENDER ENGINE — per-item error boundary
# ══════════════════════════════════════════════════════════════
def _run_render(
    items: list, adj_root: Path,
    final_dir: Optional[Path], sizes: list, cfg: dict,
) -> tuple[int, list[str]]:
    if adj_root.exists():
        shutil.rmtree(adj_root, ignore_errors=True)
    adj_root.mkdir(parents=True, exist_ok=True)

    bar    = st.progress(0)
    ph     = st.empty()
    errors = []
    ok_n   = 0
    total  = len(items)

    for idx, item in enumerate(items, 1):
        name = item.get("original_name", f"item_{idx}")
        ph.info(f"[{idx}/{total}] Đang render: **{name}**")

        src = Path(item.get("source_path", ""))
        if not src.exists():
            errors.append(f"{name}: source không tồn tại")
            bar.progress(idx / total); continue

        settings = {
            "scale_pct": int(st.session_state.get(f"adj_scale_{item['id']}", 100)),
            "offset_x":  int(st.session_state.get(f"adj_x_{item['id']}",   0)),
            "offset_y":  int(st.session_state.get(f"adj_y_{item['id']}",   0)),
        }
        es = _stem(item, final_dir, sizes, cfg)

        try:
            resize_to_multi_sizes(
                src, adj_root, item["folder_name"], es,
                cfg.get("sizes", []),
                scale_pct=int(cfg.get("default_scale_pct", 100)),
                quality=int(cfg.get("quality", 95)),
                export_format=cfg.get("export_format", "JPEG (.jpg)"),
                per_image_settings=settings,
                huge_image_mode=bool(cfg.get("huge_image_mode", True)),
            )
            ok_n += 1
            _del_thumb(item["id"])
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            _log.error("[render] %s: %s", name, exc)

        bar.progress(idx / total)

    ph.empty(); bar.empty()
    return ok_n, errors


# ══════════════════════════════════════════════════════════════
# ITEM CARD
# ══════════════════════════════════════════════════════════════
def _card(
    item: dict, cfg: dict,
    final_dir: Optional[Path], adj_dir: Optional[Path],
    tw: int, th: int, sizes: list,
):
    iid   = item["id"]
    sk    = f"adj_scale_{iid}"
    xk    = f"adj_x_{iid}"
    yk    = f"adj_y_{iid}"
    selk  = f"sel_{iid}"

    _init_item(item, cfg)
    small = _is_small(item)

    dp, ds = _display_path(item, final_dir, adj_dir, sizes, cfg)

    # Status pill
    pill_map = {
        "adjusted": ("spill spill-a", "🎯 Đã chỉnh"),
        "rendered": ("spill spill-r", "✅ Đã render"),
        "source":   ("spill spill-s", "📷 Chưa render"),
    }
    pc, pl = pill_map.get(ds, pill_map["source"])

    with st.container(border=True):
        # ── Header ────────────────────────────────────────────
        h1, h2 = st.columns([3, 2])
        with h1:
            st.checkbox(
                f"**{item.get('product','-')}** · {item.get('original_name','-')}",
                key=selk,
            )
        with h2:
            parts = [f"<span class='{pc}'>{pl}</span>"]
            if small:
                parts.append("<span class='spill' style='background:#fef2f2;color:#dc2626;border:1px solid #fca5a5'>⚠ Ảnh nhỏ</span>")
            st.markdown(
                f"<div class='info-pills'>{''.join(parts)}</div>",
                unsafe_allow_html=True,
            )

        # ── Body: Preview | Controls ──────────────────────────
        lc, rc = st.columns([1.1, 1.65])

        with lc:
            # [FIX] Phân biệt: đã render → hiện ảnh thật; chưa → CSS live preview
            if ds in ("adjusted", "rendered"):
                # Ảnh ĐÃ RENDER — hiện trực tiếp từ output
                if dp and Path(dp).exists():
                    b64 = build_live_preview_b64(dp, max_size=480)
                    st.markdown(_rendered_html(b64), unsafe_allow_html=True)
                    out_sz = readable_file_size(Path(dp).stat().st_size)
                    st.markdown(
                        f"<div class='size-info output'>"
                        f"📦 Output: {out_sz} · 🎯 {tw}×{th}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.warning("⚠ File output không tồn tại")
            else:
                # CHƯA RENDER — 2-layer CSS live preview
                sp  = str(item.get("source_path", ""))
                b64 = ""
                if sp and Path(sp).exists():
                    b64 = build_live_preview_b64(sp, max_size=360)
                if not b64 and dp:
                    b64 = build_live_preview_b64(dp, max_size=360)

                st.markdown(
                    _live_preview_html(
                        b64=b64, tw=tw, th=th,
                        scale=int(st.session_state[sk]),
                        ox=int(st.session_state[xk]),
                        oy=int(st.session_state[yk]),
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div class='size-info'>🎯 Canvas {tw}×{th}</div>",
                    unsafe_allow_html=True,
                )

            # Source info
            sw = item.get("source_width", 0); sh = item.get("source_height", 0)
            ssz = readable_file_size(item.get("source_size_bytes", 0))
            st.markdown(
                f"<div class='info-pills'>"
                f"<span class='info-pill'>📐 <b>{sw}×{sh}</b></span>"
                f"<span class='info-pill'>💾 <b>{ssz}</b></span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with rc:
            # ── Sliders ───────────────────────────────────────
            s1, s2, s3 = st.columns(3)
            with s1:
                st.slider("Scale %", 60, 200,
                          int(st.session_state[sk]), 1, key=sk,
                          on_change=_mark, args=(iid,))
            with s2:
                st.slider("X", -100, 100,
                          int(st.session_state[xk]), 1, key=xk,
                          on_change=_mark, args=(iid,))
            with s3:
                st.slider("Y", -100, 100,
                          int(st.session_state[yk]), 1, key=yk,
                          on_change=_mark, args=(iid,))

            # Live value display
            sv = int(st.session_state[sk])
            xv = int(st.session_state[xk])
            yv = int(st.session_state[yk])
            st.markdown(
                f"<div class='info-pills'>"
                f"<span class='info-pill'>🔍 <b>{sv}%</b></span>"
                f"<span class='info-pill'>↔ <b>{xv:+d}</b></span>"
                f"<span class='info-pill'>↕ <b>{yv:+d}</b></span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # ── Quick buttons ─────────────────────────────────
            qb1, qb2, qb3 = st.columns(3)
            with qb1:
                if st.button("↺ Reset", key=f"rst_{iid}", use_container_width=True):
                    d = int(item.get("default_scale_pct", cfg.get("default_scale_pct", 100)))
                    st.session_state[sk]   = d
                    st.session_state[xk]   = 0
                    st.session_state[yk]   = 0
                    st.session_state[selk] = True
                    _del_thumb(iid); st.rerun()
            with qb2:
                if st.button("➖ 5%", key=f"min_{iid}", use_container_width=True):
                    st.session_state[sk] = max(60, int(st.session_state[sk]) - 5)
                    st.session_state[selk] = True; st.rerun()
            with qb3:
                if st.button("➕ 5%", key=f"pls_{iid}", use_container_width=True):
                    st.session_state[sk] = min(200, int(st.session_state[sk]) + 5)
                    st.session_state[selk] = True; st.rerun()

            # ── Download single ───────────────────────────────
            st.markdown("<hr style='margin:8px 0;border-color:#f1f5f9'>", unsafe_allow_html=True)
            if dp and Path(dp).exists():
                try:
                    img_size = Path(dp).stat().st_size
                    bt  = "primary" if ds == "adjusted" else "secondary"
                    lbl = "📥 Tải ảnh đã chỉnh" if ds == "adjusted" else "📥 Tải ảnh"
                    if img_size <= _MAX_INMEM_IMG_BYTES:
                        # File nhỏ — đọc vào RAM an toàn
                        fb = Path(dp).read_bytes()
                        st.download_button(
                            lbl, fb, Path(dp).name, "image/jpeg",
                            use_container_width=True, type=bt, key=f"dl_{iid}",
                        )
                    else:
                        # [v10.2 FIX] File lớn > 50MB — dùng open() stream tránh OOM
                        with open(dp, "rb") as fh:
                            st.download_button(
                                lbl, fh, Path(dp).name, "image/jpeg",
                                use_container_width=True, type=bt, key=f"dl_{iid}",
                            )
                except Exception:
                    st.caption("⚠ Không đọc được file")
            else:
                st.caption("— Chưa có file output —")


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY
# ══════════════════════════════════════════════════════════════
def render_adjustment_studio():
    _inject_css()
    st.markdown("<div class='studio-wrap'>", unsafe_allow_html=True)

    st.markdown(
        "<div class='hero-card'>"
        "<h2>🎚 Studio Scale v10.2</h2>"
        "<p>Live Preview cập nhật realtime theo slider. Canvas preview <b>động theo output size thật</b>. "
        "Ảnh đã render hiển thị output thực từ đĩa.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    manifest = st.session_state.get("last_batch_manifest", [])
    cfg      = st.session_state.get("last_batch_cfg",      {})
    meta     = st.session_state.get("last_batch_meta",     {})

    if not manifest:
        st.info("⚠️ Chưa có batch. Chạy tab **Web / Drive / Local ZIP** trước.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    render_batch_kpis(meta)

    root = Path(meta["root"]) if meta.get("root") else None
    if root and not root.exists():
        st.error("❌ Workspace batch đã bị xóa (container reset). Vui lòng chạy lại.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    final_dir = (
        Path(meta["final_dir"]) if meta.get("final_dir") else
        (root / "FINAL" if root else None)
    )
    adj_dir   = Path(
        st.session_state.get("_adjusted_root", str(root / "ADJUSTED"))
    ) if root else None
    sizes     = cfg.get("sizes", [])

    # Canvas target size
    tw, th = 1020, 680
    if sizes:
        try:
            w, h, _ = sizes[0]
            if w and h: tw, th = int(w), int(h)
        except Exception:
            pass

    # Init state cho toàn bộ manifest một lần
    init_key = f"_sinit_{meta.get('batch_id','x')}"
    if not st.session_state.get(init_key):
        for it in manifest: _init_item(it, cfg)
        st.session_state[init_key] = True

    total   = len(manifest)
    sel_n   = sum(1 for it in manifest if st.session_state.get(f"sel_{it['id']}", False))
    sml_n   = sum(1 for it in manifest if _is_small(it))

    # Canvas size info pill
    st.markdown(
        f"<div class='info-pills'>"
        f"<span class='info-pill'>📦 {meta.get('batch_id','-')[:20]}</span>"
        f"<span class='info-pill'>📷 <b>{total}</b> ảnh</span>"
        f"<span class='info-pill' style='color:#7c3aed'>✏️ <b>{sel_n}</b> đang chọn</span>"
        f"<span class='info-pill' style='color:#dc2626'>⚠ <b>{sml_n}</b> ảnh nhỏ</span>"
        f"<span class='info-pill' style='background:#f5f3ff;border-color:#ddd6fe'>"
        f"🎯 Canvas <b>{tw}×{th}</b></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Filters ───────────────────────────────────────────────
    st.markdown('<div class="sec-title">🔍 Bộ lọc</div>', unsafe_allow_html=True)
    pnames = sorted({it.get("product","") for it in manifest if it.get("product")})
    fc = st.columns([1.6, 1.1, 1.4, 0.9])
    with fc[0]: kw = st.text_input("Tìm nhanh", placeholder="Tên, màu...", key="adj_kw", label_visibility="collapsed")
    with fc[1]: pf = st.selectbox("Sản phẩm", ["Tất cả",*pnames], key="adj_pf", label_visibility="collapsed")
    with fc[2]: sf = st.selectbox("Trạng thái", ["Tất cả","Chỉ ảnh đã chọn sửa","Chỉ ảnh chưa chọn","Chỉ ảnh nhỏ (bị giãn)"], key="adj_sf", label_visibility="collapsed")
    with fc[3]: pp = st.selectbox("/ trang", [6,10,16,24], index=1, key="adj_pp", label_visibility="collapsed")

    filtered = _filter(manifest, kw, pf, sf)
    if not filtered:
        st.warning("Không có ảnh phù hợp bộ lọc.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── Bulk ops ──────────────────────────────────────────────
    st.markdown('<div class="sec-title">🧩 Thao tác hàng loạt</div>', unsafe_allow_html=True)
    with st.container(border=True):
        ba = st.columns(4)
        with ba[0]:
            if st.button("☑️ Chọn tất cả", use_container_width=True, key="bsa"):
                for it in filtered: st.session_state[f"sel_{it['id']}"] = True
                st.rerun()
        with ba[1]:
            if st.button("⬜ Bỏ chọn tất cả", use_container_width=True, key="bua"):
                for it in filtered: st.session_state[f"sel_{it['id']}"] = False
                st.rerun()
        with ba[2]:
            if st.button("⚠️ Chọn ảnh nhỏ", use_container_width=True, key="bss"):
                for it in manifest:
                    if _is_small(it): st.session_state[f"sel_{it['id']}"] = True
                st.rerun()
        with ba[3]:
            if st.button("🧹 Xóa tất cả", use_container_width=True, key="bca"):
                for it in manifest: st.session_state[f"sel_{it['id']}"] = False
                st.rerun()

        bs = st.columns(3)
        with bs[0]: bsc = st.slider("Scale %", 60, 200, int(cfg.get("default_scale_pct",100)), key="bsc")
        with bs[1]: bxc = st.slider("X", -100, 100, 0, key="bxc")
        with bs[2]: byc = st.slider("Y", -100, 100, 0, key="byc")

        ab1, ab2 = st.columns(2)
        with ab1:
            if st.button("⚡ Áp dụng trang hiện tại", use_container_width=True, key="bap"):
                pg  = int(st.session_state.get("adj_pg", 1))
                s   = (pg-1)*pp; e = s+pp
                for it in filtered[s:e]:
                    iid = it["id"]
                    st.session_state[f"adj_scale_{iid}"] = int(bsc)
                    st.session_state[f"adj_x_{iid}"]     = int(bxc)
                    st.session_state[f"adj_y_{iid}"]     = int(byc)
                    st.session_state[f"sel_{iid}"]       = True
                st.rerun()
        with ab2:
            if st.button("⚡⚡ Áp dụng tất cả bộ lọc", use_container_width=True, key="baa"):
                for it in filtered:
                    iid = it["id"]
                    st.session_state[f"adj_scale_{iid}"] = int(bsc)
                    st.session_state[f"adj_x_{iid}"]     = int(bxc)
                    st.session_state[f"adj_y_{iid}"]     = int(byc)
                    st.session_state[f"sel_{iid}"]       = True
                st.rerun()

    # ── Item list với pagination ──────────────────────────────
    st.markdown(
        f'<div class="sec-title">🖼 Ảnh ({len(filtered)} phù hợp) '
        f'— Canvas <b>{tw}×{th}</b></div>',
        unsafe_allow_html=True,
    )
    _, s, e = _paginate(len(filtered), pp, "adj_pg")
    page_items = filtered[s:e]

    # [PERF] Chỉ build thumbnail cho items trên trang hiện tại
    for item in page_items:
        _card(item, cfg, final_dir, adj_dir, tw, th, sizes)

    # ── Export panel ──────────────────────────────────────────
    sel_items = [it for it in manifest if st.session_state.get(f"sel_{it['id']}", False)]

    st.markdown("""
        <div class="export-panel">
            <h2>🚀 Xuất file & tải về</h2>
            <p style="color:#64748b;font-size:.9rem">
                <b>Bước 1</b>: Render ảnh đã chọn →
                <b>Bước 2</b>: Đóng gói ZIP →
                <b>Bước 3</b>: Tải về máy.
            </p>
        </div>
    """, unsafe_allow_html=True)

    ec1, ec2 = st.columns(2)
    with ec1:
        st.markdown("<h4 style='color:#7c3aed;margin-bottom:4px'>▶ Bước 1: Render</h4>", unsafe_allow_html=True)
        do_render = st.button(
            f"🎨 Render {len(sel_items)} ảnh đã chọn",
            type="primary", use_container_width=True,
            key="adj_render", disabled=(len(sel_items) == 0),
        )
    with ec2:
        st.markdown("<h4 style='color:#7c3aed;margin-bottom:4px'>▶ Bước 2: Tạo ZIP</h4>", unsafe_allow_html=True)
        do_export = st.button(
            "📦 ZIP gộp (ảnh đã chỉnh + gốc)",
            type="primary", use_container_width=True, key="adj_export",
        )

    # ── Render logic ──────────────────────────────────────────
    if do_render:
        if not root:
            st.error("❌ Workspace không tồn tại.")
        else:
            adj_root   = root / "ADJUSTED"
            t0         = time.time()
            ok_n, errs = _run_render(sel_items, adj_root, final_dir, sizes, cfg)
            dt         = time.time() - t0
            st.session_state["_adjusted_root"]     = str(adj_root)
            st.session_state["_adjust_render_done"]= True
            if ok_n > 0:
                st.success(f"✅ Render **{ok_n}/{len(sel_items)}** ảnh trong {dt:.1f}s")
                add_to_history(
                    "Adjust", f"Studio · {ok_n} ảnh", ok_n,
                    " + ".join(get_size_label(w,h,m) for w,h,m in sizes), dt,
                )
            if errs:
                with st.expander(f"⚠️ {len(errs)} lỗi"):
                    for e in errs: st.caption(f"• {e}")
            st.rerun()

    # ── Export ZIP logic ──────────────────────────────────────
    if do_export:
        if not root:
            st.error("❌ Workspace không tồn tại.")
        elif not final_dir or not final_dir.exists():
            st.error("❌ Thư mục FINAL không tồn tại.")
        else:
            ap  = Path(st.session_state.get("_adjusted_root", str(root/"ADJUSTED")))
            uid = int(time.time())
            with st.spinner("Đang gộp ảnh..."):
                md  = root / f"MERGED_{uid}"; md.mkdir(parents=True, exist_ok=True)
                stats = merge_final_with_adjusted(final_dir, ap, md)
                zp    = root / f"FullExport_{meta.get('batch_id','b')}_{uid}.zip"
                make_zip(md, zp, compresslevel=int(cfg.get("zip_compression", 6)))
            if zp.exists() and zp.stat().st_size > 0:
                st.session_state["adjust_zip_path"] = str(zp)
                st.success(
                    f"📦 ZIP sẵn sàng · Ghi đè **{stats['overridden']}** · "
                    f"Giữ nguyên **{stats['kept']}**"
                )
                st.rerun()
            else:
                st.error("❌ Tạo ZIP thất bại.")

    # ── Download ZIP ──────────────────────────────────────────
    st.markdown(
        "<h4 style='color:#7c3aed;margin-top:16px;margin-bottom:4px'>"
        "▶ Bước 3: Tải ZIP</h4>",
        unsafe_allow_html=True,
    )
    dz1, dz2 = st.columns(2)
    with dz1:
        zorig = meta.get("zip_path","")
        if not zorig or not Path(zorig).exists():
            if root and final_dir and final_dir.exists():
                try:
                    fb = root / f"OrigExport_{meta.get('batch_id','b')}.zip"
                    if not fb.exists():
                        make_zip(final_dir, fb, compresslevel=6)
                    if fb.exists(): zorig = str(fb)
                except Exception:
                    pass
        h = open_zip_for_download(zorig)
        if h:
            try:
                st.download_button(
                    f"⬇️ ZIP Gốc ({readable_file_size(Path(zorig).stat().st_size)})",
                    h, Path(zorig).name, "application/zip",
                    use_container_width=True, key="dl_orig",
                )
            finally:
                h.close()
        else:
            st.caption("ZIP gốc chưa có.")

    with dz2:
        zm = st.session_state.get("adjust_zip_path","")
        hm = open_zip_for_download(zm)
        if hm:
            try:
                st.download_button(
                    f"⬇️ ZIP Gộp — Đã chỉnh ({readable_file_size(Path(zm).stat().st_size)})",
                    hm, Path(zm).name, "application/zip",
                    type="primary", use_container_width=True, key="dl_merged",
                )
            finally:
                hm.close()
        else:
            st.info("💡 Bấm **Bước 2** để tạo file ZIP gộp.")

    st.markdown("</div>", unsafe_allow_html=True)
