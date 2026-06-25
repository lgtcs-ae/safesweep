"""macOS packaged app launcher for SafeSweep."""

from __future__ import annotations

import os
import socket
import sys
import webbrowser

from src.app import run_local_app
from src import config


def _local_url(port: int) -> str:
    return f"http://{config.LOCAL_HOST}:{port}"


def _is_local_server_available(port: int) -> bool:
    try:
        with socket.create_connection((config.LOCAL_HOST, port), timeout=0.35):
            return True
    except OSError:
        return False


def main() -> int:
    """Start SafeSweep with the normal local browser UI."""
    port = int(os.environ.get("SAFESWEEP_PORT", str(config.DEFAULT_PORT)))
    open_browser = os.environ.get("SAFESWEEP_NO_BROWSER") != "1"
    if open_browser and _is_local_server_available(port):
        webbrowser.open(f"{_local_url(port)}/scan")
        return 0
    run_local_app(port=port, open_browser=open_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
