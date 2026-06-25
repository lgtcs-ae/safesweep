"""General utilities for SafeSweep."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def now_local() -> datetime:
    """Return the current local datetime without dropping timezone assumptions."""
    return datetime.now().astimezone()


def isoformat(dt: datetime) -> str:
    """Return a stable ISO timestamp with seconds precision."""
    return dt.isoformat(timespec="seconds")


def scan_timestamp(dt: datetime) -> str:
    """Return the timestamp format used in SafeSweep review folder names."""
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def path_is_relative_to(path: Path, parent: Path) -> bool:
    """Python 3.9-compatible Path.is_relative_to."""
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending a numeric suffix when needed."""
    if not path.exists():
        return path

    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}_{index:03d}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not create a unique path near {path}")


def unique_file_path(path: Path) -> Path:
    """Return a non-existing file path by appending a suffix before extension."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}__safesweep_{index:03d}{suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not create a unique file path near {path}")


def human_bytes(value: int) -> str:
    """Format a byte count for humans."""
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{value} B"


def top_extensions(files_by_extension: Dict[str, int], limit: int = 8) -> list[Dict[str, Any]]:
    """Return extension counts sorted for dashboard display."""
    sorted_items = sorted(
        files_by_extension.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        {"extension": extension, "count": count}
        for extension, count in sorted_items[:limit]
    ]
