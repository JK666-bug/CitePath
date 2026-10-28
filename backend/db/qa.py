import json

from db.connection import connect


def load_page_bodies(pairs: list[tuple[int, int]]) -> dict[tuple[int, int], dict]:
    if not pairs:
        return {}
    clauses = " OR ".join(["(p.document_id = %s AND p.page_number = %s)"] * len(pairs))
    params: list[int] = []
    for document_id, page_number in pairs:
        params.extend([document_id, page_number])
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT p.document_id, p.page_number, p.chapter, p.body, d.filename
                FROM pages p
                JOIN documents d ON d.id = p.document_id
                WHERE p.usable = 1 AND ({clauses})
                """,
                params,
            )
            rows = cursor.fetchall()
    finally:
        connection.close()
    return {(int(row["document_id"]), int(row["page_number"])): row for row in rows}


def insert_record(
    course_id: int,
    user_id: int,
    question: str,
    answer: str,
    cited_pages: list[dict],
    refused: bool,
) -> int:
    stored_pages = None
    if cited_pages and not refused:
        stored_pages = json.dumps(
            [
                {
                    "document_id": item["document_id"],
                    "page_number": item["page_number"],
                }
                for item in cited_pages
            ],
            ensure_ascii=False,
        )
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO qa_records
                  (course_id, user_id, question, answer, cited_pages, refused)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (course_id, user_id, question, answer, stored_pages, 1 if refused else 0),
            )
            record_id = cursor.lastrowid
        connection.commit()
        return record_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
