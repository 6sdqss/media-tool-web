"""
core/validation.py — Input parsing, normalization, deduplication.
Tất cả input (URL text, upload list, drive links) đều đi qua đây trước khi
đưa vào batch — đảm bảo mỗi item xử lý đúng 1 lần.
"""
from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse


# ══════════════════════════════════════════════════════════════
# INPUT SPLITTING
# ══════════════════════════════════════════════════════════════
_SPLIT_RE = re.compile(r"[\s,;]+")


def split_input_lines(text: str) -> list[str]:
    """
    Chấp nhận: mỗi dòng 1 URL, hoặc dấu phẩy/space/semicolon phân cách.
    Trả về list đã trim + bỏ dòng rỗng, giữ thứ tự nhập.
    """
    if not text:
        return []
    parts = _SPLIT_RE.split(text.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip().strip('"').strip("'").strip(",")
        if p:
            out.append(p)
    return out


# ══════════════════════════════════════════════════════════════
# URL NORMALIZATION & CLASSIFICATION
# ══════════════════════════════════════════════════════════════
def normalize_url(url: str) -> str:
    """
    Bỏ fragment, chuẩn hoá scheme/host lowercase, giữ path/query.
    Nếu input không giống URL (không có scheme + không có host có dấu chấm)
    → trả về "" để caller phát hiện.
    """
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"^https?://", url, re.IGNORECASE):
        # Chỉ thêm scheme nếu input trông như "host.tld/…" (có dot ở tên miền)
        if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/", url):
            url = "https://" + url
        else:
            return ""  # không phải URL
    try:
        p = urlparse(url)
        if not p.netloc or "." not in p.netloc:
            return ""
        scheme = p.scheme.lower()
        netloc = p.netloc.lower()
        return urlunparse((scheme, netloc, p.path, p.params, p.query, ""))
    except Exception:
        return ""


_DRIVE_RE = re.compile(
    r"(?:/file/d/|/drive/(?:u/\d+/)?folders/|/open\?id=|[?&]id=)"
    r"([A-Za-z0-9_-]{20,})"
)


def classify_url(url: str) -> str:
    """
    Trả 1 trong:
        "drive_file", "drive_folder", "tgdd", "image_url", "unsupported"
    """
    if not url:
        return "unsupported"
    low = url.lower()
    if "drive.google.com" in low or "drive.usercontent.google.com" in low:
        if "/folders/" in low or "/drive/folders" in low:
            return "drive_folder"
        return "drive_file"
    if "thegioididong.com" in low:
        return "tgdd"
    # ảnh direct
    if any(low.split("?")[0].endswith(ext) for ext in
           (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
        return "image_url"
    return "unsupported"


def extract_drive_id(url: str) -> Optional[str]:
    m = _DRIVE_RE.search(url or "")
    return m.group(1) if m else None


# ══════════════════════════════════════════════════════════════
# FILENAME CLEANING
# ══════════════════════════════════════════════════════════════
_UNSAFE_CHARS = re.compile(r'[\\/*?:"<>|\x00-\x1f]')


def clean_name(name: str, max_len: int = 120) -> str:
    """Chuẩn hoá tên file/folder cho mọi OS."""
    s = _UNSAFE_CHARS.sub("", str(name or ""))
    s = re.sub(r"\s+", "_", s).strip("_.")
    if not s:
        s = "unnamed"
    if len(s) > max_len:
        s = s[:max_len]
    return s


# ══════════════════════════════════════════════════════════════
# DEDUP FINGERPRINT
# ══════════════════════════════════════════════════════════════
def fingerprint(source: str, kind: str = "", extra: str = "") -> str:
    """
    Fingerprint ổn định — dùng để chống nhập trùng URL / upload lại cùng file.
    KHÔNG bao gồm timestamp hay batch_id vì mục đích là dedup xuyên batch.
    """
    payload = f"{kind}|{normalize_url(source) if source.startswith('http') else source}|{extra}"
    return hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════
# INPUT REPORT
# ══════════════════════════════════════════════════════════════
@dataclass
class InputReport:
    """Kết quả sau khi validate + dedup toàn bộ input."""
    raw_count: int = 0
    valid: list[tuple[str, str]] = None    # [(normalized_url, kind), ...]
    invalid: list[tuple[str, str]] = None  # [(raw, reason), ...]
    duplicates: list[str] = None

    def __post_init__(self):
        if self.valid is None:
            self.valid = []
        if self.invalid is None:
            self.invalid = []
        if self.duplicates is None:
            self.duplicates = []

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def dup_count(self) -> int:
        return len(self.duplicates)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid)


def validate_url_batch(
    lines: list[str],
    allowed_kinds: set[str] | None = None,
) -> InputReport:
    """
    Nhận list URL thô → chuẩn hoá → phân loại → dedup.
    allowed_kinds nếu có: chỉ giữ URL thuộc các kind chỉ định
    (vd Drive tab chỉ nhận drive_file/drive_folder).
    """
    rep = InputReport(raw_count=len(lines))
    seen: set[str] = set()

    for raw in lines:
        raw = (raw or "").strip()
        if not raw:
            continue

        norm = normalize_url(raw)
        if not norm or not norm.lower().startswith(("http://", "https://")):
            rep.invalid.append((raw[:120], "Không phải URL hợp lệ"))
            continue

        kind = classify_url(norm)
        if kind == "unsupported":
            rep.invalid.append((raw[:120], "Không hỗ trợ nguồn này"))
            continue
        if allowed_kinds is not None and kind not in allowed_kinds:
            rep.invalid.append((raw[:120], f"Không thuộc tab hiện tại ({kind})"))
            continue

        fp = fingerprint(norm, kind)
        if fp in seen:
            rep.duplicates.append(raw[:120])
            continue
        seen.add(fp)
        rep.valid.append((norm, kind))

    return rep
