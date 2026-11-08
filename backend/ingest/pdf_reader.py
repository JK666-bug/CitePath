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
    owned, carried = _split_cross_page_text(document)
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
        exported = exported or ""
        for full, head in owned.get(number, []):
            exported = exported.replace(full, head, 1)
        tails = carried.get(number, [])
        if tails:
            exported = "\n\n".join([*tails, exported])
        body = strip_page_furniture(exported)
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


def _split_cross_page_text(document) -> tuple[dict[int, list[tuple[str, str]]], dict[int, list[str]]]:
    # Docling merges a paragraph that runs onto the next page into one item, and
    # a per-page export places all of it on the first page. Each provenance entry
    # gives the characters printed on its page, so the rest is moved back to the
    # top of the page where it was printed.
    from docling_core.types.doc import ContentLayer

    owned: dict[int, list[tuple[str, str]]] = {}
    carried: dict[int, list[str]] = {}
    for item, _level in document.iterate_items(
        included_content_layers={ContentLayer.BODY}
    ):
        text = getattr(item, "text", None)
        provs = getattr(item, "prov", None) or []
        if not isinstance(text, str) or len({prov.page_no for prov in provs}) < 2:
            continue
        parts = _page_parts(text, provs)
        if parts is None:
            continue
        first_page, head = parts[0]
        owned.setdefault(first_page, []).append((text, head))
        for page_no, piece in parts[1:]:
            carried.setdefault(page_no, []).append(piece)
    return owned, carried


def _page_parts(text: str, provs) -> list[tuple[int, str]] | None:
    parts: list[tuple[int, str]] = []
    for prov in provs:
        span = getattr(prov, "charspan", None)
        if not span or len(span) != 2:
            return None
        start, end = int(span[0]), int(span[1])
        if not 0 <= start <= end <= len(text):
            return None
        piece = text[start:end].strip()
        if not piece:
            continue
        if parts and parts[-1][0] == prov.page_no:
            parts[-1] = (prov.page_no, f"{parts[-1][1]} {piece}")
        else:
            parts.append((prov.page_no, piece))
    if len(parts) < 2:
        return None
    return parts


def _page_no(item) -> int | None:
    for entry in getattr(item, "prov", None) or []:
        number = getattr(entry, "page_no", None)
        if isinstance(number, int) and number > 0:
            return number
    return None
