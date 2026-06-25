"""SHA-256 hashing utilities for duplicate matching."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.models import FileRecord, ScanError

ProgressCallback = Optional[Callable[[str, Dict[str, Any]], None]]


@dataclass(frozen=True)
class HashResult:
    """Result of hashing a single file safely."""

    path: str
    sha256: Optional[str]
    success: bool
    error_message: Optional[str]
    size_before: Optional[int]
    size_after: Optional[int]
    modified_before: Optional[float]
    modified_after: Optional[float]
    changed_during_hash: bool


@dataclass(frozen=True)
class CandidateHashResult:
    """Records after candidate hashing plus any hashing errors."""

    records: List[FileRecord]
    errors: List[ScanError]
    hashed_file_count: int


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> HashResult:
    """Hash a file in fixed-size chunks and detect unsafe changes."""
    path = path.expanduser()
    size_before: Optional[int] = None
    modified_before: Optional[float] = None
    size_after: Optional[int] = None
    modified_after: Optional[float] = None

    try:
        before = path.stat()
        size_before = int(before.st_size)
        modified_before = float(before.st_mtime)
    except FileNotFoundError:
        return HashResult(str(path), None, False, "file missing before hash", None, None, None, None, False)
    except PermissionError as exc:
        return HashResult(str(path), None, False, f"permission denied before hash: {exc}", None, None, None, None, False)
    except OSError as exc:
        return HashResult(str(path), None, False, f"could not stat before hash: {exc}", None, None, None, None, False)

    digest = hashlib.sha256()
    try:
        with path.open("rb") as file_obj:
            while True:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    except FileNotFoundError:
        return HashResult(str(path), None, False, "file deleted during hash", size_before, None, modified_before, None, True)
    except PermissionError as exc:
        return HashResult(str(path), None, False, f"permission denied during hash: {exc}", size_before, None, modified_before, None, False)
    except OSError as exc:
        return HashResult(str(path), None, False, f"could not read during hash: {exc}", size_before, None, modified_before, None, False)

    try:
        after = path.stat()
        size_after = int(after.st_size)
        modified_after = float(after.st_mtime)
    except FileNotFoundError:
        return HashResult(str(path), None, False, "file deleted after hash", size_before, None, modified_before, None, True)
    except PermissionError as exc:
        return HashResult(str(path), None, False, f"permission denied after hash: {exc}", size_before, None, modified_before, None, False)
    except OSError as exc:
        return HashResult(str(path), None, False, f"could not stat after hash: {exc}", size_before, None, modified_before, None, False)

    changed = size_before != size_after or modified_before != modified_after
    if changed:
        return HashResult(
            path=str(path),
            sha256=None,
            success=False,
            error_message="file changed during hash",
            size_before=size_before,
            size_after=size_after,
            modified_before=modified_before,
            modified_after=modified_after,
            changed_during_hash=True,
        )

    return HashResult(
        path=str(path),
        sha256=digest.hexdigest(),
        success=True,
        error_message=None,
        size_before=size_before,
        size_after=size_after,
        modified_before=modified_before,
        modified_after=modified_after,
        changed_during_hash=False,
    )


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compatibility wrapper that returns only a SHA-256 string."""
    result = sha256_file(path, chunk_size=chunk_size)
    if not result.success or result.sha256 is None:
        raise OSError(result.error_message or "hash failed")
    return result.sha256


def hash_same_size_candidates(
    records: List[FileRecord],
    progress_callback: ProgressCallback = None,
) -> CandidateHashResult:
    """Hash only files whose size appears more than once."""
    by_size: Dict[int, List[FileRecord]] = {}
    for record in records:
        by_size.setdefault(record.size_bytes, []).append(record)

    replacements: Dict[str, FileRecord] = {}
    errors: List[ScanError] = []
    hashed_count = 0

    for same_size_records in by_size.values():
        if len(same_size_records) < 2:
            continue
        for record in same_size_records:
            _progress(progress_callback, "hash_started", path=record.path)
            result = sha256_file(Path(record.path))
            if not result.success or result.sha256 is None:
                errors.append(
                    ScanError(
                        path=record.path,
                        kind="hashing_failure",
                        message=result.error_message or "hash failed",
                    )
                )
                _progress(progress_callback, "hash_failed", path=record.path)
                continue
            replacements[record.path] = replace(record, sha256=result.sha256)
            hashed_count += 1
            _progress(progress_callback, "hash_completed", path=record.path, files_hashed=hashed_count)

    updated = [replacements.get(record.path, record) for record in records]
    return CandidateHashResult(records=updated, errors=errors, hashed_file_count=hashed_count)


def _progress(progress_callback: ProgressCallback, event: str, **payload: Any) -> None:
    """Send a best-effort progress event."""
    if progress_callback:
        progress_callback(event, payload)
