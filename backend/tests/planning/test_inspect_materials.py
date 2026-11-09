"""开发检查入口测试。

使用临时 PDF 和模拟的资料读取入口。
不连接真实数据库，也不调用模型。
"""

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import fitz

from db.material_pages import (
    PlanningDocument,
    PlanningMaterialError,
    PlanningPage,
)
from planning.document_reader import DocumentReader
from planning.inspect_materials import main
from planning.material_files import save_original_pdf


class InspectMaterialsTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(folder)

        self.enterContext(
            patch(
                "planning.material_files.MATERIAL_ROOT",
                self.root / "originals",
            )
        )

        with fitz.open() as pdf:
            first = pdf.new_page()
            first.insert_text((50, 70), "Native first page.")

            pdf.new_page()

            third = pdf.new_page()
            third.insert_text((50, 70), "Native third page.")

            data = pdf.tobytes()

        digest = hashlib.sha256(data).hexdigest()
        original_path = save_original_pdf(4, digest, data)

        # 使用较长正文，检查报告没有仅保存短预览。
        self.body = "# Main topic\n\n" + "A complete paragraph. " * 100

        pages = (
            PlanningPage(
                document_id=7,
                page_number=1,
                chapter_hint="Main topic",
                body=self.body,
                database_usable=True,
                record_present=True,
            ),
            PlanningPage(
                document_id=7,
                page_number=2,
                chapter_hint="Main topic",
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

        document = PlanningDocument(
            user_id=6,
            course_id=4,
            course_name="Example Course",
            document_id=7,
            filename="lecture.pdf",
            content_hash=digest,
            original_path=original_path,
            total_pages=3,
            pages=pages,
        )

        self.reader = DocumentReader(document)

        self.open_reader = self.enterContext(
            patch(
                "planning.inspect_materials.open_document_reader",
                return_value=self.reader,
            )
        )

        # 测试不读取项目真实 .env。
        self.enterContext(
            patch("planning.inspect_materials.load_dotenv")
        )

    def run_cli(self, *extra):
        output_dir = self.root / "report"

        arguments = [
            "--user-id", "6",
            "--course-id", "4",
            "--document-id", "7",
            "--output-dir", str(output_dir),
            *extra,
        ]

        with redirect_stdout(io.StringIO()):
            with redirect_stderr(io.StringIO()):
                code = main(arguments)

        report_path = output_dir / "inspection.json"

        report = (
            json.loads(report_path.read_text(encoding="utf-8"))
            if report_path.exists()
            else None
        )

        return code, report

    def test_default_inspection_keeps_all_pages_and_full_text(self):
        with (
            patch.object(self.reader, "read_native_text") as native,
            patch.object(self.reader, "render_page") as render,
        ):
            code, report = self.run_cli()

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "completed")
        self.assertFalse(report["chapter_analysis_performed"])
        self.assertEqual(len(report["pages"]), 3)

        self.assertEqual(
            report["summary"]["database_page_states"],
            {
                "available": 1,
                "empty": 1,
                "missing": 1,
            },
        )
        self.assertEqual(
            report["pages"][0]["database"]["text"],
            self.body,
        )

        blocks = report["pages"][0]["database"]["blocks"]
        self.assertTrue(blocks)
        self.assertEqual(
            "".join(block["text"] for block in blocks).replace(
                "\n", ""
            ),
            self.body.replace("\n", ""),
        )

        native.assert_not_called()
        render.assert_not_called()
        self.assertFalse((self.root / "report" / "images").exists())

    def test_native_read_is_saved_separately(self):
        code, report = self.run_cli("--native-pages", "3")

        self.assertEqual(code, 0)
        page = report["pages"][2]

        self.assertEqual(
            page["database"]["database_text_status"],
            "missing",
        )
        self.assertEqual(page["database"]["text"], "")
        self.assertIn(
            "Native third page.",
            page["native_pdf"]["text"],
        )
        self.assertEqual(report["summary"]["native_read_count"], 1)
        self.assertEqual(
            report["summary"]["rendered_image_count"],
            0,
        )

    def test_explicit_render_saves_png_without_native_read(self):
        with patch.object(
            self.reader,
            "read_native_text",
        ) as native:
            code, report = self.run_cli(
                "--render-pages", "2",
                "--max-side", "600",
            )

        self.assertEqual(code, 0)

        image = report["pages"][1]["rendered_image"]
        self.assertFalse(image["image_understood"])

        image_path = (
            self.root
            / "report"
            / image["relative_path"]
        )

        self.assertTrue(image_path.exists())
        self.assertTrue(
            image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        )
        self.assertEqual(
            report["summary"]["rendered_image_count"],
            1,
        )
        native.assert_not_called()

    def test_same_page_can_be_explicitly_read_and_rendered(self):
        code, report = self.run_cli(
            "--native-pages", "2",
            "--render-pages", "2",
            "--max-side", "600",
        )

        self.assertEqual(code, 0)
        page = report["pages"][1]

        self.assertIsNotNone(page["native_pdf"])
        self.assertFalse(page["native_pdf"]["has_text"])
        self.assertIsNotNone(page["rendered_image"])
        self.assertEqual(
            page["database"]["database_text_status"],
            "empty",
        )

    def test_optional_failure_preserves_other_successful_results(self):
        with patch.object(
            self.reader,
            "read_native_text",
            side_effect=PlanningMaterialError(
                "native_read_failed",
                "The requested native text could not be read.",
            ),
        ):
            code, report = self.run_cli(
                "--native-pages", "3",
                "--render-pages", "2",
                "--max-side", "600",
            )

        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(len(report["pages"]), 3)

        self.assertIsNone(report["pages"][2]["native_pdf"])
        self.assertIsNotNone(
            report["pages"][1]["rendered_image"]
        )

        error = report["errors"][0]
        self.assertEqual(error["action"], "read_native_text")
        self.assertEqual(error["page_number"], 3)
        self.assertEqual(error["code"], "native_read_failed")

    def test_document_lookup_failure_creates_failed_report(self):
        self.open_reader.side_effect = PlanningMaterialError(
            "document_not_found",
            "The document was not found in this course.",
        )

        code, report = self.run_cli()

        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertIsNone(report["document"])
        self.assertEqual(report["pages"], [])
        self.assertEqual(
            report["errors"][0]["code"],
            "document_not_found",
        )

    def test_out_of_range_page_does_not_run_optional_tools(self):
        with (
            patch.object(self.reader, "read_native_text") as native,
            patch.object(self.reader, "render_page") as render,
        ):
            code, report = self.run_cli(
                "--native-pages", "4",
            )

        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")

        # 参数错误不丢掉已经完成的基础页面检查。
        self.assertEqual(len(report["pages"]), 3)
        self.assertEqual(
            report["errors"][0]["code"],
            "invalid_page_selection",
        )

        native.assert_not_called()
        render.assert_not_called()

    def test_existing_output_directory_is_not_overwritten(self):
        output_dir = self.root / "report"
        output_dir.mkdir()
        marker = output_dir / "keep.txt"
        marker.write_text("Keep this result.", encoding="utf-8")

        code, report = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIsNone(report)
        self.assertEqual(
            marker.read_text(encoding="utf-8"),
            "Keep this result.",
        )
        self.open_reader.assert_not_called()

    def test_render_requires_explicit_size(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("--render-pages", "2")

        self.assertEqual(caught.exception.code, 2)
        self.open_reader.assert_not_called()

    def test_duplicate_page_arguments_are_rejected(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("--native-pages", "1", "1")

        self.assertEqual(caught.exception.code, 2)
        self.open_reader.assert_not_called()

    def test_unknown_failure_is_not_reported_as_completed(self):
        self.open_reader.side_effect = RuntimeError(
            "Internal diagnostic information."
        )

        code, report = self.run_cli()

        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")

        error = report["errors"][0]
        self.assertEqual(
            error["code"],
            "unexpected_inspection_error",
        )
        self.assertEqual(error["error_type"], "RuntimeError")
        self.assertNotIn(
            "Internal diagnostic information.",
            error["message"],
        )

    def test_report_write_failure_returns_failure(self):
        with patch(
            "planning.inspect_materials._atomic_write",
            side_effect=OSError("Storage unavailable"),
        ):
            code, report = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()