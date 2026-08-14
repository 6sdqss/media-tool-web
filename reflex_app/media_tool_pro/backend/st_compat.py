"""
st_compat.py — Streamlit compatibility shim cho core/*.py và auth.py.

core/state.py, core/batch.py, auth.py, cleanup.py (repo gốc) dùng 2 API
Streamlit rất đơn giản:
  - st.session_state  (dict-like: setdefault/getitem/setitem/pop/get/del)
  - st.secrets.get(...)

Reflex KHÔNG phải Streamlit nên package "streamlit" không được cài trong
môi trường Reflex. Thay vì sửa core/*.py (yêu cầu: giữ business logic gốc
nguyên vẹn, không đổi hành vi/ chữ ký hàm), ta đăng ký 1 module giả tên
"streamlit" vào sys.modules TRƯỚC KHI core/state.py, core/batch.py,
auth.py, cleanup.py được import lần đầu ở bất kỳ đâu trong app Reflex.

Import module này (side-effect only) ở đầu mọi backend/state.py và mọi
chỗ cần `import core...` / `import auth` / `import cleanup`.

LƯU Ý QUAN TRỌNG (đánh đổi khi migrate):
  st.session_state ở đây là 1 dict Python **global cho toàn bộ server
  process** (không phải per-browser-session như Streamlit thật). Điều đó
  có nghĩa:
    - BatchManager (core/batch.py) chỉ cho phép 1 batch chạy CÙNG LÚC
      trên toàn hệ thống (không phải 1 batch / user). Đây vốn cũng gần
      giống hành vi gốc (mỗi Streamlit session chỉ chạy 1 batch), nhưng
      giờ giới hạn ở mức toàn server thay vì từng session.
    - Brute-force login counter (auth.py) cũng dùng chung toàn server.
  Với 1 tool nội bộ, đây là đánh đổi chấp nhận được để không phải viết
  lại core/batch.py. Xem README_MIGRATION.md mục "Follow-up" nếu muốn
  nâng cấp lên multi-tenant thật (vd Redis-backed session store).
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

# ── Thêm repo root vào sys.path để import core/, auth.py, cleanup.py, ... ──
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# auth.py (DB_FILE="users_db.json") và core/presets.py (user_presets.json)
# dùng ĐƯỜNG DẪN TƯƠNG ĐỐI — giả định cwd = thư mục gốc repo (đúng khi chạy
# `streamlit run app.py` từ repo root). `reflex run` lại chạy với cwd =
# reflex_app/, nên PHẢI chdir về repo root ở đây — nếu không auth.py sẽ tạo
# 1 users_db.json MỚI (rỗng, chỉ có admin mặc định) trong reflex_app/ thay vì
# dùng file thật ở repo root. KHÔNG được bỏ bước này.
if Path.cwd().resolve() != REPO_ROOT:
    try:
        os.chdir(REPO_ROOT)
    except OSError:
        pass


class _Secrets(dict):
    """Giả lập st.secrets — đọc override từ dict, fallback sang biến môi trường."""

    def get(self, key, default=None):
        if dict.__contains__(self, key):
            return dict.get(self, key)
        env_val = os.environ.get(key)
        if env_val is not None:
            return env_val
        return default


# Singleton dùng chung cho toàn bộ process — xem LƯU Ý ở trên.
GLOBAL_SESSION_STATE: dict = {}
GLOBAL_SECRETS = _Secrets()


def _passthrough_decorator(*dargs, **dkwargs):
    """Giả lập st.cache_data / st.cache_resource (no-op, không cache)."""
    if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
        return dargs[0]

    def _wrap(fn):
        return fn

    return _wrap


def install() -> None:
    """Đăng ký module 'streamlit' giả vào sys.modules (idempotent)."""
    if "streamlit" in sys.modules:
        return
    mod = types.ModuleType("streamlit")
    mod.session_state = GLOBAL_SESSION_STATE
    mod.secrets = GLOBAL_SECRETS
    mod.cache_data = _passthrough_decorator
    mod.cache_resource = _passthrough_decorator

    def _noop(*_a, **_k):
        return None

    for _fn_name in ("error", "warning", "info", "success", "caption",
                      "markdown", "write", "rerun", "spinner"):
        setattr(mod, _fn_name, _noop)

    sys.modules["streamlit"] = mod


install()
