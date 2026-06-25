from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.approvals import approve_confirmed
from src.mover import move_approved_duplicates
from src.preview import preview_metadata, resolve_preview_path
from src.scanner import scan_folders


class PreviewTest(unittest.TestCase):
    def test_preview_metadata_allows_scan_owned_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()
            (scan_root / "a.txt").write_text("same text", encoding="utf-8")
            (scan_root / "a copy.txt").write_text("same text", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)
            review_folder = Path(result.summary.review_folder)
            record_path = Path(result.groups[0].actual.path)

            metadata = preview_metadata(review_folder, record_path)

            self.assertEqual(metadata["kind"], "text")
            self.assertEqual(metadata["snippet"], "same text")
            self.assertEqual(metadata["name"], record_path.name)

    def test_preview_rejects_path_outside_scan_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            outside = base / "outside.txt"
            scan_root.mkdir()
            output_root.mkdir()
            outside.write_text("outside", encoding="utf-8")
            (scan_root / "a.txt").write_text("same", encoding="utf-8")
            (scan_root / "a copy.txt").write_text("same", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)

            with self.assertRaises(ValueError):
                preview_metadata(Path(result.summary.review_folder), outside)

    def test_preview_uses_vault_copy_after_duplicate_is_moved(self) -> None:
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
            vault_path = Path(move_outcome.moved[0]["vault_path"])

            resolved = resolve_preview_path(review_folder, duplicate_path)

            self.assertEqual(resolved.resolve(strict=False), vault_path.resolve(strict=False))
            self.assertFalse(duplicate_path.exists())
            self.assertTrue(vault_path.exists())


if __name__ == "__main__":
    unittest.main()
