from db.connection import connect


def list_courses(user_id: int) -> list[dict]:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.name, c.student_brief, c.created_at,
                       COUNT(d.id) AS document_count
                FROM courses c
                LEFT JOIN documents d
                  ON d.course_id = c.id AND d.ingest_status = 'complete'
                WHERE c.user_id = %s
                GROUP BY c.id, c.name, c.student_brief, c.created_at
                ORDER BY c.id DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()
    return [_course_summary(row) for row in rows]


def create_course(user_id: int, name: str, student_brief: str) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO courses (user_id, name, student_brief)
                VALUES (%s, %s, %s)
                """,
                (user_id, name, student_brief),
            )
            course_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO study_plans (course_id, student_brief, status)
                VALUES (%s, %s, 'draft')
                """,
                (course_id, student_brief),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return get_course(user_id, course_id)


def get_course(user_id: int, course_id: int) -> dict | None:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, student_brief, created_at
                FROM courses
                WHERE id = %s AND user_id = %s
                """,
                (course_id, user_id),
            )
            course = cursor.fetchone()
            if course is None:
                return None
            cursor.execute(
                """
                SELECT d.id, d.filename, d.ingest_status,
                       COUNT(p.id) AS page_count,
                       SUM(CASE WHEN p.usable = 1 THEN 1 ELSE 0 END) AS usable_page_count
                FROM documents d
                LEFT JOIN pages p ON p.document_id = d.id
                WHERE d.course_id = %s
                GROUP BY d.id, d.filename, d.ingest_status
                ORDER BY d.id
                """,
                (course_id,),
            )
            documents = cursor.fetchall()
    finally:
        connection.close()
    return {
        "id": course["id"],
        "name": course["name"],
        "student_brief": course["student_brief"],
        "created_at": _time(course["created_at"]),
        "documents": [
            {
                "id": row["id"],
                "filename": row["filename"],
                "ingest_status": row["ingest_status"],
                "page_count": int(row["page_count"] or 0),
                "usable_page_count": int(row["usable_page_count"] or 0),
            }
            for row in documents
        ],
    }


def owns_document(user_id: int, course_id: int, document_id: int) -> bool:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id
                FROM documents d
                JOIN courses c ON c.id = d.course_id
                WHERE d.id = %s AND d.course_id = %s AND c.user_id = %s
                """,
                (document_id, course_id, user_id),
            )
            return cursor.fetchone() is not None
    finally:
        connection.close()


def delete_document_rows(document_id: int) -> None:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM pages WHERE document_id = %s", (document_id,))
            cursor.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _course_summary(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "student_brief": row["student_brief"],
        "created_at": _time(row["created_at"]),
        "document_count": int(row["document_count"] or 0),
    }


def _time(value) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")
