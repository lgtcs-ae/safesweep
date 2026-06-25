from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.approvals import (
    APPROVED,
    IGNORED,
    approve_confirmed,
    approve_groups,
    ignore_group,
    ignore_groups,
)
from src.scanner import scan_folders


class ApprovalsTest(unittest.TestCase):
    def test_approve_confirmed_and_ignore_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()
            (scan_root / "a.txt").write_text("same", encoding="utf-8")
            (scan_root / "a copy.txt").write_text("same", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)
            review_folder = Path(result.summary.review_folder)
            group_id = result.groups[0].group_id

            approved = approve_confirmed(review_folder)

            self.assertEqual(approved["counts"]["approved_groups"], 1)
            self.assertEqual(
                approved["state"]["groups"][group_id]["status"],
                APPROVED,
            )

            ignored = ignore_group(review_folder, group_id)

            self.assertEqual(ignored["counts"]["ignored_groups"], 1)
            self.assertEqual(ignored["state"]["groups"][group_id]["status"], IGNORED)

    def test_same_name_different_size_is_not_grouped_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            first = scan_root / "one"
            second = scan_root / "two"
            first.mkdir(parents=True)
            second.mkdir()
            output_root.mkdir()
            (first / "same.txt").write_text("left", encoding="utf-8")
            (second / "same.txt").write_text("right side", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)

            self.assertEqual(result.groups, [])

    def test_bulk_approve_and_ignore_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()
            (scan_root / "a.txt").write_text("same", encoding="utf-8")
            (scan_root / "a copy.txt").write_text("same", encoding="utf-8")
            (scan_root / "b.txt").write_text("other", encoding="utf-8")
            (scan_root / "b copy.txt").write_text("other", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)
            review_folder = Path(result.summary.review_folder)
            group_ids = [group.group_id for group in result.groups]

            approved = approve_groups(review_folder, group_ids)

            self.assertEqual(approved["counts"]["approved_groups"], 2)

            ignored = ignore_groups(review_folder, group_ids)

            self.assertEqual(ignored["counts"]["ignored_groups"], 2)
            for group_id in group_ids:
                self.assertEqual(ignored["state"]["groups"][group_id]["status"], IGNORED)


if __name__ == "__main__":
    unittest.main()
