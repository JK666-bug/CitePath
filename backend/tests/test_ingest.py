import unittest
from types import SimpleNamespace

from ingest.clean import strip_page_furniture
from ingest.pdf_reader import _page_parts


class StripPageFurnitureTest(unittest.TestCase):
    def test_removes_page_numbers_and_keeps_content(self):
        raw = "\n".join(
            [
                "6.006 Lecture 2",
                "## Hash tables",
                "A hash table maps keys to slots.",
                "Theorem 3 uses O(1) expected time.",
                "Figure 1.2 shows the array.",
                "| op | cost |",
                "| --- | --- |",
                "| insert | 1 |",
                "3",
                "- 4 -",
                "Page 5 of 10",
                "3 / 12",
                "第 6 页",
                "<!-- image -->",
            ]
        )

        cleaned = strip_page_furniture(raw)

        self.assertIn("Theorem 3 uses O(1) expected time.", cleaned)
        self.assertIn("Figure 1.2 shows the array.", cleaned)
        self.assertIn("| insert | 1 |", cleaned)
        self.assertIn("## Hash tables", cleaned)
        for line in ["3", "- 4 -", "Page 5 of 10", "3 / 12", "第 6 页", "<!-- image -->"]:
            self.assertNotIn(line, cleaned.splitlines())


class PagePartsTest(unittest.TestCase):
    def test_splits_a_paragraph_by_printed_page(self):
        text = "first half ends here, because the second half is on page two."
        provs = [
            SimpleNamespace(page_no=1, charspan=(0, 29)),
            SimpleNamespace(page_no=2, charspan=(30, len(text))),
        ]

        self.assertEqual(
            _page_parts(text, provs),
            [(1, "first half ends here, because"), (2, "the second half is on page two.")],
        )

    def test_keeps_text_together_without_usable_spans(self):
        provs = [
            SimpleNamespace(page_no=1, charspan=None),
            SimpleNamespace(page_no=2, charspan=None),
        ]

        self.assertIsNone(_page_parts("some text", provs))


if __name__ == "__main__":
    unittest.main()
