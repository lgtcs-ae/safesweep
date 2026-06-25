from __future__ import annotations

import unittest

from src import config


class ConfigTest(unittest.TestCase):
    def test_default_scan_folders_skip_documents(self) -> None:
        folder_names = [path.name for path in config.DEFAULT_SCAN_FOLDERS]

        self.assertEqual(folder_names, ["Downloads", "Desktop"])
        self.assertNotIn("Documents", folder_names)


if __name__ == "__main__":
    unittest.main()
