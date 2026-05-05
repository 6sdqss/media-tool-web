"""
auth.py — Authentication & Auto-Sync GitHub System
Quản lý đăng ký, đăng nhập, phân quyền và chống mất data trên Streamlit Cloud.

Cơ chế chống mất tài khoản khi deploy lên Streamlit Cloud:
- Mỗi lần lưu user → push ngược file users_db.json lên GitHub repo
- Khi app khởi động → pull file mới nhất từ GitHub về
- Đảm bảo dữ liệu user luôn được đồng bộ giữa các phiên container
"""

from __future__ import annotations

import os
import json
import hashlib
import base64
import time
from typing import Tuple, Optional

import requests
import streamlit as st

DB_FILE = "users_db.json"
_LAST_PULL_KEY = "_last_github_pull_ts"
_PULL_INTERVAL_SECONDS = 30  # Pull lại sau mỗi 30s để giảm gọi API


# ═══════════════════════════════════════════════════════════════
# HASH MẬT KHẨU (SHA-256 + salt nội bộ)
# ═══════════════════════════════════════════════════════════════
_INTERNAL_SALT = "MediaToolProVIP_v7_2026"


def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng SHA-256 với salt nội bộ."""
    salted = f"{_INTERNAL_SALT}::{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════
# GITHUB SYNC — chống mất data trên Streamlit Cloud
# ═══════════════════════════════════════════════════════════════
def _get_github_config() -> Tuple[Optional[str], Optional[str], str]:
    """Đọc cấu hình GitHub từ st.secrets."""
    try:
        token = st.secrets.get("GITHUB_TOKEN", None)
        repo = st.secrets.get("GITHUB_REPO", None)
        branch = st.secrets.get("GITHUB_BRANCH", "main")
        return token, repo, branch
    except Exception:
        return None, None, "main"


def pull_from_github(force: bool = False) -> bool:
    """
    Tải file users_db.json mới nhất từ GitHub về local.
    - force=True: pull ngay không chờ throttle
    - force=False: chỉ pull nếu đã quá _PULL_INTERVAL_SECONDS từ lần trước
    """
    token, repo, branch = _get_github_config()
    if not token or not repo:
        return False

    # Throttle để giảm gọi API
    if not force:
        last_pull = st.session_state.get(_LAST_PULL_KEY, 0)
        if time.time() - last_pull < _PULL_INTERVAL_SECONDS:
            return False

    url = f"https://api.github.com/repos/{repo}/contents/{DB_FILE}?ref={branch}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            content_b64 = data.get("content", "")
            if content_b64:
                raw = base64.b64decode(content_b64)
                # Validate JSON trước khi ghi
                try:
                    json.loads(raw.decode("utf-8"))
                    with open(DB_FILE, "wb") as f:
                        f.write(raw)
                    st.session_state[_LAST_PULL_KEY] = time.time()
                    return True
                except Exception:
                    return False
    except Exception:
        return False
    return False


def push_to_github() -> bool:
    """Đẩy file users_db.json hiện tại lên GitHub (ghi đè)."""
    token, repo, branch = _get_github_config()
    if not token or not repo:
        return False
    if not os.path.exists(DB_FILE):
        return False

    url = f"https://api.github.com/repos/{repo}/contents/{DB_FILE}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Lấy SHA hiện tại để overwrite
    sha = None
    try:
        resp_get = requests.get(f"{url}?ref={branch}", headers=headers, timeout=12)
        if resp_get.status_code == 200:
            sha = resp_get.json().get("sha")
    except Exception:
        pass

    try:
        with open(DB_FILE, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "message": f"Auto-sync users DB · {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(url, headers=headers, json=payload, timeout=15)
        return put_resp.status_code in (200, 201)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# DATABASE LOCAL
# ═══════════════════════════════════════════════════════════════
DEFAULT_PERMISSIONS = ["web", "studio", "drive", "local"]


def _create_default_db() -> dict:
    """Tạo DB mặc định với master admin ducpro."""
    return {
        "ducpro": {
            "password": hash_password("234766"),
            "role": "admin",
            "status": "approved",
            "permissions": DEFAULT_PERMISSIONS.copy(),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Master admin",
        }
    }


def load_db() -> dict:
    """Tải DB từ file JSON. Tự pull GitHub nếu cấu hình."""
    # Pull GitHub trước (nếu có config)
    pull_from_github(force=False)

    if not os.path.exists(DB_FILE):
        db = _create_default_db()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
        push_to_github()
        return db

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        # Đảm bảo luôn có master admin
        if "ducpro" not in db:
            db["ducpro"] = _create_default_db()["ducpro"]
            save_db(db)
        return db
    except (json.JSONDecodeError, OSError):
        # File hỏng → khôi phục mặc định
        db = _create_default_db()
        save_db(db)
        return db


def save_db(db: dict) -> None:
    """Lưu DB local + push lên GitHub."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)
    push_to_github()


