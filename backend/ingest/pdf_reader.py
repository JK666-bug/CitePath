import fitz


def read_pdf(data: bytes) -> list[dict]:
    document = fitz.open(stream=data, filetype="pdf")
    try:
        outline = document.get_toc()
        pages = []
        for index, page in enumerate(document, start=1):
            chapter = _chapter_for_page(outline, index)
            text = page.get_text("text").strip()
            pages.append(
                {
                    "page_number": index,
                    "chapter": chapter,
                    "body": text or None,
                    "usable": 1 if text else 0,
                }
            )
        return pages
    finally:
        document.close()


def _chapter_for_page(outline: list, page_number: int) -> str:
    chapter = "Untitled"
    for _level, title, start_page in outline:
        if start_page > page_number:
            break
        cleaned = title.strip()
        if cleaned:
            chapter = cleaned
    return chapter[:255]
