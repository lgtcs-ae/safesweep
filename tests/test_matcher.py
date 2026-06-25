from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.matcher import CONFIRMED, VERY_LIKELY
from src.scanner import scan_folders


class MatcherTest(unittest.TestCase):
    def test_scan_detects_confirmed_and_ignores_different_size_name_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()

            first = scan_root / "first"
            second = scan_root / "second"
            first.mkdir()
            second.mkdir()

            (first / "Invoice.pdf").write_bytes(b"same invoice")
            (second / "Invoice copy.pdf").write_bytes(b"same invoice")

            (first / "Report.pdf").write_bytes(b"abcde")
            (second / "Report copy.pdf").write_bytes(b"vwxyz")

            (first / "Budget.xlsx").write_bytes(b"short")
            (second / "Budget copy.xlsx").write_bytes(b"longer budget")

            result = scan_folders(folders=[scan_root], output_root=output_root)
            classifications = {group.classification for group in result.groups}

            self.assertIn(CONFIRMED, classifications)
            self.assertNotIn(VERY_LIKELY, classifications)
            self.assertEqual(result.summary.confirmed_duplicate_groups, 1)
            self.assertEqual(result.summary.likely_duplicate_groups, 0)
            self.assertEqual(result.summary.possible_duplicate_groups, 0)
            self.assertGreater(result.summary.hashed_file_count, 0)
            self.assertGreater(result.summary.estimated_vault_bytes, 0)

            report_path = Path(result.summary.report_paths["report_json"])
            report = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertEqual(len(report["groups"]), 1)
            self.assertEqual(report["groups"][0]["classification"], CONFIRMED)
            self.assertIn("actual", report["groups"][0])
            self.assertIn("duplicates", report["groups"][0])


if __name__ == "__main__":
    unittest.main()
