"""用内存数据库验证历史过滤、分页和来源，用 API 测试验证认证边界。"""

import json
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from db.qa_history import load_qa_history
from main import app, current_user


class SqliteCursor:
    """执行生产查询，只转换 MySQL 的参数占位符。"""

    def __init__(self, database):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.cursor.close()

    def execute(self, sql, params):
        self.cursor = self.database.execute(sql.replace("%s", "?"), params)

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]


class QuestionHistoryDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        self.database.executescript(
            """
            CREATE TABLE courses (id INTEGER PRIMARY KEY, user_id INTEGER);
            CREATE TABLE qa_records (
                id INTEGER PRIMARY KEY, course_id INTEGER, user_id INTEGER,
                question TEXT, answer TEXT, cited_pages TEXT, refused INTEGER
            );
            INSERT INTO courses VALUES (3, 5), (4, 5), (9, 8);
            """
        )
        self.database.executemany(
            "INSERT INTO qa_records VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (10, 3, 5, "Older question", "Not supported", None, 1),
                (20, 3, 5, "Latest question", "Saved answer",
                 json.dumps([{"document_id": 12, "page_number": 5}]), 0),
                (30, 4, 5, "Other course", "Other answer", None, 1),
                (40, 9, 8, "Other account", "Private answer", None, 1),
                (50, 3, 8, "Mismatched account", "Private answer", None, 1),
            ],
        )

        self.connection = MagicMock()
        self.connection.cursor.side_effect = lambda: SqliteCursor(self.database)
        self.enterContext(patch("db.qa_history.connect", return_value=self.connection))
        self.course_lookup = self.enterContext(
            patch("db.qa_history.get_course", side_effect=self.get_course)
        )

    @staticmethod
    def get_course(user_id, course_id):
        if user_id != 5 or course_id not in (3, 4):
            return None
        return {
            "id": course_id,
            "name": f"Course {course_id}",
            "documents": [{"id": 12, "filename": "lecture.pdf"}],
        }

    def test_filters_account_and_course_and_restores_sources(self):
        result = load_qa_history(5, 3)

        self.assertEqual([row["qa_id"] for row in result["records"]], [20, 10])
        self.assertEqual(result["records"][0]["cited_pages"], [
            {"document_id": 12, "filename": "lecture.pdf", "page_number": 5},
        ])
        self.assertEqual(result["records"][0]["question"], "Latest question")
        self.assertEqual(result["records"][0]["answer"], "Saved answer")
        self.assertIsNone(result["next_before_id"])
        self.connection.close.assert_called_once()

    def test_cursor_pagination_has_no_repeated_or_missing_records(self):
        first = load_qa_history(5, 3, limit=1)
        second = load_qa_history(5, 3, before_id=first["next_before_id"], limit=1)

        self.assertEqual([row["qa_id"] for row in first["records"]], [20])
        self.assertEqual(first["next_before_id"], 20)
        self.assertEqual([row["qa_id"] for row in second["records"]], [10])
        self.assertIsNone(second["next_before_id"])

    def test_rejects_course_outside_account_before_reading_history(self):
        with self.assertRaises(LookupError):
            load_qa_history(8, 3)
        self.connection.cursor.assert_not_called()

    def test_empty_history_returns_an_empty_page(self):
        self.database.execute("DELETE FROM qa_records WHERE course_id = 4")
        self.assertEqual(load_qa_history(5, 4), {
            "records": [], "next_before_id": None,
        })

    def test_removed_file_keeps_its_original_document_id_and_page(self):
        self.database.execute(
            "UPDATE qa_records SET cited_pages = ? WHERE id = 20",
            (json.dumps([{"document_id": 77, "page_number": 6}]),),
        )
        source = load_qa_history(5, 3)["records"][0]["cited_pages"][0]
        self.assertEqual(source, {
            "document_id": 77, "filename": "Removed material", "page_number": 6,
        })

    def test_refusal_does_not_restore_citations(self):
        self.database.execute(
            "UPDATE qa_records SET refused = 1 WHERE id = 20"
        )
        record = load_qa_history(5, 3)["records"][0]
        self.assertTrue(record["refused"])
        self.assertEqual(record["cited_pages"], [])

    def test_invalid_stored_reference_is_not_fabricated(self):
        self.database.execute(
            "UPDATE qa_records SET cited_pages = ? WHERE id = 20",
            (json.dumps([{"document_id": True, "page_number": 5}]),),
        )
        with self.assertRaisesRegex(ValueError, "Invalid stored source"):
            load_qa_history(5, 3)
        self.connection.close.assert_called_once()

    def test_rejects_unbounded_history_page_sizes(self):
        for limit in (0, 101):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                load_qa_history(5, 3, limit=limit)


class QuestionHistoryApiTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))
        self.enterContext(patch.dict(app.dependency_overrides, {
            current_user: lambda: {"id": 5},
        }))

    def test_history_requires_sign_in(self):
        app.dependency_overrides.pop(current_user)
        with (
            patch("main.user_from_token", return_value=None),
            patch("main.load_qa_history") as load,
        ):
            response = self.client.get("/api/courses/3/questions")
        self.assertEqual(response.status_code, 401)
        load.assert_not_called()

    def test_uses_authenticated_account_and_course_and_pagination_cursor(self):
        payload = {"records": [], "next_before_id": None}
        with patch("main.load_qa_history", return_value=payload) as load:
            response = self.client.get(
                "/api/courses/3/questions?before_id=20&user_id=999"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        load.assert_called_once_with(5, 3, before_id=20)

    def test_foreign_course_returns_not_found(self):
        with patch("main.load_qa_history", side_effect=LookupError):
            response = self.client.get("/api/courses/9/questions")
        self.assertEqual(response.status_code, 404)

    def test_invalid_cursor_does_not_read_history(self):
        with patch("main.load_qa_history") as load:
            for value in ("0", "-1", "invalid"):
                with self.subTest(value=value):
                    response = self.client.get(
                        f"/api/courses/3/questions?before_id={value}"
                    )
                    self.assertEqual(response.status_code, 422)
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
