from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.responses import make_response
from app.main import app
from app.services.medical_content_service import medical_service
from data.medical_content.validator import validate_content
from fastapi.testclient import TestClient


class MedicalContentTests(unittest.TestCase):
    def test_checked_in_package_loads_but_reports_incomplete_coverage(self) -> None:
        report = medical_service.get_coverage()

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["coverage_status"], "incomplete")
        self.assertEqual(report["counts"]["published_conditions"], 0)
        self.assertEqual(report["deficits"]["conditions"], 200)
        self.assertTrue(report["research_only"])

    def test_unknown_prediction_does_not_get_invented_content(self) -> None:
        enriched = medical_service.enrich_prediction(
            {"condition": "unmapped research class", "probability": 0.99}
        )

        self.assertFalse(enriched["available"])
        self.assertEqual(enriched["status"], "no_reviewed_match")
        self.assertIn("incomplete", enriched["notice"].lower())

    def test_emergency_lookup_never_claims_no_emergency_when_unmatched(self) -> None:
        result = medical_service.check_emergency(["unmapped symptom"])

        self.assertEqual(result["review_status"], "not_assessed")
        self.assertNotIn("emergency", result)
        self.assertIn("does not rule out", result["notice"])

    def test_published_content_requires_review_and_https_reference(self) -> None:
        errors = validate_content(
            {
                "conditions": [
                    {
                        "condition_id": "example",
                        "content_status": "published",
                        "review_status": "unreviewed",
                        "references": [],
                    }
                ],
                "symptoms": [],
                "specialists": [],
                "emergency_signs": [],
                "drugs": [],
                "interactions": [],
                "lab_tests": [],
                "imaging_protocols": [],
                "references": [],
                "citations": [],
                "guidelines": [],
                "disclaimers": {"general": {"ar": "تنبيه", "en": "Notice"}},
            }
        )

        self.assertTrue(any("requires an HTTPS source reference" in error for error in errors))
        self.assertTrue(any("requires clinical review" in error for error in errors))
        self.assertTrue(any("missing condition_en" in error for error in errors))

    def test_prediction_response_keeps_model_scores_and_adds_content_status(self) -> None:
        predictions = [{"condition": "unknown", "probability": 0.8}]
        with patch("app.core.responses.persist_prediction", return_value=False):
            response = make_response("test", "test-model", predictions)

        payload = response.model_dump()
        self.assertEqual(payload["predictions"], predictions)
        self.assertFalse(payload["medical_content"][0]["available"])

    def test_coverage_api_exposes_incomplete_state(self) -> None:
        response = TestClient(app).get("/api/v1/medical-content/coverage")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["coverage_status"], "incomplete")
        self.assertEqual(response.json()["targets"]["symptoms"], 132)


if __name__ == "__main__":
    unittest.main()
