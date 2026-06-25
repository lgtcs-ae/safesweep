"""Approval-state management for SafeSweep scans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src import config
from src.matcher import CONFIRMED, NAME_COLLISION
from src.utils import isoformat, now_local


APPROVED = "approved"
IGNORED = "ignored"
MOVED = "moved"
PURGED = "purged"
RESTORED = "restored"
UNREVIEWED = "unreviewed"


def report_path_for_scan(review_folder: Path) -> Path:
    """Return the authoritative JSON report path for a review folder."""
    return review_folder / "01_Reports" / "safesweep_report.json"


def approval_state_path(review_folder: Path) -> Path:
    """Return the approval-state path for a review folder."""
    return review_folder / config.APPROVAL_STATE_RELATIVE_PATH


def load_report(review_folder: Path) -> Dict[str, Any]:
    """Load a SafeSweep scan report."""
    path = report_path_for_scan(review_folder)
    if not path.exists():
        raise FileNotFoundError(f"SafeSweep report not found: {path}")
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict) or "groups" not in payload:
        raise ValueError("Invalid SafeSweep report format.")
    return payload


def ensure_approval_state(review_folder: Path) -> Dict[str, Any]:
    """Load or initialize approval state for a scan."""
    report = load_report(review_folder)
    path = approval_state_path(review_folder)
    if path.exists():
        with path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        if isinstance(payload, dict) and isinstance(payload.get("groups"), dict):
            return payload

    payload = {
        "scan_id": report.get("scan_id"),
        "updated_at": isoformat(now_local()),
        "groups": {},
        "note": "Approval decisions are stored here before vault movement.",
    }
    save_approval_state(review_folder, payload)
    return payload


def save_approval_state(review_folder: Path, state: Dict[str, Any]) -> None:
    """Persist approval state."""
    state["updated_at"] = isoformat(now_local())
    path = approval_state_path(review_folder)
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(state, file_obj, indent=2)


def approval_summary(review_folder: Path) -> Dict[str, Any]:
    """Return approval state with useful counts."""
    state = ensure_approval_state(review_folder)
    groups = state.get("groups", {})
    counts = {
        "approved_groups": 0,
        "ignored_groups": 0,
        "moved_groups": 0,
        "purged_groups": 0,
        "restored_groups": 0,
        "approved_files": 0,
    }
    for group_state in groups.values():
        status = group_state.get("status", UNREVIEWED)
        if status == APPROVED:
            counts["approved_groups"] += 1
            counts["approved_files"] += len(group_state.get("approved_duplicate_paths", []))
        elif status == IGNORED:
            counts["ignored_groups"] += 1
        elif status == MOVED:
            counts["moved_groups"] += 1
        elif status == PURGED:
            counts["purged_groups"] += 1
        elif status == RESTORED:
            counts["restored_groups"] += 1
    counts.update(_restore_map_totals(review_folder))
    return {"state": state, "counts": counts}


def _restore_map_totals(review_folder: Path) -> Dict[str, int]:
    """Summarize Vault bytes by current restore-map status."""
    path = review_folder / config.RESTORE_MAP_RELATIVE_PATH
    totals = {
        "recovered_bytes": 0,
        "cleaned_bytes": 0,
        "recovered_files": 0,
        "cleaned_files": 0,
    }
    if not path.exists():
        return totals

    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        return totals

    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        size = int(entry.get("size_bytes", 0) or 0)
        status = entry.get("status", UNREVIEWED)
        if status == MOVED:
            totals["recovered_bytes"] += size
            totals["recovered_files"] += 1
        elif status == PURGED:
            totals["cleaned_bytes"] += size
            totals["cleaned_files"] += 1
    return totals


def approve_group(review_folder: Path, group_id: str) -> Dict[str, Any]:
    """Approve all duplicate candidates in one group."""
    report = load_report(review_folder)
    group = _find_group(report.get("groups", []), group_id)
    if group["classification"] == NAME_COLLISION:
        raise ValueError("Name-collision groups are report-only and cannot be approved.")

    duplicate_paths = [record["path"] for record in group.get("duplicates", [])]
    state = ensure_approval_state(review_folder)
    state.setdefault("groups", {})[group_id] = {
        "status": APPROVED,
        "approved_at": isoformat(now_local()),
        "approved_duplicate_paths": duplicate_paths,
        "classification": group["classification"],
        "confidence": group["confidence"],
    }
    save_approval_state(review_folder, state)
    return approval_summary(review_folder)


def ignore_group(review_folder: Path, group_id: str) -> Dict[str, Any]:
    """Mark one group as ignored."""
    report = load_report(review_folder)
    group = _find_group(report.get("groups", []), group_id)
    state = ensure_approval_state(review_folder)
    state.setdefault("groups", {})[group_id] = {
        "status": IGNORED,
        "ignored_at": isoformat(now_local()),
        "approved_duplicate_paths": [],
        "classification": group["classification"],
        "confidence": group["confidence"],
    }
    save_approval_state(review_folder, state)
    return approval_summary(review_folder)


def approve_groups(review_folder: Path, group_ids: Iterable[str]) -> Dict[str, Any]:
    """Approve all duplicate candidates in selected groups."""
    report = load_report(review_folder)
    by_id = {group["group_id"]: group for group in report.get("groups", [])}
    state = ensure_approval_state(review_folder)
    for group_id in group_ids:
        group = by_id.get(group_id)
        if not group:
            raise ValueError(f"Unknown group_id: {group_id}")
        if group["classification"] == NAME_COLLISION:
            raise ValueError("Name-collision groups are report-only and cannot be approved.")
        duplicate_paths = [record["path"] for record in group.get("duplicates", [])]
        state.setdefault("groups", {})[group_id] = {
            "status": APPROVED,
            "approved_at": isoformat(now_local()),
            "approved_duplicate_paths": duplicate_paths,
            "classification": group["classification"],
            "confidence": group["confidence"],
        }
    save_approval_state(review_folder, state)
    return approval_summary(review_folder)


def ignore_groups(review_folder: Path, group_ids: Iterable[str]) -> Dict[str, Any]:
    """Mark selected groups as ignored."""
    report = load_report(review_folder)
    by_id = {group["group_id"]: group for group in report.get("groups", [])}
    state = ensure_approval_state(review_folder)
    for group_id in group_ids:
        group = by_id.get(group_id)
        if not group:
            raise ValueError(f"Unknown group_id: {group_id}")
        state.setdefault("groups", {})[group_id] = {
            "status": IGNORED,
            "ignored_at": isoformat(now_local()),
            "approved_duplicate_paths": [],
            "classification": group["classification"],
            "confidence": group["confidence"],
        }
    save_approval_state(review_folder, state)
    return approval_summary(review_folder)


def approve_confirmed(review_folder: Path) -> Dict[str, Any]:
    """Approve all confirmed duplicate groups."""
    report = load_report(review_folder)
    state = ensure_approval_state(review_folder)
    for group in report.get("groups", []):
        if group.get("classification") != CONFIRMED:
            continue
        group_id = group["group_id"]
        duplicate_paths = [record["path"] for record in group.get("duplicates", [])]
        state.setdefault("groups", {})[group_id] = {
            "status": APPROVED,
            "approved_at": isoformat(now_local()),
            "approved_duplicate_paths": duplicate_paths,
            "classification": group["classification"],
            "confidence": group["confidence"],
        }
    save_approval_state(review_folder, state)
    return approval_summary(review_folder)


def mark_group_moved(
    review_folder: Path,
    group_id: str,
    moved_paths: Iterable[str],
) -> None:
    """Mark a group as moved after vault movement completes."""
    state = ensure_approval_state(review_folder)
    group_state = state.setdefault("groups", {}).setdefault(group_id, {})
    group_state["status"] = MOVED
    group_state["moved_at"] = isoformat(now_local())
    group_state["moved_duplicate_paths"] = list(moved_paths)
    save_approval_state(review_folder, state)


def mark_group_restored(review_folder: Path, group_id: str) -> None:
    """Mark a group as restored after its vault entries are restored."""
    state = ensure_approval_state(review_folder)
    group_state = state.setdefault("groups", {}).setdefault(group_id, {})
    group_state["status"] = RESTORED
    group_state["restored_at"] = isoformat(now_local())
    save_approval_state(review_folder, state)


def mark_group_purged(review_folder: Path, group_id: str) -> None:
    """Mark a group as purged after its vault entries are permanently removed."""
    state = ensure_approval_state(review_folder)
    group_state = state.setdefault("groups", {}).setdefault(group_id, {})
    group_state["status"] = PURGED
    group_state["purged_at"] = isoformat(now_local())
    save_approval_state(review_folder, state)


def approved_groups(report: Dict[str, Any], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return report groups currently approved for movement."""
    by_id = {group["group_id"]: group for group in report.get("groups", [])}
    selected: List[Dict[str, Any]] = []
    for group_id, group_state in state.get("groups", {}).items():
        if group_state.get("status") != APPROVED:
            continue
        group = by_id.get(group_id)
        if group:
            selected.append(group)
    return selected


def _find_group(groups: List[Dict[str, Any]], group_id: str) -> Dict[str, Any]:
    """Find a group by ID or raise a user-facing error."""
    for group in groups:
        if group.get("group_id") == group_id:
            return group
    raise ValueError(f"Unknown group_id: {group_id}")
