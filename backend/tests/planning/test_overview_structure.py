"""概览结构与来源约定测试。

使用模拟响应，不调用真实模型或数据库。
验证扁平结构、来源校验和有限修正，不证明真实章节语义正确。
"""

import copy
import json
import unittest
from unittest.mock import Mock

from planning.material_overview import (
    OverviewError,
    build_overview,
    validate_overview,
)


def make_context():
    descriptions = [
        ("Introduction", "The broad foundations and connected topics."),
        ("Compare A and B", "A and B provide two approaches."),
        ("Illustration", "An example of the comparison."),
        ("Compare A, B and C", "The comparison is extended to C."),
        ("Implementation", "How to implement the approaches."),
        ("Implementation steps", "Data and execution requirements."),
        ("Summary", "A review of the earlier teaching."),
    ]
    return {
        "input_mode": "full_text",
        "document": {"total_pages": len(descriptions)},
        "pages": [
            {
                "page_number": number,
                "blocks": [
                    {"block_id": f"p{number}-h", "kind": "heading", "text": title},
                    {"block_id": f"p{number}-t", "kind": "text", "text": body},
                ],
            }
            for number, (title, body) in enumerate(descriptions, start=1)
        ],
    }


def make_answer():
    return {
        "title": "Connected Foundations",
        "material_style": "handout",
        "document_goal": "Understand related approaches and their implementation.",
        "organization": "keep_together",
        "organization_reason": "The topics support one broad learning purpose.",
        "anchors": [
            {
                "page_number": 1,
                "role": "major_section",
                "title": "Foundations",
                "evidence_block_ids": ["p1-h", "p1-t"],
                "reason": "Introduces the broad teaching scope.",
                "boundary_check": {
                    "relation_to_previous": "document_start",
                    "before_block_ids": [],
                    "scope_block_ids": ["p1-t", "p2-t"],
                    "scope_reason": "The following teaching develops the foundations.",
                },
            },
            {
                "page_number": 2,
                "role": "subtopic",
                "title": "Comparison of Approaches",
                "evidence_block_ids": ["p2-t", "p4-t"],
                "reason": "The later comparison extends the earlier one.",
                "boundary_check": None,
            },
            {
                "page_number": 5,
                "role": "subtopic",
                "title": "Implementation Requirements",
                "evidence_block_ids": ["p5-t", "p6-t"],
                "reason": "A local change within the broader teaching.",
                "boundary_check": None,
            },
            {
                "page_number": 7,
                "role": "recap",
                "title": "Document Review",
                "evidence_block_ids": ["p7-t"],
                "reason": "Consolidates earlier teaching.",
                "boundary_check": None,
            },
        ],
        "next_reads": [],
    }


def document_root_answer():
    answer = make_answer()
    answer["anchors"][0]["role"] = "document_title"
    answer["anchors"][0]["boundary_check"] = None
    return answer


def promote_implementation(answer, relation):
    anchor = answer["anchors"][2]
    anchor["role"] = "major_section"
    anchor["boundary_check"] = {
        "relation_to_previous": relation,
        "before_block_ids": ["p4-t"],
        "scope_block_ids": ["p5-t", "p6-t"],
        "scope_reason": "A claimed broad implementation scope.",
    }


