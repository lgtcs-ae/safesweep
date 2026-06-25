"""Restore files from the SafeSweep Vault without overwriting."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src import config
from src.approvals import mark_group_restored
from src.utils import isoformat, now_local


@dataclass
class RestoreOutcome:
    """Result of a restore operation."""

    restored: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "restored_count": len(self.restored),
            "skipped_count": len(self.skipped),
            "restored": self.restored,
            "skipped": self.skipped,
        }


def restore_moved_files(review_folder: Path) -> RestoreOutcome:
    """Restore all currently moved files for a scan without overwriting."""
    restore_map = _load_restore_map(review_folder)
    outcome = RestoreOutcome()

    for entry in restore_map.get("entries", []):
        if entry.get("status") != "moved":
            continue
        original = Path(entry["original_path"])
        vault = Path(entry["vault_path"])
        if original.exists():
            _skip(outcome, entry, "original path already exists")
            _log_restore(review_folder, "restore_skipped", entry, "original path already exists")
            continue
        if not vault.exists():
            _skip(outcome, entry, "vault file is missing")
            _log_restore(review_folder, "restore_skipped", entry, "vault file is missing")
            continue
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(vault), str(original))
        except OSError as exc:
            reason = f"restore failed: {exc}"
            _skip(outcome, entry, reason)
            _log_restore(review_folder, "restore_failed", entry, reason)
            continue

        entry["status"] = "restored"
        entry["restored_at"] = isoformat(now_local())
        outcome.restored.append(dict(entry))
        _log_restore(review_folder, "restored_from_vault", entry, str(original))

    _save_restore_map(review_folder, restore_map)
    _mark_restored_groups(review_folder, restore_map)
    return outcome


def _mark_restored_groups(review_folder: Path, restore_map: Dict[str, Any]) -> None:
    """Mark approval groups restored when no moved entries remain for that group."""
    group_ids = {entry.get("group_id") for entry in restore_map.get("entries", []) if entry.get("group_id")}
    for group_id in group_ids:
        group_entries = [
            entry for entry in restore_map.get("entries", []) if entry.get("group_id") == group_id
        ]
        if group_entries and all(entry.get("status") == "restored" for entry in group_entries):
            mark_group_restored(review_folder, str(group_id))


def _load_restore_map(review_folder: Path) -> Dict[str, Any]:
    """Load restore map data."""
    path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    if not path.exists():
        return {"entries": []}
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("Invalid restore_map.json format.")
    return payload


def _save_restore_map(review_folder: Path, restore_map: Dict[str, Any]) -> None:
    """Persist restore map data."""
    path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(restore_map, file_obj, indent=2)


def _skip(outcome: RestoreOutcome, entry: Dict[str, Any], reason: str) -> None:
    """Record a skipped restore."""
    outcome.skipped.append(
        {
            "group_id": entry.get("group_id"),
            "original_path": entry.get("original_path"),
            "vault_path": entry.get("vault_path"),
            "reason": reason,
        }
    )


def _log_restore(
    review_folder: Path,
    action: str,
    entry: Dict[str, Any],
    result: str,
) -> None:
    """Append one restore action log line."""
    log_path = review_folder / "04_Logs" / "actions_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(
            " ".join(
                [
                    isoformat(now_local()),
                    f"action={action}",
                    f"group_id={entry.get('group_id')}",
                    f"source={entry.get('vault_path')}",
                    f"target={entry.get('original_path')}",
                    f"result={result}",
                ]
            )
            + "\n"
        )
