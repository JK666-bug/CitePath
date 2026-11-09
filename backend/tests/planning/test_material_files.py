"""原 PDF 保存、恢复、完整性和读取权限测试，供手动运行。"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient

from main import app, current_user
from planning.material_files import (
    MaterialIntegrityError,
    load_original_pdf,
    material_file_path,
    save_original_pdf,
)


def make_pdf() -> bytes:
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 70), "A test lecture about fraud detection.")
        return pdf.tobytes()


class MaterialFileTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(folder)
        self.enterContext(patch("planning.material_files.MATERIAL_ROOT", self.root))
        self.data = make_pdf()
        self.digest = hashlib.sha256(self.data).hexdigest()

    def test_saves_exact_bytes_and_reuses_existing_file(self):
        path = save_original_pdf(3, self.digest, self.data)
        self.assertEqual(path.read_bytes(), self.data)
        self.assertEqual(load_original_pdf(3, self.digest), path)

        with patch("planning.material_files.os.replace") as replace:
            repeated = save_original_pdf(3, self.digest, self.data)

        self.assertEqual(repeated, path)
        replace.assert_not_called()

    def test_restores_a_missing_original(self):
        path = save_original_pdf(3, self.digest, self.data)
        path.rename(path.with_suffix(".backup"))
        with self.assertRaises(FileNotFoundError):
            load_original_pdf(3, self.digest)

        restored = save_original_pdf(3, self.digest, self.data)
        self.assertEqual(restored.read_bytes(), self.data)

    def test_same_pdf_is_stored_under_its_course(self):
        first = save_original_pdf(3, self.digest, self.data)
        second = save_original_pdf(4, self.digest, self.data)
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent.name, "3")
        self.assertEqual(second.parent.name, "4")

    def test_rejects_content_that_does_not_match_hash(self):
        with self.assertRaises(MaterialIntegrityError):
            save_original_pdf(3, "0" * 64, self.data)

    def test_detects_and_repairs_corrupted_original(self):
        path = save_original_pdf(3, self.digest, self.data)
        path.write_bytes(b"damaged data")
        with self.assertRaises(MaterialIntegrityError):
            load_original_pdf(3, self.digest)

        save_original_pdf(3, self.digest, self.data)
        self.assertEqual(path.read_bytes(), self.data)

    def test_failed_write_does_not_leave_partial_pdf(self):
        with patch(
            "planning.material_files.os.replace",
            side_effect=OSError("Disk unavailable"),
        ):
            with self.assertRaises(OSError):
                save_original_pdf(3, self.digest, self.data)

        path = material_file_path(3, self.digest)
        self.assertFalse(path.exists())
        self.assertEqual(list(path.parent.iterdir()), [])

    def test_rejects_non_pdf_content(self):
        data = b"This is not a PDF."
        digest = hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):
            save_original_pdf(3, digest, data)


class MaterialFileApiTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(
            patch("planning.material_files.MATERIAL_ROOT", Path(folder))
        )
        self.client = self.enterContext(TestClient(app))
        self.enterContext(patch.dict(app.dependency_overrides, {
            current_user: lambda: {"id": 5},
        }))
        self.data = make_pdf()
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.document = {
            "document_id": 7,
            "filename": "lecture.pdf",
            "content_hash": self.digest,
        }
        self.url = "/api/courses/3/documents/7/file"

    def test_returns_pdf_after_ownership_lookup(self):
        save_original_pdf(3, self.digest, self.data)
        with patch("main.load_document_source", return_value=self.document) as load:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.data)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(
            response.headers["content-disposition"].startswith("inline")
        )
        load.assert_called_once_with(5, 3, 7)

    def test_requires_sign_in(self):
        app.dependency_overrides.pop(current_user)
        with (
            patch("main.user_from_token", return_value=None),
            patch("main.load_document_source") as load,
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)
        load.assert_not_called()

    def test_rejects_file_outside_account_or_course(self):
        with (
            patch("main.load_document_source", return_value=None),
            patch("main.load_original_pdf") as load_file,
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        load_file.assert_not_called()

    def test_missing_original_has_clear_response(self):
        with patch("main.load_document_source", return_value=self.document):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 410)
        self.assertIn("Upload the same PDF", response.json()["detail"])

    def test_corrupted_original_is_not_returned(self):
        path = save_original_pdf(3, self.digest, self.data)
        path.write_bytes(b"damaged")
        with patch("main.load_document_source", return_value=self.document):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 409)

    def test_duplicate_upload_restores_file_without_new_record(self):
        existing = {
            "document_id": 7,
            "filename": "lecture.pdf",
            "page_count": 1,
            "usable_page_count": 1,
            "milvus_segments": 0,
            "duplicate": True,
        }
        with (
            patch("main.get_course", return_value={"id": 3}),
            patch("main.existing_upload", return_value=existing),
            patch("main.read_pdf") as read_pdf,
            patch("main.save_document") as save_document,
        ):
            response = self.client.post(
                "/api/courses/3/documents",
                files={"file": ("lecture.pdf", self.data, "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["document_id"], 7)
        self.assertEqual(load_original_pdf(3, self.digest).read_bytes(), self.data)
        read_pdf.assert_not_called()
        save_document.assert_not_called()


if __name__ == "__main__":
    unittest.main()
