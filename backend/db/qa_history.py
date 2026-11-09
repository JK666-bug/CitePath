"""按登录账号和课程读取已保存的问答，不重新调用模型。"""

import json

from db.connection import connect
from db.courses import get_course


def load_qa_history(
    user_id: int,
    course_id: int,
    *,
    before_id: int | None = None,
    limit: int = 30,
) -> dict:
    if not 1 <= limit <= 100:
        raise ValueError("History page size must be between 1 and 100.")

    course = get_course(user_id, course_id)
    if course is None:
        raise LookupError("Course not found")

    connection = connect()
    try:
        with connection.cursor() as cursor:
            # 再次约束课程归属与记录账号，权限不依赖前端筛选。
            # 多读一条，判断是否还有更早的记录。
            cursor.execute(
                """
                SELECT q.id, q.question, q.answer, q.cited_pages, q.refused
                FROM qa_records AS q
                JOIN courses AS c ON c.id = q.course_id
                WHERE q.course_id = %s
                  AND q.user_id = %s
                  AND c.user_id = %s
                  AND (%s IS NULL OR q.id < %s)
                ORDER BY q.id DESC
                LIMIT %s
                """,
                (course_id, user_id, user_id, before_id, before_id, limit + 1),
            )
            rows = list(cursor.fetchall())
    finally:
        connection.close()

    has_more = len(rows) > limit
    rows = rows[:limit]
    filenames = {
        material["id"]: material["filename"]
        for material in course["documents"]
    }

    return {
        "records": [
            {
                "qa_id": row["id"],
                "course_id": course_id,
                "course_name": course["name"],
                "question": row["question"],
                "answer": row["answer"],
                "cited_pages": (
                    [] if row["refused"]
                    else _restore_sources(row["cited_pages"], filenames)
                ),
                "refused": bool(row["refused"]),
            }
            for row in rows
        ],
        "next_before_id": rows[-1]["id"] if has_more else None,
    }


def _restore_sources(raw: str | None, filenames: dict[int, str]) -> list[dict]:
    """历史记录保存文件 ID 和页码，读取时补回当前文件名。"""

    items = json.loads(raw) if raw else []
    if not isinstance(items, list):
        raise ValueError("Invalid stored source references.")

    sources = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid stored source references.")

        document_id = item.get("document_id")
        page_number = item.get("page_number")
        if (
            type(document_id) is not int
            or type(page_number) is not int
            or document_id <= 0
            or page_number <= 0
        ):
            raise ValueError("Invalid stored source references.")

        sources.append(
            {
                "document_id": document_id,
                "filename": filenames.get(document_id, "Removed material"),
                "page_number": page_number,
            }
        )

    return sources
