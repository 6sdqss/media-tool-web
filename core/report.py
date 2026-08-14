"""
core/report.py — sinh báo cáo CSV/JSON sau batch.
Mỗi item 1 dòng: status, attempt, error_type, error_message, timings, sizes.
"""
from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path

from .types import BatchInfo, TaskItem


_log = logging.getLogger("core.report")


CSV_COLUMNS = [
    "batch_id", "item_id", "status", "kind", "source",
    "group", "display_name",
    "attempt", "error_type", "error_message",
    "source_width", "source_height", "source_size_bytes",
    "output_count", "duration_ms",
]


def write_csv(items: list[TaskItem], out_path: Path) -> Path:
    """Ghi CSV report. Trả path đã ghi."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for it in items:
            row = it.to_report_row()
            writer.writerow({c: row.get(c, "") for c in CSV_COLUMNS})
    return out_path


def write_json_summary(batch: BatchInfo, items: list[TaskItem], out_path: Path) -> Path:
    """Ghi summary JSON dùng cho log/debug/archive."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_id": batch.batch_id,
        "state": batch.state.value,
        "source_mode": batch.source_mode,
        "preset_name": batch.preset_name,
        "started_at": batch.started_at,
        "completed_at": batch.completed_at,
        "duration_seconds": round(batch.duration, 2),
        "counts": {
            "total": batch.total,
            "success": batch.success,
            "failed": batch.failed,
            "cancelled": batch.cancelled,
            "skipped": batch.skipped,
        },
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items": [it.to_report_row() for it in items],
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path
