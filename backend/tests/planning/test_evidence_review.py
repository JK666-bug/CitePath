"""第七步工具循环测试。

模拟响应验证控制流程，不证明真实 PDF 的章节语义正确。
"""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from db.material_pages import PlanningDocument, PlanningPage
from planning.document_reader import (
    DocumentReader,
    PageText,
    SourceBlock,
)
from planning.material_overview import prepare_overview
from planning.unit_candidates import generate_candidates
from planning.evidence_review import (
    ReviewLimits,
    EvidenceReviewError,
    _apply_plan_update,
    load_candidate_input,
    run_evidence_review,
)


def make_reader(bodies=None):
    if bodies is None:
        bodies = [
            "# Introduction\n\nUnderstand one connected topic.",
            "# Example\n\nThis example develops the same learning goal.",
            "# Summary\n\nReview the connected teaching.",
        ]

    pages = tuple(
        PlanningPage(
            document_id=7,
            page_number=index,
            chapter_hint="Hint",
            body=body,
            database_usable=True,
            record_present=True,
        )
        for index, body in enumerate(bodies, start=1)
    )

    reader = DocumentReader(
        PlanningDocument(
            user_id=6,
            course_id=4,
            course_name="Example",
            document_id=7,
            filename="example.pdf",
            content_hash="a" * 64,
            original_path=Path("/unused.pdf"),
            total_pages=len(bodies),
            pages=pages,
        )
    )

    reader.render_page = Mock(
        side_effect=AssertionError("Unexpected image rendering.")
    )
    return reader


def make_source():
    return {
        "identity": {
            "user_id": 6,
            "course_id": 4,
            "document_id": 7,
            "content_hash": "a" * 64,
            "total_pages": 3,
        },
        "fingerprint": "synthetic-input",
        "plan": {
            "scopes": [
                {
                    "title": "Connected Topic",
                    "objective": "Understand the topic and its example.",
                    "start_page": 1,
                    "end_page": 3,
                    "boundary_reason": "The pages support one goal.",
                }
            ],
            "excluded_pages": [],
            "auxiliary_pages": [],
            "pending_ranges": [],
            "next_reads": [],
        },
        "questions": [
            {
                "issue_id": "issue-1",
                "page_numbers": [2],
                "question": "Does the example belong to this scope?",
            }
        ],
    }


def finish_response(payload, images):
    # 模拟模型逐个引用实际收到的页面，不允许测试伪造来源 ID。
    resolutions = []
    for question in payload["questions"]:
        reference = next(
            block["block_id"]
            for page in payload["text_evidence"]
            if page["page_number"] in question["page_numbers"]
            for block in page["blocks"]
        )
        comparisons = []
        for pair in question.get("boundary_candidates", []):
            catalog = {scope["scope_id"]: scope for scope in payload["scope_catalog"]}
            left = catalog[pair["left_scope_id"]]
            first_page = question["page_numbers"][0]
            relation = ("continues_left" if left["start_page"] <= first_page <= left["end_page"]
                        or not question["current_memberships"] else "introduces_right")
            comparison = {
                "left_scope_id": pair["left_scope_id"],
                "right_scope_id": pair["right_scope_id"],
                "relation": relation,
                "decision_reason": "The example continues the earlier teaching.",
            }
            for side in ("left", "right"):
                comparison[f"{side}_observation"] = f"Observed {side} teaching."
                comparison[f"{side}_evidence_block_ids"] = [next(
                    block["block_id"]
                    for page in payload["text_evidence"]
                    if page["page_number"] in pair[f"{side}_eligible_page_numbers"]
                    for block in page["blocks"]
                )]
            comparisons.append(comparison)
        resolutions.append({
            "issue_id": question["issue_id"], "resolved": True,
            "reason": "The example explicitly continues the topic.",
            "evidence_block_ids": [reference],
            "boundary_comparisons": comparisons,
        })

    return json.dumps(
        {
            "action": "finish",
            "reason": "The example develops the same goal.",
            "plan_update": {"mode": "keep"},
            "resolutions": resolutions,
        }
    ), {"finish_reason": "stop"}


class EvidenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.reader = make_reader()
        self.source = make_source()

    def boundary_source(self):
        """模拟撮合结果页与新章节介绍页，测试比较协议而非模型语义能力。"""
        reader = make_reader([
            "# Order Matching\n\nMatch buyer and seller orders.",
            "# After Order Matching\n\nThe chart shows the result of the matching.",
            "# Market Terminology\n\nDefinitions of bid, ask and spread.",
        ])
        source = make_source()
        template = source["plan"]["scopes"][0]
        source["plan"]["scopes"] = [
            {**template, "title": "Matching", "end_page": 1},
            {**template, "title": "Terminology", "start_page": 2},
        ]
        source["questions"][0]["question"] = "Earlier draft suggests a new section introduction; verify it."
        return reader, source

    def test_boundary_requires_both_sides_not_just_disputed_heading(self):
        reader, source = self.boundary_source()
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                value["resolutions"][0].pop("boundary_comparisons")
            else:
                left, right = source["plan"]["scopes"]
                value["resolutions"][0]["boundary_comparisons"][0]["relation"] = "continues_left"
                value["plan_update"] = {"mode": "patch", "scope_edits": [{
                    "replace_scope_ids": ["scope-1", "scope-2"],
                    "scopes": [{**left, "end_page": 2}, {**right, "start_page": 3}],
                }]}
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        self.assertEqual(len(calls), 2)
        self.assertIn("missing_boundary_comparison", json.dumps(calls[1]["validation_feedback"]))
        self.assertEqual(calls[1]["current_plan"], source["plan"])
        question = calls[0]["questions"][0]
        self.assertEqual(question["question_status"], "hypothesis_not_verified")
        pair = question["boundary_candidates"][0]
        self.assertEqual(pair["left_eligible_page_numbers"], [1])
        self.assertEqual(pair["right_eligible_page_numbers"], [3])
        self.assertEqual(result["plan"]["scopes"][0]["end_page"], 2)
        self.assertEqual(result["plan"]["scopes"][1]["start_page"], 3)
        self.assertFalse(result["semantic_coverage_verified"])
        reader.render_page.assert_not_called()

    def test_wrong_side_evidence_is_rejected_even_when_source_exists(self):
        reader, source = self.boundary_source()
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                comparison = value["resolutions"][0]["boundary_comparisons"][0]
                comparison["right_evidence_block_ids"] = comparison["left_evidence_block_ids"]
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertIn("invalid_boundary_evidence", json.dumps(calls[1]["validation_feedback"]))

    def test_boundary_decision_must_match_the_actual_page_assignment(self):
        reader, source = self.boundary_source()
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                # 声称属于左侧却保留右侧归属，不能通过格式完整的解释掩盖冲突。
                value["resolutions"][0]["boundary_comparisons"][0]["relation"] = "continues_left"
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertIn("boundary_update_mismatch", json.dumps(calls[1]["validation_feedback"]))
        self.assertEqual(calls[1]["current_plan"], source["plan"])

    def test_auxiliary_patch_records_are_preserved_and_removal_is_explicit(self):
        source = copy.deepcopy(self.source)
        reference = self.reader.read_pages([1])[0].blocks[0].block_id
        record = {"page_number": 1, "role": "document_intro", "reason": "Orientation only.",
                  "evidence_block_ids": [reference]}
        source["plan"]["auxiliary_pages"] = [record]
        original = copy.deepcopy(source)
        candidate, _ = _apply_plan_update({"plan_update": {"mode": "patch"}}, source)
        self.assertEqual(candidate["auxiliary_pages"], [record])
        candidate, _ = _apply_plan_update({"plan_update": {
            "mode": "patch", "remove_auxiliary_pages": [1],
        }}, source)
        self.assertEqual(candidate["auxiliary_pages"], [])
        self.assertEqual(source, original)
        for removal in ([1, 1], [2]):
            with self.subTest(removal=removal), self.assertRaises(EvidenceReviewError):
                _apply_plan_update({"plan_update": {
                    "mode": "patch", "remove_auxiliary_pages": removal,
                }}, source)

    def test_existing_auxiliary_records_survive_keep(self):
        reference = self.reader.read_pages([1])[0].blocks[0].block_id
        self.source["plan"]["auxiliary_pages"] = [{
            "page_number": 1, "role": "document_intro", "reason": "Whole-document orientation.",
            "evidence_block_ids": [reference],
        }]
        result = run_evidence_review(self.reader, self.source, finish_response)
        self.assertEqual(result["plan"]["auxiliary_pages"], self.source["plan"]["auxiliary_pages"])
        self.assertFalse(result["concepts_require_regeneration"])

    def test_document_recap_scope_can_be_removed_by_local_patch(self):
        source = copy.deepcopy(self.source)
        template = source["plan"]["scopes"][0]
        source["plan"]["scopes"] = [{**template, "end_page": 2}, {**template, "start_page": 3}]
        source["questions"][0]["page_numbers"] = [3]

        def decide(payload, images):
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            reference = value["resolutions"][0]["evidence_block_ids"][0]
            value["resolutions"][0]["boundary_comparisons"][0]["relation"] = "document_auxiliary"
            value["plan_update"] = {
                "mode": "patch",
                "scope_edits": [{"replace_scope_ids": ["scope-2"], "scopes": []}],
                "add_auxiliary_pages": [{
                    "page_number": 3, "role": "document_recap", "reason": "Whole-document recap only.",
                    "evidence_block_ids": [reference],
                }],
            }
            return json.dumps(value), metadata

        result = run_evidence_review(self.reader, source, decide)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertEqual(len(result["plan"]["scopes"]), 1)
        self.assertEqual(result["plan"]["auxiliary_pages"][0]["page_number"], 3)
        self.assertTrue(result["concepts_require_regeneration"])

    def test_auxiliary_change_requires_evidence_actually_supplied(self):
        reader, source = self.make_separated_issues()
        source["questions"] = [source["questions"][0]]
        reference = reader.read_pages([7])[0].blocks[0].block_id
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                value["plan_update"] = {"mode": "patch", "add_auxiliary_pages": [{
                    "page_number": 7, "role": "document_recap", "reason": "Unseen whole-document recap.",
                    "evidence_block_ids": [reference],
                }]}
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertIn("unseen_auxiliary_evidence", json.dumps(calls[1]["validation_feedback"]))
        self.assertEqual(result["plan"]["auxiliary_pages"], [])

    def test_whole_range_question_can_compare_both_sides(self):
        reader, source = self.boundary_source()
        source["questions"][0]["page_numbers"] = [1, 2, 3]
        result = run_evidence_review(reader, source, finish_response)
        self.assertEqual(result["status"], "ready_for_coverage_review")

    def test_auxiliary_disposition_survives_stage_six_to_seven_handoff(self):
        material = prepare_overview(self.reader, max_input_chars=100000)
        context = {"material": material, "overview": {
            "title": "Connected Topic", "material_style": "handout",
            "document_goal": "Understand one connected topic.",
            "organization": "keep_together", "organization_reason": "One coherent goal.",
            "anchors": [], "next_reads": [],
        }}
        recap_ref = material["pages"][2]["blocks"][0]["block_id"]
        teaching_ref = material["pages"][0]["blocks"][-1]["block_id"]
        reviewed = copy.deepcopy(self.source["plan"])
        reviewed["auxiliary_pages"] = [{
            "page_number": 3, "role": "document_recap", "reason": "Whole-document recap.",
            "evidence_block_ids": [recap_ref],
        }]
        reviewed.update(needs_scope_review=False, review_reason="Retain the connected teaching only.")
        content = {"status": "supported", "concepts": [{
            "name": "Connected teaching", "evidence_block_ids": [teaching_ref],
        }], "reason": "Supported by the teaching pages.", "next_reads": []}
        stage_six = generate_candidates(context, Mock(side_effect=[
            (json.dumps(value), {"finish_reason": "stop"}) for value in (reviewed, content)
        ]))
        self.assertEqual(stage_six["units"][0]["page_numbers"], [1, 2])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "request.json").write_text(json.dumps({"candidate_input": context}), encoding="utf-8")
            (root / "candidates.json").write_text(json.dumps({
                "stage": "unit_candidates", "status": stage_six["status"],
                "request": {"user_id": 6, "course_id": 4, "document_id": 7}, "result": stage_six,
            }), encoding="utf-8")
            source = load_candidate_input(self.reader, root / "candidates.json")
        self.assertEqual(source["plan"]["auxiliary_pages"], reviewed["auxiliary_pages"])
        # 无疑点只表示可交给第八步，不把辅助页误读成一个新章节。
        decide = Mock(side_effect=AssertionError("No model call expected."))
        result = run_evidence_review(self.reader, source, decide)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertEqual(result["plan"]["auxiliary_pages"], reviewed["auxiliary_pages"])
        self.assertFalse(result["semantic_coverage_verified"])
        decide.assert_not_called()

    def test_existing_text_can_resolve_without_image(self):
        decide = Mock(side_effect=finish_response)

        result = run_evidence_review(
            self.reader,
            self.source,
            decide,
        )

        self.assertEqual(
            result["status"],
            "ready_for_coverage_review",
        )
        self.assertEqual(decide.call_count, 1)
        self.reader.render_page.assert_not_called()
        self.assertFalse(result["ready_for_practice"])
        self.assertFalse(result["semantic_coverage_verified"])

    def test_false_resolution_source_gets_feedback(self):
        calls = []

        def decide(payload, images):
            calls.append(payload)

            raw, metadata = finish_response(payload, images)

            if len(calls) == 1:
                value = json.loads(raw)
                value["resolutions"][0]["evidence_block_ids"] = [
                    "invented"
                ]
                return json.dumps(value), metadata

            return raw, metadata

        result = run_evidence_review(
            self.reader,
            self.source,
            decide,
        )

        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(
            calls[1]["validation_feedback"]
        )
        self.assertEqual(
            result["status"],
            "ready_for_coverage_review",
        )

    def test_repeated_read_stops_without_infinite_calls(self):
        decide = Mock(
            return_value=(
                json.dumps(
                    {
                        "action": "read_pages",
                        "page_numbers": [2],
                        "reason": "Read the same page again.",
                    }
                ),
                {"finish_reason": "stop"},
            )
        )

        result = run_evidence_review(
            self.reader,
            self.source,
            decide,
            limits=ReviewLimits(max_no_progress=2),
        )

        self.assertEqual(decide.call_count, 2)
        self.assertEqual(
            result["stop_reason"]["code"],
            "no_progress",
        )
        self.assertEqual(
            result["plan"],
            self.source["plan"],
        )

    def test_native_read_can_resume_without_resetting_budget(self):
        text = "The example continues the original learning goal."

        self.reader.read_native_text = Mock(
            return_value=PageText(
                page_number=2,
                source="native_pdf",
                database_text_status="available",
                text=text,
                blocks=(
                    SourceBlock(
                        block_id="native-page-2",
                        page_number=2,
                        source="native_pdf",
                        kind="text",
                        start_char=0,
                        end_char=len(text),
                        text=text,
                    ),
                ),
            )
        )

        first_decide = Mock(
            return_value=(
                json.dumps(
                    {
                        "action": "read_native_text",
                        "page_numbers": [2],
                        "reason": "Check the original text layer.",
                    }
                ),
                {"finish_reason": "stop"},
            )
        )

        first = run_evidence_review(
            self.reader,
            self.source,
            first_decide,
            limits=ReviewLimits(max_model_calls=1),
        )

        self.assertEqual(
            first["stop_reason"]["code"],
            "model_budget_exhausted",
        )

        second = run_evidence_review(
            self.reader,
            self.source,
            finish_response,
            limits=ReviewLimits(max_model_calls=2),
            resume=first,
        )

        self.assertEqual(second["model_calls"], 2)
        self.assertEqual(
            second["status"],
            "ready_for_coverage_review",
        )

    def test_disabled_images_are_not_rendered(self):
        calls = []

        def decide(payload, images):
            calls.append(payload)

            if len(calls) == 1:
                return json.dumps(
                    {
                        "action": "inspect_image",
                        "page_numbers": [2],
                        "reason": "Check the page image.",
                    }
                ), {"finish_reason": "stop"}

            return json.dumps(
                {
                    "action": "stop",
                    "reason": "The required image tool is unavailable.",
                }
            ), {"finish_reason": "stop"}

        result = run_evidence_review(
            self.reader,
            self.source,
            decide,
            allow_images=False,
        )

        self.reader.render_page.assert_not_called()
        self.assertEqual(
            calls[1]["last_observation"]["status"],
            "unavailable",
        )
        self.assertEqual(result["status"], "needs_evidence")


    def test_same_page_questions_keep_all_distinct_reasons(self):
        # 第六步对同一页既有归属疑问又有读取请求：合成一条，但保留全部理由。
        report = {
            "stage": "unit_candidates", "status": "needs_scope_review",
            "request": {"user_id": 6, "course_id": 4, "document_id": 7},
            "result": {
                "scope_plan": copy.deepcopy(self.source["plan"]),
                "assignment_reviews": [{
                    "start_page": 2, "end_page": 2,
                    "reason": "Check whether the example continues the topic.",
                }],
                "next_reads": [{
                    "action": "read_pages", "page_numbers": [2],
                    "reason": "Compare the example with surrounding teaching.",
                }],
            },
        }
        request = {"candidate_input": {"material": {
            "document": copy.deepcopy(self.source["identity"]),
        }}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "candidates.json").write_text(json.dumps(report), encoding="utf-8")
            (root / "request.json").write_text(json.dumps(request), encoding="utf-8")
            result = load_candidate_input(self.reader, root / "candidates.json")
        self.assertEqual(len(result["questions"]), 1)
        question = result["questions"][0]
        self.assertEqual(len(question["subquestions"]), 2)
        self.assertIn("surrounding teaching", question["question"])
        self.assertIn("continues the topic", question["question"])

    def make_separated_issues(self):
        reader = make_reader([f"# Topic\nTeaching example on page {page}."
                              for page in range(1, 8)])
        source = copy.deepcopy(self.source)
        source["identity"]["total_pages"] = 7
        source["plan"]["scopes"][0]["end_page"] = 7
        source["questions"].append({
            "issue_id": "issue-2", "page_numbers": [6],
            "question": "Does the later example still belong?",
        })
        return reader, source

    def test_initial_evidence_covers_separated_issues_and_neighbors(self):
        reader, source = self.make_separated_issues()
        calls = []

        def decide(payload, images):
            calls.append(payload)
            return finish_response(payload, images)

        result = run_evidence_review(reader, source, decide)
        self.assertEqual(calls[0]["provided_page_numbers"], [1, 2, 3, 5, 6, 7])
        self.assertEqual(calls[0]["unread_question_pages"], [])
        self.assertEqual(calls[0]["questions"][1]["current_memberships"][0]["scope_id"],
                         "scope-1")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        reader.render_page.assert_not_called()

    def test_seed_budget_exposes_deferred_pages_without_claiming_success(self):
        reader, source = self.make_separated_issues()
        calls = []

        def decide(payload, images):
            calls.append(payload)
            return json.dumps({"action": "stop", "reason": "More context is needed."}), {}

        result = run_evidence_review(reader, source, decide,
                                     limits=ReviewLimits(max_tool_pages=1))
        self.assertEqual(calls[0]["provided_page_numbers"], [2])
        self.assertEqual(calls[0]["unread_question_pages"], [6])
        self.assertEqual(result["status"], "needs_evidence")
        self.assertEqual(result["plan"], source["plan"])

    def test_local_patch_preserves_unaffected_scopes(self):
        reader, source = self.make_separated_issues()
        source["questions"] = [source["questions"][1]]
        template = source["plan"]["scopes"][0]
        source["plan"]["scopes"] = [
            {**template, "start_page": 1, "end_page": 2},
            {**template, "start_page": 3, "end_page": 4},
            {**template, "start_page": 5, "end_page": 7},
        ]

        def decide(payload, images):
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            value["plan_update"] = {"mode": "patch", "scope_edits": [{
                "replace_scope_ids": ["scope-2", "scope-3"],
                "scopes": [{**template, "start_page": 3, "end_page": 7}],
            }]}
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertEqual(len(result["plan"]["scopes"]), 2)
        self.assertEqual(result["plan"]["scopes"][0], source["plan"]["scopes"][0])
        self.assertEqual(result["applied_plan_update"]["mode"], "patch")
        self.assertTrue(result["concepts_require_regeneration"])

    def test_legacy_full_replacement_cannot_drop_unaffected_scopes(self):
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                value.pop("plan_update")
                value["plan"] = {**copy.deepcopy(payload["current_plan"]), "scopes": []}
            return json.dumps(value), metadata

        result = run_evidence_review(self.reader, self.source, decide)
        feedback = calls[1]["validation_feedback"]
        self.assertEqual(feedback["issues"][0]["code"], "local_patch_required")
        self.assertEqual(calls[1]["current_plan"], self.source["plan"])
        self.assertEqual(result["plan"]["scopes"], self.source["plan"]["scopes"])

    def test_feedback_identifies_each_bad_resolution_and_its_pages(self):
        reader, source = self.make_separated_issues()
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                for item in value["resolutions"]:
                    item["evidence_block_ids"] = []
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        problems = calls[1]["validation_feedback"]["issues"]
        self.assertEqual({item["issue_id"] for item in problems}, {"issue-1", "issue-2"})
        self.assertEqual({tuple(item["question_pages"]) for item in problems}, {(2,), (6,)})
        self.assertTrue(all(item["available_evidence_block_ids"] for item in problems))
        self.assertEqual(result["status"], "ready_for_coverage_review")

    def test_invalid_scope_handle_is_rejected_without_changing_plan(self):
        with self.assertRaises(EvidenceReviewError) as caught:
            _apply_plan_update({"plan_update": {
                "mode": "patch", "scope_edits": [{
                    "replace_scope_ids": ["scope-999"], "scopes": [],
                }],
            }}, {"plan": self.source["plan"], "identity": self.source["identity"]})
        self.assertEqual(caught.exception.code, "invalid_scope_ids")
        self.assertEqual(self.source["plan"]["scopes"][0]["end_page"], 3)

    def test_unassigned_page_needs_a_patch_before_queue_is_cleared(self):
        source = copy.deepcopy(self.source)
        template = source["plan"]["scopes"][0]
        source["plan"]["scopes"] = [
            {**template, "end_page": 1},
            {**template, "start_page": 3},
        ]
        source["plan"]["pending_ranges"] = [{
            "start_page": 2, "end_page": 2, "reason": "Resolve this page.",
        }]
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 2:
                value["plan_update"] = {"mode": "patch", "scope_edits": [{
                    "replace_scope_ids": ["scope-1"],
                    "scopes": [{**template, "end_page": 2}],
                }]}
            return json.dumps(value), metadata

        result = run_evidence_review(self.reader, source, decide)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["current_plan"]["pending_ranges"],
                         source["plan"]["pending_ranges"])
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertEqual(result["plan"]["pending_ranges"], [])

    def test_unrelated_chapter_citation_does_not_resolve_later_issue(self):
        reader, source = self.make_separated_issues()
        template = source["plan"]["scopes"][0]
        source["plan"]["scopes"] = [
            {**template, "end_page": 3},
            {**template, "start_page": 4},
        ]
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 1:
                value["resolutions"][1]["evidence_block_ids"] = \
                    value["resolutions"][0]["evidence_block_ids"]
            return json.dumps(value), metadata

        result = run_evidence_review(reader, source, decide)
        feedback = calls[1]["validation_feedback"]["issues"]
        self.assertEqual(feedback[0]["code"], "unrelated_resolution_evidence")
        self.assertEqual(feedback[0]["issue_id"], "issue-2")
        self.assertEqual(result["status"], "ready_for_coverage_review")

    def test_no_questions_does_not_make_a_model_call(self):
        source = copy.deepcopy(self.source)
        source["questions"] = []
        decide = Mock(side_effect=AssertionError("Unexpected model call."))
        result = run_evidence_review(self.reader, source, decide)
        decide.assert_not_called()
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertFalse(result["semantic_coverage_verified"])

    def test_patch_that_drops_teaching_is_rejected(self):
        def decide(payload, images):
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            value["plan_update"] = {"mode": "patch", "scope_edits": [{
                "replace_scope_ids": ["scope-1"], "scopes": [],
            }]}
            return json.dumps(value), metadata

        result = run_evidence_review(self.reader, self.source, decide,
                                     limits=ReviewLimits(max_model_calls=1))
        self.assertEqual(result["status"], "needs_evidence")
        self.assertEqual(result["plan"], self.source["plan"])
        self.assertEqual(result["feedback"]["code"], "invalid_finish")
        self.assertIn("unassigned", json.dumps(result["feedback"]))

    def test_recovered_stage_six_gap_requires_real_stage_seven_assignment(self):
        """完整移交：遗漏页能进入第七步，但未补归属时仍不能提交完成。"""
        context = {
            "material": prepare_overview(self.reader, max_input_chars=100000),
            "overview": {
                "title": "Connected Topic",
                "material_style": "workshop",
                "document_goal": "Understand one connected learning goal.",
                "organization": "explore_structure",
                "organization_reason": "Compare provisional broad scopes.",
                "anchors": [], "next_reads": [],
            },
        }
        template = self.source["plan"]["scopes"][0]
        partial = copy.deepcopy(self.source["plan"])
        partial["scopes"] = [
            {**template, "end_page": 1},
            {**template, "start_page": 3},
        ]
        stage_six = generate_candidates(
            context, Mock(return_value=(json.dumps(partial), {"finish_reason": "stop"})),
        )
        self.assertEqual(stage_six["status"], "needs_scope_review")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "request.json").write_text(
                json.dumps({"candidate_input": context}), encoding="utf-8",
            )
            (root / "candidates.json").write_text(json.dumps({
                "stage": "unit_candidates", "status": stage_six["status"],
                "request": {"user_id": 6, "course_id": 4, "document_id": 7},
                "result": stage_six,
            }), encoding="utf-8")
            source = load_candidate_input(self.reader, root / "candidates.json")

        self.assertEqual(len(source["questions"]), 1)
        self.assertEqual(source["questions"][0]["page_numbers"], [2])
        calls = []

        def decide(payload, images):
            calls.append(payload)
            raw, metadata = finish_response(payload, images)
            value = json.loads(raw)
            if len(calls) == 2:
                value["plan_update"] = {"mode": "patch", "scope_edits": [{
                    "replace_scope_ids": ["scope-1"],
                    "scopes": [{**template, "end_page": 2}],
                }]}
            return json.dumps(value), metadata

        result = run_evidence_review(self.reader, source, decide)
        self.assertEqual(len(calls), 2)
        self.assertIn("unassigned_pages", json.dumps(calls[1]["validation_feedback"]))
        self.assertEqual(result["status"], "ready_for_coverage_review")
        self.assertEqual(result["plan"]["scopes"][0]["end_page"], 2)
        self.assertEqual(result["plan"]["pending_ranges"], [])
        self.assertFalse(result["ready_for_practice"])
        self.assertFalse(result["semantic_coverage_verified"])


if __name__ == "__main__":
    unittest.main()
