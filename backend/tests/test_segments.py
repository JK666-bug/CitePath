import unittest

from vector.segments import _continued_sentence, _open_sentence


class BridgeSentenceTest(unittest.TestCase):
    def test_finds_the_sentence_broken_by_the_page(self):
        body = (
            "## Arrays\n\n"
            "An array stores items in contiguous memory. Inserting at the front "
            "costs linear time compared with a linked list, because"
        )
        next_body = (
            "the linked list only updates two pointers. It also uses more memory.\n\n"
            "## Hashing"
        )

        self.assertEqual(
            _open_sentence(body),
            "Inserting at the front costs linear time compared with a linked list, because",
        )
        self.assertEqual(
            _continued_sentence(next_body),
            "the linked list only updates two pointers.",
        )

    def test_ignores_a_page_that_ends_a_sentence(self):
        self.assertIsNone(_open_sentence("A hash table maps keys to slots."))
        self.assertIsNone(_open_sentence("## Hashing"))
        self.assertIsNone(_open_sentence("| op | cost |\n| --- | --- |\n| insert | O(1) |"))

    def test_ignores_a_next_page_that_starts_a_new_block(self):
        self.assertIsNone(_continued_sentence("## Chapter 2\n\nText."))
        self.assertIsNone(_continued_sentence("| op | cost |"))
        self.assertIsNone(_continued_sentence("- first item"))

    def test_decimal_point_does_not_end_a_sentence(self):
        self.assertEqual(
            _open_sentence("The load factor is 0.75 when the table"),
            "The load factor is 0.75 when the table",
        )


if __name__ == "__main__":
    unittest.main()
