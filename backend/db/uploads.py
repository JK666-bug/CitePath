import pymysql

from db.connection import connect
from vector.segments import has_segments, sync_pages


def existing_upload(course_id: int, content_hash: str) -> dict | None:
    row = _hash_row(course_id, content_hash)
    if row is None:
        return None
    usable = int(row["usable_page_count"] or 0)
    if usable > 0 and not has_segments(row["id"]):
        count = sync_pages(row["id"], _load_pages(row["id"]))
        return _payload(row, count, False)
    return _payload(row, 0, True)


def save_document(course_id: int, filename: str, pages: list[dict], content_hash: str) -> dict:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents (course_id, filename, content_hash, ingest_status)
                VALUES (%s, %s, %s, 'pending')
                """,
                (course_id, filename, content_hash),
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
    except pymysql.err.IntegrityError:
        connection.rollback()
        existing = existing_upload(course_id, content_hash)
        if existing is not None:
            return existing
        raise
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
        "duplicate": False,
    }


def _hash_row(course_id: int, content_hash: str) -> dict | None:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, d.filename,
                       COUNT(p.id) AS page_count,
                       SUM(CASE WHEN p.usable = 1 THEN 1 ELSE 0 END) AS usable_page_count
                FROM documents d
                LEFT JOIN pages p ON p.document_id = d.id
                WHERE d.course_id = %s AND d.content_hash = %s
                GROUP BY d.id, d.filename
                """,
                (course_id, content_hash),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def _load_pages(document_id: int) -> list[dict]:
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT page_number, chapter, body, usable
                FROM pages
                WHERE document_id = %s
                ORDER BY page_number
                """,
                (document_id,),
            )
            return list(cursor.fetchall())
    finally:
        connection.close()


def _payload(row: dict, segments: int, duplicate: bool) -> dict:
    return {
        "document_id": row["id"],
        "filename": row["filename"],
        "page_count": int(row["page_count"] or 0),
        "usable_page_count": int(row["usable_page_count"] or 0),
        "milvus_segments": segments,
        "duplicate": duplicate,
    }


def load_document_source(user_id: int, course_id: int, document_id: int) -> dict | None:
    """同时校验账号、课程及文件归属，返回原件定位信息。"""

    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id AS document_id, d.filename, d.content_hash
                FROM documents AS d
                JOIN courses AS c ON c.id = d.course_id
                WHERE c.user_id = %s AND c.id = %s AND d.id = %s
                """,
                (user_id, course_id, document_id),
            )
            return cursor.fetchone()
    finally:
        connection.close()