class OverviewStructureTests(unittest.TestCase):
    def setUp(self):
        self.context = make_context()
        self.answer = make_answer()

    def test_flat_anchors_need_no_parent_field(self):
        result = validate_overview(self.answer, self.context)
        self.assertTrue(all(
            "parent_anchor_index" not in anchor
            for anchor in result["anchors"]
        ))
        self.assertEqual(
            [a["anchor_index"] for a in result["anchors"]], [1, 2, 3, 4]
        )

    def test_document_title_and_local_topics_are_valid(self):
        result = validate_overview(document_root_answer(), self.context)
        self.assertEqual(result["anchors"][0]["role"], "document_title")
        self.assertEqual(result["anchors"][1]["role"], "subtopic")

    def test_legacy_parent_fields_are_removed_with_audit(self):
        # 重现真实失败：局部话题指向 document_title。
        answer = document_root_answer()
        answer["anchors"][1]["parent_anchor_index"] = 1
        original = copy.deepcopy(answer)
        decide = Mock(return_value=(
            json.dumps(answer), {"finish_reason": "stop"}
        ))
        trace = []
        result = build_overview(self.context, decide, trace=trace)
        self.assertEqual(decide.call_count, 1)
        self.assertEqual(trace[0]["status"], "accepted")
        self.assertEqual(
            trace[0]["normalizations"][0]["operation"], "remove_unused_field"
        )
        self.assertEqual(answer, original)
        self.assertEqual(json.loads(trace[0]["raw_response"]), original)
        self.assertNotIn(
            "parent_anchor_index", result["overview"]["anchors"][1]
        )
        self.assertEqual(
            result["overview"]["anchors"][0]["role"], "document_title"
        )

    def test_program_assigns_anchor_indexes(self):
        self.answer["anchors"][0]["anchor_index"] = 999
        result = validate_overview(self.answer, self.context)
        self.assertEqual(result["anchors"][0]["anchor_index"], 1)

    def test_nonadjacent_local_evidence_is_preserved(self):
        result = validate_overview(self.answer, self.context)
        self.assertEqual(result["anchors"][1]["evidence_page_numbers"], [2, 4])

    def test_local_change_does_not_require_a_new_major_section(self):
        result = validate_overview(self.answer, self.context)
        self.assertEqual(result["anchors"][2]["role"], "subtopic")
        self.assertEqual(result["anchors"][3]["role"], "recap")

    def test_internal_shift_cannot_be_declared_major_section(self):
        promote_implementation(self.answer, "internal_shift")
        with self.assertRaisesRegex(ValueError, "Use subtopic"):
            validate_overview(self.answer, self.context)

    def test_recap_cannot_justify_major_section(self):
        promote_implementation(self.answer, "recap")
        with self.assertRaisesRegex(ValueError, "recap"):
            validate_overview(self.answer, self.context)

    def test_major_section_requires_boundary_evidence(self):
        self.answer["anchors"][0]["boundary_check"] = None
        with self.assertRaisesRegex(ValueError, "boundary_check"):
            validate_overview(self.answer, self.context)
    def test_heading_only_major_becomes_tentative(self):
        self.answer["anchors"][0]["boundary_check"][
            "scope_block_ids"
        ] = ["p1-h"]

        result = validate_overview(
            self.answer,
            self.context,
        )

        anchor = result["anchors"][0]

        self.assertEqual(
            anchor["role"],
            "possible_transition",
        )
        self.assertEqual(
            anchor["proposed_role"],
            "major_section",
        )
        self.assertEqual(
            anchor["evidence_status"],
            "needs_scope_confirmation",
        )
        self.assertTrue(
            result["structure_confirmation_pending"]
        )
        self.assertEqual(
            result["warnings"][0]["code"],
            "unconfirmed_major_section",
        )

        # 没有更改调用方的原始声明。
        self.assertEqual(
            self.answer["anchors"][0]["role"],
            "major_section",
        )
    def test_before_evidence_must_come_from_earlier_pages(self):
        promote_implementation(self.answer, "new_scope")
        self.answer["anchors"][2]["boundary_check"]["before_block_ids"] = ["p6-t"]
        with self.assertRaisesRegex(ValueError, "earlier pages"):
            validate_overview(self.answer, self.context)

    def test_same_page_can_have_different_local_topics(self):
        another = copy.deepcopy(self.answer["anchors"][2])
        another["title"] = "Implementation Constraints"
        self.answer["anchors"].insert(3, another)
        result = validate_overview(self.answer, self.context)
        self.assertEqual(
            sum(a["page_number"] == 5 for a in result["anchors"]), 2
        )

    def test_unsorted_anchors_are_rejected(self):
        self.answer["anchors"][1], self.answer["anchors"][2] = (
            self.answer["anchors"][2], self.answer["anchors"][1]
        )
        with self.assertRaisesRegex(ValueError, "page order"):
            validate_overview(self.answer, self.context)

    def test_anchor_needs_own_page_evidence(self):
        self.answer["anchors"][1]["evidence_block_ids"] = ["p4-t"]
        with self.assertRaisesRegex(ValueError, "own page"):
            validate_overview(self.answer, self.context)

    def test_parent_cleanup_does_not_bypass_source_validation(self):
        answer = document_root_answer()
        answer["anchors"][1]["parent_anchor_index"] = 1
        answer["anchors"][1]["evidence_block_ids"] = ["invented"]
        decide = Mock(return_value=(json.dumps(answer), {}))
        trace = []
        with self.assertRaises(OverviewError):
            build_overview(
                self.context, decide, max_attempts=1, trace=trace
            )
        self.assertEqual(trace[0]["status"], "rejected")
        self.assertTrue(trace[0]["normalizations"])

    def test_invalid_boundary_can_be_corrected_within_budget(self):
        wrong = copy.deepcopy(self.answer)
        promote_implementation(wrong, "internal_shift")
        decide = Mock(side_effect=[
            (json.dumps(wrong), {}), (json.dumps(self.answer), {})
        ])
        trace = []
        result = build_overview(
            self.context, decide, max_attempts=2, trace=trace
        )
        self.assertEqual(decide.call_count, 2)
        self.assertEqual(trace[0]["status"], "rejected")
        self.assertEqual(trace[1]["status"], "accepted")
        self.assertEqual(
            result["overview"]["anchors"][2]["role"], "subtopic"
        )

    def test_all_major_candidates_adjust_organization(self):
        self.answer["organization"] = "major_sections"
        self.answer["anchors"][0]["boundary_check"][
            "scope_block_ids"
        ] = ["p1-h"]

        result = validate_overview(
            self.answer,
            self.context,
        )

        self.assertEqual(
            result["organization"],
            "explore_structure",
        )
        self.assertEqual(
            result["proposed_organization"],
            "major_sections",
        )

    def test_normalized_overview_can_be_revalidated(self):
        self.answer["organization"] = "major_sections"
        self.answer["anchors"][0]["boundary_check"][
            "scope_block_ids"
        ] = ["p1-h"]

        first = validate_overview(
            self.answer,
            self.context,
        )
        second = validate_overview(
            first,
            self.context,
        )

        # 第六步重新读取概览时，不应丢失待确认状态。
        self.assertEqual(first, second)

    def test_tentative_conversion_does_not_hide_false_sources(self):
        self.answer["anchors"][0]["boundary_check"][
            "scope_block_ids"
        ] = ["invented"]

        with self.assertRaises(ValueError):
            validate_overview(
                self.answer,
                self.context,
            )

    def test_heading_only_output_does_not_require_another_call(self):
        self.answer["anchors"][0]["boundary_check"][
            "scope_block_ids"
        ] = ["p1-h"]

        decide = Mock(
            return_value=(
                json.dumps(self.answer),
                {"finish_reason": "stop"},
            )
        )
        trace = []

        result = build_overview(
            self.context,
            decide,
            trace=trace,
        )

        self.assertEqual(decide.call_count, 1)
        self.assertEqual(trace[0]["status"], "accepted")
        self.assertTrue(trace[0]["warnings"])
        self.assertTrue(
            result["reading_plan"]["structure_confirmation_pending"]
        )

if __name__ == "__main__":
    unittest.main()
