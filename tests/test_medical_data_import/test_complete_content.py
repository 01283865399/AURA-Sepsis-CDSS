from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = ROOT / "data" / "medical_content" / "final" / "complete"


class CompleteContentBuildTests(unittest.TestCase):
    def read_json(self, filename: str):
        return json.loads((BUILD_DIR / filename).read_text(encoding="utf-8"))

    def test_full_source_counts_and_explicit_nonclinical_status(self) -> None:
        stats = self.read_json("stats.json")
        conditions = self.read_json("conditions.json")
        phenotypes = self.read_json("symptoms.json")
        terms = self.read_json("symptom_terms.json")
        associations = self.read_json("associations.json")
        qa = self.read_json("qa.json")

        self.assertEqual(len(conditions), 12_335)
        self.assertEqual(
            sum(record["record_type"] == "condition_content_candidate" for record in conditions),
            500,
        )
        self.assertEqual(len(phenotypes), 1_000)
        self.assertEqual(len(terms), 300)
        self.assertEqual(len(associations), 2_222)
        self.assertEqual(len(qa), 16_407)
        self.assertTrue(
            all(record["not_for_clinical_use"] for record in conditions + phenotypes + qa)
        )
        self.assertTrue(all(record["clinical_symptom"] is False for record in phenotypes))
        self.assertTrue(all(record["question_ar"] is None for record in qa))
        self.assertEqual(stats["arabic_translation"]["translated_records"], 0)
        self.assertEqual(stats["condition_selection"]["ranking_is_not_prevalence"], True)
        self.assertFalse(stats["safety"]["source_claims_independently_verified"])

    def test_unavailable_emergency_and_specialist_data_is_not_fabricated(self) -> None:
        stats = self.read_json("stats.json")
        self.assertEqual(self.read_json("specialists.json"), [])
        self.assertEqual(self.read_json("emergency_signs.json"), [])
        self.assertEqual(
            stats["non_generated_catalogs"]["emergency_signs"]["count"], 0
        )
        self.assertEqual(stats["non_generated_catalogs"]["specialists"]["count"], 0)


class CompleteContentDraftApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_coverage_and_pagination_are_gated(self) -> None:
        summary = self.client.get(
            "/api/v1/medical-content/complete-drafts/coverage"
        )
        page = self.client.get(
            "/api/v1/medical-content/complete-drafts/conditions?limit=2"
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["counts"]["conditions"], 12_335)
        self.assertEqual(summary.json()["review_status"], "unreviewed")
        self.assertTrue(summary.json()["not_for_clinical_use"])
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["total"], 12_335)
        self.assertEqual(len(page.json()["records"]), 2)
        self.assertTrue(page.json()["records"][0]["not_for_clinical_use"])

    def test_qa_search_and_validation(self) -> None:
        response = self.client.get(
            "/api/v1/medical-content/complete-drafts/qa/search",
            params={"q": "Adult Acute Lymphoblastic Leukemia"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["total"], 1)
        self.assertIsNone(payload["records"][0]["answer_ar"])
        self.assertTrue(payload["not_for_clinical_use"])
        self.assertEqual(
            self.client.get(
                "/api/v1/medical-content/complete-drafts/qa/search",
                params={"q": " "},
            ).status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
