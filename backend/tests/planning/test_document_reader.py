"""正文块及按需读取测试。

不连接真实数据库，不调用模型。
测试 PDF 和图片全部生成在临时目录中。
"""

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import fitz

from db.material_pages import (
    PlanningDocument,
    PlanningMaterialError,
    PlanningPage,
)
from planning.document_reader import (
    DocumentReader,
    open_document_reader,
)
from planning.material_files import (
    load_original_pdf,
    save_original_pdf,
)


BODY = (
    "# Topic\n\n"
    "Paragraph one.\n"
    "Continued line.\n\n"
    "1. First step\n"
    "2. Second step\n\n"
    "| Name | Value |\n"
    "| --- | --- |\n"
    "| X | 1 |\n\n"
    "```python\n"
    "value = 1\n\n"
    "print(value)\n"
    "```\n\n"
    "Closing sentence."
)


def make_image() -> bytes:
    """先把文字和图形变成像素，用于制作纯图片页。"""
    with fitz.open() as pdf:
        page = pdf.new_page(width=200, height=200)
        page.draw_rect(
            fitz.Rect(20, 20, 180, 180),
            color=(0, 0, 0),
            fill=(0.9, 0.9, 0.9),
        )
        page.insert_text((40, 100), "Image-only content")
        return page.get_pixmap().tobytes("png")


def make_pdf() -> bytes:
    with fitz.open() as pdf:
        first = pdf.new_page()
        first.insert_text((50, 70), "Native page one.")

        second = pdf.new_page()
        second.insert_image(second.rect, stream=make_image())

        third = pdf.new_page()
        third.insert_text((50, 70), "Native page three.")

        return pdf.tobytes()


class DocumentReaderTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(
            patch(
                "planning.material_files.MATERIAL_ROOT",
                Path(folder),
            )
        )

        data = make_pdf()
        digest = hashlib.sha256(data).hexdigest()
        path = save_original_pdf(4, digest, data)

        pages = (
            PlanningPage(
                document_id=7,
                page_number=1,
                chapter_hint="Topic",
                body=BODY,
                database_usable=True,
                record_present=True,
            ),
            PlanningPage(
                document_id=7,
                page_number=2,
                chapter_hint="Topic",
                body="",
                database_usable=False,
                record_present=True,
            ),
            PlanningPage(
                document_id=7,
                page_number=3,
                chapter_hint="",
                body="",
                database_usable=None,
                record_present=False,
            ),
        )

        self.document = PlanningDocument(
            user_id=6,
            course_id=4,
            course_name="Example Course",
            document_id=7,
            filename="lecture.pdf",
            content_hash=digest,
            original_path=path,
            total_pages=3,
            pages=pages,
        )

        self.reader = DocumentReader(self.document)

    def assert_error_code(self, expected_code, operation):
        with self.assertRaises(PlanningMaterialError) as caught:
            operation()

        self.assertEqual(caught.exception.code, expected_code)

    def test_groups_basic_formats_without_splitting_code_blank_lines(self):
        page = self.reader.read_pages([1])[0]

        self.assertEqual(
            [block.kind for block in page.blocks],
            ["heading", "text", "list", "table", "code", "text"],
        )

        code = next(
            block for block in page.blocks
            if block.kind == "code"
        )

        self.assertIn("value = 1\n\nprint(value)", code.text)

    def test_blocks_preserve_original_text_and_nonblank_content(self):
        page = self.reader.read_pages([1])[0]
        covered_positions = set()

        for block in page.blocks:
            self.assertEqual(
                block.text,
                page.text[block.start_char:block.end_char],
            )
            covered_positions.update(
                range(block.start_char, block.end_char)
            )

        # 可以不为分隔空行创建块，但不能遗漏任何非空白字符。
        for index, character in enumerate(page.text):
            if not character.isspace():
                self.assertIn(index, covered_positions)

    def test_same_document_produces_same_block_ids(self):
        first = self.reader.read_pages([1])[0]
        another_reader = DocumentReader(self.document)
        second = another_reader.read_pages([1])[0]

        self.assertEqual(
            [block.block_id for block in first.blocks],
            [block.block_id for block in second.blocks],
        )

    def test_changed_text_produces_different_block_id(self):
        original = self.reader.read_pages([1])[0].blocks[0]

        changed_page = replace(
            self.document.pages[0],
            body="# Updated topic\n",
        )
        changed_document = replace(
            self.document,
            pages=(changed_page, *self.document.pages[1:]),
        )

        changed_reader = DocumentReader(changed_document)
        changed = changed_reader.read_pages([1])[0].blocks[0]

        self.assertNotEqual(original.block_id, changed.block_id)

    def test_database_read_does_not_open_original_pdf(self):
        with patch(
            "planning.document_reader.load_original_pdf"
        ) as load_file:
            self.reader.read_pages([1, 2, 3])

        load_file.assert_not_called()

    def test_empty_and_missing_pages_are_retained(self):
        pages = self.reader.read_pages([2, 3])

        self.assertEqual(len(pages), 2)
        self.assertEqual(
            [page.database_text_status for page in pages],
            ["empty", "missing"],
        )
        self.assertTrue(all(not page.has_text for page in pages))
        self.assertTrue(all(page.blocks == () for page in pages))

    def test_can_resolve_a_real_source_block(self):
        page = self.reader.read_pages([1])[0]
        block = page.blocks[1]

        resolved = self.reader.get_block(block.block_id)

        self.assertEqual(resolved.text, block.text)
        self.assertEqual(resolved.page_number, 1)
        self.assertEqual(resolved.source, "database")

    def test_unknown_source_block_is_rejected(self):
        self.assert_error_code(
            "unknown_source_block",
            lambda: self.reader.get_block("invented-block"),
        )

    def test_native_read_supplements_missing_text_without_overwriting(self):
        native = self.reader.read_native_text(3)

        self.assertEqual(native.source, "native_pdf")
        self.assertIn("Native page three.", native.text)
        self.assertTrue(native.has_text)
        self.assertTrue(native.blocks)

        # 补读之后，数据库页面状态和原正文保持不变。
        database = self.reader.read_pages([3])[0]
        self.assertEqual(database.database_text_status, "missing")
        self.assertFalse(database.has_text)
        self.assertEqual(self.document.pages[2].body, "")

    def test_native_read_does_not_perform_ocr(self):
        native = self.reader.read_native_text(2)

        self.assertFalse(native.has_text)
        self.assertEqual(native.blocks, ())

    def test_repeated_native_read_uses_cache(self):
        with patch(
            "planning.document_reader.load_original_pdf",
            wraps=load_original_pdf,
        ) as load_file:
            first = self.reader.read_native_text(3)
            second = self.reader.read_native_text(3)

        self.assertIs(first, second)
        load_file.assert_called_once()

    def test_invalid_page_selections_are_rejected(self):
        invalid_selections = [
            [],
            [0],
            [4],
            [True],
        ]

        for selection in invalid_selections:
            with self.subTest(selection=selection):
                self.assert_error_code(
                    "invalid_page_selection",
                    lambda: self.reader.read_pages(selection),
                )

        self.assert_error_code(
            "duplicate_page_selection",
            lambda: self.reader.read_pages([1, 1]),
        )

    def test_renders_image_page_without_claiming_text_was_read(self):
        image = self.reader.render_page(2, max_side=600)

        self.assertEqual(image.page_number, 2)
        self.assertTrue(image.png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

        # PDF 到像素的取整可能带来一个像素的边界差异。
        self.assertLessEqual(max(image.width, image.height), 601)
        self.assertGreater(min(image.width, image.height), 0)

        database = self.reader.read_pages([2])[0]
        self.assertFalse(database.has_text)
        self.assertEqual(database.database_text_status, "empty")

    def test_invalid_render_size_does_not_open_original(self):
        with patch(
            "planning.document_reader.load_original_pdf"
        ) as load_file:
            for size in (0, True, 4097):
                with self.subTest(size=size):
                    self.assert_error_code(
                        "invalid_render_size",
                        lambda: self.reader.render_page(
                            2,
                            max_side=size,
                        ),
                    )

        load_file.assert_not_called()

    def test_corrupted_original_is_rejected_before_native_read(self):
        self.document.original_path.write_bytes(b"damaged")

        self.assert_error_code(
            "original_pdf_integrity_error",
            lambda: self.reader.read_native_text(3),
        )

    def test_factory_uses_the_authorized_document_loader(self):
        with patch(
            "planning.document_reader.load_planning_document",
            return_value=self.document,
        ) as load_document:
            reader = open_document_reader(6, 4, 7)

        load_document.assert_called_once_with(
            user_id=6,
            course_id=4,
            document_id=7,
        )
        self.assertIs(reader.document, self.document)


if __name__ == "__main__":
    unittest.main()