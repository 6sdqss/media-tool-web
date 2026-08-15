"""
core/types.py — enums và dataclasses làm nền cho batch engine.
Toàn bộ trạng thái đi qua đây: BatchState, ItemState, TaskItem, BatchInfo, Preset.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum


# ══════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════
class BatchState(str, Enum):
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    DONE = "DONE"
    FAILED = "FAILED"


class ItemState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"  # đã có kết quả trước đó, không xử lý lại


class ErrorType(str, Enum):
    NONE = ""
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED_URL = "UNSUPPORTED_URL"
    DOWNLOAD_TIMEOUT = "DOWNLOAD_TIMEOUT"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    DRIVE_PERMISSION = "DRIVE_PERMISSION"
    DRIVE_NOT_FOUND = "DRIVE_NOT_FOUND"
    DRIVE_RATE_LIMIT = "DRIVE_RATE_LIMIT"
    DRIVE_EMPTY_FOLDER = "DRIVE_EMPTY_FOLDER"
    INVALID_IMAGE = "INVALID_IMAGE"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    RESIZE_FAILED = "RESIZE_FAILED"
    SAVE_FAILED = "SAVE_FAILED"
    DISK_FULL = "DISK_FULL"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


# Errors đáng để retry (network/rate limit tạm thời)
RETRYABLE_ERRORS: set[ErrorType] = {
    ErrorType.DOWNLOAD_TIMEOUT,
    ErrorType.DOWNLOAD_FAILED,
    ErrorType.DRIVE_RATE_LIMIT,
    ErrorType.UNKNOWN,
}

# Errors KHÔNG bao giờ nên retry (retry sẽ luôn fail như nhau)
NON_RETRYABLE_ERRORS: set[ErrorType] = {
    ErrorType.INVALID_URL,
    ErrorType.UNSUPPORTED_URL,
    ErrorType.DRIVE_PERMISSION,
    ErrorType.DRIVE_NOT_FOUND,
    ErrorType.INVALID_IMAGE,
    ErrorType.IMAGE_TOO_LARGE,
    ErrorType.FILE_TOO_LARGE,
    ErrorType.CANCELLED,
    ErrorType.DISK_FULL,
}

# Mô tả tiếng Việt để hiển thị cho user
ERROR_LABEL_VI: dict[ErrorType, str] = {
    ErrorType.NONE: "",
    ErrorType.INVALID_URL: "Link sai định dạng",
    ErrorType.UNSUPPORTED_URL: "Link không được hỗ trợ",
    ErrorType.DOWNLOAD_TIMEOUT: "Tải quá lâu (timeout)",
    ErrorType.DOWNLOAD_FAILED: "Tải thất bại",
    ErrorType.DRIVE_PERMISSION: "Google Drive từ chối truy cập",
    ErrorType.DRIVE_NOT_FOUND: "Không tìm thấy file/folder Drive",
    ErrorType.DRIVE_RATE_LIMIT: "Google Drive giới hạn lưu lượng",
    ErrorType.DRIVE_EMPTY_FOLDER: "Folder Drive rỗng hoặc không có ảnh",
    ErrorType.INVALID_IMAGE: "File tải về không phải ảnh hợp lệ",
    ErrorType.IMAGE_TOO_LARGE: "Ảnh quá lớn (vượt trần an toàn)",
    ErrorType.FILE_TOO_LARGE: "File quá lớn",
    ErrorType.RESIZE_FAILED: "Lỗi khi resize",
    ErrorType.SAVE_FAILED: "Lỗi khi ghi file",
    ErrorType.DISK_FULL: "Đĩa đầy",
    ErrorType.CANCELLED: "Đã bị huỷ",
    ErrorType.UNKNOWN: "Lỗi chưa xác định",
}


# ══════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════
@dataclass
class SizeSpec:
    width: int
    height: int
    mode: str = "letterbox"  # letterbox | crop | keep | crop_1000

    def label(self) -> str:
        if self.mode == "crop_1000":
            side = self.width or 1000
            return f"{side}x{side}_crop"
        if self.mode == "keep":
            return "keep_ratio"
        return f"{self.width}x{self.height}"

    @classmethod
    def from_tuple(cls, t: tuple) -> "SizeSpec":
        if len(t) >= 3:
            return cls(int(t[0]), int(t[1]), str(t[2]))
        return cls(int(t[0]), int(t[1]), "letterbox")

    def as_tuple(self) -> tuple:
        return (self.width, self.height, self.mode)


@dataclass
class Preset:
    """Cấu hình xử lý — user chọn 1 preset là xong."""
    name: str
    sizes: list[SizeSpec] = field(default_factory=list)
    quality: int = 92
    export_format: str = "JPEG (.jpg)"
    no_upscale: bool = True
    scale_pct: int = 100
    template: str = "{name}_{nn}"
    zip_compression: int = 6
    is_builtin: bool = False
    description: str = ""

    def to_json(self) -> dict:
        d = asdict(self)
        d["sizes"] = [asdict(s) for s in self.sizes]
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Preset":
        sizes = [SizeSpec(**s) for s in d.get("sizes", [])]
        args = {k: v for k, v in d.items() if k != "sizes"}
        return cls(sizes=sizes, **args)


@dataclass
class TaskItem:
    """Một đơn vị xử lý: 1 ảnh đầu vào → N kích thước đầu ra."""
    item_id: str
    batch_id: str
    source: str                     # URL hoặc file path
    source_kind: str                # "url" | "drive_file" | "drive_folder" | "upload" | "path"
    group_name: str = ""            # tên nhóm (folder xuất)
    display_name: str = ""          # tên gốc
    fingerprint: str = ""           # để dedup

    status: ItemState = ItemState.QUEUED
    attempt: int = 0
    max_attempts: int = 3
    error_type: ErrorType = ErrorType.NONE
    error_message: str = ""

    downloaded_path: str = ""       # đường dẫn ảnh nguồn sau khi tải
    output_paths: list[str] = field(default_factory=list)  # ảnh đã xuất
    source_size_bytes: int = 0
    source_width: int = 0
    source_height: int = 0

    started_at: float = 0.0
    completed_at: float = 0.0
    duration: float = 0.0

    # payload chứa dữ liệu bổ trợ mà không thuộc chuỗi ổn định (bytes upload,
    # drive_id, gallery_url, ...). Không được đưa vào fingerprint.
    payload: dict = field(default_factory=dict)

    def to_report_row(self) -> dict:
        """Row cho CSV report — không chứa binary."""
        return {
            "batch_id": self.batch_id,
            "item_id": self.item_id,
            "source": self.source[:200],
            "kind": self.source_kind,
            "group": self.group_name,
            "display_name": self.display_name,
            "status": self.status.value,
            "attempt": self.attempt,
            "error_type": self.error_type.value,
            "error_message": self.error_message[:300],
            "source_width": self.source_width,
            "source_height": self.source_height,
            "source_size_bytes": self.source_size_bytes,
            "output_count": len(self.output_paths),
            "duration_ms": int(self.duration * 1000),
        }


@dataclass
class BatchInfo:
    """Trạng thái tổng của 1 batch — sống trong session_state."""
    batch_id: str = ""
    state: BatchState = BatchState.IDLE
    source_mode: str = ""           # "web" | "drive" | "local"
    preset_name: str = ""
    workspace_root: str = ""
    final_dir: str = ""
    zip_path: str = ""
    report_path: str = ""

    total: int = 0
    queued: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    retrying: int = 0
    cancelled: int = 0
    skipped: int = 0

    started_at: float = 0.0
    completed_at: float = 0.0
    current_item_name: str = ""
    current_operation: str = ""     # "downloading" | "resizing 1020x680" | ...

    log_tail: list[str] = field(default_factory=list)  # ≤ 40 dòng cuối
    warnings: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.state in (
            BatchState.PREPARING, BatchState.RUNNING,
            BatchState.PAUSED, BatchState.CANCELLING,
        )

    @property
    def is_finished(self) -> bool:
        return self.state in (BatchState.DONE, BatchState.FAILED)

    @property
    def progress_ratio(self) -> float:
        if self.total <= 0:
            return 0.0
        finished = self.success + self.failed + self.cancelled + self.skipped
        return min(1.0, finished / self.total)

    @property
    def duration(self) -> float:
        if self.started_at <= 0:
            return 0.0
        end = self.completed_at if self.completed_at > 0 else time.time()
        return max(0.0, end - self.started_at)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"
