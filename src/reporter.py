"""Report artifact writers for SafeSweep scans."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Dict, Iterable, List

from src.matcher import NAME_COLLISION
from src.models import CleanupCandidate, DuplicateGroup, FileRecord, ScanSummary
from src.utils import human_bytes


def create_review_structure(review_root: Path) -> Dict[str, Path]:
    """Create the SafeSweep review folder tree without moving user files."""
    paths = {
        "review_root": review_root,
        "reports": review_root / "01_Reports",
        "actual": review_root / "02_Actual",
        "actual_aliases": review_root / "02_Actual" / "aliases_to_kept_files",
        "vault": review_root / "03_SafeSweep_Vault",
        "vault_confirmed": review_root / "03_SafeSweep_Vault" / "confirmed_duplicates",
        "vault_likely": review_root / "03_SafeSweep_Vault" / "likely_duplicates",
        "vault_possible": review_root / "03_SafeSweep_Vault" / "possible_duplicates",
        "logs": review_root / "04_Logs",
        "restore_map": review_root / "05_Restore_Map",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_phase1_artifacts(
    summary: ScanSummary,
    records: Iterable[FileRecord],
    groups: Iterable[DuplicateGroup],
    cleanup_candidates: Iterable[CleanupCandidate],
    paths: Dict[str, Path],
) -> Dict[str, str]:
    """Write scan and duplicate-candidate artifacts, then return paths."""
    reports_dir = paths["reports"]
    restore_dir = paths["restore_map"]
    actual_dir = paths["actual"]

    summary_path = reports_dir / "safesweep_scan_summary.json"
    records_path = reports_dir / "safesweep_scan_records.json"
    report_json_path = reports_dir / "safesweep_report.json"
    report_csv_path = reports_dir / "safesweep_report.csv"
    cleanup_csv_path = reports_dir / "safesweep_cleanup_candidates.csv"
    report_html_path = reports_dir / "safesweep_report.html"
    actual_index_path = actual_dir / "actual_files_index.csv"
    restore_map_path = restore_dir / "restore_map.json"
    approval_state_path = paths["review_root"] / "approval_state.json"

    record_dicts = [record.to_dict() for record in records]
    group_list = list(groups)
    group_dicts = [group.to_dict() for group in group_list]
    cleanup_list = list(cleanup_candidates)
    cleanup_dicts = [candidate.to_dict() for candidate in cleanup_list]

    with summary_path.open("w", encoding="utf-8") as file_obj:
        json.dump(summary.to_dict(), file_obj, indent=2)

    with records_path.open("w", encoding="utf-8") as file_obj:
        json.dump({"scan_id": summary.scan_id, "records": record_dicts}, file_obj, indent=2)

    with report_json_path.open("w", encoding="utf-8") as file_obj:
        json.dump(
            {
                "scan_id": summary.scan_id,
                "phase": summary.phase,
                "summary": summary.to_dict(),
                "groups": group_dicts,
                "cleanup_candidates": cleanup_dicts,
                "note": "SafeSweep detects duplicate candidates locally. Only approved duplicates can be moved to the recoverable SafeSweep Vault.",
            },
            file_obj,
            indent=2,
        )

    with report_csv_path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "group_id",
                "classification",
                "confidence",
                "role",
                "path",
                "file_name",
                "extension",
                "size_bytes",
                "created_at",
                "modified_at",
                "sha256",
                "recommended_action",
                "reason",
            ]
        )
        for group in group_list:
            _write_group_csv_rows(writer, group)

    with cleanup_csv_path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "candidate_id",
                "classification",
                "confidence",
                "path",
                "file_name",
                "extension",
                "size_bytes",
                "created_at",
                "modified_at",
                "recommended_action",
                "reason",
            ]
        )
        for candidate in cleanup_list:
            _write_cleanup_candidate_csv_row(writer, candidate)

    with actual_index_path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["group_id", "actual_file_path", "classification", "confidence", "reason"])
        for group in group_list:
            writer.writerow(
                [
                    group.group_id,
                    group.actual.path,
                    group.classification,
                    group.confidence,
                    group.reason,
                ]
            )

    with restore_map_path.open("w", encoding="utf-8") as file_obj:
        json.dump(
            {
                "scan_id": summary.scan_id,
                "entries": [],
                "note": "Entries are added only after approved duplicates are moved to the SafeSweep Vault.",
            },
            file_obj,
            indent=2,
        )

    if not approval_state_path.exists():
        with approval_state_path.open("w", encoding="utf-8") as file_obj:
            json.dump(
                {
                    "scan_id": summary.scan_id,
                    "updated_at": summary.completed_at,
                    "groups": {},
                    "note": "Approval decisions are stored here before any vault movement.",
                },
                file_obj,
                indent=2,
            )

    with report_html_path.open("w", encoding="utf-8") as file_obj:
        file_obj.write(_report_html(summary, group_list, cleanup_list))

    return {
        "scan_summary_json": str(summary_path),
        "scan_records_json": str(records_path),
        "report_json": str(report_json_path),
        "report_csv": str(report_csv_path),
        "cleanup_candidates_csv": str(cleanup_csv_path),
        "report_html": str(report_html_path),
        "actual_index_csv": str(actual_index_path),
        "restore_map_json": str(restore_map_path),
        "approval_state_json": str(approval_state_path),
    }


def _write_group_csv_rows(writer: csv.writer, group: DuplicateGroup) -> None:
    """Write CSV rows for one duplicate group."""
    _write_file_row(writer, group, group.actual, "actual")
    for record in group.duplicates:
        _write_file_row(writer, group, record, "duplicate")


def _write_file_row(
    writer: csv.writer,
    group: DuplicateGroup,
    record: FileRecord,
    role: str,
) -> None:
    """Write one group/file CSV row."""
    writer.writerow(
        [
            group.group_id,
            group.classification,
            group.confidence,
            role,
            record.path,
            record.name,
            record.extension,
            record.size_bytes,
            record.created_at,
            record.modified_at,
            record.sha256 or "",
            group.recommended_action,
            group.reason,
        ]
    )


def _write_cleanup_candidate_csv_row(writer: csv.writer, candidate: CleanupCandidate) -> None:
    """Write one cleanup candidate CSV row."""
    record = candidate.record
    writer.writerow(
        [
            candidate.candidate_id,
            candidate.classification,
            candidate.confidence,
            record.path,
            record.name,
            record.extension,
            record.size_bytes,
            record.created_at,
            record.modified_at,
            candidate.recommended_action,
            candidate.reason,
        ]
    )


def _report_html(
    summary: ScanSummary,
    groups: List[DuplicateGroup],
    cleanup_candidates: List[CleanupCandidate],
) -> str:
    """Render a standalone HTML candidate report for the scan folder."""
    group_cards = "\n".join(_group_card(group) for group in groups)
    cleanup_cards = "\n".join(_cleanup_card(candidate) for candidate in cleanup_candidates)
    if not group_cards:
        group_cards = """
        <section class="empty">
          <h2>No duplicate candidates found</h2>
          <p>SafeSweep scanned metadata and same-size hashes but did not find reportable candidate groups.</p>
        </section>
        """
    if not cleanup_cards:
        cleanup_cards = """
        <section class="empty">
          <h2>No cleanup candidates found</h2>
          <p>SafeSweep did not find Office owner/temp lock files in this scan.</p>
        </section>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SafeSweep Scan Summary</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; color: #17202a; background: #f5f7f8; }}
    main {{ max-width: 1100px; margin: 0 auto; }}
    .card, .group, .empty {{ border: 1px solid #dbe3ea; border-radius: 8px; padding: 24px; background: #fff; box-shadow: 0 16px 35px rgba(24, 38, 52, .08); }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
    .metric {{ border: 1px solid #e2e8ed; border-radius: 8px; padding: 16px; background: #fbfcfc; }}
    .label {{ color: #657382; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .value {{ margin-top: 8px; font-size: 28px; font-weight: 700; }}
    .group {{ margin-top: 18px; }}
    .badge {{ display: inline-flex; border-radius: 6px; padding: 4px 9px; font-size: 12px; font-weight: 700; background: #eaf6f1; color: #0d6147; }}
    .collision {{ background: #fff7ed; color: #7a4b13; }}
    .path {{ overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }}
    .file {{ border-top: 1px solid #edf2f4; margin-top: 14px; padding-top: 14px; }}
    .muted {{ color: #5e6b78; }}
  </style>
</head>
<body>
  <main>
    <section class="card">
      <p class="muted">SafeSweep - Review first. Clean safely.</p>
      <h1>Duplicate Candidate Report</h1>
      <div class="grid">
        <div class="metric"><div class="label">Files</div><div class="value">{summary.total_files}</div></div>
        <div class="metric"><div class="label">Groups</div><div class="value">{summary.duplicate_group_count}</div></div>
        <div class="metric"><div class="label">Confirmed</div><div class="value">{summary.confirmed_duplicate_groups}</div></div>
        <div class="metric"><div class="label">Cleanup</div><div class="value">{summary.cleanup_candidate_count}</div></div>
        <div class="metric"><div class="label">Vault Estimate</div><div class="value">{human_bytes(summary.estimated_vault_bytes)}</div></div>
      </div>
      <p class="muted">Actual files stay in place. Approved duplicates can later be moved to the recoverable SafeSweep Vault.</p>
    </section>
    <h2>Duplicate Candidates</h2>
    {group_cards}
    <h2>Cleanup Candidates</h2>
    {cleanup_cards}
  </main>
</body>
</html>
"""


def _group_card(group: DuplicateGroup) -> str:
    """Render a single duplicate group for the standalone HTML report."""
    badge_class = "badge collision" if group.classification == NAME_COLLISION else "badge"
    duplicate_items = "\n".join(_file_block(record, "Duplicate candidate") for record in group.duplicates)
    classification = html.escape(group.classification)
    group_id = html.escape(group.group_id)
    reason = html.escape(group.reason)
    action = html.escape(group.recommended_action)
    return f"""
    <section class="group">
      <span class="{badge_class}">{classification}</span>
      <h2>{group_id} - {group.confidence}% confidence</h2>
      <p>{reason}</p>
      <p class="muted">{action}</p>
      {_file_block(group.actual, "Actual")}
      {duplicate_items}
    </section>
    """


def _file_block(record: FileRecord, role: str) -> str:
    """Render one file block for the standalone HTML report."""
    sha = html.escape(record.sha256 or "not hashed")
    path = html.escape(record.path)
    role_text = html.escape(role)
    created = html.escape(record.created_at)
    modified = html.escape(record.modified_at)
    return f"""
    <div class="file">
      <strong>{role_text}</strong>
      <div class="path">{path}</div>
      <div class="muted">Size: {human_bytes(record.size_bytes)} | Created: {created} | Modified: {modified}</div>
      <div class="muted">SHA-256: {sha}</div>
    </div>
    """


def _cleanup_card(candidate: CleanupCandidate) -> str:
    """Render one cleanup candidate for the standalone HTML report."""
    classification = html.escape(candidate.classification)
    candidate_id = html.escape(candidate.candidate_id)
    reason = html.escape(candidate.reason)
    action = html.escape(candidate.recommended_action)
    return f"""
    <section class="group">
      <span class="badge collision">{classification}</span>
      <h2>{candidate_id} - {candidate.confidence}% cleanup signal</h2>
      <p>{reason}</p>
      <p class="muted">{action}</p>
      {_file_block(candidate.record, "Cleanup candidate")}
    </section>
    """
