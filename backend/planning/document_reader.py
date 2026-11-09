# 正文块整理、指定页补读和图片生成
"""规划模块的资料读取工具。

默认复用数据库正文。
只有显式调用补读或渲染方法时，才读取原 PDF。
先阅读数据库正文
    ↓
文字足够判断章节关系 → 直接判断
    ↓
文字不足 → 选择读取相邻页，或补读指定页文字
    ↓
仍不足且确有必要 → 生成指定页图片，交给后续图像理解工具
本模块不调用模型、不划分章节、不修改数据库。
"""

import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import fitz

from db.material_pages import (
    PlanningDocument,
    PlanningMaterialError,
    load_planning_document,
)
from planning.material_files import (
    MaterialIntegrityError,
    load_original_pdf,
)


# 这里只识别文字的排版形式，不判断一级章节或学习单元。
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}(?:[ \t]+|$)")
_LIST = re.compile(
    r"^[ \t]*(?:"
    r"[-+*]"
    r"|\d+[.)]"
    r"|[A-Za-z][.)]"
    r"|[ivxlcdmIVXLCDM]+[.)]"
    r")[ \t]+"
)
_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")

# 图片资源保护上限，不是章节划分参数，也不代表最佳识别分辨率。
MAX_RENDER_SIDE = 4096


@dataclass(frozen=True)
class SourceBlock:
    """一段可追溯的原文。

    start_char 和 end_char 是在本次文字来源中的字符位置。
    text 必须等于对应原文的切片，不让模型生成或改写来源。
    """

    block_id: str
    page_number: int
    source: str
    kind: str
    start_char: int
    end_char: int
    text: str


@dataclass(frozen=True)
class PageText:
    """一次页面文字读取结果。

    source 区分数据库正文和 PDF 原生文字。
    database_text_status 始终保留第二步获得的数据库页面状态。
    """

    page_number: int
    source: str
    database_text_status: str
    text: str
    blocks: tuple[SourceBlock, ...]

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


@dataclass(frozen=True)
class RenderedPage:
    """从原 PDF 生成的页面图片。

    这里只保存像素和来源页码，不表示图片已经被模型理解。
    """

    page_number: int
    width: int
    height: int
    png_bytes: bytes


def _text_spans(text: str) -> list[tuple[str, int, int]]:
    """按基本排版整理原文范围。

    这是轻量整理，不是完整 Markdown 解析器。
    分类只是形式提示，不能据此自动创建章节。

    空行通常结束一个块；代码围栏中的空行继续保留。
    """
    spans = []
    active_kind = None
    start = 0
    end = 0
    offset = 0
    fence_char = None
    fence_length = 0

    def flush():
        nonlocal active_kind

        if active_kind is not None:
            spans.append((active_kind, start, end))

        active_kind = None

    for line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(line)
        stripped = line.strip()

        # 已进入代码围栏时，标题符号、列表符号和空行都属于代码。
        if fence_char is not None:
            end = offset

            if (
                len(stripped) >= fence_length
                and set(stripped) == {fence_char}
            ):
                flush()
                fence_char = None
                fence_length = 0

            continue

        if not stripped:
            flush()
            continue

        fence = _FENCE.match(line)

        if fence is not None:
            flush()
            marker = fence.group(1)
            active_kind = "code"
            start = line_start
            end = offset
            fence_char = marker[0]
            fence_length = len(marker)
            continue

        # 标题单独保留，但不判断它是总标题、章节标题还是普通页标题。
        if _HEADING.match(line):
            flush()
            spans.append(("heading", line_start, offset))
            continue

        if line.lstrip().startswith("|"):
            kind = "table"
        elif _LIST.match(line):
            kind = "list"
        else:
            kind = "text"

        if kind != active_kind:
            flush()
            active_kind = kind
            start = line_start

        end = offset

    # 未闭合的代码围栏也保留原文，不因此丢弃文件尾部内容。
    flush()
    return spans


