"""Structured file logging setup for SafeSweep review folders."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanLoggers:
    """Named loggers for one scan."""

    scan: logging.Logger
    errors: logging.Logger
    actions: logging.Logger


def _build_file_logger(name: str, path: Path) -> logging.Logger:
    """Create a file logger with isolated handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s level=%(levelname)s event=%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(handler)
    return logger


def configure_scan_loggers(scan_id: str, logs_dir: Path) -> ScanLoggers:
    """Create scan, errors, and actions loggers for a SafeSweep scan."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    return ScanLoggers(
        scan=_build_file_logger(f"safesweep.scan.{scan_id}", logs_dir / "scan_log.txt"),
        errors=_build_file_logger(f"safesweep.errors.{scan_id}", logs_dir / "errors_log.txt"),
        actions=_build_file_logger(f"safesweep.actions.{scan_id}", logs_dir / "actions_log.txt"),
    )
