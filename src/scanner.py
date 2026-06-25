"""Safe filesystem scanning and matching for SafeSweep."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src import config
from src.logger_setup import configure_scan_loggers
from src.matcher import (
    CONFIRMED,
    NAME_COLLISION,
    POSSIBLE,
    VERY_LIKELY,
    count_by_classification,
    detect_duplicate_groups,
    estimated_vault_bytes,
)
from src.metadata import collect_file_metadata
from src.models import CleanupCandidate, FileRecord, IgnoredPath, ScanError, ScanResult, ScanSummary
from src.reporter import create_review_structure, write_phase1_artifacts
from src.utils import isoformat, now_local, path_is_relative_to, scan_timestamp, unique_path

ProgressCallback = Optional[Callable[[str, Dict[str, Any]], None]]


def scan_folders(
    folders: Optional[Iterable[Path]] = None,
    excludes: Optional[Iterable[Path]] = None,
    include_hidden: bool = False,
    output_root: Optional[Path] = None,
    progress_callback: ProgressCallback = None,
) -> ScanResult:
    """Run a safe scan, detect duplicate candidates, and write review artifacts."""
    started = now_local()
    scan_id = scan_timestamp(started)
    parent = output_root.expanduser() if output_root else Path.home()
    review_root = unique_path(parent / f"{config.OUTPUT_PREFIX}_{scan_id}")
    paths = create_review_structure(review_root)
    loggers = configure_scan_loggers(review_root.name, paths["logs"])

    raw_folders = list(folders or config.DEFAULT_SCAN_FOLDERS)
    raw_excludes = list(excludes or [])
    exclude_paths = [_resolve_path(path) for path in raw_excludes]

    records: List[FileRecord] = []
    cleanup_candidates: List[CleanupCandidate] = []
    ignored: List[IgnoredPath] = []
    errors: List[ScanError] = []
    extension_counts: Dict[str, int] = {}

    loggers.scan.info(
        "scan_started scan_id=%s folders=%s include_hidden=%s output=%s",
        scan_id,
        [str(folder) for folder in raw_folders],
        include_hidden,
        review_root,
    )
    _progress(progress_callback, "scan_started", current_path=str(review_root))

    for raw_folder in raw_folders:
        folder = _resolve_path(raw_folder)
        allowed, reason = should_scan_root(folder, include_hidden=include_hidden)
        if not allowed:
            _record_ignored(ignored, loggers.scan, folder, reason)
            continue
        if _is_user_excluded(folder, exclude_paths):
            _record_ignored(ignored, loggers.scan, folder, "user excluded")
            continue
        if not folder.exists():
            _record_error(errors, loggers.errors, folder, "missing_folder", "Folder does not exist.")
            continue
        if not folder.is_dir():
            _record_error(errors, loggers.errors, folder, "not_directory", "Path is not a directory.")
            continue

        _walk_directory(
            folder=folder,
            include_hidden=include_hidden,
            exclude_paths=exclude_paths,
            records=records,
            cleanup_candidates=cleanup_candidates,
            ignored=ignored,
            errors=errors,
            extension_counts=extension_counts,
            scan_logger=loggers.scan,
            error_logger=loggers.errors,
            progress_callback=progress_callback,
        )

    match_result = detect_duplicate_groups(records, progress_callback=progress_callback)
    records = match_result.records
    for error in match_result.errors:
        errors.append(error)
        loggers.errors.error(
            "scan_error path=%s kind=%s message=%s",
            error.path,
            error.kind,
            error.message,
        )

    groups = match_result.groups
    classification_counts = count_by_classification(groups)
    completed = now_local()
    summary = ScanSummary(
        scan_id=review_root.name.replace(f"{config.OUTPUT_PREFIX}_", "", 1),
        started_at=isoformat(started),
        completed_at=isoformat(completed),
        scan_folders=[str(_resolve_path(path)) for path in raw_folders],
        review_folder=str(review_root),
        include_hidden=include_hidden,
        total_files=len(records),
        total_bytes=sum(record.size_bytes for record in records),
        skipped_items=len(ignored),
        error_count=len(errors),
        files_by_extension=extension_counts,
        ignored_samples=[item.to_dict() for item in ignored[:25]],
        error_samples=[error.to_dict() for error in errors[:25]],
        confirmed_duplicate_groups=classification_counts.get(CONFIRMED, 0),
        likely_duplicate_groups=classification_counts.get(VERY_LIKELY, 0),
        possible_duplicate_groups=classification_counts.get(POSSIBLE, 0),
        name_collision_groups=classification_counts.get(NAME_COLLISION, 0),
        duplicate_group_count=len(groups),
        cleanup_candidate_count=len(cleanup_candidates),
        office_temp_lock_count=sum(
            1 for candidate in cleanup_candidates if candidate.classification == "office_temp_lock_file"
        ),
        cleanup_candidate_bytes=sum(candidate.record.size_bytes for candidate in cleanup_candidates),
        hashed_file_count=match_result.hashed_file_count,
        estimated_vault_bytes=estimated_vault_bytes(groups),
    )
    _progress(
        progress_callback,
        "scan_completed",
        groups_found=len(groups),
        output_scan_folder=str(review_root),
    )
    summary.report_paths = write_phase1_artifacts(summary, records, groups, cleanup_candidates, paths)

    loggers.actions.info("phase_2_no_actions no_files_moved=true no_files_deleted=true")
    loggers.scan.info(
        "scan_completed scan_id=%s total_files=%s total_bytes=%s skipped=%s errors=%s groups=%s confirmed=%s likely=%s possible=%s collisions=%s hashed_files=%s",
        summary.scan_id,
        summary.total_files,
        summary.total_bytes,
        summary.skipped_items,
        summary.error_count,
        summary.duplicate_group_count,
        summary.confirmed_duplicate_groups,
        summary.likely_duplicate_groups,
        summary.possible_duplicate_groups,
        summary.name_collision_groups,
        summary.hashed_file_count,
    )

    summary.report_paths["scan_log"] = str(paths["logs"] / "scan_log.txt")
    summary.report_paths["errors_log"] = str(paths["logs"] / "errors_log.txt")
    summary.report_paths["actions_log"] = str(paths["logs"] / "actions_log.txt")

    # Re-write the summary after report_paths are known.
    write_phase1_artifacts(summary, records, groups, cleanup_candidates, paths)
    return ScanResult(
        summary=summary,
        records=records,
        groups=groups,
        cleanup_candidates=cleanup_candidates,
        ignored=ignored,
        errors=errors,
    )


def should_scan_root(path: Path, include_hidden: bool = False) -> Tuple[bool, str]:
    """Return whether a user-supplied scan root is allowed by default."""
    resolved = _resolve_path(path)
    if _is_protected_path(resolved):
        return False, "protected system or user library folder"
    if should_ignore_directory(resolved, include_hidden=include_hidden):
        return False, "ignored folder rule"
    return True, ""


def should_ignore_directory(path: Path, include_hidden: bool = False) -> bool:
    """Return True when a directory should be skipped by default."""
    resolved = _resolve_path(path)
    if _is_protected_path(resolved):
        return True
    if resolved.name in config.IGNORED_DIR_NAMES:
        return True
    if not include_hidden and _is_hidden_dir(resolved):
        return True
    lowered = resolved.name.lower()
    if lowered.endswith(config.IGNORED_PACKAGE_SUFFIXES):
        return True
    return False


def should_ignore_file(path: Path) -> bool:
    """Return True when a file should be skipped by default."""
    if path.name in config.IGNORED_FILE_NAMES:
        return True
    return False


def is_office_temp_lock_file(path: Path) -> bool:
    """Return True for Microsoft Office owner/temp lock files."""
    return path.name.startswith("~$") and path.suffix.lower().lstrip(".") in config.IGNORED_OFFICE_TEMP_EXTENSIONS


def _walk_directory(
    folder: Path,
    include_hidden: bool,
    exclude_paths: List[Path],
    records: List[FileRecord],
    cleanup_candidates: List[CleanupCandidate],
    ignored: List[IgnoredPath],
    errors: List[ScanError],
    extension_counts: Dict[str, int],
    scan_logger,
    error_logger,
    progress_callback: ProgressCallback = None,
) -> None:
    """Recursively walk a directory without following symlinked directories."""
    if should_ignore_directory(folder, include_hidden=include_hidden):
        _record_ignored(ignored, scan_logger, folder, "ignored folder rule")
        return

    if _is_user_excluded(folder, exclude_paths):
        _record_ignored(ignored, scan_logger, folder, "user excluded")
        return

    try:
        entries = list(os.scandir(folder))
    except OSError as exc:
        _record_error(errors, error_logger, folder, "unreadable_directory", str(exc))
        return

    for entry in entries:
        path = Path(entry.path)
        _progress(progress_callback, "path_seen", current_path=str(path))
        try:
            if _is_user_excluded(path, exclude_paths):
                _record_ignored(ignored, scan_logger, path, "user excluded")
                continue

            if entry.is_dir(follow_symlinks=False):
                if entry.is_symlink():
                    _record_ignored(ignored, scan_logger, path, "symlinked directory")
                    continue
                if should_ignore_directory(path, include_hidden=include_hidden):
                    _record_ignored(ignored, scan_logger, path, "ignored folder rule")
                    continue
                _walk_directory(
                    folder=path,
                    include_hidden=include_hidden,
                    exclude_paths=exclude_paths,
                    records=records,
                    cleanup_candidates=cleanup_candidates,
                    ignored=ignored,
                    errors=errors,
                    extension_counts=extension_counts,
                    scan_logger=scan_logger,
                    error_logger=error_logger,
                    progress_callback=progress_callback,
                )
                continue

            if entry.is_file(follow_symlinks=False):
                if entry.is_symlink():
                    _record_ignored(ignored, scan_logger, path, "symlinked file")
                    continue
                if should_ignore_file(path):
                    _record_ignored(ignored, scan_logger, path, "ignored file rule")
                    continue
                try:
                    record = collect_file_metadata(path)
                except OSError as exc:
                    _record_error(errors, error_logger, path, "unreadable_file", str(exc))
                    continue
                if is_office_temp_lock_file(path):
                    cleanup_candidates.append(_office_temp_cleanup_candidate(record, len(cleanup_candidates) + 1))
                    scan_logger.info(
                        "cleanup_candidate path=%s classification=office_temp_lock_file",
                        path,
                    )
                    continue
                records.append(record)
                extension_counts[record.extension] = extension_counts.get(record.extension, 0) + 1
                _progress(
                    progress_callback,
                    "file_scanned",
                    current_path=str(path),
                    files_scanned=len(records),
                )
                continue

            _record_ignored(ignored, scan_logger, path, "not a regular file")
        except OSError as exc:
            _record_error(errors, error_logger, path, "filesystem_error", str(exc))


def _resolve_path(path: Path) -> Path:
    """Expand and resolve a path without requiring it to exist."""
    return path.expanduser().resolve(strict=False)


def _is_protected_path(path: Path) -> bool:
    """Return True if path is inside a default protected root."""
    resolved = _resolve_path(path)
    return any(path_is_relative_to(resolved, protected) for protected in config.PROTECTED_ROOTS)


def _is_hidden_dir(path: Path) -> bool:
    """Return True for hidden folder names."""
    return path.name.startswith(".") and path.name not in {".", ".."}


def _is_user_excluded(path: Path, exclude_paths: List[Path]) -> bool:
    """Return True when path is within any user-supplied exclude folder."""
    resolved = _resolve_path(path)
    return any(path_is_relative_to(resolved, excluded) for excluded in exclude_paths)


def _record_ignored(ignored: List[IgnoredPath], logger, path: Path, reason: str) -> None:
    """Track and log an ignored path."""
    ignored.append(IgnoredPath(path=str(path), reason=reason))
    logger.info("ignored_path path=%s reason=%s", path, reason)


def _office_temp_cleanup_candidate(record: FileRecord, candidate_number: int) -> CleanupCandidate:
    """Create a cleanup candidate for an Office owner/temp lock file."""
    return CleanupCandidate(
        candidate_id=f"cleanup_{candidate_number:03d}",
        classification="office_temp_lock_file",
        confidence=100,
        reason="Microsoft Office owner/temp lock file. These are not the real document contents.",
        recommended_action="Review first. If the related Office document is closed, this can later be moved to the SafeSweep Vault.",
        record=record,
    )


def _record_error(
    errors: List[ScanError],
    logger,
    path: Path,
    kind: str,
    message: str,
) -> None:
    """Track and log a scan error."""
    errors.append(ScanError(path=str(path), kind=kind, message=message))
    logger.error("scan_error path=%s kind=%s message=%s", path, kind, message)


def _progress(progress_callback: ProgressCallback, event: str, **payload: Any) -> None:
    """Send a best-effort scan progress event."""
    if progress_callback:
        progress_callback(event, payload)
