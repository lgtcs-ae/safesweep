from __future__ import annotations

import unittest
from pathlib import Path

from src import config
from src.scanner import (
    is_office_temp_lock_file,
    should_ignore_directory,
    should_ignore_file,
    should_scan_root,
)


class IgnoreRulesTest(unittest.TestCase):
    def test_protected_roots_are_not_scan_roots(self) -> None:
        allowed, reason = should_scan_root(Path("/System"))

        self.assertFalse(allowed)
        self.assertIn("protected", reason)

    def test_user_library_is_not_a_scan_root(self) -> None:
        allowed, reason = should_scan_root(config.HOME / "Library")

        self.assertFalse(allowed)
        self.assertIn("protected", reason)

    def test_noisy_directories_are_ignored(self) -> None:
        self.assertTrue(should_ignore_directory(Path("/tmp/project/node_modules")))
        self.assertTrue(should_ignore_directory(Path("/tmp/project/.git")))
        self.assertTrue(should_ignore_directory(Path("/tmp/project/.venv")))
        self.assertTrue(should_ignore_directory(Path("/tmp/project/__pycache__")))

    def test_hidden_directories_are_skipped_by_default(self) -> None:
        self.assertTrue(should_ignore_directory(Path("/tmp/project/.hidden")))
        self.assertFalse(should_ignore_directory(Path("/tmp/project/.hidden"), include_hidden=True))

    def test_macos_packages_are_ignored(self) -> None:
        self.assertTrue(should_ignore_directory(Path("/tmp/Photos Library.photoslibrary")))
        self.assertTrue(should_ignore_directory(Path("/tmp/Example.app")))

    def test_ds_store_files_are_ignored(self) -> None:
        self.assertTrue(should_ignore_file(Path("/tmp/.DS_Store")))
        self.assertTrue(should_ignore_file(Path("/tmp/.localized")))
        self.assertFalse(should_ignore_file(Path("/tmp/notes.txt")))

    def test_office_temp_lock_files_are_cleanup_candidates_not_ignored(self) -> None:
        self.assertFalse(should_ignore_file(Path("/tmp/~$Q1ImpactReportTemplate.pptx")))
        self.assertTrue(is_office_temp_lock_file(Path("/tmp/~$Q1ImpactReportTemplate.pptx")))
        self.assertTrue(is_office_temp_lock_file(Path("/tmp/~$Budget.xlsx")))
        self.assertTrue(is_office_temp_lock_file(Path("/tmp/~$Resume.docx")))
        self.assertFalse(is_office_temp_lock_file(Path("/tmp/Q1ImpactReportTemplate.pptx")))
        self.assertFalse(is_office_temp_lock_file(Path("/tmp/~$not-office.txt")))


if __name__ == "__main__":
    unittest.main()
