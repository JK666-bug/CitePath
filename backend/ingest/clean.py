import re

# A line that is only a page number or a page-number footer. Table rows are kept,
# because a cell can legitimately be a number. Theorem and figure numbers stay
# because they share the line with other words.
_PAGE_NUMBER = re.compile(
    r"^(?:"
    r"\d{1,4}"
    r"|[-–—]\s*\d{1,4}\s*[-–—]"
    r"|page\s+\d{1,4}(?:\s+of\s+\d{1,4})?"
    r"|\d{1,4}\s*/\s*\d{1,4}"
    r"|第\s*\d{1,4}\s*页"
    r")$",
    re.IGNORECASE,
)
_HEADING_MARK = re.compile(r"^#{1,6}\s+")
_IMAGE_LINE = re.compile(r"^<!--\s*image\s*-->$", re.IGNORECASE)


def strip_page_furniture(text: str) -> str:
    kept = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _drop_line(line):
            continue
        kept.append(line.rstrip())
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept))
    return cleaned.strip()


def _drop_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or "|" in stripped:
        return False
    if _IMAGE_LINE.match(stripped):
        return True
    return _PAGE_NUMBER.match(_HEADING_MARK.sub("", stripped)) is not None
