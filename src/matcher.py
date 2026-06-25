"""Duplicate candidate matching for SafeSweep."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from src.hasher import hash_same_size_candidates
from src.models import DuplicateGroup, FileRecord, ScanError
from src.normalizer import name_similarity
from src.ranker import choose_actual, order_duplicates


CONFIRMED = "confirmed_duplicate"
VERY_LIKELY = "very_likely_duplicate"
POSSIBLE = "possible_duplicate"
NAME_COLLISION = "name_collision"
ProgressCallback = Optional[Callable[[str, Dict[str, Any]], None]]


@dataclass(frozen=True)
class MatchResult:
    """Duplicate matching output."""

    records: List[FileRecord]
    groups: List[DuplicateGroup]
    errors: List[ScanError]
    hashed_file_count: int


def detect_duplicate_groups(
    records: List[FileRecord],
    progress_callback: ProgressCallback = None,
) -> MatchResult:
    """Detect duplicate candidate groups without moving or modifying files."""
    hash_result = hash_same_size_candidates(records, progress_callback=progress_callback)
    hashed_records = hash_result.records
    groups: List[DuplicateGroup] = []
    used_paths: Set[str] = set()
    next_group_number = 1

    confirmed, next_group_number = _confirmed_groups(
        hashed_records,
        used_paths,
        next_group_number,
    )
    groups.extend(confirmed)

    likely, next_group_number = _similar_groups(
        records=[record for record in hashed_records if record.path not in used_paths],
        used_paths=used_paths,
        next_group_number=next_group_number,
        classification=VERY_LIKELY,
        bucket_key=lambda record: (record.size_bytes, record.extension),
        predicate=lambda left, right: (
            left.size_bytes == right.size_bytes
            and left.extension == right.extension
            and _hashes_compatible(left, right)
            and name_similarity(left.normalized_name, right.normalized_name) >= 90
        ),
    )
    groups.extend(likely)

    groups = sorted(groups, key=lambda group: (-group.confidence, group.group_id))
    groups = [_renumber_group(group, index + 1) for index, group in enumerate(groups)]
    if progress_callback:
        progress_callback("groups_found", {"groups_found": len(groups)})
    return MatchResult(
        records=hashed_records,
        groups=groups,
        errors=hash_result.errors,
        hashed_file_count=hash_result.hashed_file_count,
    )


def count_by_classification(groups: Sequence[DuplicateGroup]) -> Dict[str, int]:
    """Return group counts by classification."""
    counts: Dict[str, int] = {
        CONFIRMED: 0,
        VERY_LIKELY: 0,
        POSSIBLE: 0,
        NAME_COLLISION: 0,
    }
    for group in groups:
        counts[group.classification] = counts.get(group.classification, 0) + 1
    return counts


def estimated_vault_bytes(groups: Sequence[DuplicateGroup]) -> int:
    """Estimate bytes represented by movable duplicate candidates."""
    return sum(
        record.size_bytes
        for group in groups
        if group.classification in {CONFIRMED, VERY_LIKELY}
        for record in group.duplicates
    )


def _hashes_compatible(left: FileRecord, right: FileRecord) -> bool:
    """Return False when available hashes prove two same-size files differ."""
    if left.sha256 and right.sha256:
        return left.sha256 == right.sha256
    return True


def _confirmed_groups(
    records: List[FileRecord],
    used_paths: Set[str],
    next_group_number: int,
) -> Tuple[List[DuplicateGroup], int]:
    """Create confirmed groups from same-size same-hash records."""
    by_size_hash: Dict[Tuple[int, str], List[FileRecord]] = {}
    for record in records:
        if record.sha256:
            by_size_hash.setdefault((record.size_bytes, record.sha256), []).append(record)

    groups: List[DuplicateGroup] = []
    for candidates in by_size_hash.values():
        available = [record for record in candidates if record.path not in used_paths]
        if len(available) < 2:
            continue
        group = _make_group(
            group_number=next_group_number,
            classification=CONFIRMED,
            confidence=100,
            reason="Same SHA-256 hash and same file size.",
            recommended_action="Review, then approve duplicate files for SafeSweep Vault if desired.",
            candidates=available,
        )
        next_group_number += 1
        groups.append(group)
        used_paths.update(record.path for record in available)
    return groups, next_group_number


def _similar_groups(
    records: List[FileRecord],
    used_paths: Set[str],
    next_group_number: int,
    classification: str,
    bucket_key: Callable[[FileRecord], object],
    predicate: Callable[[FileRecord, FileRecord], bool],
) -> Tuple[List[DuplicateGroup], int]:
    """Create groups from connected components of similar records."""
    buckets: Dict[object, List[FileRecord]] = {}
    for record in records:
        buckets.setdefault(bucket_key(record), []).append(record)

    groups: List[DuplicateGroup] = []
    for bucket in buckets.values():
        candidates = [record for record in bucket if record.path not in used_paths]
        if len(candidates) < 2:
            continue
        for component in _connected_components(candidates, predicate):
            available = [record for record in component if record.path not in used_paths]
            if len(available) < 2:
                continue
            confidence, reason, action = _classification_details(classification, available)
            group = _make_group(
                group_number=next_group_number,
                classification=classification,
                confidence=confidence,
                reason=reason,
                recommended_action=action,
                candidates=available,
            )
            next_group_number += 1
            groups.append(group)
            used_paths.update(record.path for record in available)
    return groups, next_group_number


def _name_collision_groups(
    records: List[FileRecord],
    used_paths: Set[str],
    next_group_number: int,
) -> Tuple[List[DuplicateGroup], int]:
    """Report exact filename collisions with differing content or size."""
    buckets: Dict[Tuple[str, str], List[FileRecord]] = {}
    for record in records:
        buckets.setdefault((record.name.lower(), record.extension), []).append(record)

    groups: List[DuplicateGroup] = []
    for candidates in buckets.values():
        available = [record for record in candidates if record.path not in used_paths]
        if len(available) < 2:
            continue
        sizes = {record.size_bytes for record in available}
        hashes = {record.sha256 for record in available if record.sha256}
        if len(sizes) < 2 and len(hashes) < 2:
            continue
        group = _make_group(
            group_number=next_group_number,
            classification=NAME_COLLISION,
            confidence=50,
            reason="Same filename appears in multiple locations, but size or content differs.",
            recommended_action="Report only. Review manually; do not auto-approve.",
            candidates=available,
        )
        next_group_number += 1
        groups.append(group)
        used_paths.update(record.path for record in available)
    return groups, next_group_number


def _connected_components(
    records: List[FileRecord],
    predicate: Callable[[FileRecord, FileRecord], bool],
) -> List[List[FileRecord]]:
    """Return connected components where predicate connects similar records."""
    adjacency: Dict[str, Set[str]] = {record.path: set() for record in records}
    by_path = {record.path: record for record in records}

    for left, right in combinations(records, 2):
        if predicate(left, right):
            adjacency[left.path].add(right.path)
            adjacency[right.path].add(left.path)

    components: List[List[FileRecord]] = []
    visited: Set[str] = set()
    for record in records:
        if record.path in visited or not adjacency[record.path]:
            continue
        stack = [record.path]
        paths: List[str] = []
        visited.add(record.path)
        while stack:
            current = stack.pop()
            paths.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append([by_path[path] for path in paths])
    return components


def _classification_details(
    classification: str,
    records: List[FileRecord],
) -> Tuple[int, str, str]:
    """Return confidence, reason, and action for a non-confirmed group."""
    similarity = _max_similarity(records)
    if classification == VERY_LIKELY:
        confidence = min(99, max(90, similarity))
        return (
            confidence,
            f"Same file size and extension with normalized name similarity up to {similarity}%; hash was unavailable for at least one file.",
            "Review carefully, then approve for SafeSweep Vault only if these are redundant.",
        )
    raise ValueError(f"Unsupported similarity classification: {classification}")


def _max_similarity(records: List[FileRecord]) -> int:
    """Return the strongest normalized-name similarity inside a group."""
    if len(records) < 2:
        return 0
    return max(
        name_similarity(left.normalized_name, right.normalized_name)
        for left, right in combinations(records, 2)
    )


def _make_group(
    group_number: int,
    classification: str,
    confidence: int,
    reason: str,
    recommended_action: str,
    candidates: List[FileRecord],
) -> DuplicateGroup:
    """Create a DuplicateGroup with Actual and duplicate records selected."""
    actual = choose_actual(candidates)
    duplicates = order_duplicates(candidates, actual)
    return DuplicateGroup(
        group_id=f"group_{group_number:03d}",
        classification=classification,
        confidence=confidence,
        reason=reason,
        recommended_action=recommended_action,
        actual=actual,
        duplicates=duplicates,
        candidates=sorted(candidates, key=lambda record: record.path),
    )


def _renumber_group(group: DuplicateGroup, group_number: int) -> DuplicateGroup:
    """Assign stable group IDs after final sorting."""
    return DuplicateGroup(
        group_id=f"group_{group_number:03d}",
        classification=group.classification,
        confidence=group.confidence,
        reason=group.reason,
        recommended_action=group.recommended_action,
        actual=group.actual,
        duplicates=group.duplicates,
        candidates=group.candidates,
    )
