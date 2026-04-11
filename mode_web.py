import streamlit as st
import os
import re
import time
import requests
import shutil
import tempfile
import concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils import (resize_image, create_drive_folder, upload_to_drive, 
                   check_pause_cancel_state, render_control_buttons)

RAW_COOKIES = [
    {"domain": ".thegioididong.com", "name": "_ce.clock_data", "value": "-110%2C113.161.59.60%2C1%2C91e1a2a41c0741f7f47615ab9de2fb8a%2CChrome%2CVN"},
    {"domain": ".thegioididong.com", "name": "_ce.s", "value": "v~10b349a1bfb597f2fbfafdd33af1d88e35768560~lcw~1775808302291~vir~returning~lva~1775788787457~vpv~198~v11ls~8496c620-34b3-11f1-b933-8983fd7f9723"},
    {"domain": ".thegioididong.com", "name": "cebs", "value": "1"},
    {"domain": ".thegioididong.com", "name": "cebsp_", "value": "32"},
    {"domain": ".thegioididong.com", "name": "mwgsp", "value": "1"},
    {"domain": "www.thegioididong.com", "name": "ASP.NET_SessionId", "value": "zgo0wxmkgvnqbqub0lkreuon"},
    {"domain": "www.thegioididong.com", "name": "SvID", "value": "beline26122|adivM|adhi9"},
    {"domain": "www.thegioididong.com", "name": "TBMCookie_3209819802479625248", "value": "272331001775808103SbF4f4kGHIEXWQ8vk5fTCgPn/0Q="}
]
TGDD_COOKIES_DICT = {c['name']: c['value'] for c in RAW_COOKIES}

def resolve_redirect_url(url: str) -> str:
    if "/sp-" in url or "/dtdd-" in url or "/may-tinh-bang-" in url:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, cookies=TGDD_COOKIES_DICT, allow_redirects=True, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
                if meta_refresh:
                    content = meta_refresh.get("content", "")
                    if "url=" in content.lower(): return urljoin(url, content.split("url=")[-1].strip("'\""))
            return response.url
        except: pass
    return url

def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]', "", name)).strip()

def get_item_name(main_url):
    try:
        response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"}, cookies=TGDD_COOKIES_DICT, timeout=10)
        if response.status_code != 200: return "Sản_phẩm_không_tên"
        soup = BeautifulSoup(response.text, "html.parser")
        name_tag = soup.find("h1")
        if name_tag: name = name_tag.text.strip()
        else:
            match = re.search(r'item_name\s*:\s*"(.*?)"', soup.get_text())
            name = match.group(1) if match else (soup.find("title").text.split("|")[0].strip() if soup.find("title") else "Sản phẩm")
        name = re.sub(r"(,?\s*(giá tốt|thu cũ.*|trợ giá.*|góp 0%.*))", "", name, flags=re.IGNORECASE)
        return clean_name(name)
    except: return "Sản_phẩm_không_tên"

def get_color_links_and_names(main_url):
    try:
        response = requests.get(main_url, headers={"User-Agent": "Mozilla/5.0"}, cookies=TGDD_COOKIES_DICT, timeout=10)
        if response.status_code != 200: return []
        soup = BeautifulSoup(response.text, "html.parser")
        base_path = urlparse(main_url).path
        color_data = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if base_path in href and "?code=" in href:
                c_name = a.get_text(strip=True)
                c_link = urljoin(main_url, href)
                if c_name and c_link not in [c["link"] for c in color_data]:
                    color_data.append({"name": clean_name(c_name), "link": c_link})
        return color_data if color_data else [{"name": "Mặc định", "link": main_url}]
    except: return [{"name": "Mặc định", "link": main_url}]