class DocumentReader:
    """绑定一份已经完成归属校验的资料。

    网页或模型工具入口应使用 open_document_reader() 创建对象，
    不允许从外部请求直接传入任意磁盘路径。
    """

    def __init__(self, document: PlanningDocument):
        self.document = document

        self._database_cache: dict[int, PageText] = {}
        self._native_cache: dict[int, PageText] = {}
        self._blocks: dict[str, SourceBlock] = {}

    def _validate_page(self, page_number: int) -> None:
        if (
            type(page_number) is not int
            or not 1 <= page_number <= self.document.total_pages
        ):
            raise PlanningMaterialError(
                "invalid_page_selection",
                "The requested page is outside this document.",
            )

    def _make_page_text(
        self,
        page_number: int,
        source: str,
        text: str,
    ) -> PageText:
        """只根据实际读取的原文建立来源块。"""
        blocks = []
        short_source = "db" if source == "database" else "native"

        for index, (kind, start, end) in enumerate(
            _text_spans(text),
            start=1,
        ):
            block_text = text[start:end]

            # 文件身份、页码、读取来源、位置和文字共同决定编号。
            # 相同输入产生相同编号；正文变化后不会继续沿用旧编号。
            identity = (
                f"{self.document.course_id}|"
                f"{self.document.document_id}|"
                f"{self.document.content_hash}|"
                f"{page_number}|{source}|{index}|"
                f"{kind}|{start}|{end}|{block_text}"
            )
            digest = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:16]

            block_id = (
                f"d{self.document.document_id}:"
                f"p{page_number}:{short_source}:b{index}:{digest}"
            )

            block = SourceBlock(
                block_id=block_id,
                page_number=page_number,
                source=source,
                kind=kind,
                start_char=start,
                end_char=end,
                text=block_text,
            )

            self._blocks[block_id] = block
            blocks.append(block)

        database_page = self.document.pages[page_number - 1]

        return PageText(
            page_number=page_number,
            source=source,
            database_text_status=database_page.text_status,
            text=text,
            blocks=tuple(blocks),
        )

    def read_pages(
        self,
        page_numbers: list[int] | tuple[int, ...],
    ) -> tuple[PageText, ...]:
        """读取指定页的数据库正文。
        返回指定页的数据库正文及来源块
        可以用来读取当前页及相邻页。
        不自动调用 PDF 补读、OCR 或图像理解。
        """
        if (
            not isinstance(page_numbers, (list, tuple))
            or not page_numbers
        ):
            raise PlanningMaterialError(
                "invalid_page_selection",
                "Provide a nonempty list of page numbers.",
            )

        for number in page_numbers:
            self._validate_page(number)

        if len(set(page_numbers)) != len(page_numbers):
            raise PlanningMaterialError(
                "duplicate_page_selection",
                "Do not request the same page more than once.",
            )

        results = []

        for number in page_numbers:
            if number not in self._database_cache:
                page = self.document.pages[number - 1]
                self._database_cache[number] = self._make_page_text(
                    page_number=number,
                    source="database",
                    text=page.body,
                )

            results.append(self._database_cache[number])

        return tuple(results)

    def get_block(self, block_id: str) -> SourceBlock:
        """根据块编号找回真实原文。只解析当前读取器已经建立的来源编号，不接受虚构编号。"""
        if not isinstance(block_id, str) or block_id not in self._blocks:
            raise PlanningMaterialError(
                "unknown_source_block",
                "The source block is not available in this document read.",
            )

        return self._blocks[block_id]

    @contextmanager
    def _open_original(self) -> Iterator[fitz.Document]:
        """复用已有原件校验，并确保 PDF 在操作后关闭。"""
        try:
            path = load_original_pdf(
                self.document.course_id,
                self.document.content_hash,
            )

            with fitz.open(path) as pdf:
                if (
                    not pdf.is_pdf
                    or pdf.needs_pass
                    or pdf.page_count != self.document.total_pages
                ):
                    raise PlanningMaterialError(
                        "original_pdf_mismatch",
                        "The original PDF does not match the document inventory.",
                    )

                yield pdf

        except PlanningMaterialError:
            raise

        except FileNotFoundError as error:
            raise PlanningMaterialError(
                "original_pdf_missing",
                "The original PDF is unavailable.",
            ) from error

        except MaterialIntegrityError as error:
            raise PlanningMaterialError(
                "original_pdf_integrity_error",
                "The original PDF failed its integrity check.",
            ) from error

        except (OSError, RuntimeError, ValueError) as error:
            raise PlanningMaterialError(
                "original_pdf_read_error",
                "The original PDF could not be read.",
            ) from error

    def read_native_text(self, page_number: int) -> PageText:
        """补读指定页的 PDF 原生文字层。

        不执行 OCR，因此纯图片页仍可能返回空文字。
        补读结果单独保存，不覆盖数据库正文或 usable。
        """
        self._validate_page(page_number)

        if page_number not in self._native_cache:
            with self._open_original() as pdf:
                page = pdf.load_page(page_number - 1)
                text = page.get_text("text", sort=True) or ""

            self._native_cache[page_number] = self._make_page_text(
                page_number=page_number,
                source="native_pdf",
                text=text,
            )

        return self._native_cache[page_number]

    def render_page(
        self,
        page_number: int,
        *,
        max_side: int,
    ) -> RenderedPage:
        """按调用方指定的尺寸，生成某一页的 PNG。

        max_side 表示目标最长边像素数。
        它控制图片资源消耗，不参与章节边界判断。
        """
        self._validate_page(page_number)

        if (
            type(max_side) is not int
            or not 1 <= max_side <= MAX_RENDER_SIDE
        ):
            raise PlanningMaterialError(
                "invalid_render_size",
                f"max_side must be an integer from 1 to {MAX_RENDER_SIDE}.",
            )

        with self._open_original() as pdf:
            page = pdf.load_page(page_number - 1)
            longest_side = max(page.rect.width, page.rect.height)

            if longest_side <= 0:
                raise PlanningMaterialError(
                    "invalid_page_dimensions",
                    "The PDF page has invalid dimensions.",
                )

            scale = max_side / longest_side

            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )

            return RenderedPage(
                page_number=page_number,
                width=pixmap.width,
                height=pixmap.height,
                png_bytes=pixmap.tobytes("png"),
            )


def open_document_reader(
    user_id: int,
    course_id: int,
    document_id: int,
) -> DocumentReader:
    """正式创建入口：先完成第二步的权限与完整资料读取。"""
    document = load_planning_document(
        user_id=user_id,
        course_id=course_id,
        document_id=document_id,
    )
    return DocumentReader(document)