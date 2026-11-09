import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from db.connection import connect
from planning.material_files import (
    MaterialIntegrityError,
    load_original_pdf,
)

@dataclass(frozen=True)
class MaterialPage:
    """规划模块使用的讲义页。page_number 是 PDF 原始页码。"""

    document_id: int
    filename: str
    page_number: int
    chapter: str
    body: str


def load_material_pages(user_id: int, course_id: int) -> list[MaterialPage]:

    """按课程归属读取全部已入库的可用页。"""
    
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    d.id AS document_id,
                    d.filename,
                    d.ingest_status,
                    p.page_number,
                    p.chapter,
                    p.body
                FROM courses AS c
                LEFT JOIN documents AS d ON d.course_id = c.id
                LEFT JOIN pages AS p
                    ON p.document_id = d.id
                    AND p.usable = 1
                    AND p.body IS NOT NULL
                WHERE c.id = %s AND c.user_id = %s
                ORDER BY d.id, p.page_number
                """,
                (course_id, user_id),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    if not rows:
        raise LookupError("Course not found.")

    pages = []
    filenames = {}
    readable_documents = set()

    for row in rows:
        document_id = row["document_id"]
        if document_id is None:
            # LEFT JOIN 会保留存在但尚未上传任何文件的课程。
            continue

        filename = row["filename"]
        filenames[document_id] = filename
        # 如果文件还在处理阶段，不能使用其页内容生成计划。
        if row["ingest_status"] != "complete":
            raise ValueError(f"Wait for material processing to finish: {filename}")
        # 如果页码或正文为空，说明该页无法使用。可用页的页码和正文都不应为空。
        body = (row["body"] or "").strip()
        if row["page_number"] is None or not body:
            continue

        readable_documents.add(document_id)
        pages.append(
            MaterialPage(
                document_id=document_id,
                filename=filename,
                page_number=row["page_number"],
                chapter=row["chapter"],
                body=body,
            )
        )

    if not filenames:
        raise ValueError("Upload at least one PDF before generating a study plan.")

    # 个别无正文的页可以跳过。整份文件无正文时要告知用户，
    # 否则系统可能发布一份看起来完整、实际漏掉一份讲义的计划。
    for document_id, filename in filenames.items():
        if document_id not in readable_documents:
            raise ValueError(f"No readable text was found in: {filename}")

    return pages


class PlanningMaterialError(ValueError):
    """规划资料读取失败。

    code 用于程序区分错误类型。
    message 使用英文，方便以后接入前端。
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PlanningPage:
    """完整页面清单中的一页。

    这里保留的是数据库已有文字，不会重新解析这一页。
    database_usable 仅保留原始标记，不决定是否返回该页。
    """

    document_id: int
    page_number: int
    chapter_hint: str
    body: str
    database_usable: bool | None
    record_present: bool

    @property
    def has_text(self) -> bool:
        """是否存在非空文字，不代表文字完整或足以生成练习。"""
        return bool(self.body.strip())

    @property
    def text_status(self) -> str:
        """区分有文字、无文字和缺少数据库记录。"""
        if not self.record_present:
            return "missing"

        if self.has_text:
            return "available"

        return "empty"


@dataclass(frozen=True)
class PlanningDocument:
    """供后续章节识别使用的一份完整资料。

    original_path 是后端内部路径。
    以后接入网页时，不应把这个路径直接返回给前端。
    """

    user_id: int
    course_id: int
    course_name: str
    document_id: int
    filename: str
    content_hash: str
    original_path: Path
    total_pages: int
    pages: tuple[PlanningPage, ...]

    @property
    def text_page_count(self) -> int:
        """当前实际存在非空正文的页面数量。"""
        return sum(page.has_text for page in self.pages)


def _require_positive_id(value: int, field_name: str) -> None:
    """拒绝无效 ID，包括 Python 中也属于整数的 True 和 False。"""
    if type(value) is not int or value <= 0:
        raise PlanningMaterialError(
            "invalid_identifier",
            f"{field_name} must be a positive integer.",
        )


def _read_original_page_count(original_path: Path) -> int:
    """轻量读取原 PDF 总页数，不运行 Docling，也不提取页面正文。"""
    try:
        with fitz.open(original_path) as pdf:
            if not pdf.is_pdf:
                raise PlanningMaterialError(
                    "invalid_original_pdf",
                    "The stored material is not a PDF.",
                )

            if pdf.needs_pass:
                raise PlanningMaterialError(
                    "password_protected_pdf",
                    "The stored PDF requires a password.",
                )

            if pdf.page_count <= 0:
                raise PlanningMaterialError(
                    "empty_original_pdf",
                    "The stored PDF has no pages.",
                )

            return pdf.page_count

    except PlanningMaterialError:
        # 保留上面已经明确区分的错误。
        raise

    except (RuntimeError, ValueError, OSError) as error:
        raise PlanningMaterialError(
            "original_pdf_unreadable",
            "The stored PDF could not be opened.",
        ) from error


