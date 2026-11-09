"""保存和读取课程 PDF 原件，文件身份与权限由数据库记录确定。"""

import hashlib
import os
import re
import tempfile
from pathlib import Path

import fitz


BACKEND_DIR = Path(__file__).resolve().parents[1]
MATERIAL_ROOT = BACKEND_DIR / "storage" / "materials"


class MaterialIntegrityError(ValueError):
    """原件内容与文件指纹不一致。"""


def material_file_path(course_id: int, content_hash: str) -> Path:
    """只使用课程编号和 SHA256 构造路径，不使用上传文件名。"""

    if type(course_id) is not int or course_id <= 0:
        raise ValueError("Invalid course identifier.")
    if (
        not isinstance(content_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", content_hash) is None
    ):
        raise ValueError("Invalid material fingerprint.")

    return MATERIAL_ROOT / str(course_id) / f"{content_hash}.pdf"


def _file_matches(path: Path, expected_hash: str) -> bool:
    """分块核对磁盘原件，避免一次读入整份文件。"""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except FileNotFoundError:
        return False

    return digest.hexdigest() == expected_hash


def _validate_pdf(data: bytes) -> None:
    """轻量验证原件，重复上传时无需再次执行 Docling 解析。"""

    try:
        pdf = fitz.open(stream=data, filetype="pdf")
    except Exception as error:
        raise ValueError("This PDF could not be read") from error

    with pdf:
        if not pdf.is_pdf:
            raise ValueError("Upload a PDF file")
        if pdf.needs_pass:
            raise ValueError("Upload a PDF without a password.")
        if pdf.page_count == 0:
            raise ValueError("This PDF has no pages")


def save_original_pdf(course_id: int, content_hash: str, data: bytes) -> Path:
    """幂等保存原件，已有正确原件直接复用，缺失或损坏则补齐。"""

    destination = material_file_path(course_id, content_hash)
    if hashlib.sha256(data).hexdigest() != content_hash:
        raise MaterialIntegrityError("The PDF does not match its file fingerprint.")

    _validate_pdf(data)
    if destination.is_file() and _file_matches(destination, content_hash):
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path = None
    try:
        # 先完整写入同目录的独立临时文件，再原子替换目标。
        # 并发上传相同内容时，也不会暴露写入一半的 PDF。
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".upload-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return destination


def load_original_pdf(course_id: int, content_hash: str) -> Path:
    """返回校验通过的原件路径，调用前必须检查账号与资料归属。"""

    path = material_file_path(course_id, content_hash)
    if not path.is_file():
        raise FileNotFoundError("The original PDF is unavailable.")
    if not _file_matches(path, content_hash):
        raise MaterialIntegrityError("The original PDF failed its integrity check.")

    return path
