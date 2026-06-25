"""macOS permission helper actions."""

from __future__ import annotations

import platform
import subprocess
from typing import Any, Dict


PRIVACY_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"


def open_privacy_settings() -> Dict[str, Any]:
    """Open macOS Privacy settings so the user can grant folder access."""
    if platform.system() != "Darwin":
        return {
            "opened": False,
            "message": "Privacy settings shortcut is only available on macOS.",
        }

    try:
        subprocess.run(["open", PRIVACY_SETTINGS_URL], check=False)
    except OSError as exc:
        return {
            "opened": False,
            "message": f"Could not open macOS Privacy settings: {exc}",
        }

    return {
        "opened": True,
        "message": "Opened macOS Privacy settings.",
    }
