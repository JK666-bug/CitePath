from db.connection import connect
from vector.segments import sync_pages


def save_document(course_id: int, filename: str, pages: list[dict]) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents (course_id, filename, ingest_status)
                VALUES (%s, %s, 'pending')
                """,
                (course_id, filename),
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
                "UPDATE documents SET ingest_status = 'complete' WHERE id = %s",
                (document_id,),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    usable = sum(1 for page in pages if page["usable"])
    return {
        "document_id": document_id,
        "filename": filename,
        "page_count": len(pages),
        "usable_page_count": usable,
        "milvus_segments": sync_pages(document_id, pages),
    }
