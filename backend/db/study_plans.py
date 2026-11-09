import json

from db.connection import connect
from planning.scheduler import ScheduleResult


def save_plan_version(
    user_id: int,
    course_id: int,
    result: ScheduleResult,
    *,
    expected_brief: str,
) -> int:
    # 第一版要求目标达成后才发布。容量不足或固定任务晚于目标日时，
    # 调用方应先把冲突告诉学生，再按确认后的条件重新排程。
    if not result.sessions or not result.meets_target:
        raise ValueError("Resolve the scheduling issues before saving the plan.")

    # Python date 转为 ISO 字符串，MySQL JSON 和前端都可以直接读取。
    payload = {
        "last_study_date": result.last_study_date.isoformat(),
        "target_date": result.target_date.isoformat(),
        "sessions": [
            {
                "task_id": session.task_id,
                "day": session.day.isoformat(),
                "minutes": session.minutes,
                "locked": session.locked,
            }
            for session in result.sessions
        ],
    }

    connection = connect()
    try:
        with connection.cursor() as cursor:
            # 通过课程归属校验权限。锁住计划记录，让同一课程的并发写入
            # 按顺序分配版本号。
            cursor.execute(
                """
                SELECT p.id, c.student_brief
                FROM study_plans AS p
                JOIN courses AS c ON c.id = p.course_id
                WHERE c.id = %s AND c.user_id = %s
                FOR UPDATE
                """,
                (course_id, user_id),
            )
            plan = cursor.fetchone()

            if plan is None:
                raise LookupError("Course plan not found.")

            # 排程时读到的课程设置必须和保存时一致。
            if plan["student_brief"] != expected_brief:
                raise ValueError("Course settings changed. Generate the plan again.")

            cursor.execute(
                """
                SELECT version_no, plan_data
                FROM study_plan_versions
                WHERE plan_id = %s
                ORDER BY version_no DESC
                LIMIT 1
                """,
                (plan["id"],),
            )
            latest = cursor.fetchone()

            # 连续保存同一份结果时，复用现有版本。
            if latest is not None and json.loads(latest["plan_data"]) == payload:
                version = latest["version_no"]
            else:
                version = 1 if latest is None else latest["version_no"] + 1
                cursor.execute(
                    """
                    INSERT INTO study_plan_versions (plan_id, version_no, plan_data)
                    VALUES (%s, %s, %s)
                    """,
                    (plan["id"], version, json.dumps(payload, ensure_ascii=False)),
                )

            # A regenerated plan can reuse a version and still become active again.
            cursor.execute(
                "UPDATE study_plans SET status = 'active' "
                "WHERE id = %s AND status = 'draft'",
                (plan["id"],),
            )

        # 插入版本和更新草稿状态一起提交，避免只成功一半。
        connection.commit()
        return version
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def load_plan_version(
    user_id: int,
    course_id: int,
    version: int | None = None,
) -> dict | None:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.version_no, v.plan_data
                FROM study_plan_versions AS v
                JOIN study_plans AS p ON p.id = v.plan_id
                JOIN courses AS c ON c.id = p.course_id
                WHERE c.id = %s AND c.user_id = %s
                  AND (%s IS NULL OR v.version_no = %s)
                ORDER BY v.version_no DESC
                LIMIT 1
                """,
                (course_id, user_id, version, version),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return {"version": row["version_no"], **json.loads(row["plan_data"])}