def load_planning_document(
    user_id: int,
    course_id: int,
    document_id: int,
) -> PlanningDocument:
    """读取某个用户、某门课程下的一份完整资料。

    主要正文复用 pages 表。
    原 PDF 仅用于核对文件完整性和真实总页数。
    本函数不调用模型，也不修改数据库。
    """
    _require_positive_id(user_id, "user_id")
    _require_positive_id(course_id, "course_id")
    _require_positive_id(document_id, "document_id")

    connection = connect()

    try:
        with connection.cursor() as cursor:
            # 同时检查账号、课程和文件归属。
            # 不存在与无权访问统一返回相同错误，避免泄露他人文件信息。
            cursor.execute(
                """
                SELECT
                    c.name AS course_name,
                    d.id AS document_id,
                    d.filename,
                    d.content_hash,
                    d.ingest_status
                FROM documents AS d
                JOIN courses AS c ON c.id = d.course_id
                WHERE c.user_id = %s
                  AND c.id = %s
                  AND d.id = %s
                """,
                (user_id, course_id, document_id),
            )

            source = cursor.fetchone()

            if source is None:
                raise PlanningMaterialError(
                    "document_not_found",
                    "The document was not found in this course.",
                )

            if source["ingest_status"] != "complete":
                raise PlanningMaterialError(
                    "document_not_ready",
                    "Wait for material processing to finish.",
                )

            # 不使用 usable=1 过滤，也不要求 body 非空。
            # 这一查询必须保留该文件现有的所有页面记录。
            cursor.execute(
                """
                SELECT
                    page_number,
                    chapter,
                    body,
                    usable
                FROM pages
                WHERE document_id = %s
                ORDER BY page_number
                """,
                (document_id,),
            )

            stored_rows = cursor.fetchall()

    finally:
        # 后续即使文件读取失败，也不会一直占用数据库连接。
        connection.close()

    content_hash = source["content_hash"]

    if (
        not isinstance(content_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", content_hash) is None
    ):
        raise PlanningMaterialError(
            "missing_material_fingerprint",
            "The document has no valid file fingerprint. "
            "Upload the same original PDF again.",
        )

    # 先通过数据库确认归属，之后才允许定位和读取磁盘原件。
    try:
        original_path = load_original_pdf(course_id, content_hash)

    except FileNotFoundError as error:
        raise PlanningMaterialError(
            "original_pdf_missing",
            "The original PDF is unavailable. "
            "Upload the same original PDF again.",
        ) from error

    except MaterialIntegrityError as error:
        raise PlanningMaterialError(
            "original_pdf_integrity_error",
            "The original PDF failed its integrity check.",
        ) from error

    except OSError as error:
        raise PlanningMaterialError(
            "original_pdf_read_error",
            "The original PDF could not be read from storage.",
        ) from error

    total_pages = _read_original_page_count(original_path)

    # 用真实 PDF 页数核对数据库记录，不能以数据库最大页码猜测总页数。
    rows_by_number = {}

    for row in stored_rows:
        number = row["page_number"]

        if type(number) is not int or not 1 <= number <= total_pages:
            raise PlanningMaterialError(
                "invalid_page_number",
                "A stored page number is outside the original PDF.",
            )

        if number in rows_by_number:
            raise PlanningMaterialError(
                "duplicate_page_number",
                "The document contains duplicate stored page numbers.",
            )

        if row["usable"] not in (0, 1):
            raise PlanningMaterialError(
                "invalid_usable_flag",
                "A stored page has an invalid usable flag.",
            )

        rows_by_number[number] = row

    complete_pages = []

    # 根据原 PDF 建立 1 到 total_pages 的完整清单。
    # 数据库缺少的页也返回占位记录，但不会写回数据库。
    for number in range(1, total_pages + 1):
        row = rows_by_number.get(number)

        if row is None:
            complete_pages.append(
                PlanningPage(
                    document_id=document_id,
                    page_number=number,
                    chapter_hint="",
                    body="",
                    database_usable=None,
                    record_present=False,
                )
            )
            continue

        complete_pages.append(
            PlanningPage(
                document_id=document_id,
                page_number=number,
                # 这是入库时的标题提示，不直接作为正式章节。
                chapter_hint=row["chapter"] or "",
                # 保留已有正文，不在本步骤重新清理或改写文字。
                body=row["body"] or "",
                database_usable=bool(row["usable"]),
                record_present=True,
            )
        )

    return PlanningDocument(
        user_id=user_id,
        course_id=course_id,
        course_name=source["course_name"],
        document_id=document_id,
        filename=source["filename"],
        content_hash=content_hash,
        original_path=original_path,
        total_pages=total_pages,
        pages=tuple(complete_pages),
    )