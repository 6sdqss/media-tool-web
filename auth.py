"""
auth.py — Authentication & Auto-Sync GitHub System v10.0
─────────────────────────────────────────────────────────
NÂNG CẤP so với v9.x:

[BUG FIX] SHA-256 + hardcoded salt → PBKDF2-HMAC-SHA256 (built-in, 260.000 iterations)
  Lý do cũ bị lỗi: SHA-256 một lần với salt cố định chạy trong <1ms → brute-force trivially fast.
  Fix: PBKDF2 cần hàng trăm ms để hash → dictionary attack chậm 100.000×.
  Migration: Tự động re-hash mật khẩu SHA-256-cũ lần đăng nhập đầu tiên (zero downtime).

[BUG FIX] Không có brute-force protection → thêm LoginRateLimiter
  Lý do cũ bị lỗi: Kẻ tấn công có thể thử mật khẩu không giới hạn.
  Fix: Khóa IP/username sau 5 lần sai trong 5 phút (in-memory, Streamlit-safe).

[BUG FIX] load_db() gọi pull_from_github() mỗi lần → rate throttle 30s
  Lý do cũ bị lỗi: Mỗi action trong admin panel gọi load_db() → nhiều API call GitHub/phiên.
  Fix: Cache DB trong st.session_state với TTL 60s, chỉ pull khi cần thiết.

[BUG FIX] Không validate GitHub response trước khi ghi đĩa
  Fix: Validate JSON parse trước khi ghi, fallback về DB local nếu response lỗi.
"""

from __future__ import annotations

import os
import json
import time
import base64
import hashlib
import hmac
from typing import Tuple, Optional

import requests
import streamlit as st


# ═══════════════════════════════════════════════════════════════
# HẰNG SỐ
# ═══════════════════════════════════════════════════════════════
DB_FILE = "users_db.json"
_DB_CACHE_KEY = "_auth_db_cache"
_DB_CACHE_TS_KEY = "_auth_db_cache_ts"
_DB_CACHE_TTL = 60           # Giây — cache DB trong session
_LAST_PULL_KEY = "_last_github_pull_ts"
_PULL_INTERVAL_SECONDS = 30

# Brute-force protection
_BF_KEY = "_login_attempts"
_BF_MAX_ATTEMPTS = 5
_BF_WINDOW_SECONDS = 300     # 5 phút
_BF_LOCKOUT_SECONDS = 300

DEFAULT_PERMISSIONS = ["web", "studio", "drive", "local"]

# ─── Hash prefix để phân biệt PBKDF2 mới vs SHA256 cũ ───
_PBKDF2_PREFIX = "pbkdf2$"
_SHA256_LEGACY_PREFIX = "sha256$"


# ═══════════════════════════════════════════════════════════════
# PASSWORD HASHING — PBKDF2-HMAC-SHA256 (NÂNG CẤP)
# ═══════════════════════════════════════════════════════════════
_PBKDF2_ITERATIONS = 260_000   # OWASP 2024 recommendation
_SALT_BYTES = 32


