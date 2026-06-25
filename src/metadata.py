"""File metadata collection for SafeSweep scans."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.models import FileRecord
from src.normalizer import normalize_name


def _timestamp(seconds: float) -> str:
    """Convert a filesystem timestamp to ISO format."""
    return datetime.fromtimestamp(seconds).astimezone().isoformat(timespec="seconds")


def collect_file_metadata(path: Path) -> FileRecord:
    """Collect metadata for a regular file without hashing or moving it."""
    stat_result = path.stat()
    suffix = path.suffix.lower()
    extension = suffix[1:] if suffix.startswith(".") else suffix
    return FileRecord(
        path=str(path),
        name=path.name,
        normalized_name=normalize_name(path.name),
        extension=extension or "[no extension]",
        size_bytes=int(stat_result.st_size),
        created_at=_timestamp(stat_result.st_ctime),
        modified_at=_timestamp(stat_result.st_mtime),
        accessed_at=_timestamp(stat_result.st_atime),
        inode=getattr(stat_result, "st_ino", None),
        is_symlink=path.is_symlink(),
    )
