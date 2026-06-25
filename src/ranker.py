"""Actual-file selection for SafeSweep duplicate groups."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from src import config
from src.models import FileRecord


def choose_actual(records: List[FileRecord]) -> FileRecord:
    """Choose the Actual file to keep.

    SafeSweep keeps the newest file by default. Folder preference and size are
    used only as tie-breakers and Actual files are never moved.
    """
    if not records:
        raise ValueError("Cannot choose an Actual file from an empty group.")
    return sorted(records, key=_rank_key, reverse=True)[0]


def order_duplicates(records: List[FileRecord], actual: FileRecord) -> List[FileRecord]:
    """Return non-Actual records in stable newest-first order."""
    return [
        record
        for record in sorted(records, key=_rank_key, reverse=True)
        if record.path != actual.path
    ]


def _rank_key(record: FileRecord) -> Tuple[int, float, float, float, int, int, str]:
    """Build a sorting key matching the configured Actual selection priority."""
    created = _parse_timestamp(record.created_at)
    modified = _parse_timestamp(record.modified_at)
    accessed = _parse_timestamp(record.accessed_at)
    folder_score = _folder_preference_score(Path(record.path))
    return (
        _originality_score(record),
        created,
        modified,
        accessed,
        folder_score,
        record.size_bytes,
        record.path,
    )


def _parse_timestamp(value: str) -> float:
    """Parse an ISO timestamp into epoch seconds with a safe fallback."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _folder_preference_score(path: Path) -> int:
    """Return a higher score for more preferred user-facing folders."""
    parts = set(path.parts)
    preference_count = len(config.FOLDER_PREFERENCE_NAMES)
    for index, name in enumerate(config.FOLDER_PREFERENCE_NAMES):
        if name in parts:
            return preference_count - index
    return 0


def _originality_score(record: FileRecord) -> int:
    """Prefer cleaner names over obvious duplicate/copy names."""
    stem = Path(record.name).stem.lower()
    score = 100
    if re.search(r"(^|[\s_\-])copy($|[\s_\-\d])", stem):
        score -= 35
    if "duplicate" in stem:
        score -= 35
    if re.search(r"[\(\[]\d+[\)\]]$", stem.strip()):
        score -= 25
    if re.search(r"[\s_\-]\d+$", stem.strip()):
        score -= 10
    return score
