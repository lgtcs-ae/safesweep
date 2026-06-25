"""Local background scan jobs for SafeSweep."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Iterable, Optional

from src.models import ScanResult
from src.scanner import scan_folders
from src.utils import isoformat, now_local


@dataclass
class ScanJob:
    """Progress and result state for one background scan."""

    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    files_seen: int = 0
    files_scanned: int = 0
    files_hashed: int = 0
    groups_found: int = 0
    current_path: Optional[str] = None
    error_message: Optional[str] = None
    output_scan_folder: Optional[str] = None
    scan_id: Optional[str] = None
    result: Optional[ScanResult] = None

    def status_dict(self) -> Dict[str, Any]:
        """Return API-safe status data without the full scan result."""
        payload = asdict(self)
        payload.pop("result", None)
        return payload


class ScanJobManager:
    """Simple local-only background worker for scan jobs."""

    def __init__(
        self,
        on_completed: Callable[[ScanResult], None],
        max_workers: int = 1,
    ) -> None:
        self._on_completed = on_completed
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="safesweep-scan")
        self._lock = Lock()
        self._jobs: Dict[str, ScanJob] = {}

    def start_scan(
        self,
        folders: Iterable[Path],
        excludes: Iterable[Path],
        include_hidden: bool = False,
        output_root: Optional[Path] = None,
    ) -> ScanJob:
        """Queue a background scan and return its job state immediately."""
        job_id = uuid.uuid4().hex
        job = ScanJob(job_id=job_id, status="queued")
        with self._lock:
            self._jobs[job_id] = job

        self._executor.submit(
            self._run_scan,
            job_id,
            list(folders),
            list(excludes),
            include_hidden,
            output_root,
        )
        return job

    def status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return status data for a job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return job.status_dict()

    def result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return final result data for a completed job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.result is None:
                return {"job": job.status_dict(), "scan": None}
            return {"job": job.status_dict(), "scan": job.result.summary.to_dict()}

    def _run_scan(
        self,
        job_id: str,
        folders: list[Path],
        excludes: list[Path],
        include_hidden: bool,
        output_root: Optional[Path],
    ) -> None:
        self._update(job_id, status="running", started_at=isoformat(now_local()))

        def progress(event: str, payload: Dict[str, Any]) -> None:
            self._apply_progress(job_id, event, payload)

        try:
            result = scan_folders(
                folders=folders,
                excludes=excludes,
                include_hidden=include_hidden,
                output_root=output_root,
                progress_callback=progress,
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                completed_at=isoformat(now_local()),
                error_message=str(exc),
            )
            return

        self._on_completed(result)
        self._update(
            job_id,
            status="completed",
            completed_at=isoformat(now_local()),
            files_scanned=result.summary.total_files,
            files_hashed=result.summary.hashed_file_count,
            groups_found=result.summary.duplicate_group_count,
            output_scan_folder=result.summary.review_folder,
            scan_id=result.summary.scan_id,
            result=result,
        )

    def _apply_progress(self, job_id: str, event: str, payload: Dict[str, Any]) -> None:
        updates: Dict[str, Any] = {}
        if "current_path" in payload:
            updates["current_path"] = _sanitize_path(str(payload["current_path"]))
        if event == "path_seen":
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    updates["files_seen"] = job.files_seen + 1
        if "files_scanned" in payload:
            updates["files_scanned"] = int(payload["files_scanned"])
        if "files_hashed" in payload:
            updates["files_hashed"] = int(payload["files_hashed"])
        if "groups_found" in payload:
            updates["groups_found"] = int(payload["groups_found"])
        if "output_scan_folder" in payload:
            updates["output_scan_folder"] = str(payload["output_scan_folder"])
        if updates:
            self._update(job_id, **updates)

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in updates.items():
                setattr(job, key, value)


def _sanitize_path(path: str, max_length: int = 180) -> str:
    """Trim long paths for UI status display."""
    if len(path) <= max_length:
        return path
    return "..." + path[-(max_length - 3):]
