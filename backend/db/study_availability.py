"""按账户读取和保存每周学习时间。"""

import json

from db.connection import connect
from planning.inputs import StudyAvailability


def load_study_availability(user_id: int) -> StudyAvailability | None:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT weekday_minutes FROM study_availability WHERE user_id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    # MySQL 保存的是 JSON 数组，转换为现有输入模块使用的元组。
    return StudyAvailability(tuple(json.loads(row["weekday_minutes"])))


def save_study_availability(user_id: int, settings: StudyAvailability) -> None:
    encoded = json.dumps(settings.weekday_minutes)
    connection = connect()

    try:
        with connection.cursor() as cursor:
            # 第一次保存时插入。之后点击 Save 更新同一账户的那一行。
            cursor.execute(
                """
                INSERT INTO study_availability (user_id, weekday_minutes)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE weekday_minutes = %s
                """,
                (user_id, encoded, encoded),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()