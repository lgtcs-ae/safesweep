"""Dataclasses used by the SafeSweep backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FileRecord:
    """Metadata captured for one scanned file."""

    path: str
    name: str
    normalized_name: str
    extension: str
    size_bytes: int
    created_at: str
    modified_at: str
    accessed_at: str
    inode: Optional[int]
    is_symlink: bool
    sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class DuplicateGroup:
    """A duplicate candidate group discovered during matching."""

    group_id: str
    classification: str
    confidence: int
    reason: str
    recommended_action: str
    actual: FileRecord
    duplicates: List[FileRecord]
    candidates: List[FileRecord]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "group_id": self.group_id,
            "classification": self.classification,
            "confidence": self.confidence,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "actual": self.actual.to_dict(),
            "duplicates": [record.to_dict() for record in self.duplicates],
            "candidates": [record.to_dict() for record in self.candidates],
            "duplicate_bytes": sum(record.size_bytes for record in self.duplicates),
        }


@dataclass(frozen=True)
class CleanupCandidate:
    """A non-duplicate cleanup candidate discovered during scanning."""

    candidate_id: str
    classification: str
    confidence: int
    reason: str
    recommended_action: str
    record: FileRecord

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "candidate_id": self.candidate_id,
            "classification": self.classification,
            "confidence": self.confidence,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "record": self.record.to_dict(),
            "candidate_bytes": self.record.size_bytes,
        }


@dataclass(frozen=True)
class ScanError:
    """A scanner error or unreadable filesystem item."""

    path: str
    kind: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class IgnoredPath:
    """A filesystem path skipped by a safety or noise rule."""

    path: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class ScanSummary:
    """High-level scan outcome returned to the UI."""

    scan_id: str
    started_at: str
    completed_at: str
    scan_folders: List[str]
    review_folder: str
    include_hidden: bool
    total_files: int
    total_bytes: int
    skipped_items: int
    error_count: int
    files_by_extension: Dict[str, int] = field(default_factory=dict)
    ignored_samples: List[Dict[str, str]] = field(default_factory=list)
    error_samples: List[Dict[str, str]] = field(default_factory=list)
    report_paths: Dict[str, str] = field(default_factory=dict)
    confirmed_duplicate_groups: int = 0
    likely_duplicate_groups: int = 0
    possible_duplicate_groups: int = 0
    name_collision_groups: int = 0
    duplicate_group_count: int = 0
    cleanup_candidate_count: int = 0
    office_temp_lock_count: int = 0
    cleanup_candidate_bytes: int = 0
    hashed_file_count: int = 0
    estimated_vault_bytes: int = 0
    phase: str = "full_local_review_flow"

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class ScanResult:
    """Complete scan result used internally and by CLI commands."""

    summary: ScanSummary
    records: List[FileRecord]
    groups: List[DuplicateGroup]
    cleanup_candidates: List[CleanupCandidate]
    ignored: List[IgnoredPath]
    errors: List[ScanError]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "summary": self.summary.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "groups": [group.to_dict() for group in self.groups],
            "cleanup_candidates": [candidate.to_dict() for candidate in self.cleanup_candidates],
            "ignored": [item.to_dict() for item in self.ignored],
            "errors": [error.to_dict() for error in self.errors],
        }
