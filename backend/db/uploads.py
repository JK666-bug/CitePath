from db.connection import connect
from vector.segments import sync_pages


def save_upload(filename: str, student_brief: str, pages: list[dict]) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO documents (filename, ingest_status) VALUES (%s, 'pending')",
                (filename,),
            )
            document_id = cursor.lastrowid
            cursor.executemany(
                """
                INSERT INTO pages (document_id, page_number, chapter, body, usable)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        document_id,
                        page["page_number"],
                        page["chapter"],
                        page["body"],
                        page["usable"],
                    )
                    for page in pages
                ],
            )
            cursor.execute(
                """
                INSERT INTO study_plans (document_id, student_brief, status)
                VALUES (%s, %s, 'draft')
                """,
                (document_id, student_brief),
            )
            plan_id = cursor.lastrowid
            cursor.execute(
                "UPDATE documents SET ingest_status = 'complete' WHERE id = %s",
                (document_id,),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    record = read_upload(document_id, plan_id)
    record["milvus_segments"] = sync_pages(document_id, pages)
    return record


def read_upload(document_id: int, plan_id: int | None = None) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, filename, ingest_status
                FROM documents
                WHERE id = %s
                """,
                (document_id,),
            )
            document = cursor.fetchone()
            if document is None:
                return None
            if plan_id is None:
                cursor.execute(
                    """
                    SELECT id, student_brief, status
                    FROM study_plans
                    WHERE document_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (document_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, student_brief, status
                    FROM study_plans
                    WHERE id = %s AND document_id = %s
                    """,
                    (plan_id, document_id),
                )
            plan = cursor.fetchone()
            cursor.execute(
                """
                SELECT page_number, chapter, body, usable
                FROM pages
                WHERE document_id = %s
                ORDER BY page_number
                """,
                (document_id,),
            )
            pages = cursor.fetchall()
    finally:
        connection.close()
    if plan is None:
        return None
    return _present(document, plan, pages)


def _present(document: dict, plan: dict, pages: list[dict]) -> dict:
    usable_count = sum(1 for page in pages if page["usable"])
    return {
        "document_id": document["id"],
        "plan_id": plan["id"],
        "filename": document["filename"],
        "ingest_status": document["ingest_status"],
        "plan_status": plan["status"],
        "student_brief": plan["student_brief"],
        "page_count": len(pages),
        "usable_page_count": usable_count,
        "pages": [
            {
                "page_number": page["page_number"],
                "chapter": page["chapter"],
                "usable": bool(page["usable"]),
                "excerpt": (page["body"] or "")[:120],
            }
            for page in pages
        ],
    }
