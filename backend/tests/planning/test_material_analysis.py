import json
import unittest
from dataclasses import replace
from unittest.mock import Mock

from db.material_pages import MaterialPage
from planning.material_analysis import MaterialAnalysisError, analyze_materials


def make_pages(*numbers: int, document_id: int = 7) -> list[MaterialPage]:
    return [
        MaterialPage(
            document_id=document_id,
            filename=f"lecture-{document_id}.pdf",
            page_number=number,
            chapter="Object-Oriented Programming",
            body=f"Example lecture content for page {number}.",
        )
        for number in numbers
    ]


def submit(*numbers: int) -> str:
    return json.dumps(
        {
            "action": "submit_units",
            "units": [
                {
                    "title": "Encapsulation",
                    "concepts": ["Classes", "Private fields"],
                    "page_numbers": list(numbers),
                    "estimated_minutes": 30,
                }
            ],
        }
    )


class MaterialAnalysisTest(unittest.TestCase):
    def test_model_can_request_more_pages_before_submitting(self):
        decide = Mock(
            side_effect=[
                ('{"action": "read_more"}', {"total_tokens": 80}),
                (submit(1, 2, 3, 4, 5), {"total_tokens": 120}),
            ]
        )

        result = analyze_materials(make_pages(1, 2, 3, 4, 5), decide)

        first_context = decide.call_args_list[0].args[0]
        second_context = decide.call_args_list[1].args[0]
        self.assertEqual([p["page_number"] for p in first_context["pages"]], [1, 2, 3])
        self.assertEqual(
            [p["page_number"] for p in second_context["pages"]], [1, 2, 3, 4, 5]
        )
        self.assertEqual(result.trace[0]["added_pages"], [4, 5])
        self.assertEqual(result.units[0].page_numbers, (1, 2, 3, 4, 5))

    def test_partial_submission_leaves_the_remaining_pages_for_the_next_call(self):
        decide = Mock(side_effect=[(submit(1, 2), None), (submit(3, 4), None)])

        result = analyze_materials(make_pages(1, 2, 3, 4), decide)

        self.assertEqual([unit.page_numbers for unit in result.units], [(1, 2), (3, 4)])
        self.assertEqual([unit.id for unit in result.units], ["7:1", "7:2"])

    def test_invented_page_is_rejected_and_can_be_corrected(self):
        decide = Mock(side_effect=[(submit(1, 2), None), (submit(1, 3), None)])

        result = analyze_materials(make_pages(1, 3), decide)

        # 第 2 页没有可用正文。原始页码 1 和 3 仍然可以组成一个单元。
        self.assertEqual(result.units[0].page_numbers, (1, 3))
        self.assertEqual(result.trace[0]["action"], "rejected")
        retry_context = decide.call_args.args[0]
        self.assertEqual(retry_context["allowed_page_numbers"], [1, 3])
        self.assertIn("[1, 3]", retry_context["validation_feedback"])
        self.assertEqual(
            result.trace[0]["submitted_unit_refs"],
            [{"page_numbers": [1, 2], "continues_previous": None}],
        )

    def test_continuation_starts_at_first_allowed_page_after_correction(self):
        middle = json.loads(submit(18, 19, 20))
        middle["units"][0]["continues_previous"] = True
        invalid = json.loads(submit(22, 23))
        invalid["units"][0]["continues_previous"] = True
        corrected = json.loads(submit(21))
        corrected["units"][0]["continues_previous"] = True
        corrected["units"].extend(json.loads(submit(22, 23))["units"])
        decide = Mock(
            side_effect=[
                (submit(15, 16, 17), None),
                (json.dumps(middle), None),
                (json.dumps(invalid), None),
                (json.dumps(corrected), None),
            ]
        )

        result = analyze_materials(make_pages(*range(15, 24)), decide)

        retry_context = decide.call_args.args[0]
        self.assertEqual(retry_context["allowed_page_numbers"], [21, 22, 23])
        self.assertEqual(retry_context["continuation_start_page"], 21)
        self.assertIn("start on page 21", retry_context["validation_feedback"])
        self.assertEqual(
            result.trace[2]["submitted_unit_refs"],
            [{"page_numbers": [22, 23], "continues_previous": True}],
        )
        self.assertEqual(result.units[0].page_numbers, tuple(range(15, 22)))
        self.assertEqual(result.units[1].page_numbers, (22, 23))

    def test_continuation_without_new_concepts_retains_the_existing_unit(self):
        continuation = json.loads(submit(13))
        continuation["units"][0].update(concepts=[], continues_previous=True)
        continuation["units"].extend(json.loads(submit(14, 15))["units"])
        decide = Mock(
            side_effect=[(submit(10, 11, 12), None), (json.dumps(continuation), None)]
        )

        result = analyze_materials(make_pages(*range(10, 16)), decide)

        self.assertEqual(decide.call_count, 2)
        self.assertEqual(result.units[0].page_numbers, (10, 11, 12, 13))
        self.assertEqual(result.units[0].concepts, ("Classes", "Private fields"))
        self.assertEqual(result.units[0].estimated_minutes, 60)
        self.assertEqual(result.units[1].page_numbers, (14, 15))

    def test_new_unit_concept_errors_identify_the_field_and_group(self):
        cases = [
            ([], "must have 1 to 8 entries. Received 0"),
            ("Inheritance", "must be a JSON array of strings"),
            ([" "], "item 1 must be a string of 1 to 100 characters"),
        ]
        for concepts, message in cases:
            with self.subTest(concepts=concepts):
                invalid = json.loads(submit(13))
                invalid["units"].extend(json.loads(submit(14, 15))["units"])
                corrected = json.dumps(invalid)
                invalid["units"][1]["concepts"] = concepts
                decide = Mock(side_effect=[(json.dumps(invalid), None), (corrected, None)])

                result = analyze_materials(make_pages(13, 14, 15), decide)

                feedback = decide.call_args.args[0]["validation_feedback"]
                self.assertEqual(result.trace[0]["reason"], feedback)
                self.assertIn(f"Unit 2 concepts {message}", feedback)
                self.assertEqual(result.units[1].page_numbers, (14, 15))

    def test_section_heading_at_window_edge_is_sent_with_teaching_content(self):
        pages = make_pages(10, 11, 12, 13, 14)
        pages[2] = replace(pages[2], body="## Object-Oriented Programming")
        decide = Mock(side_effect=[(submit(10, 11), None), (submit(12, 13, 14), None)])

        result = analyze_materials(pages, decide)

        first_context = decide.call_args_list[0].args[0]
        second_context = decide.call_args_list[1].args[0]
        self.assertEqual(first_context["allowed_page_numbers"], [10, 11, 12, 13])
        self.assertEqual(second_context["allowed_page_numbers"], [12, 13, 14])
        self.assertEqual(set(second_context["open_unit"]), {"title", "concepts"})
        self.assertEqual([unit.page_numbers for unit in result.units], [(10, 11), (12, 13, 14)])

    def test_agenda_and_dividers_form_two_section_reviews(self):
        pages = make_pages(*range(1, 8))
        pages[0] = replace(pages[0], body="## Java and OOP Revision")
        pages[1] = replace(pages[1], body="## Agenda\n\n- Java syntax\n- OOP")
        pages[2] = replace(pages[2], body="## Java Syntax")
        pages[5] = replace(pages[5], body="## Object-Oriented Programming")
        concepts = [f"Concept {number}" for number in range(1, 11)]
        concepts[1] = "A long concept label " * 6 + "with details"
        response = json.dumps(
            {"action": "submit_units", "units": [{"concepts": concepts, "estimated_minutes": 3}]}
        )
        decide = Mock(return_value=(response, None))

        result = analyze_materials(pages, decide)

        self.assertEqual([unit.title for unit in result.units], ["Java Syntax", "Object-Oriented Programming"])
        self.assertEqual([unit.page_numbers for unit in result.units], [(1, 2, 3, 4, 5), (6, 7)])
        self.assertEqual([unit.id for unit in result.units], ["7:1", "7:2"])
        self.assertEqual([unit.estimated_minutes for unit in result.units], [3, 3])
        self.assertEqual(result.units[1].concepts, tuple(concepts))
        self.assertEqual(decide.call_args_list[0].args[0]["orientation_page_numbers"], [1, 2, 3])
        self.assertEqual(decide.call_args_list[0].args[0]["typical_review_minutes"], 4)

    def test_short_review_can_take_less_than_five_minutes(self):
        response = json.loads(submit(1, 2))
        response["units"][0]["estimated_minutes"] = 3
        decide = Mock(return_value=(json.dumps(response), None))

        result = analyze_materials(make_pages(1, 2), decide)

        self.assertEqual(result.units[0].estimated_minutes, 3)

    def test_skipping_the_first_page_is_rejected(self):
        decide = Mock(side_effect=[(submit(2, 3), None), (submit(1, 2, 3), None)])

        result = analyze_materials(make_pages(1, 2, 3), decide)

        self.assertEqual(result.trace[0]["action"], "rejected")
        self.assertEqual(result.units[0].page_numbers, (1, 2, 3))

    def test_trailing_chapter_marker_is_skipped_without_using_a_model_call(self):
        teaching, marker = make_pages(25, 26)
        marker = replace(marker, body="## Chapter 3.")
        decide = Mock(return_value=(submit(25), None))

        result = analyze_materials([teaching, marker], decide, max_calls=1)

        decide.assert_called_once()
        self.assertEqual(decide.call_args.args[0]["allowed_page_numbers"], [25])
        self.assertTrue(decide.call_args.args[0]["at_document_end"])
        self.assertEqual(result.units[0].page_numbers, (25,))
        self.assertEqual(result.trace[0]["action"], "skip_non_instructional_pages")
        self.assertEqual(result.trace[0]["pages"], [26])

    def test_last_page_with_teaching_content_is_required_on_retry(self):
        teaching, exercise = make_pages(25, 26)
        exercise = replace(exercise, body="## End of Chapter 3\n\nExplain why static fields are shared.")
        decide = Mock(side_effect=[(submit(25), None), (submit(25, 26), None)])

        result = analyze_materials([teaching, exercise], decide)

        retry_context = decide.call_args.args[0]
        self.assertEqual(retry_context["allowed_page_numbers"], [25, 26])
        self.assertIn("Missing page numbers are [26]", retry_context["validation_feedback"])
        self.assertEqual(result.units[0].page_numbers, (25, 26))

    def test_document_with_only_a_closing_marker_has_no_learning_plan(self):
        marker = replace(make_pages(26)[0], body="## End\n\nChapter 3.")
        decide = Mock()

        with self.assertRaisesRegex(MaterialAnalysisError, "No instructional pages"):
            analyze_materials([marker], decide)

        decide.assert_not_called()

    def test_two_invalid_responses_stop_with_a_trace(self):
        decide = Mock(return_value=("invalid JSON", None))

        with self.assertRaises(MaterialAnalysisError) as error:
            analyze_materials(make_pages(1, 2), decide)

        self.assertEqual(decide.call_count, 2)
        self.assertEqual(
            [event["action"] for event in error.exception.trace],
            ["rejected", "rejected"],
        )

    def test_call_limit_stops_before_a_second_model_call(self):
        decide = Mock(return_value=('{"action": "read_more"}', None))

        with self.assertRaisesRegex(MaterialAnalysisError, "model call limit"):
            analyze_materials(make_pages(1, 2, 3, 4), decide, max_calls=1)

        self.assertEqual(decide.call_count, 1)

    def test_each_document_keeps_its_own_page_numbers_and_id(self):
        decide = Mock(return_value=(submit(1), None))
        pages = make_pages(1, document_id=7) + make_pages(1, document_id=8)

        result = analyze_materials(pages, decide)

        self.assertEqual([unit.id for unit in result.units], ["7:1", "8:1"])
        self.assertEqual([unit.document_id for unit in result.units], [7, 8])

    def test_model_connection_error_stops_and_records_the_failure(self):
        decide = Mock(side_effect=TimeoutError("test timeout"))

        with self.assertRaises(MaterialAnalysisError) as error:
            analyze_materials(make_pages(1), decide)

        self.assertEqual(decide.call_count, 1)
        self.assertEqual(error.exception.trace[0]["action"], "model_error")