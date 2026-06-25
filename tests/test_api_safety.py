from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.finder import reveal_in_finder
from src.scanner import scan_folders


class ApiSafetyTest(unittest.TestCase):
    def test_reveal_rejects_paths_outside_scan_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()
            (scan_root / "a.txt").write_text("same", encoding="utf-8")
            (scan_root / "a copy.txt").write_text("same", encoding="utf-8")

            result = scan_folders(folders=[scan_root], output_root=output_root)

            with self.assertRaises(ValueError):
                reveal_in_finder(Path(result.summary.review_folder), Path("/etc/hosts"))


if __name__ == "__main__":
    unittest.main()
