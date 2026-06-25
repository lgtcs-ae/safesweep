"""SafeSweep command line launcher.

The current build provides a localhost-only browser UI, safe scanning,
duplicate-candidate matching, and review reports. Later phases will add
approvals, vault movement, and restore.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

from src.approvals import approval_summary, approve_confirmed
from src.app import run_local_app
from src.mover import move_approved_duplicates
from src.restore import restore_moved_files
from src.scanner import scan_folders
from src.utils import human_bytes


def _print_scan_summary(summary: dict) -> None:
    """Print a concise scan summary for CLI users."""
    print("\nSafeSweep scan complete.")
    print(f"Review folder: {summary['review_folder']}")
    print(f"Files scanned: {summary['total_files']}")
    print(f"Data inspected: {human_bytes(summary['total_bytes'])}")
    print(f"Files hashed: {summary['hashed_file_count']}")
    print(f"Duplicate candidate groups: {summary['duplicate_group_count']}")
    print(f"Confirmed groups: {summary['confirmed_duplicate_groups']}")
    print(f"Very likely groups: {summary['likely_duplicate_groups']}")
    print(f"Possible groups: {summary['possible_duplicate_groups']}")
    print(f"Name collisions: {summary['name_collision_groups']}")
    print(f"Estimated review candidate size: {human_bytes(summary['estimated_vault_bytes'])}")
    print(f"Skipped items: {summary['skipped_items']}")
    print(f"Unreadable/errors: {summary['error_count']}")
    print("\nNo files were moved.")
    print("No files were deleted.")


def _parse_path_list(values: Optional[Iterable[str]]) -> list[Path]:
    """Convert CLI path values into Path objects without resolving yet."""
    if not values:
        return []
    return [Path(value).expanduser() for value in values]


def build_parser() -> argparse.ArgumentParser:
    """Build the SafeSweep CLI parser."""
    parser = argparse.ArgumentParser(
        prog="safesweep.py",
        description="SafeSweep - Review first. Clean safely.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch = subparsers.add_parser("launch", help="Start the local browser UI.")
    launch.add_argument("--port", type=int, default=8765, help="Local port to bind.")
    launch.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening a browser window.",
    )

    serve = subparsers.add_parser("serve", help="Alias for launch --no-browser.")
    serve.add_argument("--port", type=int, default=8765, help="Local port to bind.")

    scan = subparsers.add_parser("scan", help="Run a safe review scan.")
    scan.add_argument("--folders", nargs="*", help="Folders to scan.")
    scan.add_argument("--exclude", nargs="*", help="Extra folders to exclude.")
    scan.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden folders. Hidden folders are skipped by default.",
    )
    scan.add_argument(
        "--output-root",
        help="Parent folder for SafeSweep_Review_<timestamp> output.",
    )

    review = subparsers.add_parser("review", help="Show approval summary for a scan.")
    review.add_argument("--scan", required=True, help="Path to a SafeSweep scan folder.")

    approve = subparsers.add_parser("approve-confirmed", help="Approve confirmed duplicate groups.")
    approve.add_argument("--scan", required=True, help="Path to a SafeSweep scan folder.")

    move = subparsers.add_parser("move-approved", help="Move approved duplicates to SafeSweep Vault.")
    move.add_argument("--scan", required=True, help="Path to a SafeSweep scan folder.")

    restore = subparsers.add_parser("restore", help="Restore moved files from a SafeSweep Vault.")
    restore.add_argument("--scan", required=True, help="Path to a SafeSweep scan folder.")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Run the SafeSweep CLI."""
    args = build_parser().parse_args(argv)

    if args.command == "launch":
        run_local_app(port=args.port, open_browser=not args.no_browser)
        return 0

    if args.command == "serve":
        run_local_app(port=args.port, open_browser=False)
        return 0

    if args.command == "scan":
        output_root = Path(args.output_root).expanduser() if args.output_root else None
        result = scan_folders(
            folders=_parse_path_list(args.folders),
            excludes=_parse_path_list(args.exclude),
            include_hidden=bool(args.include_hidden),
            output_root=output_root,
        )
        summary = result.summary.to_dict()
        _print_scan_summary(summary)
        return 0

    if args.command == "review":
        review_folder = Path(args.scan).expanduser()
        summary = approval_summary(review_folder)
        counts = summary["counts"]
        print(f"SafeSweep review folder: {review_folder}")
        print(f"Approved groups: {counts['approved_groups']}")
        print(f"Approved duplicate files: {counts['approved_files']}")
        print(f"Ignored groups: {counts['ignored_groups']}")
        print(f"Moved groups: {counts['moved_groups']}")
        return 0

    if args.command == "approve-confirmed":
        review_folder = Path(args.scan).expanduser()
        summary = approve_confirmed(review_folder)
        print(f"Approved confirmed groups: {summary['counts']['approved_groups']}")
        print("No files were moved.")
        return 0

    if args.command == "move-approved":
        review_folder = Path(args.scan).expanduser()
        outcome = move_approved_duplicates(review_folder)
        print(f"Moved files: {len(outcome.moved)}")
        print(f"Skipped files: {len(outcome.skipped)}")
        print("No files were permanently deleted.")
        return 0

    if args.command == "restore":
        review_folder = Path(args.scan).expanduser()
        outcome = restore_moved_files(review_folder)
        print(f"Restored files: {len(outcome.restored)}")
        print(f"Skipped files: {len(outcome.skipped)}")
        print("No files were overwritten.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
