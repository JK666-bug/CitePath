import io

import fitz

from ingest.clean import strip_page_furniture

_converter = None


def read_pdf(data: bytes) -> list[dict]:
    page_count = _page_count(data)
    if page_count == 0:
        return []
    document = _convert(data)
    chapters = _chapters(document, page_count)
    pages = []
    for number in range(1, page_count + 1):
        exported = document.export_to_markdown(
            page_no=number,
            included_content_layers={_body_layer()},
            escape_html=False,
            escape_underscores=False,
            image_placeholder="",
            include_annotations=False,
            include_picture_classification=False,
        )
        body = strip_page_furniture(exported or "")
        pages.append(
            {
                "page_number": number,
                "chapter": chapters.get(number, "Untitled"),
                "body": body or None,
                "usable": 1 if body else 0,
            }
        )
    return pages


def _page_count(data: bytes) -> int:
    document = fitz.open(stream=data, filetype="pdf")
    try:
        return document.page_count
    finally:
        document.close()


def _convert(data: bytes):
    from docling.datamodel.base_models import ConversionStatus, DocumentStream

    result = _get_converter().convert(
        DocumentStream(name="upload.pdf", stream=io.BytesIO(data))
    )
    if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        raise RuntimeError("This PDF could not be read")
    return result.document


def _get_converter():
    global _converter
    if _converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = False
        options.do_table_structure = True
        options.do_formula_enrichment = True
        options.generate_page_images = False
        options.generate_picture_images = False
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            }
        )
    return _converter


def _body_layer():
    from docling_core.types.doc import ContentLayer

    return ContentLayer.BODY


def _chapters(document, page_count: int) -> dict[int, str]:
    from docling_core.types.doc import ContentLayer, DocItemLabel

    headers = {DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER}
    first_header: dict[int, str] = {}
    for item, _level in document.iterate_items(
        included_content_layers={ContentLayer.BODY}
    ):
        if getattr(item, "label", None) not in headers:
            continue
        text = str(getattr(item, "text", "") or "").strip()
        page_no = _page_no(item)
        if text and page_no:
            first_header.setdefault(page_no, text[:255])

    chapters = {}
    current = "Untitled"
    for number in range(1, page_count + 1):
        if number in first_header:
            current = first_header[number]
        chapters[number] = current
    return chapters


def _page_no(item) -> int | None:
    for entry in getattr(item, "prov", None) or []:
        number = getattr(entry, "page_no", None)
        if isinstance(number, int) and number > 0:
            return number
    return None
