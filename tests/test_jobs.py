from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from src.jobs import ScanJobManager


class JobsTest(unittest.TestCase):
    def test_background_scan_job_completes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            scan_root = base / "scan"
            output_root = base / "out"
            scan_root.mkdir()
            output_root.mkdir()
            (scan_root / "a.txt").write_text("same", encoding="utf-8")
            (scan_root / "a copy.txt").write_text("same", encoding="utf-8")

            completed = []
            manager = ScanJobManager(on_completed=completed.append)
            job = manager.start_scan(
                folders=[scan_root],
                excludes=[],
                output_root=output_root,
            )

            status = {}
            for _ in range(50):
                status = manager.status(job.job_id) or {}
                if status.get("status") == "completed":
                    break
                time.sleep(0.05)

            result = manager.result(job.job_id)

            self.assertEqual(status.get("status"), "completed")
            self.assertEqual(status.get("files_scanned"), 2)
            self.assertEqual(status.get("files_hashed"), 2)
            self.assertEqual(status.get("groups_found"), 1)
            self.assertEqual(len(completed), 1)
            self.assertIsNotNone(result)
            self.assertIsNotNone(result["scan"])


if __name__ == "__main__":
    unittest.main()
