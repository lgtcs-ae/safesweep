"""Local file preview support with scan-data validation."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

from src import config
from src.approvals import load_report
from src.utils import human_bytes, path_is_relative_to

TEXT_EXTENSIONS = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".log",
    ".md",
    ".py",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp"}
PDF_EXTENSIONS = {".pdf"}
VIDEO_EXTENSIONS = {".m4v", ".mov", ".mp4", ".webm"}
AUDIO_EXTENSIONS = {".aac", ".m4a", ".mp3", ".ogg", ".wav"}
SNIPPET_LIMIT = 24 * 1024


def preview_metadata(review_folder: Path, requested_path: Path) -> Dict[str, Any]:
    """Return safe preview metadata for a scan-owned path."""
    resolved = resolve_preview_path(review_folder, requested_path)
    stat = resolved.stat()
    content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    kind = preview_kind(resolved, content_type)
    payload: Dict[str, Any] = {
        "name": resolved.name,
        "path": str(resolved),
        "size_bytes": stat.st_size,
        "size_label": human_bytes(stat.st_size),
        "content_type": content_type,
        "kind": kind,
        "can_inline": kind in {"image", "pdf", "video", "audio"},
        "snippet": "",
    }
    if kind == "text":
        payload["snippet"] = read_text_snippet(resolved)
    return payload


def resolve_preview_path(review_folder: Path, requested_path: Path) -> Path:
    """Resolve a requested path to an existing scan-owned file or Vault copy."""
    allowed = allowed_preview_paths(review_folder)
    requested = requested_path.expanduser().resolve(strict=False)
    resolved = requested if requested.exists() else vault_replacement(review_folder, requested)
    if resolved is None:
        raise FileNotFoundError(f"Path does not exist: {requested}")
    if not _is_allowed(resolved, review_folder, allowed):
        raise ValueError("Path is not part of this SafeSweep scan or vault.")
    if not resolved.is_file():
        raise ValueError("Preview is available only for regular files.")
    return resolved


def preview_kind(path: Path, content_type: str) -> str:
    """Return the preview category for a file."""
    extension = path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in PDF_EXTENSIONS or content_type == "application/pdf":
        return "pdf"
    if extension in VIDEO_EXTENSIONS or content_type.startswith("video/"):
        return "video"
    if extension in AUDIO_EXTENSIONS or content_type.startswith("audio/"):
        return "audio"
    if extension in TEXT_EXTENSIONS or content_type.startswith("text/"):
        return "text"
    return "unsupported"


def read_text_snippet(path: Path) -> str:
    """Read a bounded text snippet for preview."""
    raw = path.read_bytes()[:SNIPPET_LIMIT]
    return raw.decode("utf-8", errors="replace")


def allowed_preview_paths(review_folder: Path) -> Set[Path]:
    """Collect previewable paths known to this scan."""
    paths: Set[Path] = {review_folder.resolve(strict=False)}
    report = load_report(review_folder)
    for group in report.get("groups", []):
        paths.add(Path(group["actual"]["path"]).resolve(strict=False))
        for duplicate in group.get("duplicates", []):
            paths.add(Path(duplicate["path"]).resolve(strict=False))
    for candidate in report.get("cleanup_candidates", []):
        record = candidate.get("record") or {}
        if record.get("path"):
            paths.add(Path(record["path"]).resolve(strict=False))

    restore_map_path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    if restore_map_path.exists():
        with restore_map_path.open("r", encoding="utf-8") as file_obj:
            restore_map = json.load(file_obj)
        for entry in restore_map.get("entries", []):
            paths.add(Path(entry["original_path"]).resolve(strict=False))
            paths.add(Path(entry["vault_path"]).resolve(strict=False))
    return paths


def vault_replacement(review_folder: Path, original_path: Path) -> Optional[Path]:
    """Return an existing Vault copy for an original path when available."""
    restore_map_path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    if not restore_map_path.exists():
        return None
    with restore_map_path.open("r", encoding="utf-8") as file_obj:
        restore_map = json.load(file_obj)
    for entry in restore_map.get("entries", []):
        entry_original = Path(entry.get("original_path", "")).resolve(strict=False)
        if entry_original != original_path:
            continue
        vault_path = Path(entry.get("vault_path", "")).resolve(strict=False)
        if vault_path.exists():
            return vault_path
    return None


def _is_allowed(path: Path, review_folder: Path, allowed: Iterable[Path]) -> bool:
    """Return True if a preview path belongs to scan data or the review folder."""
    if path_is_relative_to(path, review_folder):
        return True
    return any(path == allowed_path for allowed_path in allowed)