# ═══════════════════════════════════════════════════════════════
# REGISTER / AUTH
# ═══════════════════════════════════════════════════════════════
def register_user(username: str, password: str) -> Tuple[bool, str]:
    """Đăng ký tài khoản mới — trạng thái pending, không có quyền."""
    username = (username or "").strip().lower()
    password = (password or "").strip()

    if not username or not password:
        return False, "Tài khoản và mật khẩu không được để trống."
    if len(username) < 3:
        return False, "Tên tài khoản phải có ít nhất 3 ký tự."
    if len(password) < 4:
        return False, "Mật khẩu phải có ít nhất 4 ký tự."
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Tên tài khoản chỉ được chứa chữ, số, dấu _ và -."

    db = load_db()
    if username in db:
        return False, "Tài khoản đã tồn tại!"

    db[username] = {
        "password": hash_password(password),
        "role": "user",
        "status": "pending",
        "permissions": [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "",
    }
    save_db(db)
    return True, "Đăng ký thành công! Vui lòng chờ Admin duyệt tài khoản."


def authenticate(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """Kiểm tra đăng nhập. Trả về (ok, message, user_data)."""
    username = (username or "").strip().lower()
    password = (password or "").strip()

    if not username or not password:
        return False, "Vui lòng nhập đầy đủ tài khoản và mật khẩu.", None

    db = load_db()
    user = db.get(username)
    if not user:
        return False, "Sai tài khoản hoặc mật khẩu!", None

    if user.get("password") != hash_password(password):
        return False, "Sai tài khoản hoặc mật khẩu!", None

    status = user.get("status", "pending")
    if status == "pending":
        return False, "Tài khoản đang chờ Admin duyệt.", None
    if status == "banned":
        return False, "Tài khoản đã bị khóa.", None
    if status != "approved":
        return False, f"Trạng thái tài khoản không hợp lệ: {status}", None

    return True, "Đăng nhập thành công.", {"username": username, **user}


# ═══════════════════════════════════════════════════════════════
# ADMIN OPERATIONS
# ═══════════════════════════════════════════════════════════════
def list_users() -> dict:
    return load_db()


def update_user_admin(username: str, new_status: str,
                      new_permissions: list, note: str = "") -> bool:
    """Admin cập nhật trạng thái + quyền truy cập của user."""
    db = load_db()
    if username not in db:
        return False
    if db[username].get("role") == "admin" and username == "ducpro":
        # Không cho thay đổi master admin
        new_status = "approved"
        new_permissions = DEFAULT_PERMISSIONS.copy()

    db[username]["status"] = new_status
    db[username]["permissions"] = list(new_permissions or [])
    if note:
        db[username]["note"] = note
    save_db(db)
    return True


def delete_user(username: str) -> bool:
    """Admin xóa user (không xóa được master admin)."""
    db = load_db()
    if username not in db:
        return False
    if db[username].get("role") == "admin":
        return False
    del db[username]
    save_db(db)
    return True


def reset_password(username: str, new_password: str) -> bool:
    """Admin reset mật khẩu user."""
    db = load_db()
    if username not in db:
        return False
    if not new_password or len(new_password) < 4:
        return False
    db[username]["password"] = hash_password(new_password)
    save_db(db)
    return True


def change_own_password(username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """User tự đổi mật khẩu của mình."""
    if not new_password or len(new_password) < 4:
        return False, "Mật khẩu mới phải có ít nhất 4 ký tự."
    db = load_db()
    user = db.get(username)
    if not user:
        return False, "Tài khoản không tồn tại."
    if user.get("password") != hash_password(old_password):
        return False, "Mật khẩu cũ không đúng."
    db[username]["password"] = hash_password(new_password)
    save_db(db)
    return True, "Đổi mật khẩu thành công."


def has_permission(user_data: dict, permission: str) -> bool:
    """Kiểm tra user có quyền truy cập tab cụ thể không."""
    if not user_data:
        return False
    if user_data.get("role") == "admin":
        return True
    perms = user_data.get("permissions", []) or []
    return permission in perms
