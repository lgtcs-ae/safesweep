from __future__ import annotations

import unittest
from unittest.mock import patch

from src.permissions import PRIVACY_SETTINGS_URL, open_privacy_settings


class PermissionsTest(unittest.TestCase):
    def test_open_privacy_settings_invokes_macos_settings(self) -> None:
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run") as run:
            result = open_privacy_settings()

        self.assertTrue(result["opened"])
        self.assertEqual(result["message"], "Opened macOS Privacy settings.")
        run.assert_called_once_with(["open", PRIVACY_SETTINGS_URL], check=False)

    def test_open_privacy_settings_is_noop_off_macos(self) -> None:
        with patch("platform.system", return_value="Linux"), patch("subprocess.run") as run:
            result = open_privacy_settings()

        self.assertFalse(result["opened"])
        self.assertIn("only available on macOS", result["message"])
        run.assert_not_called()

    def test_open_privacy_settings_reports_launch_failure(self) -> None:
        with patch("platform.system", return_value="Darwin"), patch(
            "subprocess.run", side_effect=OSError("blocked")
        ):
            result = open_privacy_settings()

        self.assertFalse(result["opened"])
        self.assertIn("Could not open macOS Privacy settings", result["message"])


if __name__ == "__main__":
    unittest.main()
