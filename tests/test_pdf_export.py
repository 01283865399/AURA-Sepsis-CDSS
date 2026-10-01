from __future__ import annotations

import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from backend import main


class PDFExportTests(unittest.TestCase):
    @staticmethod
    def _patient_report_fixture() -> dict:
        return {
            "generated_at": "2026-10-01T12:00:00+00:00",
            "patient_summary": {
                "age_years": 65,
                "gender": "Male",
                "admission_context": "ICU monitoring context supplied by the operator; not independently verified.",
            },
            "vital_signs_and_lab_biomarkers": {
                "observations": [
                    {
                        "feature": "HR",
                        "value": 105,
                        "unit": "bpm",
                        "general_adult_reference_range": {"lower": 60, "upper": 100},
                    },
                    {"feature": "WBC", "value": 14.5, "unit": "×10⁹/L"},
                ],
            },
            "sepsis_assessment": {
                "risk_tier": "Medium",
                "risk_level": "Moderate Risk",
                "model_probability": 0.42,
                "deployment_status": "research_only",
                "data_completeness": {
                    "score": 0.75,
                    "provided_feature_count": 3,
                    "required_feature_count": 4,
                },
            },
            "explainable_ai": {
                "top_contributing_factors": [
                    {"feature": "HR", "impact": 0.2},
                    {"feature": "WBC", "impact": -0.1},
                ],
            },
            "medical_image_review": {
                "status": "not_provided",
                "clinical_summary": "No medical image was supplied for review.",
                "findings": None,
                "infection_site": None,
                "confidence_score": None,
            },
            "clinical_recommendations": {
                "immediate_medical_action_bundle": [
                    "Arrange timely clinician review and compare the current observations with the patient's baseline and recent trend."
                ],
                "lab_and_imaging_follow_up": [
                    "Review recent laboratory results and trends; repeat testing only when clinically indicated by the treating team or local protocol."
                ],
            },
        }

    def test_export_endpoint_returns_downloadable_single_page_pdf(self) -> None:
        research_service = SimpleNamespace(
            clinically_approved=False,
            metadata={"model_version": "test-model"},
        )
        payload = {
            "risk_tier": "Medium",
            "sepsis_probability": 0.42,
            "data_completeness": {
                "score": 0.75,
                "provided_feature_count": 3,
                "required_feature_count": 4,
                "provided_features": ["HR", "WBC", "Temp"],
                "imputed_features": ["Lactate"],
            },
            "top_shap_contributions": [
                {"feature": "Heart rate", "impact": 0.25},
                {"feature": "Lactate", "impact": -0.12},
            ],
            "risk_thresholds": {"medium": 0.2, "high": 0.45},
            "uncertainty_interval": {"lower": 0.31, "upper": 0.56},
            "model_version": "test-model",
        }

        with patch("backend.main.get_sepsis_service", return_value=research_service):
            response = main.export_pdf(main.PDFExportRequest.model_validate(payload))

        self.assertEqual(response.media_type, "application/pdf")
        self.assertIn(
            'attachment; filename="Sepsis_Clinical_Report.pdf"',
            response.headers["Content-Disposition"],
        )
        self.assertTrue(response.body.startswith(b"%PDF-"))
        self.assertEqual(
            len(re.findall(rb"/Type\s*/Page\b", response.body)),
            1,
            "The CDS PDF export should fit on exactly one page.",
        )

    def test_export_endpoint_rejects_invalid_score_and_feature_counts(self) -> None:
        payload = {
            "risk_tier": "High",
            "sepsis_probability": 1.5,
            "data_completeness": {
                "score": 1.2,
                "provided_feature_count": 1,
                "required_feature_count": 2,
                "provided_features": ["HR"],
                "imputed_features": ["WBC"],
            },
            "top_shap_contributions": [],
        }

        with self.assertRaises(ValidationError):
            main.PDFExportRequest.model_validate(payload)

    def test_arabic_pdf_is_shaped_embeds_font_and_stays_single_page(self) -> None:
        research_service = SimpleNamespace(
            clinically_approved=False,
            metadata={"model_version": "test-model"},
        )
        payload = {
            "lang": "ar",
            "risk_tier": "High",
            "sepsis_probability": 0.82,
            "data_completeness": {
                "score": 0.75,
                "provided_feature_count": 3,
                "required_feature_count": 4,
                "provided_features": ["HR", "WBC", "Temp"],
                "imputed_features": ["Lactate"],
            },
            "top_shap_contributions": [
                {"feature": "Heart rate", "impact": 0.25},
                {"feature": "Lactate", "impact": -0.12},
            ],
            "risk_thresholds": {"medium": 0.2, "high": 0.45},
            "uncertainty_interval": {"lower": 0.31, "upper": 0.92},
        }

        with patch("backend.main.get_sepsis_service", return_value=research_service):
            response = main.export_pdf(main.PDFExportRequest.model_validate(payload))

        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))
        self.assertIn(b"/FontFile2", response.body)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", response.body)), 1)
        shaped = main._pdf_localize("تقرير طبي", "ar")
        self.assertTrue(
            any(
                "\ufb50" <= character <= "\ufdff"
                or "\ufe70" <= character <= "\ufeff"
                for character in shaped
            )
        )

    def test_export_pdf_rejects_unsupported_language(self) -> None:
        with self.assertRaises(ValidationError):
            main.PDFExportRequest.model_validate({
                "lang": "fr",
                "risk_tier": "Low",
                "sepsis_probability": 0.1,
                "data_completeness": {
                    "score": 1.0,
                    "provided_feature_count": 1,
                    "required_feature_count": 1,
                    "provided_features": ["HR"],
                    "imputed_features": [],
                },
                "top_shap_contributions": [],
            })

    def test_patient_report_pdf_exports_with_requested_language(self) -> None:
        report = self._patient_report_fixture()
        for language in ("en", "ar"):
            request = main.PatientReportExportRequest.model_validate({
                "lang": language,
                "vitals": {"HR": 105, "WBC": 14.5},
            })
            with patch("backend.main.generate_full_report", return_value=report):
                response = main.export_patient_report_pdf(request)

            self.assertEqual(response.media_type, "application/pdf")
            self.assertIn(
                'attachment; filename="Sepsis_Patient_Report.pdf"',
                response.headers["Content-Disposition"],
            )
            self.assertTrue(response.body.startswith(b"%PDF-"))
            self.assertGreaterEqual(
                len(re.findall(rb"/Type\s*/Page\b", response.body)),
                1,
            )
            if language == "ar":
                self.assertIn(b"/FontFile2", response.body)

if __name__ == "__main__":
    unittest.main()
