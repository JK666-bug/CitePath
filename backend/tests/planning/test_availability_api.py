"""API coverage for account study availability, without a running database."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app, current_user
from planning.inputs import StudyAvailability


PATH = "/api/me/study-availability"


class StudyAvailabilityApiTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))
        self.owner_id = 17
        self.enterContext(patch.dict(app.dependency_overrides, {
            current_user: lambda: {"id": self.owner_id},
        }))

    def test_requires_sign_in_to_read_or_write(self):
        app.dependency_overrides.pop(current_user)
        with (
            patch("main.user_from_token", return_value=None),
            patch("main.load_study_availability") as load,
            patch("main.save_study_availability") as save,
        ):
            self.assertEqual(self.client.get(PATH).status_code, 401)
            self.assertEqual(
                self.client.put(PATH, json={"weekday_minutes": [480] * 7}).status_code,
                401,
            )

        load.assert_not_called()
        save.assert_not_called()

    def test_returns_eight_hours_a_day_for_an_account_without_settings(self):
        with patch("main.load_study_availability", return_value=None) as load:
            response = self.client.get(PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"weekday_minutes": [480] * 7, "saved": False})
        load.assert_called_once_with(self.owner_id)

    def test_returns_saved_rest_days(self):
        values = [480, 0, 480, 480, 480, 0, 0]
        with patch("main.load_study_availability", return_value=StudyAvailability(tuple(values))):
            response = self.client.get(PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"weekday_minutes": values, "saved": True})

    def test_rejects_invalid_values_without_saving(self):
        with patch("main.save_study_availability") as save:
            for values in (
                [480] * 6,
                [480] * 8,
                [True] + [480] * 6,
                [1441] + [480] * 6,
                [-1] + [480] * 6,
            ):
                with self.subTest(values=values):
                    response = self.client.put(PATH, json={"weekday_minutes": values})
                    self.assertEqual(response.status_code, 422)

        save.assert_not_called()

    def test_save_and_reload_use_only_the_signed_in_account(self):
        stored = {}
        values = [0, 60, 120, 180, 240, 300, 360]
        with (
            patch("main.load_study_availability", side_effect=stored.get),
            patch("main.save_study_availability", side_effect=stored.__setitem__) as save,
        ):
            # A client-supplied account ID must not override the authenticated user.
            response = self.client.put(PATH, json={"user_id": 99, "weekday_minutes": values})
            reloaded = self.client.get(PATH)
            self.owner_id = 99
            other_account = self.client.get(PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"weekday_minutes": values, "saved": True})
        self.assertEqual(reloaded.status_code, 200)
        self.assertEqual(reloaded.json(), response.json())
        self.assertEqual(other_account.status_code, 200)
        self.assertEqual(other_account.json(), {"weekday_minutes": [480] * 7, "saved": False})
        save.assert_called_once_with(17, StudyAvailability(tuple(values)))


if __name__ == "__main__":
    unittest.main()
