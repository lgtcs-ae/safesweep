"""Finder reveal integration with scan-data validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, Set

from src import config
from src.approvals import load_report
from src.utils import path_is_relative_to


def reveal_in_finder(review_folder: Path, requested_path: Path) -> Dict[str, Any]:
    """Reveal a report-owned path in Finder."""
    allowed = _allowed_paths(review_folder)
    resolved = requested_path.expanduser().resolve(strict=False)
    if not _is_allowed(resolved, review_folder, allowed):
        raise ValueError("Path is not part of this SafeSweep scan or vault.")
    if not resolved.exists():
        raise FileNotFoundError(f"Path does not exist: {resolved}")

    target = resolved if resolved.is_file() else resolved
    subprocess.run(["open", "-R", str(target)], check=False)
    return {"revealed": str(target)}


def _allowed_paths(review_folder: Path) -> Set[Path]:
    """Collect paths known to this scan."""
    paths: Set[Path] = {review_folder.resolve(strict=False)}
    report = load_report(review_folder)
    for group in report.get("groups", []):
        paths.add(Path(group["actual"]["path"]).resolve(strict=False))
        for duplicate in group.get("duplicates", []):
            paths.add(Path(duplicate["path"]).resolve(strict=False))

    restore_map_path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    if restore_map_path.exists():
        with restore_map_path.open("r", encoding="utf-8") as file_obj:
            restore_map = json.load(file_obj)
        for entry in restore_map.get("entries", []):
            paths.add(Path(entry["original_path"]).resolve(strict=False))
            paths.add(Path(entry["vault_path"]).resolve(strict=False))
    return paths


def _is_allowed(path: Path, review_folder: Path, allowed: Iterable[Path]) -> bool:
    """Return True if a reveal path belongs to scan data or the review folder."""
    if path_is_relative_to(path, review_folder):
        return True
    return any(path == allowed_path for allowed_path in allowed)
