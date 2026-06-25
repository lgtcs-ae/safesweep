from __future__ import annotations

import unittest

from src.normalizer import name_similarity, normalize_name


class NormalizerTest(unittest.TestCase):
    def test_common_copy_markers_are_removed(self) -> None:
        examples = {
            "Resume.pdf": "resume",
            "Resume copy.pdf": "resume",
            "Resume (1).pdf": "resume",
            "Resume_final.pdf": "resume final",
            "Resume-final-copy-2.pdf": "resume final",
            "Invoice [2].pdf": "invoice",
        }

        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(normalize_name(original), expected)

    def test_meaningful_trailing_numbers_are_preserved(self) -> None:
        self.assertEqual(normalize_name("Tax 2025.pdf"), "tax 2025")

    def test_similarity_uses_normalized_names(self) -> None:
        self.assertGreaterEqual(
            name_similarity(normalize_name("Invoice.pdf"), normalize_name("Invoice copy.pdf")),
            90,
        )


if __name__ == "__main__":
    unittest.main()
