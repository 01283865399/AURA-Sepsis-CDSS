from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class MedicalContentDraftApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_coverage_separates_drafts_from_clinical_readiness(self) -> None:
        response = self.client.get("/api/v1/medical-content/final/coverage")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["counts"],
            {
                "conditions": 500,
                "symptoms": 300,
                "phenotype_concepts": 1000,
                "associations": 2222,
            },
        )
        self.assertEqual(payload["content_status"], "draft_only")
        self.assertTrue(payload["not_for_clinical_use"])
        self.assertEqual(payload["arabic_translations_available"], 0)

    def test_condition_and_phenotype_records_are_paginated_and_gated(self) -> None:
        conditions = self.client.get(
            "/api/v1/medical-content/final/conditions?offset=0&limit=2"
        )
        phenotypes = self.client.get(
            "/api/v1/medical-content/final/phenotype_concepts?offset=0&limit=1"
        )

        self.assertEqual(conditions.status_code, 200)
        self.assertEqual(conditions.json()["total"], 500)
        self.assertEqual(len(conditions.json()["records"]), 2)
        self.assertEqual(conditions.json()["records"][0]["condition_ar"], None)
        self.assertTrue(conditions.json()["records"][0]["not_for_clinical_use"])
        self.assertEqual(phenotypes.status_code, 200)
        self.assertFalse(phenotypes.json()["records"][0]["clinical_symptom"])
        self.assertFalse(phenotypes.json()["records"][0]["symptom_catalog_eligible"])

    def test_single_condition_and_symptom_routes_use_stable_ids(self) -> None:
        condition_page = self.client.get(
            "/api/v1/medical-content/final/conditions?limit=1"
        ).json()
        symptom_page = self.client.get(
            "/api/v1/medical-content/final/symptoms?limit=1"
        ).json()
        condition_id = condition_page["records"][0]["condition_id"]
        symptom_id = symptom_page["records"][0]["symptom_id"]

        condition = self.client.get(
            f"/api/v1/medical-content/final/conditions/{condition_id}"
        )
        symptom = self.client.get(
            f"/api/v1/medical-content/final/symptoms/{symptom_id}"
        )

        self.assertEqual(condition.status_code, 200)
        self.assertEqual(condition.json()["record"]["condition_id"], condition_id)
        self.assertEqual(symptom.status_code, 200)
        self.assertEqual(symptom.json()["record"]["symptom_id"], symptom_id)

    def test_association_can_be_fetched_by_id(self) -> None:
        response = self.client.get(
            "/api/v1/medical-content/final/associations/"
            "doid_1205__symp_0000900"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["record"]["clinical_symptom_approved"])
        self.assertTrue(response.json()["not_for_clinical_use"])

    def test_api_rejects_unbounded_or_invalid_requests(self) -> None:
        self.assertEqual(
            self.client.get("/api/v1/medical-content/final/unknown").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/medical-content/final/conditions?limit=101"
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/medical-content/final/conditions?condition_id=doid_1"
            ).status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
