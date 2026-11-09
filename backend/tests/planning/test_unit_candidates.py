"""分阶段候选生成测试。

不调用真实模型，不连接真实数据库。
模拟响应只验证程序行为，不证明真实切分质量。
"""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from db.material_pages import PlanningDocument, PlanningPage
from planning.document_reader import DocumentReader
from planning.material_overview import prepare_overview
from planning.unit_candidates import (
    CandidateError,
    OutputError,
    generate_candidates,
    main,
    prepare_candidate_input,
    validate_scope_draft,
    validate_scope_plan,
    validate_scope_review,
    validate_unit_content,
)


def make_reader(last_body=""):
    bodies = [
        "# Introduction\n\nBuild a complete feature.",
        "# Comparison\n\nCompare alternative approaches.",
        "# Implementation\n\nImplement and test the feature.",
        last_body,
    ]
    pages = tuple(
        PlanningPage(
            document_id=7,
            page_number=index,
            chapter_hint="Topic hint",
            body=body,
            database_usable=bool(body),
            record_present=True,
        )
        for index, body in enumerate(bodies, start=1)
    )
    return DocumentReader(
        PlanningDocument(
            user_id=6,
            course_id=4,
            course_name="Example",
            document_id=7,
            filename="workshop.pdf",
            content_hash="a" * 64,
            original_path=Path("/unused-test.pdf"),
            total_pages=4,
            pages=pages,
        )
    )


def overview_value():
    return {
        "title": "Complete Feature Workshop",
        "material_style": "workshop",
        "document_goal": "Build and test one complete feature.",
        "organization": "keep_together",
        "organization_reason": "The steps support one deliverable.",
        "anchors": [],
        "next_reads": [],
    }


def scope(start=1, end=4):
    return {
        "title": "Build the Complete Feature",
        "objective": "Compare approaches and implement the feature.",
        "start_page": start,
        "end_page": end,
        "boundary_reason": "These contents support one complete goal.",
    }


def plan(scopes=None):
    return {
        "scopes": [scope()] if scopes is None else scopes,
        "excluded_pages": [],
        "pending_ranges": [],
        "next_reads": [],
    }


def review(proposal=None):
    result = copy.deepcopy(proposal or plan())
    result["needs_scope_review"] = False
    result["review_reason"] = "Related stages support one complete goal."
    return result


def replies(*values):
    return Mock(
        side_effect=[
            (json.dumps(value), {"finish_reason": "stop"})
            for value in values
        ]
    )


