from __future__ import annotations

import unittest

from src.models import FileRecord
from src.ranker import choose_actual


def _record(path: str, created_at: str, modified_at: str, size: int = 10) -> FileRecord:
    return FileRecord(
        path=path,
        name=path.rsplit("/", 1)[-1],
        normalized_name="invoice",
        extension="pdf",
        size_bytes=size,
        created_at=created_at,
        modified_at=modified_at,
        accessed_at=modified_at,
        inode=None,
        is_symlink=False,
    )


class RankerTest(unittest.TestCase):
    def test_newest_creation_time_wins_when_names_are_equally_clean(self) -> None:
        older = _record(
            "/Users/example/Desktop/Invoice.pdf",
            "2026-01-01T10:00:00+00:00",
            "2026-01-01T10:00:00+00:00",
        )
        newer = _record(
            "/Users/example/Downloads/Invoice.pdf",
            "2026-02-01T10:00:00+00:00",
            "2026-02-01T10:00:00+00:00",
        )

        self.assertEqual(choose_actual([older, newer]).path, newer.path)

    def test_folder_preference_breaks_timestamp_tie(self) -> None:
        desktop = _record(
            "/Users/example/Desktop/Invoice.pdf",
            "2026-01-01T10:00:00+00:00",
            "2026-01-01T10:00:00+00:00",
        )
        music = _record(
            "/Users/example/Music/Invoice.pdf",
            "2026-01-01T10:00:00+00:00",
            "2026-01-01T10:00:00+00:00",
        )

        self.assertEqual(choose_actual([music, desktop]).path, desktop.path)

    def test_clean_name_wins_over_newer_copy_marker(self) -> None:
        original = _record(
            "/Users/example/Downloads/Fa.png",
            "2026-01-01T10:00:00+00:00",
            "2026-01-01T10:00:00+00:00",
        )
        copy = _record(
            "/Users/example/Downloads/fa-copy.png",
            "2026-02-01T10:00:00+00:00",
            "2026-02-01T10:00:00+00:00",
        )

        self.assertEqual(choose_actual([copy, original]).path, original.path)


if __name__ == "__main__":
    unittest.main()
