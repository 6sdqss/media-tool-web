import streamlit as st
from utils import get_gdrive_service, extract_drive_id_and_type

# ─────────────────────────────────────────────────────────────
# CẤU HÌNH TRANG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Media Tool Pro",
    layout="centered",
    page_icon="🖼️",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CSS TOÀN CỤC
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Ẩn menu mặc định Streamlit ── */
#MainMenu, header, footer { visibility: hidden; }

/* ── Layout ── */
.block-container { padding-top: 1.8rem; padding-bottom: 2rem; max-width: 780px; }

/* ── Nút bấm chính ── */
div.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.95rem;
    transition: all 0.25s ease;
    height: 46px;
}
div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.18);
}

/* ── Khung điều khiển Pause/Resume/Cancel ── */
.control-box {
    background: #f0f4ff;
    border: 1px solid #c7d2fe;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 10px 0 14px 0;
}

/* ── Log box ── */
.log-box {
    background: #0f172a;
    color: #94a3b8;
    font-family: 'Courier New', monospace;
    font-size: 0.78rem;
    line-height: 1.6;
    padding: 12px 16px;
    border-radius: 8px;
    max-height: 260px;
    overflow-y: auto;
    margin-top: 10px;
    border: 1px solid #1e293b;
}

/* ── Tiêu đề section ── */
h3 { color: #1e3a8a; margin-top: 1.2rem !important; }

/* ── Expander ── */
details > summary {
    font-weight: 600;
    font-size: 0.95rem;
}

/* ── Radio ngang ── */
div[role="radiogroup"] { gap: 6px; }

/* ── Nút download nổi bật ── */
div.stDownloadButton > button {
    background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    height: 48px !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
}
div.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%) !important;
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(37,99,235,0.35) !important;
}

/* ── Badge trạng thái API ── */
.api-badge-ok  { color: #16a34a; font-weight: 600; }
.api-badge-err { color: #dc2626; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# KHỞI TẠO SESSION STATE
# ─────────────────────────────────────────────────────────────
if "download_status" not in st.session_state:
    st.session_state.download_status = "idle"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ─────────────────────────────────────────────────────────────
# MÀN HÌNH ĐĂNG NHẬP
# ─────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    st.markdown(
        "<h1 style='text-align:center;color:#1E3A8A;margin-bottom:4px;'>🔐 ĐĂNG NHẬP HỆ THỐNG</h1>"
        "<p style='text-align:center;color:#64748b;margin-bottom:24px;'>Media Tool Pro — Resize & Upload Tự Động</p>",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        username = st.text_input("👤 Tài khoản:", placeholder="Nhập tài khoản...")
        password = st.text_input("🔑 Mật khẩu:", type="password", placeholder="Nhập mật khẩu...")
        st.write("")
        if st.button("🚀 Đăng nhập", type="primary", use_container_width=True):
            if username == "ducpro" and password == "234766":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu. Vui lòng thử lại!")
    st.stop()

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 👤 ducpro")
    st.caption("Media Tool Pro v2.0")
    st.divider()

    # Kiểm tra kết nối Google Drive API
    drive_service = get_gdrive_service()
    if drive_service:
        st.markdown('<p class="api-badge-ok">✅ Google Drive API: Kết nối</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="api-badge-err">⚠️ Google Drive API: Chưa kết nối</p>', unsafe_allow_html=True)
        st.caption("Cần `credentials.json` hoặc `st.secrets` để upload Drive.")

    st.divider()
    st.markdown("**📐 Kích thước resize:**")
    st.caption("Chọn ở khung bên phải")
    st.divider()

    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.download_status = "idle"
        st.rerun()

# ─────────────────────────────────────────────────────────────
# IMPORT MODE MODULES (sau khi đăng nhập)
# ─────────────────────────────────────────────────────────────
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web   import run_mode_web

# ─────────────────────────────────────────────────────────────
# TIÊU ĐỀ CHÍNH
# ─────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;color:#1E3A8A;margin-bottom:4px;'>"
    "🖼️ Media Tool Pro</h1>"
    "<p style='text-align:center;color:#64748b;margin-bottom:20px;'>"
    "Resize &amp; Auto Upload — TGDD / DMX / Google Drive / Local</p>",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────
# CHỌN CHẾ ĐỘ & KÍCH THƯỚC
# ─────────────────────────────────────────────────────────────
with st.container(border=True):
    mode = st.radio(
        "**Chế độ hoạt động:**",
        options=[
            "🌐 Tải từ Google Drive",
            "💻 Tải ảnh từ máy tính",
            "🛒 Tải từ Web (TGDD / DMX)",
        ],
        horizontal=True,
        label_visibility="visible",
    )

    size_options = {
        "🖼️  1020 × 680  (ngang)":        (1020, 680),
        "🖼️  1020 × 570  (ngang rộng)":   (1020, 570),
        "🖼️  1200 × 1200  (vuông)":        (1200, 1200),
        "📦  Tải hình gốc (Không Resize)": (None, None),
    }

    selected_size = st.selectbox(
        "**Kích thước Resize:**",
        list(size_options.keys()),
        help="Ảnh sẽ được giữ tỉ lệ gốc, phần còn lại fill màu trắng.",
    )
    w, h = size_options[selected_size]

st.write("")

# ─────────────────────────────────────────────────────────────
# DISPATCH VÀO TỪNG MODE
# ─────────────────────────────────────────────────────────────
if "Google Drive" in mode:
    run_mode_drive(w, h, drive_service)

elif "máy tính" in mode:
    upload_link = st.text_input(
        "📤 Link Thư mục Drive ĐÍCH:",
        placeholder="Bỏ trống nếu chỉ muốn tải ZIP về máy",
        key="local_upload_link",
    )
    run_mode_local(w, h, drive_service, upload_link, extract_drive_id_and_type)

elif "Web" in mode:
    run_mode_web(w, h, drive_service, extract_drive_id_and_type)
