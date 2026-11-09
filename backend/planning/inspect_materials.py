"""课程资料的开发检查入口。

运行方式：
    python -m planning.inspect_materials ...

默认只读取完整资料和数据库正文。
原生文字补读、页面图片生成必须显式指定。
本模块不调用模型，不进行章节分析，不修改数据库。
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from db.material_pages import PlanningMaterialError
from planning.document_reader import (
    MAX_RENDER_SIDE,
    open_document_reader,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _positive_integer(raw: str) -> int:
    """供命令行参数使用，拒绝零、负数和非整数。"""
    try:
        value = int(raw)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Provide a positive integer."
        ) from error

    if value <= 0:
        raise argparse.ArgumentTypeError(
            "Provide a positive integer."
        )

    return value

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect stored course material without running "
            "chapter analysis or calling a model."
        )
    )

    parser.add_argument(
        "--user-id",
        type=_positive_integer,
        required=True,
        help="The database user ID.",
    )
    parser.add_argument(
        "--course-id",
        type=_positive_integer,
        required=True,
        help="The database course ID.",
    )
    parser.add_argument(
        "--document-id",
        type=_positive_integer,
        required=True,
        help="The database document ID, not the displayed Doc number.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="A new directory for this inspection run.",
    )
    parser.add_argument(
        "--native-pages",
        type=_positive_integer,
        nargs="+",
        default=[],
        help="Original PDF page numbers to read as native text.",
    )
    parser.add_argument(
        "--render-pages",
        type=_positive_integer,
        nargs="+",
        default=[],
        help="Original PDF page numbers to render as PNG images.",
    )
    parser.add_argument(
        "--max-side",
        type=_positive_integer,
        default=None,
        help=(
            "Target longest image side in pixels. "
            "Required when --render-pages is used."
        ),
    )

    return parser


def _validate_options(parser, args) -> None:
    """在连接数据库前，检查无需读取资料就能发现的参数错误。"""
    for name in ("native_pages", "render_pages"):
        values = getattr(args, name)

        if len(values) != len(set(values)):
            parser.error(
                f"--{name.replace('_', '-')} contains duplicate pages."
            )

    if args.render_pages:
        if args.max_side is None:
            parser.error("--render-pages requires --max-side.")

        if args.max_side > MAX_RENDER_SIDE:
            parser.error(
                f"--max-side must not exceed {MAX_RENDER_SIDE}."
            )

    elif args.max_side is not None:
        parser.error("--max-side requires --render-pages.")


def _error_details(error: Exception) -> dict:
    """已知业务错误保留具体说明；未知错误不直接导出内部异常详情。"""
    if isinstance(error, PlanningMaterialError):
        return {
            "code": error.code,
            "error_type": type(error).__name__,
            "message": str(error),
        }

    return {
        "code": "unexpected_inspection_error",
        "error_type": type(error).__name__,
        "message": (
            "The inspection operation failed. "
            "Check the error type and local service configuration."
        ),
    }


def _capture(
    report: dict,
    action: str,
    operation,
    *,
    page_number: int | None = None,
):
    """执行一个普通 Python 操作，并记录结果。

    operation 是传入的函数，不是模型。
    返回 (是否成功, 操作结果)，方便保留部分成功的检查。
    """
    started = perf_counter()

    entry = {
        "action": action,
        "page_number": page_number,
    }

    try:
        result = operation()

    except Exception as error:
        details = _error_details(error)

        entry["status"] = "failed"
        report["errors"].append(
            {
                "action": action,
                "page_number": page_number,
                **details,
            }
        )
        success = False
        result = None

    else:
        entry["status"] = "completed"
        success = True

    entry["elapsed_ms"] = round(
        (perf_counter() - started) * 1000,
        2,
    )
    report["operations"].append(entry)

    return success, result


def _page_payload(page_text) -> dict:
    """保留完整文字与来源块，不在 JSON 报告中截断正文。"""
    payload = asdict(page_text)
    payload["has_text"] = page_text.has_text
    return payload


def _atomic_write(path: Path, data: bytes) -> None:
    """先写临时文件，再替换目标，避免把未写完的文件当成结果。"""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _render_and_save(
    reader,
    page_number: int,
    max_side: int,
    output_dir: Path,
) -> dict:
    """只保存明确请求的页面图片，不进行图像理解。"""
    image = reader.render_page(
        page_number,
        max_side=max_side,
    )

    image_dir = output_dir / "images"
    image_dir.mkdir(exist_ok=True)

    destination = image_dir / f"page-{page_number:04d}.png"
    _atomic_write(destination, image.png_bytes)

    return {
        "page_number": page_number,
        "relative_path": destination.relative_to(
            output_dir
        ).as_posix(),
        "width": image.width,
        "height": image.height,
        "image_understood": False,
    }


def _validate_requested_pages(reader, args) -> None:
    """总页数读取后，才能判断请求页码是否超出原 PDF。"""
    requested = set(args.native_pages) | set(args.render_pages)

    invalid = sorted(
        number
        for number in requested
        if number > reader.document.total_pages
    )

    if invalid:
        raise PlanningMaterialError(
            "invalid_page_selection",
            f"Requested pages are outside this document: {invalid}.",
        )


def _inspect(report: dict, args, output_dir: Path) -> None:
    """填充报告；必要步骤失败则停止，单页补充操作失败则保留其他结果。"""
    success, _ = _capture(
        report,
        "load_environment",
        lambda: load_dotenv(BACKEND_DIR / ".env"),
    )

    if not success:
        report["status"] = "failed"
        return

    success, reader = _capture(
        report,
        "load_document",
        lambda: open_document_reader(
            user_id=args.user_id,
            course_id=args.course_id,
            document_id=args.document_id,
        ),
    )

    if not success:
        report["status"] = "failed"
        return

    document = reader.document

    # 明确选择需要写入报告的字段，不导出后端原件磁盘路径。
    report["document"] = {
        "user_id": document.user_id,
        "course_id": document.course_id,
        "course_name": document.course_name,
        "document_id": document.document_id,
        "filename": document.filename,
        "content_hash": document.content_hash,
        "total_pages": document.total_pages,
    }

    success, database_pages = _capture(
        report,
        "read_database_pages",
        lambda: reader.read_pages(
            list(range(1, document.total_pages + 1))
        ),
    )

    if not success:
        report["status"] = "failed"
        return

    for original, database in zip(
        document.pages,
        database_pages,
        strict=True,
    ):
        report["pages"].append(
            {
                "page_number": original.page_number,
                "chapter_hint": original.chapter_hint,
                "record_present": original.record_present,
                "database_usable": original.database_usable,
                "database": _page_payload(database),
                "native_pdf": None,
                "rendered_image": None,
            }
        )

    # 即使请求页码有误，也保留上面已经得到的基础检查结果。
    success, _ = _capture(
        report,
        "validate_requested_pages",
        lambda: _validate_requested_pages(reader, args),
    )

    if not success:
        report["status"] = "failed"
        return

    pages_by_number = {
        page["page_number"]: page
        for page in report["pages"]
    }

    for number in args.native_pages:
        success, native = _capture(
            report,
            "read_native_text",
            lambda: reader.read_native_text(number),
            page_number=number,
        )

        if success:
            pages_by_number[number]["native_pdf"] = (
                _page_payload(native)
            )

    for number in args.render_pages:
        success, image = _capture(
            report,
            "render_page",
            lambda: _render_and_save(
                reader,
                number,
                args.max_side,
                output_dir,
            ),
            page_number=number,
        )

        if success:
            pages_by_number[number]["rendered_image"] = image

    report["status"] = (
        "partial" if report["errors"] else "completed"
    )


def _make_summary(report: dict) -> dict:
    """分别统计数据库正文、补读和图片结果，避免混为一谈。"""
    pages = report["pages"]
    document = report["document"]

    states = {
        "available": 0,
        "empty": 0,
        "missing": 0,
    }

    for page in pages:
        state = page["database"]["database_text_status"]
        states[state] += 1

    return {
        "original_page_count": (
            document["total_pages"] if document else None
        ),
        "reported_page_count": len(pages),
        "database_page_states": states,
        "database_usable_page_count": sum(
            page["database_usable"] is True
            for page in pages
        ),
        "database_text_page_count": sum(
            page["database"]["has_text"]
            for page in pages
        ),
        "database_block_count": sum(
            len(page["database"]["blocks"])
            for page in pages
        ),
        "empty_page_numbers": [
            page["page_number"]
            for page in pages
            if page["database"]["database_text_status"] == "empty"
        ],
        "missing_page_numbers": [
            page["page_number"]
            for page in pages
            if page["database"]["database_text_status"] == "missing"
        ],
        "native_read_count": sum(
            page["native_pdf"] is not None
            for page in pages
        ),
        "rendered_image_count": sum(
            page["rendered_image"] is not None
            for page in pages
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_options(parser, args)

    output_dir = args.output_dir.expanduser().resolve()

    try:
        # 每次检查使用新目录，避免旧图片与新报告混在一起。
        output_dir.mkdir(parents=True, exist_ok=False)

    except OSError as error:
        print(
            "Cannot create a new output directory "
            f"({type(error).__name__}). "
            "Use a new directory and check write access.",
            file=sys.stderr,
        )
        return 1

    report = {
        "stage": "material_inspection",
        "status": "running",
        "chapter_analysis_performed": False,
        "request": {
            "user_id": args.user_id,
            "course_id": args.course_id,
            "document_id": args.document_id,
            "native_pages": args.native_pages,
            "render_pages": args.render_pages,
            "max_side": args.max_side,
        },
        "document": None,
        "summary": {},
        "pages": [],
        "operations": [],
        "errors": [],
    }

    started = perf_counter()
    _inspect(report, args, output_dir)

    report["inspection_elapsed_ms"] = round(
        (perf_counter() - started) * 1000,
        2,
    )
    report["summary"] = _make_summary(report)

    destination = output_dir / "inspection.json"

    try:
        encoded = json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")

        _atomic_write(destination, encoded)

    except OSError as error:
        print(
            f"Cannot save the inspection report "
            f"({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1

    summary = report["summary"]

    print("Status:", report["status"])
    print("Report:", destination)
    print("Reported pages:", summary["reported_page_count"])
    print(
        "Database page states:",
        summary["database_page_states"],
    )
    print("Database blocks:", summary["database_block_count"])
    print("Native reads:", summary["native_read_count"])
    print("Rendered images:", summary["rendered_image_count"])
    print("Chapter analysis performed: False")

    for error in report["errors"]:
        print(
            f"Error: {error['action']} | "
            f"page={error['page_number']} | "
            f"{error['code']} | "
            f"{error['error_type']} | "
            f"{error['message']}",
            file=sys.stderr,
        )

    return {
        "completed": 0,
        "failed": 1,
        "partial": 2,
    }[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())