class UnitCandidateTests(unittest.TestCase):

    def auxiliary(self, number=1, role="document_intro", context=None):
        return {
            "page_number": number, "role": role,
            "reason": "This page orients the whole document, without new teaching.",
            "evidence_block_ids": [self.ref(number, context)],
        }

    def test_auxiliary_pages_have_coverage_without_teaching_membership(self):
        proposal = plan([scope(2, 4)])
        proposal["auxiliary_pages"] = [self.auxiliary()]
        checked = validate_scope_plan(proposal, self.context)
        self.assertEqual(checked["auxiliary_pages"], proposal["auxiliary_pages"])
        self.assertEqual(checked["pending_ranges"], [])
        self.assertEqual(checked["excluded_pages"], [])

    def test_standalone_auxiliary_scope_must_be_removed(self):
        proposal = plan([scope(1, 3), scope(4, 4)])
        reader = make_reader("# Key Takeaways\n\nReview of the whole document.")
        context = {**self.context, "material": prepare_overview(reader, max_input_chars=100000)}
        proposal["auxiliary_pages"] = [self.auxiliary(4, "document_recap", context)]
        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(proposal, context)
        self.assertEqual(caught.exception.issue["code"], "empty_teaching_scope")
        proposal["scopes"].pop()
        self.assertEqual(validate_scope_plan(proposal, context)["pending_ranges"], [])

    def test_auxiliary_inside_bounds_is_not_sent_to_concept_extraction(self):
        proposal = plan()
        proposal["auxiliary_pages"] = [self.auxiliary(2, "document_outline")]
        decide = replies(review(proposal), self.content(3))
        result = generate_candidates(self.context, decide)
        content_payload = decide.call_args_list[1].args[0]["data"]
        self.assertEqual(content_payload["teaching_page_numbers"], [1, 3, 4])
        self.assertEqual([page["page_number"] for page in content_payload["pages"]], [1, 3, 4])
        self.assertEqual(result["units"][0]["page_numbers"], [1, 3, 4])
        self.assertNotIn(self.ref(2), result["units"][0]["page_block_ids"])
        self.assertEqual(result["auxiliary_pages"], proposal["auxiliary_pages"])

    def test_concept_cannot_use_auxiliary_as_its_teaching_evidence(self):
        with self.assertRaises(OutputError) as caught:
            validate_unit_content(self.content(2), self.context, scope(), 1,
                                  auxiliary_pages=[self.auxiliary(2, "document_outline")])
        self.assertEqual(caught.exception.issue["code"], "invalid_evidence")

    def test_auxiliary_conflicts_invalid_sources_and_duplicates_are_rejected(self):
        for change in ("excluded", "pending", "duplicate", "foreign_source", "bad_role"):
            with self.subTest(change=change):
                proposal = plan()
                proposal["auxiliary_pages"] = [self.auxiliary()]
                if change == "excluded":
                    proposal["excluded_pages"] = [{**self.auxiliary(), "role": "administrative"}]
                elif change == "pending":
                    proposal["pending_ranges"] = [{"start_page": 1, "end_page": 1, "reason": "Unresolved."}]
                    proposal["next_reads"] = [{"action": "read_pages", "page_numbers": [1], "reason": "Check."}]
                elif change == "duplicate":
                    proposal["auxiliary_pages"] *= 2
                elif change == "foreign_source":
                    proposal["auxiliary_pages"][0]["evidence_block_ids"] = [self.ref(2)]
                else:
                    proposal["auxiliary_pages"][0]["role"] = ["document_intro"]
                with self.assertRaises(OutputError):
                    validate_scope_draft(proposal, self.context)

    def test_empty_text_page_cannot_be_declared_auxiliary_without_evidence(self):
        proposal = plan([scope(1, 3)])
        proposal["auxiliary_pages"] = [{
            "page_number": 4, "role": "document_recap", "reason": "It looks empty.",
            "evidence_block_ids": [],
        }]
        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(proposal, self.context)
        self.assertEqual(caught.exception.issue["code"], "missing_evidence")

    def test_review_cannot_silently_drop_auxiliary_records(self):
        proposal = plan()
        proposal["auxiliary_pages"] = [self.auxiliary()]
        with self.assertRaises(OutputError) as caught:
            validate_scope_review(review(), self.context, proposal)
        self.assertEqual(caught.exception.issue["code"], "missing_auxiliary_dispositions")

    def test_legacy_plan_is_readable_without_guessing_auxiliary_roles(self):
        checked = validate_scope_plan(plan(), self.context)
        self.assertEqual(checked["auxiliary_pages"], [])
        self.assertEqual(checked["scopes"], plan()["scopes"])

    def test_auxiliary_hints_survive_candidate_preparation(self):
        answer = overview_value()
        answer["anchors"] = [{
            "page_number": 1, "role": "document_title", "title": "Orientation",
            "evidence_block_ids": [self.ref(1)], "reason": "Document orientation.",
            "boundary_check": None,
        }]
        saved = json.loads(self.overview_path.read_text(encoding="utf-8"))
        saved["result"]["overview"] = answer
        self.overview_path.write_text(json.dumps(saved), encoding="utf-8")
        prepared = prepare_candidate_input(self.reader, self.overview_path, max_input_chars=100000)
        hint = prepared["overview"]["auxiliary_hints"][0]
        self.assertEqual(hint["page_number"], 1)
        self.assertEqual(hint["role"], "document_title")
        self.assertEqual(prepared["overview"]["structure_evidence"], [])

    def test_exclusion_conflicts_and_missing_pages_reported_together(self):
        context = self.two_empty_page_context()

        # 第 1 页未声明；第 2 页同时被分配和排除；
        # 第 4 页无正文，却被无依据地排除。
        proposal = plan([scope(2, 3)])
        proposal["excluded_pages"] = [
            {
                "page_number": number,
                "role": "administrative",
                "evidence_block_ids": [],
                "reason": "No text was extracted.",
            }
            for number in (2, 4)
        ]

        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(proposal, context)

        issue = caught.exception.issue

        self.assertEqual(
            issue["code"],
            "plan_validation_errors",
        )

        by_code = {
            item["code"]: item
            for item in issue["issues"]
        }

        self.assertIn("invalid_exclusions", by_code)
        self.assertEqual(
            by_code["unassigned_pages"]["pages"],
            [1],
        )

        self.assertEqual(
            [
                item["page_number"]
                for item in by_code["invalid_exclusions"]["items"]
            ],
            [2, 4],
        )

    def test_retry_receives_exclusion_and_coverage_feedback(self):
        context = self.two_empty_page_context()
        context["overview"]["organization"] = "explore_structure"

        wrong = plan([scope(2, 3)])
        wrong["excluded_pages"] = [
            {
                "page_number": number,
                "role": "administrative",
                "evidence_block_ids": [],
                "reason": "No text was extracted.",
            }
            for number in (2, 4)
        ]

        corrected = plan()

        decide = replies(
            wrong,
            corrected,
            review(corrected),
            self.content(3),
        )

        result = generate_candidates(
            context,
            decide,
            max_attempts=2,
        )

        feedback = decide.call_args_list[1].args[0][
            "validation_feedback"
        ]

        self.assertEqual(
            {
                item["code"]
                for item in feedback["issue"]["issues"]
            },
            {"invalid_exclusions", "unassigned_pages"},
        )
        self.assertEqual(result["status"], "draft_ready")

    def test_review_receives_whole_document_alternative(self):
        context = copy.deepcopy(self.context)
        context["overview"]["organization"] = "explore_structure"

        fine = plan(
            [scope(number, number) for number in range(1, 5)]
        )

        decide = replies(
            fine,
            review(),
            self.content(),
        )

        result = generate_candidates(context, decide)

        review_data = decide.call_args_list[1].args[0]["data"]

        self.assertIn(
            "whole_document_alternative",
            review_data,
        )
        self.assertEqual(
            review_data["whole_document_alternative"]["candidate_goal"],
            context["overview"]["document_goal"],
        )
        self.assertEqual(len(result["units"]), 1)
    
    def assigned_pending_plan(self):
        """模拟真实失败：页面已有范围，但模型又把它写成待定。"""
        value = plan()
        value["pending_ranges"] = [{
            "start_page": 2,
            "end_page": 2,
            "reason": "Confirm whether this page belongs to the provisional goal.",
        }]
        value["next_reads"] = [{
            "action": "read_pages",
            "page_numbers": [2],
            "reason": "Review the uncertain membership using surrounding teaching.",
        }]
        return value

    def test_assigned_pending_is_preserved_as_review_request(self):
        value = self.assigned_pending_plan()
        original = copy.deepcopy(value)
        result = validate_scope_plan(value, self.context)
        self.assertEqual(value, original)
        self.assertEqual(result["scopes"], original["scopes"])
        self.assertEqual(result["pending_ranges"], [])
        self.assertEqual(result["next_reads"], original["next_reads"])
        self.assertEqual(len(result["assignment_reviews"]), 1)
        question = result["assignment_reviews"][0]
        self.assertEqual(question["reason"], original["pending_ranges"][0]["reason"])
        self.assertEqual(question["status"], "unresolved")
        self.assertEqual(question["source_scope_indexes"], [1])
        self.assertEqual(
            result["normalizations"][0]["code"], "assigned_pending_to_review"
        )
        self.assertEqual(
            result["normalizations"][0]["original_pending_range"],
            original["pending_ranges"][0],
        )

    def test_assigned_pending_without_targeted_read_is_rejected(self):
        value = self.assigned_pending_plan()
        value["next_reads"] = []
        with self.assertRaises(OutputError):
            validate_scope_plan(value, self.context)

    def test_partial_overlap_is_not_silently_normalized(self):
        value = plan([scope(1, 2)])
        value["pending_ranges"] = [{
            "start_page": 2, "end_page": 4,
            "reason": "This range is only partly assigned.",
        }]
        value["next_reads"] = [{
            "action": "read_pages", "page_numbers": [3],
            "reason": "Inspect the uncertain range.",
        }]
        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(value, self.context)
        self.assertEqual(caught.exception.issue["code"], "conflicting_pending_range")

    def test_duplicate_pending_ranges_remain_invalid(self):
        value = self.assigned_pending_plan()
        value["pending_ranges"].append(copy.deepcopy(value["pending_ranges"][0]))
        with self.assertRaises(OutputError):
            validate_scope_plan(value, self.context)

    def test_excluded_page_conflict_remains_invalid(self):
        value = self.assigned_pending_plan()
        value["excluded_pages"] = [{
            "page_number": 2,
            "role": "administrative",
            "evidence_block_ids": [self.ref(2)],
            "reason": "A contradictory exclusion.",
        }]
        with self.assertRaises(OutputError):
            validate_scope_plan(value, self.context)

    def test_truly_unassigned_pending_range_is_retained(self):
        value = plan([scope(1, 3)])
        value["pending_ranges"] = [{
            "start_page": 4, "end_page": 4,
            "reason": "This page has no membership yet.",
        }]
        value["next_reads"] = [{
            "action": "inspect_image", "page_numbers": [4],
            "reason": "Determine the visual page's membership.",
        }]
        result = validate_scope_plan(value, self.context)
        self.assertEqual(result["pending_ranges"], value["pending_ranges"])
        self.assertEqual(result["assignment_reviews"], [])
        self.assertEqual(result["normalizations"], [])

    def test_existing_overview_read_is_preserved_locally(self):
        value = self.assigned_pending_plan()
        context = copy.deepcopy(self.context)
        context["overview"]["next_reads"] = copy.deepcopy(value["next_reads"])
        value["next_reads"] = []
        result = validate_scope_plan(value, context)
        self.assertEqual(
            result["next_reads"], context["overview"]["next_reads"]
        )
        self.assertEqual(len(result["assignment_reviews"]), 1)

    def test_review_cannot_silently_erase_membership_questions(self):
        proposal = validate_scope_plan(self.assigned_pending_plan(), self.context)
        # 模型返回干净的四个数组，也不能当作解决了前序疑点。
        result = validate_scope_review(review(), self.context, proposal)
        self.assertTrue(result["needs_scope_review"])
        self.assertEqual(result["assignment_reviews"], proposal["assignment_reviews"])
        self.assertEqual(result["next_reads"], proposal["next_reads"])

    def test_unresolved_membership_hands_off_before_concept_extraction(self):
        context = copy.deepcopy(self.context)
        context["overview"]["organization"] = "explore_structure"
        raw_plan = self.assigned_pending_plan()
        decide = replies(raw_plan, review())
        progress = {}
        trace = []
        result = generate_candidates(
            context, decide, progress=progress, trace=trace
        )
        self.assertEqual(decide.call_count, 2)
        self.assertEqual([item["stage"] for item in trace], ["plan", "review"])
        self.assertEqual(result["status"], "needs_scope_review")
        self.assertEqual(result["scope_plan"]["scopes"], raw_plan["scopes"])
        self.assertEqual(result["units"], [])
        self.assertTrue(result["assignment_reviews"])
        self.assertTrue(result["next_reads"])
        self.assertFalse(result["ready_for_practice"])
        self.assertEqual(progress["stage"], "awaiting_scope_review")
        self.assertEqual(json.loads(trace[0]["raw_response"]), raw_plan)
        self.assertEqual(
            trace[0]["normalizations"][0]["code"], "assigned_pending_to_review"
        )

    def test_pending_generated_during_review_also_hands_off(self):
        value = review(self.assigned_pending_plan())
        decide = replies(value)
        result = generate_candidates(self.context, decide)
        self.assertEqual(decide.call_count, 1)
        self.assertEqual(result["status"], "needs_scope_review")
        self.assertTrue(result["assignment_reviews"])
        self.assertEqual(result["scope_plan"]["scopes"], value["scopes"])

    def setUp(self):
        self.root = Path(
            self.enterContext(tempfile.TemporaryDirectory())
        )
        self.reader = make_reader()
        material = prepare_overview(
            self.reader, max_input_chars=100_000
        )
        self.context = {
            "material": material,
            "overview": overview_value(),
        }

        self.overview_path = self.root / "overview.json"
        self.saved_request = {
            "material": {"document": material["document"]}
        }
        self.overview_path.write_text(
            json.dumps(
                {
                    "stage": "document_overview",
                    "status": "completed",
                    "request": {"user_id": 6},
                    "result": {"overview": overview_value()},
                }
            ),
            encoding="utf-8",
        )
        self.write_request()

    def write_request(self):
        (self.root / "request.json").write_text(
            json.dumps(self.saved_request),
            encoding="utf-8",
        )

    def ref(self, number, context=None):
        context = context or self.context
        return context["material"]["pages"][number - 1][
            "blocks"
        ][-1]["block_id"]

    def content(self, number=2):
        return {
            "status": "supported",
            "concepts": [
                {
                    "name": "Supported concept",
                    "evidence_block_ids": [self.ref(number)],
                }
            ],
            "reason": "The supplied teaching supports this concept.",
            "next_reads": [],
        }

    def test_keep_together_starts_with_one_scope_and_skips_planning_call(self):
        decide = replies(review(), self.content())
        trace = []

        result = generate_candidates(
            self.context, decide, trace=trace
        )

        self.assertEqual(
            [entry["stage"] for entry in trace],
            ["review", "concepts"],
        )
        self.assertEqual(decide.call_count, 2)
        self.assertEqual(len(result["units"]), 1)
        self.assertEqual(result["units"][0]["page_numbers"], [1, 2, 3, 4])
        self.assertEqual(result["units"][0]["pages_without_database_text"], [4])
        self.assertFalse(result["ready_for_practice"])

    def test_fine_proposal_can_be_merged_before_concept_extraction(self):
        context = copy.deepcopy(self.context)
        context["overview"]["organization"] = "explore_structure"
        fine = plan([scope(n, n) for n in range(1, 5)])
        decide = replies(fine, review(), self.content())

        result = generate_candidates(context, decide)

        self.assertEqual(decide.call_count, 3)
        self.assertEqual(len(result["units"]), 1)

    def test_review_cannot_increase_scope_count(self):
        more = review(plan([scope(1, 2), scope(3, 4)]))

        with self.assertRaises(OutputError) as caught:
            validate_scope_review(more, self.context, plan())

        self.assertEqual(
            caught.exception.issue["code"],
            "review_increased_scope_count",
        )

    def test_concept_payload_contains_only_current_scope_sources(self):
        first = scope(1, 2)
        second = scope(3, 4)
        reviewed = review(plan([first, second]))
        context = copy.deepcopy(self.context)
        context["overview"]["organization"] = "explore_structure"
        decide = replies(
            plan([first, second]),
            reviewed,
            self.content(2),
            self.content(3),
        )

        result = generate_candidates(context, decide)

        first_payload = decide.call_args_list[2].args[0]["data"]
        self.assertEqual(
            [page["page_number"] for page in first_payload["pages"]],
            [1, 2],
        )
        self.assertNotIn(
            self.ref(3),
            json.dumps(first_payload),
        )
        self.assertEqual(len(result["units"]), 2)

    def test_outside_reference_reports_actual_page_and_allowed_range(self):
        with self.assertRaises(OutputError) as caught:
            validate_unit_content(
                self.content(3),
                self.context,
                scope(1, 2),
                1,
            )

        issue = caught.exception.issue
        self.assertEqual(issue["code"], "invalid_evidence")
        self.assertEqual(issue["allowed_range"], [1, 2])
        self.assertEqual(
            issue["invalid_references"][0]["actual_page"], 3
        )
        self.assertIn("units[0].concepts[0]", issue["field"])

    def test_concept_retry_does_not_repeat_completed_scope_review(self):
        reviewed = review(
            {
                "scopes": [scope(1, 2)],
                "excluded_pages": [],
                "pending_ranges": [
                    {
                        "start_page": 3,
                        "end_page": 4,
                        "reason": "Remaining membership needs review.",
                    }
                ],
                "next_reads": [
                    {
                        "action": "read_pages",
                        "page_numbers": [3],
                        "reason": "Inspect the remaining scope.",
                    }
                ],
            }
        )
        decide = replies(
            reviewed,
            self.content(3),
            self.content(2),
        )
        trace = []

        result = generate_candidates(
            self.context, decide, trace=trace
        )

        self.assertEqual(
            [entry["stage"] for entry in trace],
            ["review", "concepts", "concepts"],
        )
        self.assertEqual(trace[1]["status"], "rejected")
        self.assertEqual(trace[2]["status"], "accepted")
        self.assertEqual(result["status"], "needs_evidence")

    def test_assigned_page_cannot_also_be_excluded(self):
        proposal = plan()
        proposal["excluded_pages"] = [
            {
                "page_number": 2,
                "role": "administrative",
                "evidence_block_ids": [self.ref(2)],
                "reason": "An unsupported exclusion.",
            }
        ]

        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(proposal, self.context)

        issue = caught.exception.issue
        self.assertEqual(issue["code"], "invalid_exclusions")
        self.assertEqual(issue["items"][0]["assigned_scope_indexes"], [1])

    def test_empty_text_page_cannot_be_excluded_without_evidence(self):
        proposal = plan([scope(1, 3)])
        proposal["excluded_pages"] = [
            {
                "page_number": 4,
                "role": "administrative",
                "evidence_block_ids": [],
                "reason": "No text was extracted.",
            }
        ]

        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(proposal, self.context)

        issue = caught.exception.issue
        self.assertEqual(issue["code"], "invalid_exclusions")
        self.assertFalse(issue["items"][0]["has_visible_text_blocks"])

    def test_missing_page_assignment_is_rejected(self):
        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(plan([scope(1, 3)]), self.context)

        self.assertEqual(caught.exception.issue["pages"], [4])

    def test_complete_draft_is_unchanged_by_recovery_entry(self):
        # 正常 PDF 保持原来的校验结果，不凭空增加复核问题。
        self.assertEqual(
            validate_scope_draft(plan(), self.context),
            validate_scope_plan(plan(), self.context),
        )

    def test_internal_gap_becomes_pending_without_changing_scopes(self):
        value = plan([scope(1, 1), scope(3, 4)])
        original = copy.deepcopy(value)
        result = validate_scope_draft(value, self.context)
        self.assertEqual(value, original)
        self.assertEqual(result["scopes"], original["scopes"])
        self.assertEqual(result["pending_ranges"][0]["start_page"], 2)
        self.assertEqual(result["pending_ranges"][0]["end_page"], 2)
        self.assertEqual(result["next_reads"][0]["page_numbers"], [2])
        self.assertTrue(result["needs_scope_review"])
        self.assertEqual(result["coverage_recovery"]["status"], "unresolved")
        self.assertFalse(result["coverage_recovery"]["semantic_assignment_inferred"])

    def test_leading_trailing_and_multiple_gaps_are_explicit(self):
        cases = [
            ([scope(2, 4)], [1], [(1, 1)]),
            ([scope(1, 3)], [4], [(4, 4)]),
            ([scope(1, 1), scope(3, 3)], [2, 4], [(2, 2), (4, 4)]),
        ]
        for scopes, missing, ranges in cases:
            with self.subTest(missing=missing):
                result = validate_scope_draft(plan(scopes), self.context)
                self.assertEqual(result["coverage_recovery"]["missing_page_numbers"],
                                 missing)
                self.assertEqual([
                    (item["start_page"], item["end_page"])
                    for item in result["pending_ranges"]
                ], ranges)
                # 第 4 页没有正文，也不能自动排除或猜测归属。
                self.assertEqual(result["excluded_pages"], [])

    def test_existing_pending_and_reads_survive_new_gap_recovery(self):
        value = plan([scope(1, 1), scope(3, 3)])
        value["pending_ranges"] = [{
            "start_page": 4, "end_page": 4,
            "reason": "Existing visual uncertainty.",
        }]
        value["next_reads"] = [{
            "action": "inspect_image", "page_numbers": [4],
            "reason": "Existing visual uncertainty.",
        }]
        result = validate_scope_draft(value, self.context)
        self.assertEqual(result["pending_ranges"][0], value["pending_ranges"][0])
        self.assertEqual(result["next_reads"][0], value["next_reads"][0])
        self.assertEqual(result["coverage_recovery"]["missing_page_numbers"], [2])

    def test_invalid_source_or_conflict_is_not_recovered_as_a_gap(self):
        value = plan([scope(2, 3)])
        value["excluded_pages"] = [{
            "page_number": 4, "role": "administrative",
            "evidence_block_ids": ["invented-source"],
            "reason": "Unsupported exclusion.",
        }]
        original = copy.deepcopy(value)
        with self.assertRaises(OutputError) as caught:
            validate_scope_draft(value, self.context)
        self.assertEqual(caught.exception.issue["code"], "plan_validation_errors")
        self.assertEqual(value, original)

    def test_invalid_ranges_and_empty_scope_plan_still_fail(self):
        for value in [plan([scope(0, 3)]), plan([scope(1, 3), scope(2, 4)]), plan([])]:
            with self.subTest(value=value):
                with self.assertRaises(OutputError):
                    validate_scope_draft(value, self.context)

    def test_missing_pending_read_is_not_silently_added(self):
        value = plan([scope(1, 1)])
        value["pending_ranges"] = [{
            "start_page": 3, "end_page": 4, "reason": "Unresolved teaching.",
        }]
        # 第 2 页遗漏，同时第 3–4 页已有 pending 却缺读取请求。
        # 这不满足“唯一问题是遗漏页”，不能自动放行。
        with self.assertRaises(OutputError) as caught:
            validate_scope_draft(value, self.context)
        self.assertEqual(caught.exception.issue["code"], "plan_validation_errors")

    def test_plan_gap_hands_off_without_repeating_plan_or_extracting_concepts(self):
        context = copy.deepcopy(self.context)
        context["overview"]["organization"] = "explore_structure"
        original = plan([scope(1, 1), scope(3, 4)])
        decide = replies(original)
        progress = {}
        trace = []
        result = generate_candidates(context, decide, progress=progress, trace=trace)
        self.assertEqual(decide.call_count, 1)
        self.assertEqual(progress["stage"], "awaiting_scope_review")
        self.assertEqual(result["status"], "needs_scope_review")
        self.assertEqual(result["scope_plan"]["scopes"], original["scopes"])
        self.assertEqual(result["units"], [])
        self.assertFalse(result["ready_for_practice"])
        self.assertFalse(result["semantic_coverage_verified"])
        self.assertEqual(result["coverage_recovery"]["missing_page_numbers"], [2])
        self.assertIn("missing_pages_to_pending", [
            item["code"] for item in trace[0]["normalizations"]
        ])
        self.assertEqual(json.loads(trace[0]["raw_response"]), original)

    def test_gap_introduced_during_review_also_hands_off(self):
        value = review(plan([scope(1, 3)]))
        decide = replies(value)
        result = generate_candidates(self.context, decide)
        self.assertEqual(decide.call_count, 1)
        self.assertEqual(result["status"], "needs_scope_review")
        self.assertEqual(result["coverage_recovery"]["missing_page_numbers"], [4])
        self.assertEqual(result["units"], [])

    def test_many_missing_pages_are_not_reported_as_complete(self):
        context = copy.deepcopy(self.context)
        context["material"]["document"]["total_pages"] = 100
        context["overview"]["organization"] = "explore_structure"
        result = generate_candidates(context, replies(plan([scope(1, 1)])))
        self.assertEqual(result["status"], "needs_scope_review")
        self.assertEqual(result["coverage_recovery"]["assigned_scope_page_count"], 1)
        self.assertEqual(len(result["coverage_recovery"]["missing_page_numbers"]), 99)
        self.assertEqual(result["units"], [])
        self.assertFalse(result["semantic_coverage_verified"])

    def test_overlapping_scope_interiors_are_rejected(self):
        with self.assertRaises(OutputError):
            validate_scope_plan(
                plan([scope(1, 3), scope(2, 4)]),
                self.context,
            )

    def test_shared_boundary_is_allowed_and_marked(self):
        context = copy.deepcopy(self.context)
        context["overview"]["organization"] = "explore_structure"
        proposal = plan([scope(1, 2), scope(2, 4)])
        decide = replies(
            proposal,
            review(proposal),
            self.content(2),
            self.content(3),
        )

        result = generate_candidates(context, decide)

        self.assertEqual(
            result["units"][0]["shared_boundary_pages"], [2]
        )
        self.assertFalse(result["semantic_coverage_verified"])

    def test_total_call_budget_preserves_completed_stage(self):
        decide = replies(review())
        progress = {}

        with self.assertRaises(CandidateError) as caught:
            generate_candidates(
                self.context,
                decide,
                max_calls=1,
                progress=progress,
            )

        self.assertEqual(
            caught.exception.code, "model_budget_exhausted"
        )
        self.assertIn("reviewed_plan", progress)
        self.assertEqual(progress["model_calls"], 1)
        self.assertEqual(decide.call_count, 1)

    def test_repeated_invalid_output_stops(self):
        decide = Mock(return_value=("not JSON", {}))

        with self.assertRaises(CandidateError) as caught:
            generate_candidates(
                self.context,
                decide,
                max_attempts=4,
            )

        self.assertEqual(caught.exception.code, "no_progress")
        self.assertEqual(decide.call_count, 2)

    def test_truncated_output_is_not_retried_with_same_budget(self):
        decide = Mock(
            return_value=('{"scopes":', {"finish_reason": "length"})
        )

        with self.assertRaises(CandidateError) as caught:
            generate_candidates(self.context, decide)

        self.assertEqual(
            caught.exception.code, "model_output_truncated"
        )
        self.assertEqual(decide.call_count, 1)

    def test_index_input_does_not_call_model(self):
        context = copy.deepcopy(self.context)
        context["material"]["input_mode"] = "page_index"
        decide = Mock()

        result = generate_candidates(context, decide)

        self.assertEqual(result["status"], "needs_staged_reading")
        decide.assert_not_called()

    def test_boundary_uncertainty_is_preserved_instead_of_fake_success(self):
        content = {
            "status": "needs_boundary_review",
            "concepts": [],
            "reason": "The objective needs additional neighboring teaching.",
            "next_reads": [
                {
                    "action": "read_pages",
                    "page_numbers": [3],
                    "reason": "Review the proposed boundary.",
                }
            ],
        }
        decide = replies(review(), content)

        result = generate_candidates(self.context, decide)

        self.assertEqual(result["status"], "needs_scope_review")
        self.assertEqual(result["units"][0]["concepts"], [])
        self.assertFalse(result["ready_for_practice"])

    def test_overview_requests_remain_pending(self):
        context = copy.deepcopy(self.context)
        context["overview"]["next_reads"] = [
            {
                "action": "inspect_image",
                "page_numbers": [4],
                "reason": "Resolve an earlier uncertainty.",
            }
        ]
        result = generate_candidates(
            context, replies(review(), self.content())
        )

        self.assertEqual(result["status"], "needs_evidence")
        self.assertEqual(result["next_reads"][0]["page_numbers"], [4])

    def test_wrong_document_overview_is_rejected(self):
        self.saved_request["material"]["document"]["document_id"] = 99
        self.write_request()

        with self.assertRaises(CandidateError) as caught:
            prepare_candidate_input(
                self.reader,
                self.overview_path,
                max_input_chars=100_000,
            )

        self.assertEqual(
            caught.exception.code, "overview_document_mismatch"
        )

    def test_preparation_removes_fine_anchor_list_from_planning_input(self):
        context = prepare_candidate_input(
            self.reader,
            self.overview_path,
            max_input_chars=100_000,
        )

        self.assertNotIn("anchors", context["overview"])
        self.assertEqual(
            context["overview"]["document_goal"],
            overview_value()["document_goal"],
        )

    def test_broad_structure_survives_repeated_brief_preparation(self):
        from planning.unit_candidates import _brief

        overview = overview_value()
        overview["anchors"] = [
            {
                "anchor_index": 1,
                "page_number": 1,
                "role": "major_section",
                "title": "Complete Feature",
                "evidence_block_ids": ["source-1"],
                "reason": "A supported broad scope.",
                "boundary_check": {
                    "relation_to_previous": "document_start",
                    "before_block_ids": [],
                    "scope_block_ids": ["source-1", "source-2"],
                    "scope_reason": "The teaching develops one feature.",
                },
            },
            {
                "anchor_index": 2,
                "page_number": 2,
                "role": "subtopic",
                "title": "A Local Step",
                "evidence_block_ids": ["source-2"],
                "reason": "One step within the feature.",
                "boundary_check": None,
            },
        ]
        first = _brief(overview)
        second = _brief(first)
        self.assertNotIn("anchors", first)
        self.assertEqual(len(first["structure_evidence"]), 1)
        self.assertEqual(first["structure_evidence"][0]["role"], "major_section")
        self.assertEqual(first, second)

    def test_preparation_keeps_validated_broad_structure(self):
        value = overview_value()
        value["organization"] = "major_sections"
        value["anchors"] = [
            {
                "page_number": 1,
                "role": "major_section",
                "title": "Complete Feature",
                "evidence_block_ids": [self.ref(1)],
                "reason": "The introduction establishes the feature goal.",
                "boundary_check": {
                    "relation_to_previous": "document_start",
                    "before_block_ids": [],
                    "scope_block_ids": [self.ref(1), self.ref(2)],
                    "scope_reason": "Later teaching develops the feature.",
                },
            },
        ]
        self.overview_path.write_text(json.dumps({
            "stage": "document_overview",
            "status": "completed",
            "request": {"user_id": 6},
            "result": {"overview": value},
        }))
        context = prepare_candidate_input(
            self.reader, self.overview_path, max_input_chars=100_000
        )
        hints = context["overview"]["structure_evidence"]
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["evidence_block_ids"], [self.ref(1)])
        self.assertNotIn("parent_anchor_index", hints[0])

    def two_empty_page_context(self):
        context = copy.deepcopy(self.context)
        # 第 4 页本来没有正文，再将第 2 页设成无正文。
        page = context["material"]["pages"][1]
        page["blocks"] = []
        page["database_text_status"] = "empty"
        page["database_text_chars"] = 0
        return context

    def invalid_two_page_exclusions(self):
        proposal = plan()
        proposal["excluded_pages"] = [
            {
                "page_number": number,
                "role": "administrative",
                "evidence_block_ids": [],
                "reason": "No text was extracted.",
            }
            for number in (2, 4)
        ]
        return proposal

    def test_two_exclusion_problems_are_reported_together(self):
        context = self.two_empty_page_context()
        proposal = self.invalid_two_page_exclusions()
        original = copy.deepcopy(proposal)
        with self.assertRaises(OutputError) as caught:
            validate_scope_plan(proposal, context)
        issue = caught.exception.issue
        self.assertEqual(issue["code"], "invalid_exclusions")
        self.assertEqual(
            [item["page_number"] for item in issue["items"]], [2, 4]
        )
        self.assertEqual(proposal, original)

    def test_one_retry_receives_both_exclusion_problems(self):
        context = self.two_empty_page_context()
        context["overview"]["organization"] = "explore_structure"
        corrected = plan()
        decide = replies(
            self.invalid_two_page_exclusions(), corrected,
            review(corrected), self.content(3),
        )
        trace = []
        result = generate_candidates(
            context, decide, max_attempts=2, trace=trace
        )
        feedback = decide.call_args_list[1].args[0]["validation_feedback"]
        self.assertEqual(
            [item["page_number"] for item in feedback["issue"]["items"]],
            [2, 4],
        )
        self.assertEqual(
            [entry["stage"] for entry in trace],
            ["plan", "plan", "review", "concepts"],
        )
        self.assertEqual(result["status"], "draft_ready")

    def test_cli_preparation_does_not_create_model(self):
        output = self.root / "prepare"

        with (
            patch(
                "planning.unit_candidates.open_document_reader",
                return_value=self.reader,
            ),
            patch("planning.unit_candidates.load_dotenv"),
            patch(
                "planning.unit_candidates.make_candidate_decider"
            ) as create_model,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            code = main(
                [
                    "--user-id", "6",
                    "--course-id", "4",
                    "--document-id", "7",
                    "--overview-report", str(self.overview_path),
                    "--max-input-chars", "100000",
                    "--max-output-tokens", "8000",
                    "--output-dir", str(output),
                ]
            )

        self.assertEqual(code, 0)
        create_model.assert_not_called()

        report = json.loads(
            (output / "candidates.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "prepared")


if __name__ == "__main__":
    unittest.main()
