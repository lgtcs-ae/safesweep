"""Localhost-only SafeSweep web backend."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from src import config
from src.approvals import (
    approval_summary,
    approve_confirmed,
    approve_group,
    approve_groups,
    ignore_group,
    ignore_groups,
)
from src.finder import reveal_in_finder
from src.jobs import ScanJobManager
from src.mover import move_approved_duplicates
from src.models import ScanResult
from src.permissions import open_privacy_settings
from src.preview import preview_kind, preview_metadata, resolve_preview_path
from src.purge import purge_moved_vault_files
from src.restore import restore_moved_files
from src.scanner import scan_folders
from src.utils import human_bytes, top_extensions


class ScanStore:
    """In-memory scan summary store for the running local process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scans: Dict[str, Dict[str, Any]] = {}
        self._latest_scan_id: Optional[str] = None

    def add(self, result: ScanResult) -> None:
        """Store a complete scan result."""
        with self._lock:
            data = result.to_dict()
            self._scans[result.summary.scan_id] = data
            self._latest_scan_id = result.summary.scan_id

    def load_existing(self, root: Path, limit: int = 25) -> None:
        """Load recent SafeSweep review reports from disk into the running session."""
        candidates = sorted(
            root.glob(f"{config.OUTPUT_PREFIX}_*/01_Reports/safesweep_report.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:limit]
        loaded: list[Dict[str, Any]] = []
        for report_path in candidates:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                summary = report.get("summary")
                if not isinstance(summary, dict) or not summary.get("scan_id"):
                    continue
                loaded.append(
                    {
                        "summary": summary,
                        "groups": report.get("groups", []),
                        "cleanup_candidates": report.get("cleanup_candidates", []),
                        "records": [],
                        "ignored": [],
                        "errors": [],
                    }
                )
            except (OSError, ValueError, json.JSONDecodeError):
                continue

        with self._lock:
            for result in loaded:
                scan_id = result["summary"]["scan_id"]
                self._scans[scan_id] = result
            if loaded:
                self._latest_scan_id = loaded[0]["summary"]["scan_id"]

    def list(self) -> list[Dict[str, Any]]:
        """Return scan summaries newest first."""
        with self._lock:
            summaries = [item["summary"] for item in self._scans.values()]
            return sorted(
                summaries,
                key=lambda item: item.get("completed_at", ""),
                reverse=True,
            )

    def get_summary(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Return one scan summary."""
        with self._lock:
            result = self._scans.get(scan_id)
            if not result:
                return None
            return result["summary"]

    def get_groups(self, scan_id: str) -> Optional[list[Dict[str, Any]]]:
        """Return duplicate groups for one scan."""
        with self._lock:
            result = self._scans.get(scan_id)
            if not result:
                return None
            return result["groups"]

    def get_cleanup_candidates(self, scan_id: str) -> Optional[list[Dict[str, Any]]]:
        """Return cleanup candidates for one scan."""
        with self._lock:
            result = self._scans.get(scan_id)
            if not result:
                return None
            return result.get("cleanup_candidates", [])

    def get_review_folder(self, scan_id: str) -> Optional[Path]:
        """Return the review folder for one scan."""
        summary = self.get_summary(scan_id)
        if not summary:
            return None
        return Path(summary["review_folder"])

    def latest(self) -> Optional[Dict[str, Any]]:
        """Return the latest scan summary."""
        with self._lock:
            if not self._latest_scan_id:
                return None
            result = self._scans.get(self._latest_scan_id)
            if not result:
                return None
            return result["summary"]


SCAN_STORE = ScanStore()
SCAN_STORE.load_existing(Path.home())
SCAN_JOBS = ScanJobManager(on_completed=SCAN_STORE.add)


class TemplateRenderer:
    """Render Jinja2 templates when available, with a safe stdlib fallback."""

    def __init__(self, template_dir: Path) -> None:
        self.template_dir = template_dir
        self._jinja_env = None
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape

            self._jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
        except ImportError:
            self._jinja_env = None

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a page template inside base.html."""
        full_context = {
            "app_name": config.APP_NAME,
            "tagline": config.TAGLINE,
            **context,
        }
        if self._jinja_env is not None:
            return self._jinja_env.get_template(template_name).render(**full_context)

        template = (self.template_dir / template_name).read_text(encoding="utf-8")
        return self._simple_render(template, full_context)

    @staticmethod
    def _simple_render(template: str, context: Dict[str, Any]) -> str:
        """Very small placeholder renderer for local development."""
        rendered = template
        for key, value in context.items():
            text = str(value)
            rendered = rendered.replace("{{ " + key + " }}", text)
            rendered = rendered.replace("{{ " + key + " | safe }}", text)
            rendered = rendered.replace("{{ " + key + "|safe }}", text)
        return rendered


RENDERER = TemplateRenderer(config.TEMPLATE_DIR)


class SafeSweepRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for the localhost-only SafeSweep UI and API."""

    server_version = "SafeSweepLocal/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        """Handle GET requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path in {"/", "/home", "/dashboard"}:
            self._send_html(
                RENDERER.render(
                    "dashboard.html",
                    {
                        "title": "SafeSweep Home",
                        "page": "dashboard",
                        "default_folders_json": json.dumps(_default_folders()),
                    },
                )
            )
            return

        if path == "/scan":
            self._send_html(
                RENDERER.render(
                    "scan.html",
                    {
                        "title": "SafeSweep Scan",
                        "page": "scan",
                        "default_folders_json": json.dumps(_default_folders()),
                    },
                )
            )
            return

        if path == "/results":
            self._send_html(
                RENDERER.render(
                    "results.html",
                    {
                        "title": "SafeSweep Results",
                        "page": "results",
                        "default_folders_json": json.dumps(_default_folders()),
                    },
                )
            )
            return

        if path == "/api/dashboard":
            self._send_json(_dashboard_payload())
            return

        if path == "/api/scans":
            self._send_json({"scans": SCAN_STORE.list()})
            return

        if path.startswith("/api/scan/status/"):
            job_id = path.rsplit("/", 1)[-1]
            status = SCAN_JOBS.status(job_id)
            if status is None:
                self._send_json({"error": "Scan job not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"job": status})
            return

        if path.startswith("/api/scan/result/"):
            job_id = path.rsplit("/", 1)[-1]
            result = SCAN_JOBS.result(job_id)
            if result is None:
                self._send_json({"error": "Scan job not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(result)
            return

        if path.startswith("/api/scan/") and path.endswith("/groups"):
            parts = path.strip("/").split("/")
            scan_id = parts[2] if len(parts) >= 4 else ""
            groups = SCAN_STORE.get_groups(scan_id)
            if groups is None:
                self._send_json({"error": "Scan not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"groups": groups})
            return

        if path.startswith("/api/scan/") and path.endswith("/cleanup-candidates"):
            parts = path.strip("/").split("/")
            scan_id = parts[2] if len(parts) >= 4 else ""
            candidates = SCAN_STORE.get_cleanup_candidates(scan_id)
            if candidates is None:
                self._send_json({"error": "Scan not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"cleanup_candidates": candidates})
            return

        if path.startswith("/api/scan/") and path.endswith("/approvals"):
            parts = path.strip("/").split("/")
            scan_id = parts[2] if len(parts) >= 4 else ""
            review_folder = SCAN_STORE.get_review_folder(scan_id)
            if review_folder is None:
                self._send_json({"error": "Scan not found."}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                self._send_json(approval_summary(review_folder))
            except Exception as exc:
                self._send_json(
                    {"error": "approval_state_failed", "message": str(exc)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if path == "/api/file-preview":
            self._handle_file_preview(parsed_url.query)
            return

        if path == "/api/file-preview/content":
            self._serve_file_preview_content(parsed_url.query)
            return

        if path.startswith("/api/scan/"):
            scan_id = path.rsplit("/", 1)[-1]
            summary = SCAN_STORE.get_summary(scan_id)
            if not summary:
                self._send_json({"error": "Scan not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"scan": summary})
            return

        if path.startswith("/static/"):
            self._serve_static(path)
            return

        self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        """Handle POST requests."""
        path = urlparse(self.path).path
        if path == "/api/select-folder":
            self._handle_select_folder()
            return

        if path == "/api/scan/start":
            self._handle_scan_start()
            return

        if path == "/api/scan":
            self._handle_scan()
            return

        if path == "/api/reveal-in-finder":
            self._handle_reveal_in_finder()
            return

        if path == "/api/open-privacy-settings":
            try:
                self._send_json(open_privacy_settings())
            except Exception as exc:
                self._send_json(
                    {"error": "open_privacy_settings_failed", "message": str(exc)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if path.startswith("/api/scan/"):
            self._handle_scan_action(path)
            return

        self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the terminal output clean while preserving server behavior."""
        return

    def _handle_scan(self) -> None:
        """Run a synchronous review scan from a JSON API request."""
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        folders = [Path(item).expanduser() for item in payload.get("folders", []) if str(item).strip()]
        excludes = [Path(item).expanduser() for item in payload.get("excludes", []) if str(item).strip()]
        include_hidden = bool(payload.get("include_hidden", False))

        try:
            result = scan_folders(
                folders=folders,
                excludes=excludes,
                include_hidden=include_hidden,
            )
        except Exception as exc:  # API guardrail: report, do not crash server.
            self._send_json(
                {"error": "scan_failed", "message": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        SCAN_STORE.add(result)
        self._send_json({"scan": result.summary.to_dict()})

    def _handle_select_folder(self) -> None:
        """Show a native folder picker and return the selected folder path."""
        try:
            folder = self._select_folder_dialog()
            self._send_json({"folder": folder})
        except FileNotFoundError as exc:
            self._send_json({"error": "selection_cancelled", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": "select_folder_failed", "message": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_scan_start(self) -> None:
        """Start a background scan and return immediately."""
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        folders = [Path(item).expanduser() for item in payload.get("folders", []) if str(item).strip()]
        excludes = [Path(item).expanduser() for item in payload.get("excludes", []) if str(item).strip()]
        include_hidden = bool(payload.get("include_hidden", False))
        output_root_value = str(payload.get("output_root", "")).strip()
        output_root = Path(output_root_value).expanduser() if output_root_value else None

        job = SCAN_JOBS.start_scan(
            folders=folders,
            excludes=excludes,
            include_hidden=include_hidden,
            output_root=output_root,
        )
        self._send_json({"job": job.status_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_scan_action(self, path: str) -> None:
        """Handle approval, movement, and restore actions for one scan."""
        parts = path.strip("/").split("/")
        if len(parts) < 4:
            self._send_json({"error": "Invalid scan action."}, status=HTTPStatus.BAD_REQUEST)
            return

        scan_id = parts[2]
        action = parts[3]
        review_folder = SCAN_STORE.get_review_folder(scan_id)
        if review_folder is None:
            self._send_json({"error": "Scan not found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            if action == "approve-group":
                group_id = str(payload.get("group_id", "")).strip()
                if not group_id:
                    raise ValueError("group_id is required.")
                self._send_json(approve_group(review_folder, group_id))
                return

            if action == "ignore-group":
                group_id = str(payload.get("group_id", "")).strip()
                if not group_id:
                    raise ValueError("group_id is required.")
                self._send_json(ignore_group(review_folder, group_id))
                return

            if action == "approve-groups":
                group_ids = _group_ids_from_payload(payload)
                self._send_json(approve_groups(review_folder, group_ids))
                return

            if action == "ignore-groups":
                group_ids = _group_ids_from_payload(payload)
                self._send_json(ignore_groups(review_folder, group_ids))
                return

            if action == "approve-confirmed":
                self._send_json(approve_confirmed(review_folder))
                return

            if action == "move-approved":
                outcome = move_approved_duplicates(review_folder)
                self._send_json({"move": outcome.to_dict(), **approval_summary(review_folder)})
                return

            if action == "restore":
                outcome = restore_moved_files(review_folder)
                self._send_json({"restore": outcome.to_dict(), **approval_summary(review_folder)})
                return

            if action == "purge-vault":
                confirmation_phrase = str(payload.get("confirmation_phrase", ""))
                outcome = purge_moved_vault_files(review_folder, confirmation_phrase)
                self._send_json({"purge": outcome.to_dict(), **approval_summary(review_folder)})
                return

            self._send_json({"error": "Unknown scan action."}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"error": "invalid_request", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json(
                {"error": "action_failed", "message": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _select_folder_dialog(self) -> str:
        """Open a native macOS Finder folder picker and return the selected path."""
        import subprocess
        
        applescript = 'POSIX path of (choose folder with prompt "Select a folder to scan")'
        
        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                if "User canceled" in stderr or "User cancelled" in stderr:
                    raise FileNotFoundError("No folder was selected.")
                raise RuntimeError(stderr or "Folder selection failed.")
            
            selected = result.stdout.strip()
            if not selected:
                raise FileNotFoundError("No folder was selected.")
            
            return selected
        except subprocess.TimeoutExpired:
            raise RuntimeError("Folder selection timed out.")
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Folder selection failed: {exc}") from exc

    def _handle_reveal_in_finder(self) -> None:
        """Reveal a scan-owned file in Finder."""
        try:
            payload = self._read_json()
            scan_id = str(payload.get("scan_id", "")).strip()
            requested_path = str(payload.get("path", "")).strip()
            if not scan_id or not requested_path:
                raise ValueError("scan_id and path are required.")
            review_folder = SCAN_STORE.get_review_folder(scan_id)
            if review_folder is None:
                self._send_json({"error": "Scan not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(reveal_in_finder(review_folder, Path(requested_path)))
        except ValueError as exc:
            self._send_json({"error": "invalid_request", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._send_json({"error": "not_found", "message": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json(
                {"error": "reveal_failed", "message": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _handle_file_preview(self, query: str) -> None:
        """Return preview metadata for a scan-owned file."""
        try:
            review_folder, requested_path = self._preview_request(query)
            self._send_json(preview_metadata(review_folder, requested_path))
        except ValueError as exc:
            self._send_json({"error": "invalid_request", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as exc:
            self._send_json({"error": "not_found", "message": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json(
                {"error": "preview_failed", "message": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _serve_file_preview_content(self, query: str) -> None:
        """Serve inline preview bytes for a scan-owned file."""
        try:
            review_folder, requested_path = self._preview_request(query)
            preview_path = resolve_preview_path(review_folder, requested_path)
        except ValueError as exc:
            self._send_json({"error": "invalid_request", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except FileNotFoundError as exc:
            self._send_json({"error": "not_found", "message": str(exc)}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(str(preview_path))[0] or "application/octet-stream"
        if preview_kind(preview_path, content_type) not in {"image", "pdf", "video", "audio"}:
            self._send_json({"error": "unsupported_preview", "message": "Inline preview is not available for this file type."}, status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        safe_name = preview_path.name.replace('"', "'")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
        self.send_header("Content-Length", str(preview_path.stat().st_size))
        self.end_headers()
        with preview_path.open("rb") as file_obj:
            while True:
                chunk = file_obj.read(1024 * 256)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _preview_request(self, query: str) -> tuple[Path, Path]:
        """Parse and validate a file preview request."""
        values = parse_qs(query)
        scan_id = (values.get("scan_id") or [""])[0].strip()
        requested_path = (values.get("path") or [""])[0].strip()
        if not scan_id or not requested_path:
            raise ValueError("scan_id and path are required.")
        review_folder = SCAN_STORE.get_review_folder(scan_id)
        if review_folder is None:
            raise FileNotFoundError("Scan not found.")
        return review_folder, Path(requested_path)

    def _read_json(self) -> Dict[str, Any]:
        """Read and parse a JSON request body."""
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON request body.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON request body must be an object.")
        return parsed

    def _serve_static(self, request_path: str) -> None:
        """Serve local static files without allowing path traversal."""
        relative = request_path.replace("/static/", "", 1)
        candidate = (config.STATIC_DIR / relative).resolve(strict=False)
        static_root = config.STATIC_DIR.resolve(strict=False)
        try:
            candidate.relative_to(static_root)
        except ValueError:
            self._send_json({"error": "Invalid static path."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not candidate.exists() or not candidate.is_file():
            self._send_json({"error": "Static file not found."}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(candidate.stat().st_size))
        self.end_headers()
        with candidate.open("rb") as file_obj:
            self.wfile.write(file_obj.read())

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        """Send an HTML response."""
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        """Send a JSON response."""
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_local_app(port: int = config.DEFAULT_PORT, open_browser: bool = True) -> None:
    """Run the SafeSweep local server bound only to 127.0.0.1."""
    server = ThreadingHTTPServer((config.LOCAL_HOST, port), SafeSweepRequestHandler)
    url = f"http://{config.LOCAL_HOST}:{server.server_port}"
    print(f"SafeSweep is running at {url}")
    print("Bound to 127.0.0.1 only. Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSafeSweep stopped.")
    finally:
        server.server_close()


def _default_folders() -> list[str]:
    """Return default folder paths for the UI."""
    return [str(path) for path in config.DEFAULT_SCAN_FOLDERS]


def _group_ids_from_payload(payload: Dict[str, Any]) -> list[str]:
    """Return validated group ids from a JSON payload."""
    raw_group_ids = payload.get("group_ids", [])
    if not isinstance(raw_group_ids, list):
        raise ValueError("group_ids must be a list.")
    group_ids = [str(group_id).strip() for group_id in raw_group_ids if str(group_id).strip()]
    if not group_ids:
        raise ValueError("At least one group_id is required.")
    return group_ids


def _dashboard_payload() -> Dict[str, Any]:
    """Build dashboard data from the latest scan."""
    latest = SCAN_STORE.latest()
    if not latest:
        return {
            "latest_scan": None,
            "totals": {
                "total_files": 0,
                "confirmed_duplicate_groups": 0,
                "likely_duplicate_groups": 0,
                "possible_duplicate_groups": 0,
                "name_collision_groups": 0,
                "duplicate_group_count": 0,
                "cleanup_candidate_count": 0,
                "office_temp_lock_count": 0,
                "cleanup_candidate_bytes": 0,
                "hashed_file_count": 0,
                "estimated_vault_bytes": 0,
                "estimated_vault_size": "0 B",
            },
            "extensions": [],
        }

    return {
        "latest_scan": latest,
        "totals": {
            "total_files": latest.get("total_files", 0),
            "confirmed_duplicate_groups": latest.get("confirmed_duplicate_groups", 0),
            "likely_duplicate_groups": latest.get("likely_duplicate_groups", 0),
            "possible_duplicate_groups": latest.get("possible_duplicate_groups", 0),
            "name_collision_groups": latest.get("name_collision_groups", 0),
            "duplicate_group_count": latest.get("duplicate_group_count", 0),
            "cleanup_candidate_count": latest.get("cleanup_candidate_count", 0),
            "office_temp_lock_count": latest.get("office_temp_lock_count", 0),
            "cleanup_candidate_bytes": latest.get("cleanup_candidate_bytes", 0),
            "hashed_file_count": latest.get("hashed_file_count", 0),
            "estimated_vault_bytes": latest.get("estimated_vault_bytes", 0),
            "estimated_vault_size": human_bytes(latest.get("estimated_vault_bytes", 0)),
        },
        "extensions": top_extensions(latest.get("files_by_extension", {})),
    }
