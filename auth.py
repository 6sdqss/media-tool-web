"""
auth.py — Authentication & Auto-Sync GitHub System
Quản lý đăng ký, đăng nhập, phân quyền và chống mất data trên Streamlit Cloud.
"""

import os
import json
import hashlib
import requests
import base64
import streamlit as st

DB_FILE = "users_db.json"

def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def push_to_github():
    """
    Đồng bộ file users_db.json lên GitHub để không bị mất data khi Streamlit reset.
    Yêu cầu cấu hình GITHUB_TOKEN và GITHUB_REPO trong st.secrets.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO")  # Định dạng: "username/repo"
    
    if not token or not repo:
        return # Nếu chưa cài secret thì chỉ chạy local (có thể mất data khi reset cloud)
        
    url = f"https://api.github.com/repos/{repo}/contents/{DB_FILE}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Lấy SHA của file hiện tại trên GitHub (để ghi đè)
    sha = None
    resp_get = requests.get(url, headers=headers)
    if resp_get.status_code == 200:
        sha = resp_get.json().get("sha")
        
    # 2. Đọc file local và mã hóa base64
    with open(DB_FILE, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
        
    # 3. Đẩy lên GitHub
    data = {
        "message": "Auto-sync users database [Media Tool Pro]",
        "content": content
    }
    if sha:
        data["sha"] = sha
        
    requests.put(url, headers=headers, json=data)

def load_db() -> dict:
    """Tải database từ file JSON. Nếu chưa có, tạo master admin mặc định."""
    if not os.path.exists(DB_FILE):
        db = {
            "ducpro": {
                "password": hash_password("234766"),
                "role": "admin",
                "status": "approved",
                "permissions": ["drive", "local", "web"]
            }
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4)
        return db
        
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_db(db: dict):
    """Lưu database và tự động đồng bộ lên GitHub."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)
    push_to_github()

def register_user(username, password):
    """Đăng ký tài khoản mới (trạng thái chờ duyệt)."""
    db = load_db()
    if username in db:
        return False, "Tài khoản đã tồn tại!"
    
    db[username] = {
        "password": hash_password(password),
        "role": "user",
        "status": "pending",  # Chờ Admin duyệt
        "permissions": []     # Chưa có quyền vào tab nào
    }
    save_db(db)
    return True, "Đăng ký thành công! Vui lòng chờ Admin duyệt."

def authenticate(username, password):
    """Kiểm tra đăng nhập."""
    db = load_db()
    user = db.get(username)
    
    if not user:
        return False, "Sai tài khoản hoặc mật khẩu!", None
        
    if user["password"] != hash_password(password):
        return False, "Sai tài khoản hoặc mật khẩu!", None
        
    if user["status"] == "pending":
        return False, "Tài khoản đang chờ Admin duyệt!", None
        
    if user["status"] == "banned":
        return False, "Tài khoản đã bị khóa!", None
        
    return True, "Thành công", user

def update_user_admin(username, new_status, new_permissions):
    """Admin cập nhật trạng thái và quyền của user."""
    db = load_db()
    if username in db:
        db[username]["status"] = new_status
        db[username]["permissions"] = new_permissions
        save_db(db)
        return True
    return False

def delete_user(username):
    """Admin xóa user."""
    db = load_db()
    if username in db and db[username]["role"] != "admin":
        del db[username]
        save_db(db)
        return True
    return False
