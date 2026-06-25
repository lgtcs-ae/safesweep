from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.scanner import scan_folders


class ScannerTest(unittest.TestCase):
    def test_scan_collects_metadata_and_writes_phase1_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan_root"
            output_root = base / "output"
            scan_root.mkdir()
            output_root.mkdir()

            (scan_root / "document.txt").write_text("safe", encoding="utf-8")
            nested = scan_root / "nested"
            nested.mkdir()
            (nested / "notes.md").write_text("# Notes", encoding="utf-8")

            hidden = scan_root / ".hidden"
            hidden.mkdir()
            (hidden / "secret.txt").write_text("skip", encoding="utf-8")

            node_modules = scan_root / "node_modules"
            node_modules.mkdir()
            (node_modules / "bundle.js").write_text("skip", encoding="utf-8")
            (scan_root / ".DS_Store").write_text("skip", encoding="utf-8")
            (scan_root / "~$Q1ImpactReportTemplate.pptx").write_text("skip", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)
            summary = result.summary

            self.assertEqual(summary.total_files, 2)
            self.assertEqual(summary.files_by_extension["txt"], 1)
            self.assertEqual(summary.files_by_extension["md"], 1)
            self.assertGreaterEqual(summary.skipped_items, 3)
            self.assertEqual(summary.estimated_vault_bytes, 0)

            review_folder = Path(summary.review_folder)
            self.assertTrue((review_folder / "04_Logs" / "scan_log.txt").exists())
            self.assertTrue((review_folder / "04_Logs" / "errors_log.txt").exists())
            self.assertTrue((review_folder / "04_Logs" / "actions_log.txt").exists())
            self.assertTrue((review_folder / "05_Restore_Map" / "restore_map.json").exists())
            self.assertTrue((review_folder / "01_Reports" / "safesweep_cleanup_candidates.csv").exists())
            self.assertEqual(summary.cleanup_candidate_count, 1)
            self.assertEqual(summary.office_temp_lock_count, 1)
            self.assertEqual(len(result.cleanup_candidates), 1)

            records_path = Path(summary.report_paths["scan_records_json"])
            payload = json.loads(records_path.read_text(encoding="utf-8"))
            scanned_names = {record["name"] for record in payload["records"]}

            self.assertEqual(scanned_names, {"document.txt", "notes.md"})
            self.assertEqual(result.cleanup_candidates[0].record.name, "~$Q1ImpactReportTemplate.pptx")

    def test_include_hidden_allows_hidden_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan_root"
            output_root = base / "output"
            hidden = scan_root / ".hidden"
            hidden.mkdir(parents=True)
            output_root.mkdir()
            (hidden / "visible_when_enabled.txt").write_text("ok", encoding="utf-8")

            result = scan_folders(
                folders=[scan_root],
                output_root=output_root,
                include_hidden=True,
            )

            self.assertEqual(result.summary.total_files, 1)


if __name__ == "__main__":
    unittest.main()
