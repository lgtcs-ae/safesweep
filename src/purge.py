"""Permanent purge of files already moved into the SafeSweep Vault."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src import config
from src.approvals import mark_group_purged
from src.utils import isoformat, now_local, path_is_relative_to


PERMANENT_SWEEP_PHRASE = "PERMANENT SWEEP"


@dataclass
class PurgeOutcome:
    """Result of permanently removing moved Vault files."""

    purged: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "purged_count": len(self.purged),
            "skipped_count": len(self.skipped),
            "purged": self.purged,
            "skipped": self.skipped,
        }


def purge_moved_vault_files(review_folder: Path, confirmation_phrase: str) -> PurgeOutcome:
    """Permanently remove Vault files with status 'moved' after explicit confirmation."""
    if confirmation_phrase != PERMANENT_SWEEP_PHRASE:
        raise ValueError(f'Type "{PERMANENT_SWEEP_PHRASE}" to permanently sweep Vault files.')

    restore_map = _load_restore_map(review_folder)
    outcome = PurgeOutcome()
    vault_root = (review_folder / "03_SafeSweep_Vault").resolve(strict=False)

    for entry in restore_map.get("entries", []):
        if entry.get("status") != "moved":
            continue
        vault_path = Path(entry["vault_path"]).resolve(strict=False)
        if not path_is_relative_to(vault_path, vault_root):
            _skip(outcome, entry, "vault path is outside SafeSweep Vault")
            _log_purge(review_folder, "purge_skipped", entry, "vault path is outside SafeSweep Vault")
            continue
        if not vault_path.exists():
            _skip(outcome, entry, "vault file is missing")
            _log_purge(review_folder, "purge_skipped", entry, "vault file is missing")
            continue
        if not vault_path.is_file():
            _skip(outcome, entry, "vault path is not a regular file")
            _log_purge(review_folder, "purge_skipped", entry, "vault path is not a regular file")
            continue

        try:
            vault_path.unlink()
            _remove_empty_vault_parents(vault_path.parent, vault_root)
        except OSError as exc:
            reason = f"purge failed: {exc}"
            _skip(outcome, entry, reason)
            _log_purge(review_folder, "purge_failed", entry, reason)
            continue

        entry["status"] = "purged"
        entry["purged_at"] = isoformat(now_local())
        outcome.purged.append(dict(entry))
        _log_purge(review_folder, "purged_from_vault", entry, "permanently removed")

    _save_restore_map(review_folder, restore_map)
    _mark_purged_groups(review_folder, restore_map)
    return outcome


def _mark_purged_groups(review_folder: Path, restore_map: Dict[str, Any]) -> None:
    """Mark groups purged when all their restore-map entries are purged."""
    group_ids = {entry.get("group_id") for entry in restore_map.get("entries", []) if entry.get("group_id")}
    for group_id in group_ids:
        group_entries = [
            entry for entry in restore_map.get("entries", []) if entry.get("group_id") == group_id
        ]
        if group_entries and all(entry.get("status") == "purged" for entry in group_entries):
            mark_group_purged(review_folder, str(group_id))


def _remove_empty_vault_parents(start: Path, vault_root: Path) -> None:
    """Remove empty Vault directories created only to preserve original paths."""
    current = start.resolve(strict=False)
    while current != vault_root and path_is_relative_to(current, vault_root):
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


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
    """Persist restore map data after marking purged entries."""
    path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(restore_map, file_obj, indent=2)


def _skip(outcome: PurgeOutcome, entry: Dict[str, Any], reason: str) -> None:
    """Record a skipped purge."""
    outcome.skipped.append(
        {
            "group_id": entry.get("group_id"),
            "original_path": entry.get("original_path"),
            "vault_path": entry.get("vault_path"),
            "reason": reason,
        }
    )


def _log_purge(
    review_folder: Path,
    action: str,
    entry: Dict[str, Any],
    result: str,
) -> None:
    """Append one permanent sweep action log line."""
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
                    f"original={entry.get('original_path')}",
                    f"result={result}",
                ]
            )
            + "\n"
        )
