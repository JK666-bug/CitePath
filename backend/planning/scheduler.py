"""把已确认的学习任务分配到日期，所有时间统一使用整数分钟。"""
from collections import defaultdict # 记录每天和每周的用量，未记录的键默认是 0。
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping, Sequence


@dataclass(frozen=True) # 对象创建后，字段不能被直接重新赋值。

class PlanningRules:
    """排程所需的课程条件。"""
    start_date: date
    deadline: date
    weekly_minutes: int
    early_days: int = 0 # 比表单期限提前多少天完成，默认 0 天。
    exam_date: date | None = None
    blocked_dates: frozenset[date] = frozenset()


@dataclass(frozen=True)
class StudyTask:
    """本次需要安排的工作。补排时传入剩余分钟数。"""

    id: str
    minutes: int
    fixed_date: date | None = None


@dataclass(frozen=True)
class StudySession:
    """一个任务分配到某一天的学习时段。"""

    task_id: str
    day: date
    minutes: int
    locked: bool


@dataclass(frozen=True)
class Unscheduled:
    """无法排入日历的工作量，以及上层可以识别的原因。"""

    task_id: str
    minutes: int
    reason: str


@dataclass(frozen=True)
class ScheduleResult:
    last_study_date: date
    target_date: date
    sessions: tuple[StudySession, ...]
    unscheduled: tuple[Unscheduled, ...]

    @property
    def meets_target(self) -> bool:
        # 固定任务可能在目标日之后，但仍在硬截止日之内。
        # 本次输入的工作全部排好，且都在目标日内，才算达到目标。
        return not self.unscheduled and all(
            session.day <= self.target_date for session in self.sessions
        )


def _week_start(day: date) -> date:
    # weekday() 用 0 表示星期一。用星期一的日期作为这一周的键。
    return day - timedelta(days=day.weekday())


def schedule(
    rules: PlanningRules,
    tasks: Sequence[StudyTask],
    daily_capacity: Mapping[date, int],
    *,
    booked_minutes: Mapping[date, int] | None = None,
) -> ScheduleResult:
    """为一门课程安排本次新增或待补排的任务。

    daily_capacity 是每天的总容量，缺少某个日期等于当天容量为零。
    booked_minutes 是已完成或已保留的分钟数，不会被重新排入结果。
    tasks 中的可移动任务按传入顺序分配，调用方决定其优先级。
    """
    # 先检查输入的合理性，避免后续逻辑出错。
    if rules.weekly_minutes <= 0 or rules.early_days < 0:
        raise ValueError("Invalid weekly minutes or early days")
    if len({task.id for task in tasks}) != len(tasks):
        raise ValueError("Task IDs must be unique")
    if any(not task.id.strip() or task.minutes <= 0 for task in tasks):
        raise ValueError("Each task needs an ID and positive minutes")

    # 复制已有占用。下面的容量计算只更新本次调用里的临时记录。
    used_per_day = defaultdict(int, booked_minutes or {})
    if any(minutes < 0 for minutes in daily_capacity.values()) or any(
        minutes < 0 for minutes in used_per_day.values()
    ):
        raise ValueError("Capacity and booked minutes cannot be negative")

    # 表单期限当天可学习。考试范围内的学习任务最晚排到考试前一天。
    last_day = rules.deadline
    if rules.exam_date is not None:
        last_day = min(last_day, rules.exam_date - timedelta(days=1))

    # 提前天数以表单期限为基准，目标也不能晚于硬截止日。
    target = min(last_day, rules.deadline - timedelta(days=rules.early_days))
    
    used_per_week: dict[date, int] = defaultdict(int)
    for day, minutes in used_per_day.items():
        used_per_week[_week_start(day)] += minutes

    sessions: list[StudySession] = []
    unscheduled: list[Unscheduled] = []

    def available(day: date) -> int:
        # 每次都同时检查每日和每周的余额，取其中较小的值。
        daily_left = daily_capacity.get(day, 0) - used_per_day[day]
        weekly_left = rules.weekly_minutes - used_per_week[_week_start(day)]
        return max(0, min(daily_left, weekly_left))

    def add_session(task: StudyTask, day: date, minutes: int, locked: bool) -> None:
        # 写入候选时段时，立即更新两种预算，后续任务才能看到余额。
        sessions.append(StudySession(task.id, day, minutes, locked))
        used_per_day[day] += minutes
        used_per_week[_week_start(day)] += minutes

    # 先给固定任务预留容量，避免可移动任务抢占同一天。
    for task in tasks:
        day = task.fixed_date
        if day is None:
            continue
        if (
            not rules.start_date <= day <= last_day
            or day in rules.blocked_dates
            or available(day) < task.minutes
        ):
            unscheduled.append(Unscheduled(task.id, task.minutes, "fixed_date_conflict"))
        else:
            add_session(task, day, task.minutes, locked=True)

    eligible_dates = sorted(
        day for day in daily_capacity
        if rules.start_date <= day <= target and day not in rules.blocked_dates
    )

    # 可移动任务从最早的可用日开始。一个任务的分钟数可以分到多天。
    for task in tasks:
        if task.fixed_date is not None:
            continue
        remaining = task.minutes
        for day in eligible_dates:
            minutes = min(remaining, available(day))
            if minutes:
                add_session(task, day, minutes, locked=False)
                remaining -= minutes
            if remaining == 0:
                break

        # 保留确切的缺口，由上层决定是否询问用户调整条件。
        if remaining:
            unscheduled.append(
                Unscheduled(task.id, remaining, "insufficient_capacity_before_target")
            )

    sessions.sort(key=lambda session: session.day)
    return ScheduleResult(last_day, target, tuple(sessions), tuple(unscheduled))