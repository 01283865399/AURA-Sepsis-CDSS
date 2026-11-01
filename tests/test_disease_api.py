"""API contract tests that do not require model training or Supabase credentials."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class DiseaseApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.predictions = [
            {"condition": "research label", "probability": 0.75},
            {"condition": "alternate label", "probability": 0.25},
        ]

    def test_all_diagnosis_routes_return_ranked_research_scores(self) -> None:
        cases = [
            (
                "/api/v1/diagnose/symptoms",
                {"symptoms": ["fever", "cough"], "top_k": 2},
                "app.routers.symptoms.predict_symptoms",
            ),
            (
                "/api/v1/diagnose/ddxplus",
                {"age": 33, "sex": "F", "evidences": ["E_48"], "top_k": 2},
                "app.routers.ddxplus.predict_ddxplus",
            ),
            (
                "/api/v1/diagnose/diabetes",
                {
                    "gender": "Female",
                    "age": 36,
                    "hypertension": 0,
                    "heart_disease": 0,
                    "smoking_history": "never",
                    "bmi": 24.0,
                    "HbA1c_level": 5.4,
                    "blood_glucose_level": 100,
                    "top_k": 2,
                },
                "app.routers.diabetes.predict_tabular",
            ),
            (
                "/api/v1/diagnose/heart",
                {"age": 63, "sex": "Male", "top_k": 2},
                "app.routers.heart.predict_tabular",
            ),
            (
                "/api/v1/diagnose/kidney",
                {"age": 48, "top_k": 2},
                "app.routers.kidney.predict_tabular",
            ),
        ]
        for path, payload, predictor in cases:
            with self.subTest(path=path):
                with (
                    patch(predictor, return_value=("test-model", self.predictions)),
                    patch("app.core.responses.persist_prediction", return_value=False),
                ):
                    response = self.client.post(path, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertEqual(result["model_name"], "test-model")
                self.assertEqual(result["predictions"], self.predictions)
                self.assertFalse(result["persisted"])
                self.assertTrue(result["research_only"])
                self.assertIn("not a diagnosis", result["notice"])

    def test_invalid_ddxplus_evidence_is_rejected_by_schema(self) -> None:
        response = self.client.post(
            "/api/v1/diagnose/ddxplus",
            json={"age": 30, "sex": "M", "evidences": ["unknown"]},
        )
        self.assertEqual(response.status_code, 422)

    def test_kidney_request_requires_at_least_one_feature(self) -> None:
        response = self.client.post("/api/v1/diagnose/kidney", json={})
        self.assertEqual(response.status_code, 422)

    def test_health_discloses_research_scope_and_persistence_state(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["research_only"])
        self.assertIn("supabase_configured", response.json())

    def test_cors_allows_the_configured_local_frontend(self) -> None:
        response = self.client.options(
            "/api/v1/diagnose/diabetes",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
