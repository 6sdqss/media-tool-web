import streamlit as st
from utils import get_gdrive_service

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH TRANG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Media Tool Pro",
    layout="wide",
    page_icon="🖼️",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════
# CSS TOÀN CỤC
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
#MainMenu, header, footer { visibility: hidden; }
.stDeployButton { display: none; }
html, body, [class*="css"] { font-family: 'Inter','Segoe UI',sans-serif; }
.block-container { padding-top:1.4rem; padding-bottom:2rem; max-width:960px; }

/* ── Sidebar dark ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0f172a 0%,#1e293b 100%) !important;
}
section[data-testid="stSidebar"] * { color:#e2e8f0 !important; }
section[data-testid="stSidebar"] hr { border-color:#334155 !important; }
section[data-testid="stSidebar"] .stButton>button {
    background:#334155 !important; color:#f1f5f9 !important;
    border:1px solid #475569 !important; border-radius:8px !important; width:100%;
}
section[data-testid="stSidebar"] .stButton>button:hover {
    background:#ef4444 !important; border-color:#ef4444 !important;
}

/* ── Buttons ── */
div.stButton>button {
    border-radius:10px; font-weight:700; font-size:0.95rem;
    transition:all .2s ease; height:48px; letter-spacing:.3px;
}
div.stButton>button[kind="primary"] {
    background:linear-gradient(135deg,#1d4ed8,#2563eb) !important;
    color:#fff !important; border:none !important;
}
div.stButton>button[kind="primary"]:hover {
    background:linear-gradient(135deg,#1e40af,#1d4ed8) !important;
    transform:translateY(-2px); box-shadow:0 8px 20px rgba(37,99,235,.35) !important;
}
div.stButton>button:not([kind="primary"]):hover {
    transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,.15);
}

/* ── Download button ── */
div.stDownloadButton>button {
    background:linear-gradient(135deg,#059669,#10b981) !important;
    color:#fff !important; border:none !important; border-radius:10px !important;
    height:52px !important; font-size:1.05rem !important;
    font-weight:800 !important; letter-spacing:.5px !important;
}
div.stDownloadButton>button:hover {
    background:linear-gradient(135deg,#047857,#059669) !important;
    transform:translateY(-2px) !important;
    box-shadow:0 8px 24px rgba(16,185,129,.4) !important;
}

/* ── Cards ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius:14px !important; border:1.5px solid #e2e8f0 !important;
    box-shadow:0 2px 10px rgba(0,0,0,.06); padding:6px 4px !important;
}

/* ── Tabs ── */
div[data-testid="stTabs"] button { font-weight:600 !important; font-size:.93rem !important; border-radius:8px 8px 0 0 !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color:#1d4ed8 !important; border-bottom:3px solid #1d4ed8 !important; }

/* ── Section titles ── */
.sec-title {
    font-size:.8rem; font-weight:800; color:#1d4ed8; text-transform:uppercase;
    letter-spacing:1.2px; margin:14px 0 6px; padding-left:10px;
    border-left:3px solid #1d4ed8;
}

/* ── Control box ── */
.control-box {
    background:#eff6ff; border:1.5px solid #bfdbfe;
    border-radius:12px; padding:12px 16px; margin:10px 0 14px;
}

/* ── Terminal log ── */
.log-box {
    background:#0f172a; color:#7dd3fc;
    font-family:'JetBrains Mono','Courier New',monospace;
    font-size:.76rem; line-height:1.75; padding:14px 18px;
    border-radius:10px; max-height:220px; overflow-y:auto;
    margin-top:10px; border:1px solid #1e3a5f;
    white-space:pre-wrap; word-break:break-word;
}

/* ── Badges ── */
.badge-ok  { background:#dcfce7; color:#166534; border-radius:20px; padding:3px 12px; font-size:.8rem; font-weight:700; }
.badge-err { background:#fee2e2; color:#991b1b; border-radius:20px; padding:3px 12px; font-size:.8rem; font-weight:700; }

/* ── Guide box ── */
.guide-box {
    background:linear-gradient(135deg,#f0f9ff,#e0f2fe);
    border:1.5px solid #7dd3fc; border-radius:12px;
    padding:18px 22px; margin-bottom:16px; font-size:.88rem; line-height:1.85;
}
.guide-box b { color:#0369a1; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════
for key, val in [("download_status","idle"),("logged_in",False)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ══════════════════════════════════════════════════════════════
# ĐĂNG NHẬP
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    _, col, _ = st.columns([1,1.5,1])
    with col:
        st.markdown("""
        <div style='text-align:center;padding:28px 0 10px'>
            <div style='font-size:3.2rem'>🖼️</div>
            <h1 style='color:#1e3a8a;margin:0;font-size:1.8rem;font-weight:900'>Media Tool Pro</h1>
            <p style='color:#64748b;margin:6px 0 22px;font-size:.9rem'>
                Tự động Resize & Tải ảnh — TGDD / DMX / Google Drive
            </p>
        </div>""", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            username = st.text_input("👤 Tài khoản", placeholder="Nhập tài khoản...")
            password = st.text_input("🔑 Mật khẩu", type="password", placeholder="Nhập mật khẩu...")
            st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
            if st.button("🚀  Đăng Nhập", type="primary", use_container_width=True):
                if username == "ducpro" and password == "234766":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("❌ Sai tài khoản hoặc mật khẩu!")
        st.markdown("<p style='text-align:center;color:#94a3b8;font-size:.76rem;margin-top:14px'>© 2025 Media Tool Pro · v3.1</p>", unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:18px 0 8px'>
        <div style='font-size:2.5rem'>🖼️</div>
        <div style='font-size:1.05rem;font-weight:800;color:#f1f5f9'>Media Tool Pro</div>
        <div style='font-size:.73rem;color:#94a3b8'>v3.1 · ducpro</div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<span class="badge-ok">✅ Drive API: Kết nối</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">⚠️ Drive API: Chưa kết nối</span>', unsafe_allow_html=True)
        st.caption("Cần `credentials.json` hoặc Streamlit Secrets.")
    st.divider()

    st.markdown("**📐 Kích thước hỗ trợ:**")
    st.caption("• 1020×680 — Ảnh ngang chuẩn\n• 1020×570 — Ảnh ngang rộng\n• 1200×1200 — Ảnh vuông\n• 1000×1000 — Photoshop Crop\n• Gốc — Không resize")
    st.divider()

    st.markdown("**⚡ Tính năng:**")
    st.caption("✅ Giữ tỉ lệ ảnh gốc\n✅ Fill nền trắng\n✅ Điều chỉnh phóng to ảnh nhỏ\n✅ Crop 1:1 kiểu Photoshop\n✅ Xem trước ảnh sau resize\n✅ Đặt tên hàng loạt\n✅ Lịch sử xử lý\n✅ ZIP có cấu trúc rõ ràng")
    st.divider()

    # ── LỊCH SỬ XỬ LÝ ──
    st.markdown("**📋 Lịch sử xử lý:**")
    from utils import render_history_sidebar
    render_history_sidebar()
    st.divider()

    if st.button("🚪  Đăng Xuất", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ══════════════════════════════════════════════════════════════
# IMPORT MODES
# ══════════════════════════════════════════════════════════════
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web   import run_mode_web

# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div style='margin-bottom:16px'>
    <h1 style='color:#1e3a8a;margin:0;font-size:1.9rem;font-weight:900'>🖼️ Media Tool Pro</h1>
    <p style='color:#64748b;margin:3px 0 0;font-size:.9rem'>Tải · Resize · Đóng gói ZIP</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# SIZE OPTIONS (dùng chung)
# ══════════════════════════════════════════════════════════════
SIZE_OPTIONS = {
    "🖼️  1020 × 680  —  Ngang chuẩn":          (1020, 680,  "letterbox"),
    "🖼️  1020 × 570  —  Ngang rộng":           (1020, 570,  "letterbox"),
    "🖼️  1200 × 1200  —  Vuông":                (1200, 1200, "letterbox"),
    "✂️  1000 × 1000  —  Photoshop Crop 1:1":   (1000, 1000, "crop_1000"),
    "📦  Tải hình gốc  —  Không Resize":        (None, None, "letterbox"),
}

# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "🌐  Google Drive",
    "💻  Máy Tính (Local)",
    "🛒  Web (TGDD / DMX)",
    "📖  Hướng Dẫn",
])

# ── TAB 1: DRIVE ──────────────────────────────────────────────
with tab1:
    with st.container(border=True):
        size_key_1 = st.selectbox(
            "📐 Kích thước Resize:", list(SIZE_OPTIONS.keys()), key="sz_drive",
            help="Ảnh giữ tỉ lệ gốc, phần thừa fill trắng — không bao giờ méo ảnh")
        w1, h1, mode1 = SIZE_OPTIONS[size_key_1]

        # Hiện slider scale khi KHÔNG phải mode crop_1000 và KHÔNG phải tải gốc
        if mode1 == "letterbox" and w1 is not None:
            scale1 = st.slider(
                "🔍 Tỉ lệ phóng to ảnh trên canvas (%):",
                min_value=50, max_value=150, value=100, step=5,
                key="scale_drive",
                help="100% = vừa khung. >100% = ảnh to hơn (có thể bị crop). <100% = ảnh nhỏ hơn (nhiều viền trắng)")
        else:
            scale1 = 100

        rename1 = st.toggle("✏️ Đặt tên hàng loạt (VD: TenSP_Mau_01.jpg)", value=False, key="rename_drive")
    st.write("")
    run_mode_drive(w1, h1, drive_service, scale_pct=scale1, mode=mode1, rename=rename1)

# ── TAB 2: LOCAL ──────────────────────────────────────────────
with tab2:
    with st.container(border=True):
        size_key_2 = st.selectbox(
            "📐 Kích thước Resize:", list(SIZE_OPTIONS.keys()), key="sz_local")
        w2, h2, mode2 = SIZE_OPTIONS[size_key_2]

        if mode2 == "letterbox" and w2 is not None:
            scale2 = st.slider(
                "🔍 Tỉ lệ phóng to ảnh trên canvas (%):",
                min_value=50, max_value=150, value=100, step=5,
                key="scale_local",
                help="100% = vừa khung. >100% = ảnh to hơn (có thể bị crop). <100% = ảnh nhỏ hơn (nhiều viền trắng)")
        else:
            scale2 = 100

        rename2 = st.toggle("✏️ Đặt tên hàng loạt (VD: TenSP_Mau_01.jpg)", value=False, key="rename_local")
    st.write("")
    run_mode_local(w2, h2, scale_pct=scale2, mode=mode2, rename=rename2)

# ── TAB 3: WEB ────────────────────────────────────────────────
with tab3:
    with st.container(border=True):
        size_key_3 = st.selectbox(
            "📐 Kích thước Resize:", list(SIZE_OPTIONS.keys()), key="sz_web")
        w3, h3, mode3 = SIZE_OPTIONS[size_key_3]

        if mode3 == "letterbox" and w3 is not None:
            scale3 = st.slider(
                "🔍 Tỉ lệ phóng to ảnh trên canvas (%):",
                min_value=50, max_value=150, value=100, step=5,
                key="scale_web",
                help="100% = vừa khung. >100% = ảnh to hơn (có thể bị crop). <100% = ảnh nhỏ hơn (nhiều viền trắng)")
        else:
            scale3 = 100

        rename3 = st.toggle("✏️ Đặt tên hàng loạt (VD: TenSP_Mau_01.jpg)", value=False, key="rename_web")
    st.write("")
    run_mode_web(w3, h3, scale_pct=scale3, mode=mode3, rename=rename3)

# ── TAB 4: HƯỚNG DẪN ──────────────────────────────────────────
with tab4:
    st.markdown("""
    <div class="guide-box">
        <div style='font-size:1.05rem;font-weight:800;color:#0c4a6e;margin-bottom:10px'>
            📋 TỔNG QUAN — Media Tool Pro v3.1
        </div>
        <b>Media Tool Pro</b> là công cụ xử lý ảnh sản phẩm chạy hoàn toàn trên trình duyệt.
        Tự động tải ảnh từ nhiều nguồn, resize về đúng kích thước chuẩn, giữ nguyên tỉ lệ,
        đóng gói ZIP có cấu trúc thư mục rõ ràng — sẵn sàng để upload lên website hay sàn TMĐT.
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("🌐 Google Drive — Hướng dẫn chi tiết", expanded=True):
            st.markdown("""
**Mục đích:** Tải ảnh từ thư mục / file đơn trên Google Drive, resize, tải về ZIP.

---
**📌 B1 — Chia sẻ đúng quyền**
- Vào Drive → Chuột phải thư mục/file → **Chia sẻ**
- Chọn **"Bất kỳ ai có đường liên kết"** — Quyền: Người xem

**📌 B2 — Copy link & dán vào ô**
- Hỗ trợ link thư mục và link file đơn
- Mỗi link 1 dòng — có thể dán nhiều link cùng lúc

**📌 B3 — Chọn kích thước + điều chỉnh tỉ lệ → Bắt đầu**

**📌 B4 — Tải ZIP về máy**
- ZIP giữ đúng tên thư mục Drive gốc
- Cấu trúc: `tên_thư_mục/ảnh.jpg`

---
**⚠️ Lưu ý quan trọng:**
- Nếu link lỗi → **tự động bỏ qua**, tải link tiếp theo
- Thư mục giới hạn **7 ảnh** để tránh timeout
- Không hỗ trợ Drive cá nhân chưa chia sẻ public
            """)

        with st.expander("💻 Local (Máy tính) — Hướng dẫn chi tiết"):
            st.markdown("""
**Mục đích:** Upload ZIP ảnh từ máy, resize hàng loạt, tải về ZIP kết quả.

---
**📌 B1 — Tạo file ZIP đúng cấu trúc**
```
my_images.zip
├── Samsung_S25/
│   ├── Den/  ← ảnh màu đen
│   └── Trang/ ← ảnh màu trắng
└── iPhone_16/
    └── Xanh/
```

**📌 B2 — Upload ZIP** (tối đa ~200MB)

**📌 B3 — Chọn kích thước + điều chỉnh tỉ lệ → Bắt đầu**

**📌 B4 — Tải ZIP kết quả**
- Giữ nguyên cấu trúc thư mục
- Tất cả ảnh output là **.jpg** chất lượng 95%

---
**⚠️ Lưu ý:**
- Chỉ hỗ trợ **.zip** (không rar, 7z)
- File `__MACOSX`, `.DS_Store` tự động bỏ qua
- Định dạng ảnh: jpg, png, webp, bmp
            """)

    with c2:
        with st.expander("🛒 Web TGDD/DMX — Hướng dẫn chi tiết", expanded=True):
            st.markdown("""
**Mục đích:** Tự động tải toàn bộ ảnh sản phẩm từ website TGDD & DMX.

---
**📌 B1 — Copy link sản phẩm**

Ví dụ:
```
https://www.thegioididong.com/dtdd/samsung-galaxy-s25
https://www.dienmayxanh.com/tivi/...
```

**📌 B2 — Quét màu**
- Dán link (nhiều link → mỗi dòng 1 link)
- Bấm **🔍 Quét sản phẩm & màu**
- Hệ thống tự phát hiện các biến thể màu

**📌 B3 — Tick chọn màu cần tải**
- Mặc định tick hết tất cả màu
- Bỏ tick màu không cần

**📌 B4 — Tải & Resize → Tải ZIP**
- Cấu trúc ZIP: `tên_sp/tên_màu/ảnh.jpg`
- Ảnh lỗi → bỏ qua, tải màu tiếp theo

---
**⚠️ Lưu ý:**
- Nếu ảnh không tải được → **tự động bỏ qua**
- Số ảnh phụ thuộc gallery trang gốc
            """)

        with st.expander("🔧 Resize hoạt động như thế nào?"):
            st.markdown("""
**Thuật toán Letterbox Resize:**

1. Scale ảnh **vừa khung**, giữ nguyên tỉ lệ
2. Phần trống → **fill màu trắng** (không crop, không méo)
3. Xuất **.jpg** chất lượng 95%, nén tối ưu
4. **Thanh trượt tỉ lệ**: điều chỉnh % phóng to/thu nhỏ so với kích thước vừa khung

**Thuật toán Photoshop Crop 1:1 (1000×1000):**

1. Ảnh lớn → crop chính giữa 1:1 → resize down về 1000×1000
2. Ảnh nhỏ → giữ nguyên, đặt vào nền trắng 1000×1000

**Kích thước phù hợp:**
| Size | Dùng cho |
|------|---------|
| 1020×680 | Banner ngang, điện thoại |
| 1020×570 | Ảnh ngang rộng 16:9 |
| 1200×1200 | Shopee, Lazada, TikTok Shop |
| 1000×1000 | Photoshop Crop 1:1 |
| Gốc | Giữ nguyên không xử lý |
            """)

        with st.expander("❓ Lỗi thường gặp & cách xử lý"):
            st.markdown("""
| Lỗi | Nguyên nhân | Cách xử lý |
|-----|-------------|------------|
| ❌ Không tải được Drive | Chưa chia sẻ public | Chia sẻ "Bất kỳ ai có link" |
| ❌ ZIP rỗng / không có file | Ảnh bị lỗi hết | Kiểm tra link / file ZIP |
| ⚠️ Bỏ qua link | Link lỗi bình thường | Xem log để biết link nào lỗi |
| 🐢 Chạy chậm | Server Streamlit Cloud | Đợi hoặc giảm số link |
| ❌ File ZIP không hợp lệ | File bị hỏng khi nén | Nén lại từ đầu |
            """)

    st.divider()
    st.markdown("""
    <div style='text-align:center;color:#94a3b8;font-size:.8rem;padding:8px 0'>
        🖼️ <b>Media Tool Pro v3.1</b> · Python & Streamlit ·
        Hỗ trợ: Google Drive · TheGiớiDiĐộng · ĐiệnMáyXanh · Local ZIP
    </div>""", unsafe_allow_html=True)
