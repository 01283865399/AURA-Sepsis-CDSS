from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from backend.sepsis_service import (
    ModelNotApprovedError,
    SepsisService,
    prepare_prediction_payload,
)
from backend.train_sepsis import (
    _select_f2_threshold,
    load_patient_data,
    preprocess_patient_frame,
    split_by_patient,
    train_pipeline,
)


class TemporalPreprocessingTests(unittest.TestCase):
    def test_forward_fill_uses_prior_timestamp_and_preserves_leading_missing(self) -> None:
        frame = pd.DataFrame(
            {
                "ICULOS": [3, 1, 2],
                "HR": [None, None, 90.0],
                "SepsisLabel": [0, 0, 1],
            }
        )

        result = preprocess_patient_frame(frame, "patient-1")

        self.assertEqual(result["ICULOS"].tolist(), [1, 2, 3])
        self.assertTrue(pd.isna(result.loc[0, "HR"]))
        self.assertEqual(result["HR"].iloc[1:].tolist(), [90.0, 90.0])
        self.assertEqual(result["SepsisLabel"].tolist(), [0, 1, 0])

    def test_missing_timestamp_fails_instead_of_guessing_order(self) -> None:
        frame = pd.DataFrame({"ICULOS": [None], "HR": [80.0], "SepsisLabel": [0]})
        with self.assertRaisesRegex(ValueError, "missing or invalid ICULOS"):
            preprocess_patient_frame(frame, "patient-1")

    def test_file_loading_can_use_process_workers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for patient_id, heart_rate in (("p1", 70), ("p2", 110)):
                pd.DataFrame(
                    {
                        "ICULOS": [1, 2],
                        "HR": [heart_rate, None],
                        "SepsisLabel": [0, 1 if heart_rate > 100 else 0],
                    }
                ).to_csv(root / f"{patient_id}.psv", sep="|", index=False)

            dataset = load_patient_data(root, n_jobs=2)

            self.assertEqual(dataset["Patient_ID"].nunique(), 2)
            self.assertEqual(dataset["HR"].tolist(), [70.0, 70.0, 110.0, 110.0])


class PatientSplitTests(unittest.TestCase):
    def test_patient_groups_do_not_overlap_between_splits(self) -> None:
        patient_ids = pd.Series(
            [patient for patient in range(30) for _ in range(2)],
            dtype="int64",
        )
        labels = pd.Series([0, 1] * 30, dtype="int64")

        splits = split_by_patient(labels, patient_ids, random_state=17)
        train_groups = set(patient_ids.iloc[splits.train])
        validation_groups = set(patient_ids.iloc[splits.validation])
        test_groups = set(patient_ids.iloc[splits.test])

        self.assertFalse(train_groups & validation_groups)
        self.assertFalse(train_groups & test_groups)
        self.assertFalse(validation_groups & test_groups)

    def test_f2_threshold_selection_prioritizes_recall(self) -> None:
        labels = pd.Series([0, 0, 0, 1, 1, 1], dtype="int64")
        probabilities = np.array([0.01, 0.10, 0.35, 0.12, 0.40, 0.80])

        selected = _select_f2_threshold(labels, probabilities)

        self.assertGreaterEqual(selected["recall"], 2 / 3)
        self.assertGreater(selected["threshold"], 0.0)


class DynamicPayloadTests(unittest.TestCase):
    def test_missing_features_are_imputed_and_completeness_is_countable(self) -> None:
        features, provided, imputed = prepare_prediction_payload(
            {"HR": 92},
            ["HR", "Lactate"],
            {"HR": 80, "Lactate": 1.8},
        )

        self.assertEqual(features.columns.tolist(), ["HR", "Lactate"])
        self.assertEqual(features.iloc[0].tolist(), [92.0, 1.8])
        self.assertEqual(provided, ["HR"])
        self.assertEqual(imputed, ["Lactate"])

    def test_invalid_values_and_unknown_features_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown model feature"):
            prepare_prediction_payload(
                {"HR": 92, "unexpected": 1},
                ["HR"],
                {"HR": 80},
            )
        with self.assertRaisesRegex(ValueError, "must be finite"):
            prepare_prediction_payload(
                {"HR": float("nan")},
                ["HR"],
                {"HR": 80},
            )


class TrainingAndInferenceTests(unittest.TestCase):
    def test_grouped_training_artifact_serves_prediction_and_interval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data_dir = root / "data"
            data_dir.mkdir()
            for patient_number in range(30):
                is_positive_patient = patient_number % 2 == 0
                frame = pd.DataFrame(
                    {
                        "ICULOS": [1, 2, 3],
                        "HR": [
                            105.0 if is_positive_patient else 70.0,
                            None,
                            110.0 if is_positive_patient else 72.0,
                        ],
                        "WBC": [12.0 if is_positive_patient else 6.0, None, 14.0 if is_positive_patient else 7.0],
                        "SepsisLabel": [0, int(is_positive_patient), int(is_positive_patient)],
                    }
                )
                frame.to_csv(data_dir / f"patient-{patient_number:02}.psv", sep="|", index=False)

            artifact_path = root / "sepsis_model.joblib"
            metadata = train_pipeline(
                data_dir,
                artifact_path,
                ensemble_size=2,
                random_state=12,
                n_jobs=1,
            )
            with self.assertRaises(ModelNotApprovedError):
                SepsisService.from_artifact(artifact_path)
            service = SepsisService.from_artifact(
                artifact_path,
                allow_research_artifact=True,
            )
            result = service.predict({"HR": 112.0, "WBC": 16.0})

            self.assertTrue(metadata["split_patient_overlap_verified"])
            self.assertIn("test", metadata["metrics"])
            self.assertEqual(metadata["artifact_format"], 2)
            self.assertEqual(metadata["cross_validation"]["method"], "StratifiedGroupKFold")
            self.assertEqual(len(metadata["imputation"]["member_training_medians"]), 2)
            self.assertEqual(
                metadata["threshold_selection"]["selection_metric"],
                "validation F2 (beta=2); recall prioritized",
            )
            self.assertIn("test_ensemble_mean", metadata["probability_distributions"])
            self.assertTrue(0.0 <= result["sepsis_probability"] <= 1.0)
            self.assertEqual(result["data_completeness"]["provided_feature_count"], 2)
            self.assertLessEqual(result["model_uncertainty_interval"]["lower"], result["model_uncertainty_interval"]["upper"])
            self.assertIn("not a calibrated statistical confidence interval", result["model_uncertainty_interval"]["interpretation"])
            self.assertIn("medical_disclaimer", result)
            self.assertEqual(result["deployment_status"], "research_only")


if __name__ == "__main__":
    unittest.main()