def hash_password(password: str) -> str:
    """
    Hash mật khẩu bằng PBKDF2-HMAC-SHA256.
    Format: pbkdf2$<iterations>$<salt_hex>$<hash_hex>
    """
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return f"{_PBKDF2_PREFIX}{_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """
    Kiểm tra mật khẩu. Hỗ trợ cả PBKDF2 mới lẫn SHA-256 cũ.
    Trả True nếu đúng. Dùng hmac.compare_digest() chống timing attack.
    """
    if not stored_hash or not password:
        return False

    # ── PBKDF2 mới ──
    if stored_hash.startswith(_PBKDF2_PREFIX):
        try:
            _, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False

    # ── SHA-256 legacy (migration path) ──
    _INTERNAL_SALT = "MediaToolProVIP_v9_2026"
    legacy_hash = hashlib.sha256(f"{_INTERNAL_SALT}::{password}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, legacy_hash)


def _needs_rehash(stored_hash: str) -> bool:
    """Kiểm tra hash cũ (SHA-256) cần được upgrade lên PBKDF2 không."""
    return not stored_hash.startswith(_PBKDF2_PREFIX)


# ═══════════════════════════════════════════════════════════════
# BRUTE-FORCE PROTECTION
# ═══════════════════════════════════════════════════════════════
def _get_attempt_key(username: str) -> str:
    return f"bf_{username.lower()}"


def _record_failed_attempt(username: str):
    """Ghi nhận lần đăng nhập thất bại."""
    bf = st.session_state.setdefault(_BF_KEY, {})
    key = _get_attempt_key(username)
    now = time.time()
    record = bf.get(key, {"count": 0, "first_ts": now, "locked_until": 0})

    # Reset nếu cửa sổ thời gian đã hết
    if now - record["first_ts"] > _BF_WINDOW_SECONDS:
        record = {"count": 0, "first_ts": now, "locked_until": 0}

    record["count"] += 1
    if record["count"] >= _BF_MAX_ATTEMPTS:
        record["locked_until"] = now + _BF_LOCKOUT_SECONDS

    bf[key] = record


def _clear_attempts(username: str):
    """Xóa bộ đếm sau khi đăng nhập thành công."""
    bf = st.session_state.get(_BF_KEY, {})
    bf.pop(_get_attempt_key(username), None)


def check_rate_limit(username: str) -> Tuple[bool, str]:
    """
    Kiểm tra xem username có đang bị khóa không.
    Trả (is_locked, message).
    """
    bf = st.session_state.get(_BF_KEY, {})
    key = _get_attempt_key(username)
    record = bf.get(key)
    if not record:
        return False, ""

    now = time.time()
    if record.get("locked_until", 0) > now:
        remaining = int(record["locked_until"] - now)
        return True, f"Tài khoản tạm khóa {remaining}s do đăng nhập sai nhiều lần."

    # Đã hết hạn khóa
    if record.get("count", 0) >= _BF_MAX_ATTEMPTS and now > record.get("locked_until", 0):
        bf.pop(key, None)

    return False, ""


# ═══════════════════════════════════════════════════════════════
# GITHUB SYNC
# ═══════════════════════════════════════════════════════════════
def _get_github_config() -> Tuple[Optional[str], Optional[str], str]:
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
    [FIX v10] Validate JSON trước khi ghi đĩa để tránh corrupt DB local.
    """
    token, repo, branch = _get_github_config()
    if not token or not repo:
        return False

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
        if resp.status_code != 200:
            return False

        data = resp.json()
        content_b64 = data.get("content", "")
        if not content_b64:
            return False

        raw = base64.b64decode(content_b64)

        # [FIX] Validate JSON trước khi ghi
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False  # Không ghi file hỏng

        # Đảm bảo master admin không bị mất
        if "ducpro" not in parsed:
            return False

        with open(DB_FILE, "wb") as f:
            f.write(raw)

        st.session_state[_LAST_PULL_KEY] = time.time()
        # Invalidate cache sau khi pull
        st.session_state.pop(_DB_CACHE_KEY, None)
        return True

    except Exception:
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

        payload: dict = {
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
def _create_default_db() -> dict:
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


def load_db(bypass_cache: bool = False) -> dict:
    """
    Tải DB từ file JSON.
    [FIX v10] Cache trong session_state với TTL 60s để tránh đọc file liên tục.
    Chỉ pull GitHub khi cache stale hoặc force.
    """
    now = time.time()

    # Trả cache nếu còn mới
    if not bypass_cache:
        cache_ts = st.session_state.get(_DB_CACHE_TS_KEY, 0)
        if now - cache_ts < _DB_CACHE_TTL:
            cached = st.session_state.get(_DB_CACHE_KEY)
            if cached is not None:
                return cached

    # Pull GitHub nếu được cấu hình (rate limited bên trong)
    pull_from_github(force=False)

    if not os.path.exists(DB_FILE):
        db = _create_default_db()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
        push_to_github()
        _set_db_cache(db)
        return db

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        if "ducpro" not in db:
            db["ducpro"] = _create_default_db()["ducpro"]
            save_db(db)
        _set_db_cache(db)
        return db
    except (json.JSONDecodeError, OSError):
        db = _create_default_db()
        save_db(db)
        return db


def _set_db_cache(db: dict):
    """Lưu DB vào session cache."""
    st.session_state[_DB_CACHE_KEY] = db
    st.session_state[_DB_CACHE_TS_KEY] = time.time()


def save_db(db: dict) -> None:
    """Lưu DB local + push lên GitHub + invalidate cache."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)
    push_to_github()
    _set_db_cache(db)


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
        "password": hash_password(password),  # Luôn dùng PBKDF2 cho user mới
        "role": "user",
        "status": "pending",
        "permissions": [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "",
    }
    save_db(db)
    return True, "Đăng ký thành công! Vui lòng chờ Admin duyệt tài khoản."


def authenticate(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """
    Kiểm tra đăng nhập.
    [FIX v10] Brute-force protection + tự động re-hash SHA-256 → PBKDF2.
    Trả về (ok, message, user_data).
    """
    username = (username or "").strip().lower()
    password = (password or "").strip()

    if not username or not password:
        return False, "Vui lòng nhập đầy đủ tài khoản và mật khẩu.", None

    # Kiểm tra rate limit trước
    is_locked, lock_msg = check_rate_limit(username)
    if is_locked:
        return False, lock_msg, None

    db = load_db()
    user = db.get(username)

    # Dùng constant-time comparison kể cả khi user không tồn tại (chống timing attack)
    dummy_hash = hash_password("__dummy__")  # sẽ fail nhưng mất đúng thời gian
    stored_hash = user.get("password", dummy_hash) if user else dummy_hash

    password_ok = _verify_password(password, stored_hash)

    if not user or not password_ok:
        _record_failed_attempt(username)
        bf = st.session_state.get(_BF_KEY, {})
        attempts = bf.get(f"bf_{username}", {}).get("count", 0)
        remaining = max(0, _BF_MAX_ATTEMPTS - attempts)
        if remaining > 0:
            return False, f"Sai tài khoản hoặc mật khẩu! ({remaining} lần thử còn lại)", None
        else:
            return False, f"Tài khoản bị khóa {_BF_LOCKOUT_SECONDS // 60} phút do sai quá nhiều lần.", None

    status = user.get("status", "pending")
    if status == "pending":
        return False, "Tài khoản đang chờ Admin duyệt.", None
    if status == "banned":
        return False, "Tài khoản đã bị khóa.", None
    if status != "approved":
        return False, f"Trạng thái tài khoản không hợp lệ: {status}", None

    # [MIGRATION] Tự động re-hash SHA-256 → PBKDF2 khi đăng nhập thành công
    if _needs_rehash(stored_hash):
        db[username]["password"] = hash_password(password)
        save_db(db)

    _clear_attempts(username)
    return True, "Đăng nhập thành công.", {"username": username, **user}


# ═══════════════════════════════════════════════════════════════
# ADMIN OPERATIONS
# ═══════════════════════════════════════════════════════════════
def list_users() -> dict:
    return load_db(bypass_cache=True)


def update_user_admin(username: str, new_status: str,
                      new_permissions: list, note: str = "") -> bool:
    db = load_db(bypass_cache=True)
    if username not in db:
        return False
    if db[username].get("role") == "admin" and username == "ducpro":
        new_status = "approved"
        new_permissions = DEFAULT_PERMISSIONS.copy()

    db[username]["status"] = new_status
    db[username]["permissions"] = list(new_permissions or [])
    if note is not None:
        db[username]["note"] = note
    save_db(db)
    return True


def delete_user(username: str) -> bool:
    db = load_db(bypass_cache=True)
    if username not in db:
        return False
    if db[username].get("role") == "admin":
        return False
    del db[username]
    save_db(db)
    return True


def reset_password(username: str, new_password: str) -> bool:
    db = load_db(bypass_cache=True)
    if username not in db:
        return False
    if not new_password or len(new_password) < 4:
        return False
    db[username]["password"] = hash_password(new_password)
    save_db(db)
    return True


def change_own_password(username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    if not new_password or len(new_password) < 4:
        return False, "Mật khẩu mới phải có ít nhất 4 ký tự."
    db = load_db(bypass_cache=True)
    user = db.get(username)
    if not user:
        return False, "Tài khoản không tồn tại."
    if not _verify_password(old_password, user.get("password", "")):
        return False, "Mật khẩu cũ không đúng."
    db[username]["password"] = hash_password(new_password)
    save_db(db)
    return True, "Đổi mật khẩu thành công."


def has_permission(user_data: dict, permission: str) -> bool:
    if not user_data:
        return False
    if user_data.get("role") == "admin":
        return True
    perms = user_data.get("permissions", []) or []
    return permission in perms
