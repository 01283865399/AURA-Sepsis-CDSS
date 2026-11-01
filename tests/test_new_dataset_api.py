"""Contract tests for the imported dataset inference endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.predictors import ModelUnavailableError
from app.main import app


class NewDatasetApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.predictions = [
            {"condition": "research label", "probability": 0.75},
            {"condition": "alternate label", "probability": 0.25},
        ]

    def test_image_routes_accept_uploads_and_return_research_scores(self) -> None:
        routes = (
            "skin_lesions_8class",
            "isic_2019",
            "covid19_radiography",
            "tb_chest_radiography",
        )
        for dataset in routes:
            with self.subTest(dataset=dataset):
                with (
                    patch(
                        "app.routers._image_common.predict_image",
                        return_value=("EfficientNet-B0", self.predictions),
                    ) as predictor,
                    patch("app.core.responses.persist_prediction", return_value=False),
                ):
                    response = self.client.post(
                        f"/api/v1/diagnose/{dataset}",
                        files={"image": ("sample.png", b"sample image", "image/png")},
                        data={"top_k": "2"},
                    )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["predictions"], self.predictions)
                self.assertTrue(response.json()["research_only"])
                predictor.assert_called_once()

    def test_image_routes_reject_non_image_multipart_files(self) -> None:
        response = self.client.post(
            "/api/v1/diagnose/isic_2019",
            files={"image": ("sample.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)

    def test_image_model_unavailability_is_reported_as_service_unavailable(self) -> None:
        with patch(
            "app.routers._image_common.predict_image",
            side_effect=ModelUnavailableError("model has not been trained"),
        ):
            response = self.client.post(
                "/api/v1/diagnose/tb_chest_radiography",
                files={"image": ("sample.png", b"sample image", "image/png")},
            )
        self.assertEqual(response.status_code, 503)

    def test_liver_route_validates_schema_and_returns_ranked_scores(self) -> None:
        payload = {
            "AGE": 46,
            "GENDER": 2,
            "TB": 1.4,
            "DB": 0.4,
            "ALK": 298,
            "SGPT": 509,
            "SGOT": 623,
            "TP": 3.6,
            "ALB": 1,
            "AG": 0.3,
            "top_k": 2,
        }
        with (
            patch(
                "app.routers.indian_liver_patient.predict_tabular",
                return_value=("indian_liver_patient:XGBoost", self.predictions),
            ),
            patch("app.core.responses.persist_prediction", return_value=False),
        ):
            response = self.client.post(
                "/api/v1/diagnose/indian_liver_patient", json=payload
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["predictions"], self.predictions)
        self.assertTrue(response.json()["research_only"])

    def test_liver_route_rejects_invalid_gender(self) -> None:
        response = self.client.post(
            "/api/v1/diagnose/indian_liver_patient",
            json={
                "AGE": 46,
                "GENDER": 3,
                "TB": 1,
                "DB": 0.3,
                "ALK": 200,
                "SGPT": 30,
                "SGOT": 30,
                "TP": 6,
                "ALB": 3,
                "AG": 1,
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
