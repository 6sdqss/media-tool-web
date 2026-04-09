import streamlit as st
import json
import re
import os
import html
import shutil
import tempfile
import pandas as pd
from pathlib import Path
from PIL import Image
import gdown

# ==========================================
# CẤU HÌNH GIAO DIỆN & TIỆN ÍCH CHUNG
# ==========================================
st.set_page_config(page_title="Media Hub Pro", layout="wide", page_icon="⚡")

st.markdown("""
<style>
    div.stButton > button:first-child { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 60px; background-color: transparent; border-radius: 8px 8px 0px 0px; font-size: 18px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

KEYWORD_FILE = "keywords.json"
WEB_OPTIONS = ["Thế Giới Di Động", "Điện Máy Xanh", "TopZone"]

# ==========================================
# HÀM LOGIC DÙNG CHUNG
# ==========================================
@st.cache_data(ttl=1)
def load_keywords():
    if os.path.exists(KEYWORD_FILE):
        try:
            with open(KEYWORD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for w in WEB_OPTIONS:
                    if w not in data: data[w] = {}
                return data
        except: pass
    return {w: {} for w in WEB_OPTIONS}

def save_keywords(data):
    with open(KEYWORD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_drive_id_and_type(url: str):
    folder_match = re.search(r"drive/folders/([a-zA-Z0-9_-]+)", url)
    file_match = re.search(r"file/d/([a-zA-Z0-9_-]+)", url)
    id_match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if folder_match: return folder_match.group(1), "folder"
    elif file_match: return file_match.group(1), "file"
    elif id_match: return id_match.group(1), "file"
    return None, None

def resize_image_logic(image_path: Path, width=1020, height=680):
    try:
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            else:
                img = img.convert("RGB")

            if width and height:
                img_ratio = img.width / img.height
                target_ratio = width / height
                if img_ratio > target_ratio:
                    new_w, new_h = width, int(width / img_ratio)
                else:
                    new_w, new_h = int(height * img_ratio), height

                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                new_img = Image.new("RGB", (width, height), (255, 255, 255))
                new_img.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
            else:
                new_img = img 

            save_path = image_path.with_suffix(".jpg")
            new_img.save(save_path, "JPEG", quality=95)
            if str(image_path) != str(save_path):
                image_path.unlink(missing_ok=True)
    except Exception as e: pass

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>⚡ Trung Tâm Xử Lý Content & Media</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #6B7280; font-size: 16px; margin-bottom: 30px;'>Công cụ tối ưu hiệu suất dành riêng cho team. Xử lý hàng loạt chỉ trong chớp mắt.</p>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 TOOL CHÈN LINK TỰ ĐỘNG", "🖼️ TOOL TẢI & RESIZE ẢNH"])

# ----------------- TAB 1: CHÈN LINK -----------------
with tab1:
    col1, col2 = st.columns([1, 1.5], gap="large")
    
    with col1:
        st.subheader("📚 1. Cập nhật Bảng Từ khóa")
        with st.container(border=True):
            kw_data = load_keywords()
            web_selected = st.selectbox("🎯 Chọn Website mục tiêu:", WEB_OPTIONS)
            
            st.caption("✨ Tích 'Sử dụng' để bật từ khóa. Bạn có thể Bôi đen -> Copy từ Excel và Dán trực tiếp vào bảng này.")
            df_data = [{"Sử dụng": True, "Từ khóa": k, "Link": v} for k, v in kw_data[web_selected].items()]
            df = pd.DataFrame(df_data) if df_data else pd.DataFrame(columns=["Sử dụng", "Từ khóa", "Link"])
            if not df.empty: df["Sử dụng"] = df["Sử dụng"].astype(bool)
            
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True, height=400)
            
            if st.button("💾 Lưu thay đổi Từ Khóa", use_container_width=True):
                new_dict = {}
                for _, row in edited_df.iterrows():
                    kw = str(row.get("Từ khóa", "")).strip()
                    lk = str(row.get("Link", "")).strip()
                    if kw and kw != "nan" and lk and lk != "nan":
                        new_dict[kw] = lk
                kw_data[web_selected] = new_dict
                save_keywords(kw_data)
                load_keywords.clear()
                st.toast("✅ Đã cập nhật database từ khóa!", icon="🎉")

    with col2:
        st.subheader("📝 2. Xử lý Nội dung")
        raw_text = st.text_area("Dán bài viết của bạn vào đây:", height=300, placeholder="Dán văn bản text vào đây...")
        
        if raw_text:
            with st.expander("🛠️ Cài đặt thẻ H3", expanded=False):
                blocks = [b.strip() for b in re.split(r'\n\s*\n', raw_text) if b.strip()]
                h3_options = {i: f"Đoạn {i+1}: {blocks[i][:60]}..." for i in range(len(blocks))}
                selected_h3 = st.multiselect("Chọn đoạn muốn gán thẻ <h3>:", options=list(h3_options.keys()), format_func=lambda x: h3_options[x])

            if st.button("⚡ TẠO HTML CHÈN LINK", type="primary", use_container_width=True):
                with st.spinner("Đang chèn link..."):
                    active_kws = edited_df[edited_df["Sử dụng"] == True]
                    selected_kw_dict = {str(r["Từ khóa"]).strip(): str(r["Link"]).strip() for _, r in active_kws.iterrows() if str(r["Từ khóa"]).strip() != "nan"}

                    anchors_map = {}
                    # BẢN FIX LỖI: Dùng Dictionary để tránh lỗi phạm vi biến (scope)
                    anchor_state = {"counter": 0} 

                    def new_anchor_token(anchor_html):
                        token = f"[[ANCHOR_{anchor_state['counter']}]]"
                        anchors_map[token] = anchor_html
                        anchor_state["counter"] += 1
                        return token

                    kw_items = sorted(selected_kw_dict.items(), key=lambda x: len(x[0]), reverse=True)
                    formatted_blocks = [{'tag': 'h3' if i in selected_h3 else 'p', 'text': p} for i, p in enumerate(blocks)]

                    for kw, link in kw_items:
                        pattern = re.compile(rf'\b{re.escape(kw)}\b', flags=re.IGNORECASE)
                        anchor_html = f'<a href="{html.escape(link)}" target="_blank" title="Tham khảo {html.escape(kw)} tại {web_selected}">{html.escape(kw)}</a>'
                        token = new_anchor_token(anchor_html)
                        for b in formatted_blocks:
                            new_text, n = pattern.subn(lambda m: token, b['text'], count=1)
                            if n > 0:
                                b['text'] = new_text
                                break 

                    token_regex = re.compile(r'(\[\[ANCHOR_\d+\]\])')
                    final_parts = []
                    for b in formatted_blocks:
                        parts = token_regex.split(b['text'])
                        rendered = [anchors_map[p] if p in anchors_map else html.escape(p).replace("\n", "<br/>") for p in parts]
                        final_parts.append(f"<{b['tag']}>{''.join(rendered)}</{b['tag']}>")

                    final_html = "\n\n".join(final_parts)
                    
                    st.success("✨ Tạo HTML thành công!")
                    st.balloons()
                    st.code(final_html, language="html")
                    st.download_button("📥 TẢI FILE HTML", data=final_html, file_name="bai_viet_seo.html", mime="text/html", type="secondary")

# ----------------- TAB 2: RESIZE ẢNH -----------------
with tab2:
    st.subheader("⚙️ Nguồn Ảnh & Cấu hình")
    col_a, col_b = st.columns([1, 1], gap="medium")
    with col_a:
        mode = st.radio("Lấy ảnh từ đâu?", ["🌐 Tải hàng loạt Link/Thư mục từ Google Drive", "💻 Chọn nhiều ảnh từ máy tính (Local)"], horizontal=True)
    with col_b:
        size_opt = st.selectbox("Định dạng đầu ra (Resize lọt lòng bù nền trắng):", ["1020x680", "1020x570", "1200x1200", "Chỉ đổi nền trắng (Không đổi kích thước)"])
        w, h = (None, None) if "Không đổi kích thước" in size_opt else map(int, size_opt.split("x"))

    st.divider()

    if "Google Drive" in mode:
        links_text = st.text_area("🔗 Dán danh sách Link Drive (Mỗi link 1 dòng. Hỗ trợ cả link File và link Thư mục):", height=200)
        if st.button("🚀 XỬ LÝ ẢNH DRIVE", type="primary", use_container_width=True):
            links = [l.strip() for l in links_text.splitlines() if l.strip()]
            if not links: st.error("⚠️ Vui lòng dán link Drive!")
            else:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    progress_bar = st.progress(0, text="Đang bắt đầu...")
                    
                    for i, url in enumerate(links):
                        file_id, kind = extract_drive_id_and_type(url)
                        if not file_id: continue
                        
                        progress_bar.progress((i+1) / len(links), text=f"Đang xử lý link {i+1}/{len(links)}...")
                        if kind == "folder":
                            folder_out = temp_path / f"Folder_{file_id}"
                            folder_out.mkdir(exist_ok=True)
                            gdown.download_folder(id=file_id, output=str(folder_out), quiet=True)
                            for img in folder_out.rglob("*.*"):
                                if img.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]: resize_image_logic(img, w, h)
                        else:
                            file_out = temp_path / f"File_{file_id}.jpg"
                            gdown.download(f'https://drive.google.com/uc?id={file_id}', str(file_out), quiet=True)
                            if file_out.exists(): resize_image_logic(file_out, w, h)
                    
                    progress_bar.progress(1.0, text="Nén file ZIP hoàn tất!")
                    shutil.make_archive(temp_path / "Media_Output", 'zip', temp_path)
                    st.success("✨ Mọi thứ đã sẵn sàng!")
                    st.balloons()
                    with open(temp_path / "Media_Output.zip", "rb") as f:
                        st.download_button("📥 TẢI TOÀN BỘ ẢNH (ZIP)", f, file_name="Drive_Images_Resized.zip", mime="application/zip", type="primary", use_container_width=True)

    else:
        with st.container(border=True):
            st.info("💡 **Mẹo:** Bấm chọn `Upload files` -> Nhấn `Ctrl + A` (Windows) để chọn hàng loạt ảnh từ thư mục máy tính của bạn.")
            uploaded_files = st.file_uploader("Kéo thả hoặc tải ảnh lên", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'webp'])
            
        if st.button("🚀 BẮT ĐẦU RESIZE", type="primary", use_container_width=True):
            if not uploaded_files: st.error("⚠️ Bạn chưa tải ảnh nào lên!")
            else:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    progress_bar = st.progress(0, text="Đang xử lý ảnh...")
                    for i, file in enumerate(uploaded_files):
                        img_path = temp_path / file.name
                        with open(img_path, "wb") as f: f.write(file.getbuffer())
                        resize_image_logic(img_path, w, h)
                        progress_bar.progress((i + 1) / len(uploaded_files), text=f"Xong {i+1}/{len(uploaded_files)} ảnh...")
                    
                    shutil.make_archive(temp_path / "Local_Output", 'zip', temp_path)
                    st.success("✨ Xử lý thành công!")
                    st.balloons()
                    with open(temp_path / "Local_Output.zip", "rb") as f:
                        st.download_button("📥 TẢI TOÀN BỘ ẢNH (ZIP)", f, file_name="Local_Images_Resized.zip", mime="application/zip", type="primary", use_container_width=True)
