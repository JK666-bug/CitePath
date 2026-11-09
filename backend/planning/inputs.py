"""把已保存的课程设置和账户时间转换成排程器需要的输入。"""
import json
from dataclasses import dataclass
from datetime import date, timedelta

from planning.scheduler import PlanningRules


class PlanningInputError(ValueError):
    """用稳定的错误代码区分需要补充的条件。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CourseBrief:
    deadline: date | None
    early_days: int
    note: str


@dataclass(frozen=True)
class StudyAvailability:
    # 星期一到星期日，每项是当天所有课程共享的分钟数。
    weekday_minutes: tuple[int, ...] = (480,) * 7

    def __post_init__(self) -> None:
        if len(self.weekday_minutes) != 7 or any(
            type(minutes) is not int or not 0 <= minutes <= 1440
            for minutes in self.weekday_minutes
        ):
            raise PlanningInputError(
                "invalid_availability",
                "Enter seven daily values between 0 and 1,440 minutes.",
            )

    @property
    def weekly_minutes(self) -> int:
        return sum(self.weekday_minutes)


@dataclass(frozen=True)
class ScheduleInputs:
    rules: PlanningRules
    daily_capacity: dict[date, int]


def decode_course_brief(raw: str) -> CourseBrief:
    """读取当前前端的课程设置，返回截止日期、提早完成天数和备注。仅要求格式正确，不检查逻辑合理性。"""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None

    # 和前端一样，通过课程日期字段识别设置。旧的纯文本备注会保留原文。
    if not isinstance(value, dict) or (
        "deadline" not in value and "earlyDays" not in value
    ):
        return CourseBrief(deadline=None, early_days=0, note=raw)

    deadline_text = value.get("deadline")
    try:
        deadline = (
            date.fromisoformat(deadline_text)
            if isinstance(deadline_text, str)
            else None
        )
    except ValueError:
        deadline = None
    if deadline is None or deadline.isoformat() != deadline_text:
        raise PlanningInputError("invalid_deadline", "Enter a valid learning deadline.")

    # 早完成天数必须是非负整数，备注是字符串。
    early_days = value.get("earlyDays")
    note = value.get("note", "")
    if type(early_days) is not int or early_days < 0 or not isinstance(note, str):
        raise PlanningInputError(
            "invalid_course_brief", "Check the early finish days and course note."
        )

    return CourseBrief(deadline=deadline, early_days=early_days, note=note)


def build_schedule_inputs(
    brief: CourseBrief,#包含截止日期，提早日期和备注
    start_date: date,
    *,
    availability: StudyAvailability | None = None,#系统设置的可学习时长e
    exam_date: date | None = None,
    blocked_dates: frozenset[date] = frozenset(),
) -> ScheduleInputs:
    """exam_date 是已确认、适用于本次学习目标的考试日期。"""
    # 先检查截止日期和考试日期是否合理，再把账户可用时间转换成每天的容量表。
    deadline = brief.deadline
    if deadline is None:
        raise PlanningInputError("missing_deadline", "Set a learning deadline first.")
    if deadline < start_date:
        raise PlanningInputError("expired_deadline", "Choose a new learning deadline.")

    if exam_date is not None and exam_date <= start_date:
        # 由上层确认是否继续学习。确认后可不传历史考试日期。
        raise PlanningInputError(
            "exam_has_no_study_window",
            "Confirm whether to keep studying with the course learning deadline.",
        )
    # 如果考试日期在截止日期之后，排程器会忽略它。考试日期在截止日期之前时，排程器会把考试前一天作为最后可学习日。
    last_day = min(deadline, exam_date - timedelta(days=1)) if exam_date else deadline
    if not 0 <= brief.early_days <= (deadline - start_date).days:
        raise PlanningInputError(
            "invalid_target_date", "Choose a target finish date on or after the start date."
        )
    # 目标日是截止日期前的第 N 天，N 是提早完成天数。排程器会把目标日作为可移动任务的最后可学习日。
    settings = availability if availability is not None else StudyAvailability()
    if settings.weekly_minutes == 0:
        raise PlanningInputError(
            "no_study_time", "Set some study time in Study availability."
        )

    # 容量表保留到硬截止日。排程器会用目标日限制可移动任务，
    # 也能检查目标日之后、硬截止日之前的固定任务。
    daily_capacity: dict[date, int] = {}
    for offset in range((last_day - start_date).days + 1):
        day = start_date + timedelta(days=offset)
        daily_capacity[day] = settings.weekday_minutes[day.weekday()]
    
    rules = PlanningRules(
        start_date=start_date,
        deadline=deadline,
        weekly_minutes=settings.weekly_minutes,
        early_days=brief.early_days,
        exam_date=exam_date,
        blocked_dates=blocked_dates,
    )
    return ScheduleInputs(rules=rules, daily_capacity=daily_capacity)
