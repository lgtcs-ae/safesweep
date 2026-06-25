"""Name normalization for SafeSweep duplicate matching."""

from __future__ import annotations

import re
from pathlib import Path


_SPACES = re.compile(r"\s+")
_BRACKETED_COPY_NUMBER = re.compile(r"\s*[\(\[]\d+[\)\]]\s*$")
_TRAILING_COPY_MARKER = re.compile(r"\s+(copy|duplicate)(\s+\d+)?$")
_TRAILING_VERSION_COPY = re.compile(r"\s+version\s+copy$")


def normalize_name(name: str) -> str:
    """Normalize a file name enough to compare copy-style duplicates safely.

    Original file names are always preserved elsewhere. This normalized value is
    used only as a matching signal and never as proof of a confirmed duplicate.
    """
    text = Path(name).stem.lower()
    text = text.replace("_", " ").replace("-", " ")
    text = _BRACKETED_COPY_NUMBER.sub("", text)
    text = _SPACES.sub(" ", text).strip()

    previous = None
    while previous != text:
        previous = text
        text = _TRAILING_VERSION_COPY.sub(" version", text).strip()
        text = _TRAILING_COPY_MARKER.sub("", text).strip()
        text = _BRACKETED_COPY_NUMBER.sub("", text).strip()
        text = _SPACES.sub(" ", text).strip()

    return _SPACES.sub(" ", text).strip()


def name_similarity(left: str, right: str) -> int:
    """Return a 0-100 normalized-name similarity score."""
    try:
        from rapidfuzz import fuzz

        return int(round(fuzz.ratio(left, right)))
    except ImportError:
        from difflib import SequenceMatcher

        return int(round(SequenceMatcher(None, left, right).ratio() * 100))
