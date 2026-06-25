"""Configuration constants for SafeSweep."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import FrozenSet, Tuple


APP_NAME = "SafeSweep"
TAGLINE = "Review first. Clean safely."
LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
OUTPUT_PREFIX = "SafeSweep_Review"

PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
TEMPLATE_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

HOME = Path.home()
DEFAULT_SCAN_FOLDERS: Tuple[Path, ...] = (
    HOME / "Downloads",
    HOME / "Desktop",
)

PROTECTED_ROOTS: Tuple[Path, ...] = (
    Path("/System"),
    Path("/Library"),
    Path("/Applications"),
    HOME / "Library",
    HOME / ".Trash",
)

IGNORED_DIR_NAMES: FrozenSet[str] = frozenset(
    {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "Backups.backupdb",
    }
)

IGNORED_FILE_NAMES: FrozenSet[str] = frozenset({".DS_Store", ".localized"})

IGNORED_OFFICE_TEMP_EXTENSIONS: FrozenSet[str] = frozenset(
    {
        "doc",
        "docm",
        "docx",
        "dotm",
        "dotx",
        "ppt",
        "pptm",
        "pptx",
        "ppsx",
        "ppsm",
        "potm",
        "potx",
        "xls",
        "xlsb",
        "xlsm",
        "xlsx",
        "xltm",
        "xltx",
    }
)

IGNORED_PACKAGE_SUFFIXES: Tuple[str, ...] = (
    ".photoslibrary",
    ".app",
)

PHASE1_NOT_IMPLEMENTED_MESSAGE = (
    "This action is not available for the selected scan or file."
)

FOLDER_PREFERENCE_NAMES = (
    "Downloads",
    "Desktop",
    "Documents",
    "Pictures",
    "Movies",
    "Music",
)

CLASSIFICATION_VAULT_DIRS = {
    "confirmed_duplicate": "confirmed_duplicates",
    "very_likely_duplicate": "likely_duplicates",
}

RESTORE_MAP_RELATIVE_PATH = "05_Restore_Map/restore_map.json"
APPROVAL_STATE_RELATIVE_PATH = "approval_state.json"
