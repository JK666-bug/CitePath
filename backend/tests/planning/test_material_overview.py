"""整份资料概览测试。

使用模拟模型响应，不调用真实 HKU API。
这里验证输入组织、来源校验和停止条件，
不把模拟响应当作真实章节识别效果。
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from db.material_pages import PlanningDocument, PlanningPage
from planning.document_reader import DocumentReader
from planning.material_overview import (
    OverviewError,
    build_overview,
    main,
    prepare_overview,
)


def make_reader(bodies: list[str]) -> DocumentReader:
    """这里只读取数据库正文，因此不需要真实 PDF 文件。"""
    pages = tuple(
        PlanningPage(
            document_id=7,
            page_number=index,
            chapter_hint="Ingestion hint",
            body=body,
            database_usable=bool(body.strip()),
            record_present=True,
        )
        for index, body in enumerate(bodies, start=1)
    )

    document = PlanningDocument(
        user_id=6,
        course_id=4,
        course_name="Example Course",
        document_id=7,
        filename="lecture.pdf",
        content_hash="a" * 64,
        original_path=Path("/unused-test-original.pdf"),
        total_pages=len(pages),
        pages=pages,
    )

    return DocumentReader(document)


def valid_answer(context: dict) -> dict:
    reference = context["pages"][0]["blocks"][0]["block_id"]

    return {
        "title": "Example Lecture",
        "material_style": "slides",
        "document_goal": "Understand the connected lecture topics.",
        "organization": "keep_together",
        "organization_reason": "The supplied topics form one coherent scope.",
        "anchors": [
            {
                "page_number": 1,
                "role": "document_title",
                "title": "Lecture Introduction",
                "evidence_block_ids": [reference],
                "reason": "The first visible heading introduces the document.",
            }
        ],
        "next_reads": [],
    }


class MaterialOverviewTests(unittest.TestCase):
    def setUp(self):
        self.reader = make_reader(
            [
                "# Introduction\n\nTeaching content.",
                "# Related example\n\nMore teaching content.",
                "",
            ]
        )

    def context(self):
        return prepare_overview(
            self.reader,
            max_input_chars=100_000,
        )

    def test_full_text_preserves_all_pages_and_source_blocks(self):
        with (
            patch.object(self.reader, "read_native_text") as native,
            patch.object(self.reader, "render_page") as render,
        ):
            context = self.context()

        self.assertEqual(context["input_mode"], "full_text")
        self.assertEqual(
            [page["page_number"] for page in context["pages"]],
            [1, 2, 3],
        )
        self.assertTrue(
            all(
                page["database_text_complete"]
                for page in context["pages"]
            )
        )
        self.assertFalse(context["visual_content_inspected"])
        native.assert_not_called()
        render.assert_not_called()

    def test_limited_budget_keeps_a_complete_page_index(self):
        reader = make_reader(
            [
                "# Topic\n\n" + "Long explanation. " * 1000
                for _ in range(3)
            ]
        )

        context = prepare_overview(
            reader,
            max_input_chars=2500,
        )

        size = len(
            json.dumps(
                context,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

        self.assertEqual(context["input_mode"], "page_index")
        self.assertLessEqual(size, 2500)
        self.assertEqual(
            [page["page_number"] for page in context["pages"]],
            [1, 2, 3],
        )
        self.assertTrue(
            any(
                not page["database_text_complete"]
                for page in context["pages"]
            )
        )

    def test_too_small_budget_does_not_drop_pages_silently(self):
        with self.assertRaises(OverviewError) as caught:
            prepare_overview(
                self.reader,
                max_input_chars=1,
            )

        self.assertEqual(
            caught.exception.code,
            "input_budget_too_small",
        )

    def test_valid_output_produces_a_provisional_reading_plan(self):
        context = self.context()
        decide = Mock(
            return_value=(
                json.dumps(valid_answer(context)),
                {"usage": {"total_tokens": 100}},
            )
        )
        trace = []

        result = build_overview(
            context,
            decide,
            trace=trace,
        )

        self.assertEqual(
            result["reading_plan"]["text_reading"],
            "whole_document",
        )
        self.assertEqual(
            result["reading_plan"]["organization"],
            "keep_together",
        )
        self.assertEqual(trace[0]["status"], "accepted")
        self.assertNotIn("learning_units", result)

    def test_invented_source_can_receive_one_correction(self):
        context = self.context()
        wrong = valid_answer(context)
        wrong["anchors"][0]["evidence_block_ids"] = ["invented"]

        decide = Mock(
            side_effect=[
                (json.dumps(wrong), {}),
                (json.dumps(valid_answer(context)), {}),
            ]
        )
        trace = []

        build_overview(context, decide, trace=trace)

        self.assertEqual(decide.call_count, 2)
        self.assertEqual(trace[0]["status"], "rejected")
        self.assertEqual(trace[1]["status"], "accepted")

        retry = decide.call_args_list[1].args[0]
        self.assertIsNotNone(retry["validation_feedback"])

    def test_anchor_must_include_evidence_from_its_own_page(self):
        context = self.context()
        wrong = valid_answer(context)
        wrong["anchors"][0]["page_number"] = 2

        with self.assertRaises(OverviewError):
            build_overview(
                context,
                Mock(return_value=(json.dumps(wrong), {})),
                max_attempts=1,
            )

    def test_identical_invalid_output_stops_without_more_retries(self):
        context = self.context()
        decide = Mock(return_value=("not JSON", {}))

        with self.assertRaises(OverviewError) as caught:
            build_overview(
                context,
                decide,
                max_attempts=4,
            )

        self.assertEqual(caught.exception.code, "no_progress")
        self.assertEqual(decide.call_count, 2)

    def test_truncated_output_does_not_repeat_the_same_budget(self):
        context = self.context()
        decide = Mock(
            return_value=(
                '{"title":',
                {"finish_reason": "length"},
            )
        )

        with self.assertRaises(OverviewError) as caught:
            build_overview(context, decide)

        self.assertEqual(
            caught.exception.code,
            "model_output_truncated",
        )
        self.assertEqual(decide.call_count, 1)

    def test_index_input_stays_staged_even_when_scope_is_coherent(self):
        reader = make_reader(
            [
                "# Topic\n\n" + "Long explanation. " * 1000
                for _ in range(3)
            ]
        )
        context = prepare_overview(
            reader,
            max_input_chars=2500,
        )

        result = build_overview(
            context,
            Mock(
                return_value=(
                    json.dumps(valid_answer(context)),
                    {},
                )
            ),
        )

        self.assertEqual(
            result["reading_plan"]["organization"],
            "keep_together",
        )
        self.assertEqual(
            result["reading_plan"]["text_reading"],
            "staged",
        )

    def test_no_text_can_return_insufficient_evidence_without_inventing_anchors(self):
        context = prepare_overview(
            make_reader(["", ""]),
            max_input_chars=100_000,
        )

        answer = {
            "title": "Unresolved Lecture",
            "material_style": "unknown",
            "document_goal": "The teaching goal cannot yet be established.",
            "organization": "insufficient_evidence",
            "organization_reason": "No teaching text is available.",
            "anchors": [],
            "next_reads": [
                {
                    "action": "read_native_text",
                    "page_numbers": [1],
                    "reason": "Check whether a readable text layer exists.",
                }
            ],
        }

        result = build_overview(
            context,
            Mock(return_value=(json.dumps(answer), {})),
        )

        self.assertTrue(
            result["reading_plan"]["evidence_requests_pending"]
        )
        self.assertEqual(result["overview"]["anchors"], [])

    def test_model_call_failure_preserves_failure_trace(self):
        trace = []

        with self.assertRaises(OverviewError) as caught:
            build_overview(
                self.context(),
                Mock(side_effect=RuntimeError("API unavailable")),
                trace=trace,
            )

        self.assertEqual(
            caught.exception.code,
            "model_call_failed",
        )
        self.assertEqual(trace[0]["status"], "call_failed")

    def test_cli_preparation_does_not_create_a_model(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "prepared"

            with (
                patch(
                    "planning.material_overview.open_document_reader",
                    return_value=self.reader,
                ),
                patch("planning.material_overview.load_dotenv"),
                patch(
                    "planning.material_overview.make_overview_decider"
                ) as create_model,
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                code = main(
                    [
                        "--user-id", "6",
                        "--course-id", "4",
                        "--document-id", "7",
                        "--max-input-chars", "100000",
                        "--max-output-tokens", "4000",
                        "--output-dir", str(output),
                    ]
                )

            self.assertEqual(code, 0)
            create_model.assert_not_called()
            self.assertTrue((output / "request.json").exists())

            report = json.loads(
                (output / "overview.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(report["status"], "prepared")
            self.assertEqual(report["trace"], [])
            self.assertFalse(report["learning_units_generated"])


if __name__ == "__main__":
    unittest.main()