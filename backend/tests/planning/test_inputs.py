import json
import unittest
from datetime import date

from planning.inputs import (
    PlanningInputError,
    StudyAvailability,
    build_schedule_inputs,
    decode_course_brief,
)
from planning.scheduler import StudyTask, schedule


def course_json(**changes) -> str:
    """模拟现有前端保存到 student_brief 的字符串。"""
    fields = {
        "deadline": "2026-11-15",
        "earlyDays": 0,
        "note": "",
    }
    fields.update(changes)
    return json.dumps(fields, ensure_ascii=False)


class PlanningInputsTest(unittest.TestCase):
    def test_empty_note_uses_form_dates_and_account_defaults(self):
        brief = decode_course_brief(course_json())
        start = date(2026, 11, 9)

        inputs = build_schedule_inputs(brief, start)

        self.assertEqual(brief.note, "")
        self.assertEqual(inputs.rules.deadline, date(2026, 11, 15))
        self.assertEqual(inputs.rules.weekly_minutes, 3360)
        self.assertEqual(inputs.daily_capacity[start], 480)

    def test_saved_course_with_a_version_tag_is_still_readable(self):
        raw = course_json(schema="citepath-course-v2", earlyDays=2, note="复习 Lecture 3")

        brief = decode_course_brief(raw)

        self.assertEqual(brief.deadline, date(2026, 11, 15))
        self.assertEqual(brief.early_days, 2)
        self.assertEqual(brief.note, "复习 Lecture 3")

    def test_preserves_background_and_goal_as_original_text(self):
        note = "我是零基础，希望能独立解释 MA 交叉策略。"
        brief = decode_course_brief(course_json(note=note))
        self.assertEqual(brief.note, note)

    def test_legacy_plain_text_requires_a_deadline_before_scheduling(self):
        brief = decode_course_brief("希望复习 Lecture 3")
        self.assertEqual(brief.note, "希望复习 Lecture 3")
        self.assertIsNone(brief.deadline)

        with self.assertRaises(PlanningInputError) as error:
            build_schedule_inputs(brief, date(2026, 11, 9))

        self.assertEqual(error.exception.code, "missing_deadline")

    def test_invalid_calendar_date_is_rejected(self):
        with self.assertRaises(PlanningInputError) as error:
            decode_course_brief(course_json(deadline="2026-11-31"))

        self.assertEqual(error.exception.code, "invalid_deadline")

    def test_user_availability_keeps_zero_day_and_weekly_sum(self):
        brief = decode_course_brief(course_json())
        settings = StudyAvailability((60, 60, 0, 60, 0, 120, 120))

        inputs = build_schedule_inputs(brief, date(2026, 11, 9), availability=settings)

        self.assertEqual(inputs.rules.weekly_minutes, 420)
        self.assertEqual(inputs.daily_capacity[date(2026, 11, 11)], 0)
        self.assertEqual(inputs.daily_capacity[date(2026, 11, 14)], 120)

    def test_all_zero_requires_setting_available_time(self):
        brief = decode_course_brief(course_json())

        with self.assertRaises(PlanningInputError) as error:
            build_schedule_inputs(
                brief, date(2026, 11, 9), availability=StudyAvailability((0,) * 7)
            )

        self.assertEqual(error.exception.code, "no_study_time")

    def test_past_exam_requires_a_decision_before_it_can_be_ignored(self):
        brief = decode_course_brief(course_json())
        start = date(2026, 11, 9)

        with self.assertRaises(PlanningInputError) as error:
            build_schedule_inputs(brief, start, exam_date=date(2026, 11, 8))

        self.assertEqual(error.exception.code, "exam_has_no_study_window")
        # 模拟上层确认继续学习后的输入。
        confirmed = build_schedule_inputs(brief, start, exam_date=None)
        self.assertEqual(confirmed.rules.deadline, date(2026, 11, 15))

    def test_confirmed_constraints_are_usable_by_the_real_scheduler(self):
        brief = decode_course_brief(course_json(note="11 日不学习，13 日期末考试。"))
        inputs = build_schedule_inputs(
            brief,
            date(2026, 11, 11),
            exam_date=date(2026, 11, 13),
            blocked_dates=frozenset({date(2026, 11, 11)}),
        )
        # 此处传入模拟的已确认条件。备注的自动解析将在下一步接入。
        result = schedule(inputs.rules, [StudyTask("ma-cross", 25)], inputs.daily_capacity)

        self.assertTrue(result.meets_target)
        self.assertEqual(len(result.sessions), 1)
        self.assertEqual(result.sessions[0].day, date(2026, 11, 12))
        self.assertEqual(result.sessions[0].minutes, 25)


if __name__ == "__main__":
    unittest.main()
