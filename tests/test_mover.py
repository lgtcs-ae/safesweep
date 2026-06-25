from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.approvals import approve_confirmed, approval_summary
from src.mover import move_approved_duplicates
from src.purge import PERMANENT_SWEEP_PHRASE, purge_moved_vault_files
from src.restore import restore_moved_files
from src.scanner import scan_folders


class MoverRestoreTest(unittest.TestCase):
    def test_move_approved_duplicate_to_vault_then_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()
            (scan_root / "Fa.png").write_bytes(b"image bytes")
            (scan_root / "fa-copy.png").write_bytes(b"image bytes")

            result = scan_folders(folders=[scan_root], output_root=output_root)
            review_folder = Path(result.summary.review_folder)
            group = result.groups[0]
            actual_path = Path(group.actual.path)
            duplicate_path = Path(group.duplicates[0].path)

            approve_confirmed(review_folder)
            move_outcome = move_approved_duplicates(review_folder)

            self.assertEqual(len(move_outcome.moved), 1)
            self.assertTrue(actual_path.exists())
            self.assertFalse(duplicate_path.exists())

            vault_path = Path(move_outcome.moved[0]["vault_path"])
            self.assertTrue(vault_path.exists())
            self.assertIn("03_SafeSweep_Vault", str(vault_path))

            restore_map = json.loads(
                (review_folder / "05_Restore_Map" / "restore_map.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(restore_map["entries"][0]["original_path"], str(duplicate_path))

            restore_outcome = restore_moved_files(review_folder)

            self.assertEqual(len(restore_outcome.restored), 1)
            self.assertTrue(actual_path.exists())
            self.assertTrue(duplicate_path.exists())
            self.assertFalse(vault_path.exists())

    def test_changed_duplicate_is_skipped_before_move(self) -> None:
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
            duplicate_path = Path(result.groups[0].duplicates[0].path)
            duplicate_path.write_text("changed", encoding="utf-8")

            approve_confirmed(review_folder)
            outcome = move_approved_duplicates(review_folder)

            self.assertEqual(len(outcome.moved), 0)
            self.assertEqual(len(outcome.skipped), 1)
            self.assertTrue(duplicate_path.exists())

    def test_restore_does_not_overwrite_existing_original(self) -> None:
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
            duplicate_path = Path(result.groups[0].duplicates[0].path)

            approve_confirmed(review_folder)
            move_outcome = move_approved_duplicates(review_folder)
            duplicate_path.write_text("new file at original path", encoding="utf-8")

            restore_outcome = restore_moved_files(review_folder)

            self.assertEqual(len(restore_outcome.restored), 0)
            self.assertEqual(len(restore_outcome.skipped), 1)
            self.assertTrue(Path(move_outcome.moved[0]["vault_path"]).exists())

    def test_purge_removes_vault_file_after_confirmation(self) -> None:
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
            approve_confirmed(review_folder)
            move_outcome = move_approved_duplicates(review_folder)
            vault_path = Path(move_outcome.moved[0]["vault_path"])

            move_summary = approval_summary(review_folder)
            self.assertEqual(move_summary["counts"]["recovered_bytes"], move_outcome.moved[0]["size_bytes"])
            self.assertEqual(move_summary["counts"]["cleaned_bytes"], 0)

            purge_outcome = purge_moved_vault_files(review_folder, PERMANENT_SWEEP_PHRASE)

            self.assertEqual(len(purge_outcome.purged), 1)
            self.assertFalse(vault_path.exists())

            purge_summary = approval_summary(review_folder)
            self.assertEqual(purge_summary["counts"]["recovered_bytes"], 0)
            self.assertEqual(purge_summary["counts"]["cleaned_bytes"], purge_outcome.purged[0]["size_bytes"])

            restore_map = json.loads(
                (review_folder / "05_Restore_Map" / "restore_map.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(restore_map["entries"][0]["status"], "purged")

            restore_outcome = restore_moved_files(review_folder)

            self.assertEqual(len(restore_outcome.restored), 0)

    def test_purge_requires_exact_confirmation_phrase(self) -> None:
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
            approve_confirmed(review_folder)
            move_outcome = move_approved_duplicates(review_folder)

            with self.assertRaises(ValueError):
                purge_moved_vault_files(review_folder, "delete")

            self.assertTrue(Path(move_outcome.moved[0]["vault_path"]).exists())


if __name__ == "__main__":
    unittest.main()
