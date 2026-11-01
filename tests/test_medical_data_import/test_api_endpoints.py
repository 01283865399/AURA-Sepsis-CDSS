from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class ImportApiIsolationTests(unittest.TestCase):
    def test_candidate_import_does_not_add_published_api_coverage(self) -> None:
        response = TestClient(app).get("/api/v1/medical-content/coverage")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["published_conditions"], 0)
        self.assertEqual(payload["coverage_status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
