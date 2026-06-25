from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.hasher import sha256_file


class HasherTest(unittest.TestCase):
    def test_hashes_small_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "small.txt"
            path.write_bytes(b"hello")

            result = sha256_file(path, chunk_size=2)

            self.assertTrue(result.success)
            self.assertEqual(result.sha256, hashlib.sha256(b"hello").hexdigest())
            self.assertFalse(result.changed_during_hash)

    def test_hashes_large_file_in_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large.bin"
            data = (b"0123456789abcdef" * 128 * 1024) + b"tail"
            path.write_bytes(data)

            result = sha256_file(path, chunk_size=1024 * 1024)

            self.assertTrue(result.success)
            self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())

    def test_hashes_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.bin"
            path.write_bytes(b"")

            result = sha256_file(path)

            self.assertTrue(result.success)
            self.assertEqual(result.sha256, hashlib.sha256(b"").hexdigest())

    def test_missing_file_returns_failure(self) -> None:
        result = sha256_file(Path("/private/tmp/safesweep_missing_hash_test.bin"))

        self.assertFalse(result.success)
        self.assertIn("missing", result.error_message or "")

    def test_permission_error_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locked.bin"
            path.write_bytes(b"secret")

            with patch("pathlib.Path.open", side_effect=PermissionError("denied")):
                result = sha256_file(path)

            self.assertFalse(result.success)
            self.assertIn("permission denied", result.error_message or "")

    def test_file_changed_during_hash_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "changing.bin"
            path.write_bytes(b"stable")
            before = path.stat()

            class ChangedStat:
                st_size = before.st_size + 1
                st_mtime = before.st_mtime

            with patch("pathlib.Path.stat", side_effect=[before, ChangedStat()]):
                result = sha256_file(path)

            self.assertFalse(result.success)
            self.assertTrue(result.changed_during_hash)
            self.assertIsNone(result.sha256)


if __name__ == "__main__":
    unittest.main()
