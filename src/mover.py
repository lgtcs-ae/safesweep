"""Safe movement of approved duplicates into the SafeSweep Vault."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src import config
from src.approvals import (
    approved_groups,
    ensure_approval_state,
    load_report,
    mark_group_moved,
)
from src.hasher import hash_file
from src.utils import isoformat, now_local, unique_file_path


@dataclass
class MoveOutcome:
    """Result of a move-approved operation."""

    moved: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "moved_count": len(self.moved),
            "skipped_count": len(self.skipped),
            "moved": self.moved,
            "skipped": self.skipped,
        }


def move_approved_duplicates(review_folder: Path) -> MoveOutcome:
    """Move only approved duplicate files into the recoverable vault."""
    report = load_report(review_folder)
    state = ensure_approval_state(review_folder)
    outcome = MoveOutcome()
    restore_map = _load_restore_map(review_folder, report.get("scan_id"))

    for group in approved_groups(report, state):
        group_moved_paths: List[str] = []
        approved_paths = set(
            state.get("groups", {})
            .get(group["group_id"], {})
            .get("approved_duplicate_paths", [])
        )
        for duplicate in group.get("duplicates", []):
            if duplicate["path"] not in approved_paths:
                continue
            validation_error = _validate_duplicate_before_move(group, duplicate)
            if validation_error:
                _skip(outcome, group, duplicate, validation_error)
                _log_action(review_folder, "move_skipped", group, duplicate, validation_error)
                continue

            destination = _vault_destination(review_folder, group, duplicate)
            destination = unique_file_path(destination)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(duplicate["path"], str(destination))
            except OSError as exc:
                reason = f"move failed: {exc}"
                _skip(outcome, group, duplicate, reason)
                _log_action(review_folder, "move_failed", group, duplicate, reason)
                continue

            moved_at = isoformat(now_local())
            entry = {
                "group_id": group["group_id"],
                "classification": group["classification"],
                "confidence": group["confidence"],
                "original_path": duplicate["path"],
                "vault_path": str(destination),
                "actual_path": group["actual"]["path"],
                "size_bytes": duplicate["size_bytes"],
                "sha256": duplicate.get("sha256"),
                "modified_at_at_scan": duplicate["modified_at"],
                "moved_at": moved_at,
                "restored_at": None,
                "status": "moved",
            }
            restore_map.setdefault("entries", []).append(entry)
            outcome.moved.append(entry)
            group_moved_paths.append(duplicate["path"])
            _log_action(review_folder, "moved_to_vault", group, duplicate, str(destination))

        if group_moved_paths:
            mark_group_moved(review_folder, group["group_id"], group_moved_paths)

    _save_restore_map(review_folder, restore_map)
    return outcome


def _validate_duplicate_before_move(
    group: Dict[str, Any],
    duplicate: Dict[str, Any],
) -> Optional[str]:
    """Return an error reason when a duplicate is not safe to move."""
    classification = group.get("classification")
    if classification not in config.CLASSIFICATION_VAULT_DIRS:
        return f"classification is not movable: {classification}"

    source = Path(duplicate["path"])
    actual = Path(group["actual"]["path"])
    if source.resolve(strict=False) == actual.resolve(strict=False):
        return "duplicate source is the selected Actual file"
    if not actual.exists():
        return "Actual file no longer exists"
    if not source.exists():
        return "source file no longer exists"
    if not source.is_file():
        return "source is not a regular file"

    stat_result = source.stat()
    if int(stat_result.st_size) != int(duplicate["size_bytes"]):
        return "source size changed after scan"

    scanned_mtime = _parse_iso_timestamp(duplicate["modified_at"])
    if scanned_mtime is None:
        return "scan modified timestamp is invalid"
    if abs(stat_result.st_mtime - scanned_mtime) > 1.0:
        return "source modified time changed after scan"

    expected_hash = duplicate.get("sha256")
    if expected_hash:
        try:
            current_hash = hash_file(source)
        except OSError as exc:
            return f"could not re-hash source: {exc}"
        if current_hash != expected_hash:
            return "source hash changed after scan"

    return None


def _vault_destination(
    review_folder: Path,
    group: Dict[str, Any],
    duplicate: Dict[str, Any],
) -> Path:
    """Return the vault destination preserving original absolute structure."""
    source = Path(duplicate["path"]).resolve(strict=False)
    if not source.is_absolute():
        raise ValueError("Report source path must be absolute.")
    relative_source = Path(*source.parts[1:])
    vault_dir = config.CLASSIFICATION_VAULT_DIRS[group["classification"]]
    return review_folder / "03_SafeSweep_Vault" / vault_dir / relative_source


def _load_restore_map(review_folder: Path, scan_id: Optional[str]) -> Dict[str, Any]:
    """Load or initialize restore map data."""
    path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    if path.exists():
        with path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            return payload
    return {
        "scan_id": scan_id,
        "entries": [],
        "note": "Every SafeSweep Vault move is recorded here for restore.",
    }


def _save_restore_map(review_folder: Path, restore_map: Dict[str, Any]) -> None:
    """Persist restore map data."""
    path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(restore_map, file_obj, indent=2)


def _parse_iso_timestamp(value: str) -> Optional[float]:
    """Parse an ISO timestamp into epoch seconds."""
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _skip(
    outcome: MoveOutcome,
    group: Dict[str, Any],
    duplicate: Dict[str, Any],
    reason: str,
) -> None:
    """Record a skipped move."""
    outcome.skipped.append(
        {
            "group_id": group.get("group_id"),
            "source_path": duplicate.get("path"),
            "reason": reason,
        }
    )


def _log_action(
    review_folder: Path,
    action: str,
    group: Dict[str, Any],
    duplicate: Dict[str, Any],
    result: str,
) -> None:
    """Append one action log line."""
    log_path = review_folder / "04_Logs" / "actions_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(
            " ".join(
                [
                    isoformat(now_local()),
                    f"action={action}",
                    f"group_id={group.get('group_id')}",
                    f"classification={group.get('classification')}",
                    f"source={duplicate.get('path')}",
                    f"result={result}",
                ]
            )
            + "\n"
        )
