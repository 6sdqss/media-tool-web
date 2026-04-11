import streamlit as st
from utils import get_gdrive_service, extract_drive_id_and_type

# Phải gọi đầu tiên
st.set_page_config(page_title="Hệ thống Resize & Auto Upload", layout="centered", page_icon="🖼️")

st.markdown("""
<style>
    div.stButton > button:first-child { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; height: 45px; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .control-box { background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 10px; margin-bottom: 15px; border: 1px solid #e5e7eb;}
</style>
""", unsafe_allow_html=True)

if 'download_status' not in st.session_state:
    st.session_state.download_status = 'idle'

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A; margin-bottom: 20px;'>🔐 ĐĂNG NHẬP HỆ THỐNG</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        username = st.text_input("👤 Tài khoản:")
        password = st.text_input("🔑 Mật khẩu:", type="password")
        if st.button("Đăng nhập", type="primary", use_container_width=True):
            if username == "ducpro" and password == "234766":
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ Sai tài khoản hoặc mật khẩu. Vui lòng thử lại!")
    st.stop()

with st.sidebar:
    st.markdown("### 👤 Xin chào, **ducpro**")
    if st.button("🚪 Đăng xuất"):
        st.session_state["logged_in"] = False
        st.rerun()

# Import các logic điều khiển đã tách Module
from mode_drive import run_mode_drive
from mode_local import run_mode_local
from mode_web import run_mode_web

st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>📥 Tool Resize & Auto Upload Pro</h1>", unsafe_allow_html=True)

with st.container(border=True):
    mode = st.radio("Chế độ:", ["🌐 Tải từ Google Drive", "💻 Tải ảnh từ máy tính (Upload ZIP)", "🛒 Tải từ Web (TGDD / DMX)"], horizontal=True)
    size_options = {
        "Tải & resize 1020x680": (1020, 680),
        "Tải & resize 1020x570": (1020, 570),
        "Tải & resize 1200x1200": (1200, 1200),
        "Tải hình gốc (Không Resize)": (None, None)
    }
    w, h = size_options[st.selectbox("Kích thước Resize:", list(size_options.keys()))]

st.write("")
drive_service = get_gdrive_service()

# BỘ ĐIỀU HƯỚNG TỚI CÁC FILE MODULE
if "Google Drive" in mode:
    run_mode_drive(w, h, drive_service)
elif "máy tính" in mode or "Upload ZIP" in mode:
    # Giao diện của Local có thêm Upload Link nên cần lấy riêng ở đây
    upload_link = st.text_input("📤 Link Thư mục Drive ĐÍCH (Nếu muốn Auto Upload):", placeholder="Bỏ trống nếu chỉ lấy file ZIP")
    run_mode_local(w, h, drive_service, upload_link, extract_drive_id_and_type)
elif "Web" in mode:
    run_mode_web(w, h, drive_service, upload_link=None, extract_drive_id_and_type=extract_drive_id_and_type)