def get_gallery_image_urls(product_url):
    try:
        response = requests.get(product_url, headers={"User-Agent": "Mozilla/5.0"}, cookies=TGDD_COOKIES_DICT, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        img_urls = []
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src")
            if src:
                if "-750x500" in src or "-800x800" in src:
                    img_urls.append(re.sub(r"-\d+x\d+", "", urljoin(product_url, src)))
                elif ("/product/" in src or "/dien-thoai/" in src) and (".jpg" in src or ".png" in src):
                    img_urls.append(urljoin(product_url, src))
        return list(set(img_urls))
    except: return []

def run_mode_web(w, h, drive_service, extract_drive_id_and_type):
    st.info("💡 **HƯỚNG DẪN:** Dán link sản phẩm. Hệ thống tự quét màu.")
    
    if "web_scanned_data" not in st.session_state:
        st.session_state["web_scanned_data"] = []
    if "web_zip_data" not in st.session_state:
        st.session_state.web_zip_data = None

    links_text = st.text_area("🔗 Dán Link sản phẩm (Mỗi link 1 dòng):", height=100)
    
    if st.button("🔍 QUÉT SẢN PHẨM & MÀU", use_container_width=True):
        links = [l.strip() for l in links_text.splitlines() if l.strip()]
        if not links: st.error("⚠️ Vui lòng dán link!")
        else:
            with st.spinner("Đang quét..."):
                scanned_data = []
                def scan_url_worker(link):
                    real_link = resolve_redirect_url(link)
                    return {"original_link": link, "real_link": real_link, "product_name": get_item_name(real_link), "colors": get_color_links_and_names(real_link)}

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(scan_url_worker, l) for l in links]
                    for future in concurrent.futures.as_completed(futures):
                        try: scanned_data.append(future.result())
                        except: pass
                st.session_state["web_scanned_data"] = scanned_data
            st.success("✅ Đã quét xong! Chọn màu bên dưới.")

    if st.session_state["web_scanned_data"]:
        st.markdown("---")
        st.markdown("### 🎨 CHỌN MÀU")
        selected_tasks = []
        
        for idx_item, item in enumerate(st.session_state["web_scanned_data"]):
            st.markdown(f"**📦 {item['product_name']}**")
            cols = st.columns(3)
            for idx_color, color in enumerate(item["colors"]):
                with cols[idx_color % 3]:
                    unique_key = f"cb_{idx_item}_{idx_color}_{hash(item['original_link'])}"
                    if st.checkbox(color["name"], value=True, key=unique_key):
                        selected_tasks.append({"product_name": item["product_name"], "color_name": color["name"], "link": color["link"]})
        
        st.markdown("---")
        upload_link_web = st.text_input("Link Drive ĐÍCH:", placeholder="Bỏ trống nếu chỉ lấy ZIP")
        
        if st.button("🚀 BẮT ĐẦU TẢI & RESIZE", type="primary", use_container_width=True):
            st.session_state.download_status = 'running'
            st.session_state.web_zip_data = None
            
            if not selected_tasks:
                st.error("⚠️ Bạn chưa chọn màu!")
                st.session_state.download_status = 'idle'
            else:
                render_control_buttons()
                target_folder_id, _ = extract_drive_id_and_type(upload_link_web) if upload_link_web else (None, None)
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    raw_dir = temp_path / "RAW"
                    final_dir = temp_path / "FINAL"
                    
                    status_text = st.empty()
                    progress_bar = st.progress(0)
                    total_tasks = len(selected_tasks)

                    def process_image_url(img_url, c_raw_dir, c_final_dir, headers):
                        # BẢO VỆ LUỒNG: Không gán check_pause_cancel_state() ở đây để tránh lỗi crash
                        try:
                            img_name = os.path.basename(img_url.split("?")[0])
                            save_path = c_raw_dir / img_name
                            out_file = c_final_dir / f"{save_path.stem}.jpg"
                            img_data = requests.get(img_url, headers=headers, cookies=TGDD_COOKIES_DICT, timeout=10).content
                            with open(save_path, "wb") as f: f.write(img_data)
                            resize_image(save_path, out_file, w, h)
                        except: pass

                    for i, task in enumerate(selected_tasks):
                        if not check_pause_cancel_state(): break
                        p_name, c_name, c_link = task["product_name"], task["color_name"], task["link"]
                        status_text.info(f"⏳ Đang xử lý: {p_name} - {c_name} ({i+1}/{total_tasks})")
                        
                        c_raw_dir = raw_dir / p_name / c_name
                        c_final_dir = final_dir / p_name / c_name
                        c_raw_dir.mkdir(parents=True, exist_ok=True)
                        c_final_dir.mkdir(parents=True, exist_ok=True)
                        
                        img_urls = get_gallery_image_urls(c_link)
                        if not img_urls:
                            st.warning(f"⚠️ Không tìm thấy ảnh cho {c_name}")
                            
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            futures = [executor.submit(process_image_url, url, c_raw_dir, c_final_dir, {"User-Agent": "Mozilla/5.0"}) for url in img_urls]
                            concurrent.futures.wait(futures)
                            
                        progress_bar.progress((i + 1) / total_tasks)
                    
                    if target_folder_id and drive_service and check_pause_cancel_state():
                        status_text.info("📤 Đang Upload lên Google Drive...")
                        try:
                            root_folder_id = create_drive_folder(drive_service, f"Web_Resized_{int(time.time())}", target_folder_id)
                            folder_cache = {"": root_folder_id, ".": root_folder_id}
                            for img in final_dir.rglob("*.jpg"):
                                if not check_pause_cancel_state(): break
                                rel_dir_str = str(img.parent.relative_to(final_dir))
                                if rel_dir_str not in folder_cache:
                                    current_parent = root_folder_id
                                    current_path = ""
                                    for part in Path(rel_dir_str).parts:
                                        current_path = os.path.join(current_path, part) if current_path else part
                                        if current_path not in folder_cache:
                                            folder_cache[current_path] = create_drive_folder(drive_service, part, current_parent)
                                        current_parent = folder_cache[current_path]
                                    upload_to_drive(drive_service, img, folder_cache[rel_dir_str])
                        except: pass

                    if st.session_state.download_status == 'cancelled':
                        status_text.error("🚫 Đã hủy quá trình!")
                    else:
                        status_text.success("🎉 Hoàn tất!")
                        shutil.make_archive(str(temp_path / "Web_Images_Done"), 'zip', final_dir)
                        
                        if os.path.exists(temp_path / "Web_Images_Done.zip"):
                            with open(temp_path / "Web_Images_Done.zip", "rb") as f:
                                st.session_state.web_zip_data = f.read()
                                
                    st.session_state.download_status = 'idle'
                    
        if st.session_state.get('web_zip_data'):
            st.download_button(
                label="📥 TẢI KẾT QUẢ VỀ MÁY", 
                data=st.session_state.web_zip_data, 
                file_name="Web_Images_Done.zip", 
                mime="application/zip", 
                use_container_width=True, 
                type="primary"
            )
