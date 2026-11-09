import unittest
from datetime import date

from planning.scheduler import PlanningRules, StudySession, StudyTask, schedule


def nov(day: int) -> date:
    """统一测试日期，让每个案例更容易读。"""
    return date(2026, 11, day)


class PlanningSchedulerTest(unittest.TestCase):
    def test_carryover_skips_blocked_day_and_exam_day(self):
        # 10 日没学完。11 日不能学，13 日考试，只能使用 12 日。
        rules = PlanningRules(
            start_date=nov(11),
            deadline=nov(16),
            weekly_minutes=180,
            exam_date=nov(13),
            blocked_dates=frozenset({nov(11)}),
        )
        result = schedule(
            rules,
            [StudyTask("ma-cross", 25)],
            {nov(11): 60, nov(12): 30, nov(13): 60},
        )

        self.assertEqual(result.last_study_date, nov(12))
        self.assertEqual(result.sessions, (StudySession("ma-cross", nov(12), 25, False),))
        self.assertTrue(result.meets_target)

    def test_fixed_task_reserves_capacity_before_flexible_task(self):
        # 即使可移动任务在输入列表中更靠前，固定任务仍先拿到 10 日的容量。
        rules = PlanningRules(nov(10), nov(12), 180)
        result = schedule(
            rules,
            [StudyTask("reading", 35), StudyTask("fixed", 40, fixed_date=nov(10))],
            {nov(10): 40, nov(12): 60},
        )

        self.assertEqual(
            result.sessions,
            (
                StudySession("fixed", nov(10), 40, True),
                StudySession("reading", nov(12), 35, False),
            ),
        )

    def test_fixed_task_conflicting_with_blocked_day_is_reported(self):
        # 11 日既禁排又有固定任务。12 日有空也不能擅自改日期。
        rules = PlanningRules(nov(10), nov(12), 180, blocked_dates=frozenset({nov(11)}))
        result = schedule(
            rules,
            [StudyTask("fixed", 40, fixed_date=nov(11))],
            {nov(11): 60, nov(12): 60},
        )

        self.assertEqual(result.sessions, ())
        self.assertEqual(result.unscheduled[0].reason, "fixed_date_conflict")
        self.assertEqual(result.unscheduled[0].minutes, 40)
        self.assertFalse(result.meets_target)

    def test_weekly_budget_includes_minutes_already_booked(self):
        # 9 日和 10 日同一周。9 日已用 40 分钟，本周只剩 20 分钟。
        # 16 日进入新一周，可以安排任务剩下的 30 分钟。
        rules = PlanningRules(nov(10), nov(16), 60)
        result = schedule(
            rules,
            [StudyTask("read", 50)],
            {nov(10): 60, nov(16): 60},
            booked_minutes={nov(9): 40},
        )

        self.assertEqual(
            result.sessions,
            (
                StudySession("read", nov(10), 20, False),
                StudySession("read", nov(16), 30, False),
            ),
        )
        self.assertTrue(result.meets_target)

    def test_insufficient_capacity_preserves_remaining_minutes(self):
        # 需要 45 分钟，考试前只有 30 分钟。15 分钟应保留在未安排结果中。
        rules = PlanningRules(nov(11), nov(13), 180, exam_date=nov(13))
        result = schedule(
            rules,
            [StudyTask("review", 45)],
            {nov(12): 30, nov(13): 60},
        )

        self.assertEqual(result.sessions, (StudySession("review", nov(12), 30, False),))
        self.assertEqual(result.unscheduled[0].minutes, 15)
        self.assertFalse(result.meets_target)

    def test_early_target_keeps_later_fixed_task_on_its_date(self):
        # 目标日是 12 日，用户明确指定 13 日的固定任务仍保留在 13 日。
        rules = PlanningRules(nov(10), nov(14), 180, early_days=2)
        result = schedule(
            rules,
            [StudyTask("read", 60), StudyTask("fixed", 20, fixed_date=nov(13))],
            {nov(12): 30, nov(13): 60},
        )

        self.assertEqual(result.target_date, nov(12))
        self.assertEqual(
            result.sessions,
            (
                StudySession("read", nov(12), 30, False),
                StudySession("fixed", nov(13), 20, True),
            ),
        )
        self.assertEqual(result.unscheduled[0].minutes, 30)
        self.assertFalse(result.meets_target)

    def test_duplicate_task_ids_are_rejected(self):
        # 两个输入任务共用一个 ID，会让后续进度记录无法区分。
        rules = PlanningRules(nov(10), nov(12), 180)
        with self.assertRaisesRegex(ValueError, "Task IDs must be unique"):
            schedule(rules, [StudyTask("ma", 15), StudyTask("ma", 30)], {nov(10): 60})