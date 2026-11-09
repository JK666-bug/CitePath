"""完整资料读取测试。

数据库使用 Mock，不连接真实 MySQL。
原 PDF 使用临时目录中的小文件，不影响已上传资料。
"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz

from db.material_pages import (
    PlanningMaterialError,
    load_planning_document,
)
from planning.material_files import save_original_pdf


def make_pdf(page_count: int) -> bytes:
    """生成指定页数的空白 PDF，用于核对真实页数。"""
    with fitz.open() as pdf:
        for _ in range(page_count):
            pdf.new_page()

        return pdf.tobytes()


def make_row(
    number: int,
    body: str | None = "",
    usable: int = 1,
    chapter: str = "Topic hint",
) -> dict:
    """模拟 pages 表的一条查询结果。"""
    return {
        "page_number": number,
        "chapter": chapter,
        "body": body,
        "usable": usable,
    }


class PlanningDocumentTests(unittest.TestCase):
    def setUp(self):
        # 原件保存到临时目录，测试结束后自动清理。
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(
            patch(
                "planning.material_files.MATERIAL_ROOT",
                Path(folder),
            )
        )

        self.data = make_pdf(3)
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.original_path = save_original_pdf(
            4,
            self.digest,
            self.data,
        )

        self.source = {
            "course_name": "Example Course",
            "document_id": 7,
            "filename": "lecture.pdf",
            "content_hash": self.digest,
            "ingest_status": "complete",
        }

        self.rows = [
            make_row(1, "  Existing database text.\n", 1),
            make_row(2, None, 0),
            # 特意保留一个 usable=0 但有文字的旧记录，
            # 验证新入口不会根据 usable 丢弃它。
            make_row(3, "A diagram title.", 0),
        ]

        self.cursor = MagicMock()
        self.cursor.fetchone.return_value = self.source
        self.cursor.fetchall.return_value = self.rows

        self.connection = MagicMock()
        self.connection.cursor.return_value.__enter__.return_value = (
            self.cursor
        )

        self.connect = self.enterContext(
            patch(
                "db.material_pages.connect",
                return_value=self.connection,
            )
        )

    def load(self):
        return load_planning_document(
            user_id=6,
            course_id=4,
            document_id=7,
        )

    def assert_error_code(self, expected_code: str):
        """执行读取，并检查程序能区分具体错误类型。"""
        with self.assertRaises(PlanningMaterialError) as caught:
            self.load()

        self.assertEqual(caught.exception.code, expected_code)

    def test_returns_all_original_pages_and_reuses_database_text(self):
        result = self.load()

        self.assertEqual(result.course_name, "Example Course")
        self.assertEqual(result.document_id, 7)
        self.assertEqual(result.filename, "lecture.pdf")
        self.assertEqual(result.content_hash, self.digest)
        self.assertEqual(result.original_path, self.original_path)
        self.assertEqual(result.total_pages, 3)

        self.assertEqual(
            [page.page_number for page in result.pages],
            [1, 2, 3],
        )
        self.assertEqual(
            [page.text_status for page in result.pages],
            ["available", "empty", "available"],
        )

        # PDF 本身是空白的。这段文字只能来自模拟数据库，
        # 可以验证本入口复用了正文，而不是重新提取 PDF。
        self.assertEqual(
            result.pages[0].body,
            "  Existing database text.\n",
        )
        self.assertEqual(
            result.pages[0].chapter_hint,
            "Topic hint",
        )

        self.assertFalse(result.pages[2].database_usable)
        self.assertTrue(result.pages[2].has_text)
        self.assertEqual(result.text_page_count, 2)

        # 检查传入查询的身份范围。
        first_parameters = self.cursor.execute.call_args_list[0].args[1]
        self.assertEqual(first_parameters, (6, 4, 7))
        self.connection.close.assert_called_once()

    def test_missing_database_page_gets_explicit_placeholder(self):
        self.cursor.fetchall.return_value = [
            self.rows[0],
            self.rows[2],
        ]

        result = self.load()
        missing_page = result.pages[1]

        self.assertEqual(result.total_pages, 3)
        self.assertEqual(len(result.pages), 3)
        self.assertEqual(missing_page.page_number, 2)
        self.assertEqual(missing_page.text_status, "missing")
        self.assertFalse(missing_page.record_present)
        self.assertIsNone(missing_page.database_usable)
        self.assertEqual(missing_page.body, "")

    def test_document_with_no_text_is_still_returned(self):
        self.cursor.fetchall.return_value = [
            make_row(number, None, 0)
            for number in range(1, 4)
        ]

        result = self.load()

        self.assertEqual(result.text_page_count, 0)
        self.assertEqual(
            [page.text_status for page in result.pages],
            ["empty", "empty", "empty"],
        )

    def test_document_with_no_page_rows_keeps_original_page_count(self):
        self.cursor.fetchall.return_value = []

        result = self.load()

        self.assertEqual(result.total_pages, 3)
        self.assertEqual(len(result.pages), 3)
        self.assertTrue(
            all(page.text_status == "missing" for page in result.pages)
        )

    def test_not_found_does_not_access_original_file(self):
        self.cursor.fetchone.return_value = None

        with patch("db.material_pages.load_original_pdf") as load_file:
            self.assert_error_code("document_not_found")

        load_file.assert_not_called()
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.close.assert_called_once()

    def test_pending_document_does_not_access_original_file(self):
        self.source["ingest_status"] = "pending"

        with patch("db.material_pages.load_original_pdf") as load_file:
            self.assert_error_code("document_not_ready")

        load_file.assert_not_called()
        self.connection.close.assert_called_once()

    def test_missing_fingerprint_has_clear_error(self):
        self.source["content_hash"] = None

        with patch("db.material_pages.load_original_pdf") as load_file:
            self.assert_error_code("missing_material_fingerprint")

        load_file.assert_not_called()

    def test_missing_original_has_clear_error(self):
        self.original_path.unlink()

        self.assert_error_code("original_pdf_missing")

    def test_corrupted_original_is_rejected(self):
        self.original_path.write_bytes(b"corrupted PDF bytes")

        self.assert_error_code("original_pdf_integrity_error")

    def test_page_outside_original_pdf_is_rejected(self):
        self.cursor.fetchall.return_value = [
            *self.rows,
            make_row(4, "An impossible fourth page.", 1),
        ]

        self.assert_error_code("invalid_page_number")

    def test_duplicate_page_number_is_rejected(self):
        self.cursor.fetchall.return_value = [
            *self.rows,
            make_row(1, "Duplicate first page.", 1),
        ]

        self.assert_error_code("duplicate_page_number")

    def test_invalid_usable_flag_is_rejected(self):
        self.cursor.fetchall.return_value = [
            make_row(1, "Some text.", 2),
        ]

        self.assert_error_code("invalid_usable_flag")

    def test_invalid_identifiers_do_not_connect_to_database(self):
        invalid_inputs = [
            (0, 4, 7),
            (6, -1, 7),
            (6, 4, 0),
            (True, 4, 7),
        ]

        for identifiers in invalid_inputs:
            with self.subTest(identifiers=identifiers):
                with self.assertRaises(PlanningMaterialError) as caught:
                    load_planning_document(*identifiers)

                self.assertEqual(
                    caught.exception.code,
                    "invalid_identifier",
                )

        self.connect.assert_not_called()

    def test_database_failure_still_closes_connection(self):
        self.cursor.fetchall.side_effect = RuntimeError(
            "Database unavailable"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Database unavailable",
        ):
            self.load()

        self.connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()