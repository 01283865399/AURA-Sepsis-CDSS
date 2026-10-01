"""Validated-input inference service for a trained sepsis model ensemble."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
import shap

MEDICAL_DISCLAIMER = (
    "For clinician review only. This model output is not a diagnosis, is not "
    "a treatment recommendation, and must not replace clinical judgment or "
    "local protocols. The model and thresholds have not been clinically validated."
)
INTERVAL_WARNING = (
    "This is exploratory disagreement among cross-validation fold models, not "
    "a calibrated statistical confidence interval or a clinically validated "
    "probability interval."
)


class ModelNotApprovedError(RuntimeError):
    """Raised when a model artifact has no explicit clinical release approval."""


def prepare_prediction_payload(
    payload: Mapping[str, Any],
    feature_names: Sequence[str],
    imputation_values: Mapping[str, float],
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Validate inputs and produce ordered model features with explicit imputation."""
    expected_features = list(feature_names)
    unexpected = sorted(set(payload) - set(expected_features))
    if unexpected:
        raise ValueError(f"Unknown model feature(s): {unexpected}")
    missing_baselines = sorted(set(expected_features) - set(imputation_values))
    if missing_baselines:
        raise ValueError(f"No imputation value configured for feature(s): {missing_baselines}")

    values: dict[str, float] = {}
    provided_features: list[str] = []
    imputed_features: list[str] = []
    for feature in expected_features:
        raw_value = payload.get(feature)
        if raw_value is None:
            values[feature] = float(imputation_values[feature])
            imputed_features.append(feature)
            continue
        if isinstance(raw_value, bool):
            raise ValueError(f"Feature {feature!r} must be numeric, not boolean.")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Feature {feature!r} must be numeric.") from error
        if not np.isfinite(value):
            raise ValueError(f"Feature {feature!r} must be finite.")
        values[feature] = value
        provided_features.append(feature)

    frame = pd.DataFrame([values], columns=expected_features, dtype=float)
    return frame, provided_features, imputed_features


class SepsisService:
    """Run an ensemble prediction and return risk, uncertainty, and explanations."""

    def __init__(
        self,
        artifact: Mapping[str, Any],
        *,
        allow_research_artifact: bool = False,
    ) -> None:
        artifact_format = artifact.get("artifact_format")
        if artifact_format not in {1, 2}:
            raise ValueError("Unsupported sepsis model artifact format.")
        models = artifact.get("models")
        metadata = artifact.get("metadata")
        if not isinstance(models, list) or len(models) < 2 or not isinstance(metadata, dict):
            raise ValueError("Artifact must contain at least two fitted models and metadata.")
        self.clinically_approved = (
            metadata.get("deployment_approved") is True
            and metadata.get("clinical_validation_status") == "approved"
        )
        if not self.clinically_approved and not allow_research_artifact:
            raise ModelNotApprovedError(
                "This model has no explicit clinical validation and deployment approval."
            )
        self.models = models
        self.metadata = metadata
        self.feature_names = list(metadata.get("feature_names", []))
        imputation = metadata.get("imputation", {})
        member_medians = imputation.get("member_training_medians")
        if member_medians is None:
            common_medians = dict(imputation.get("training_medians", {}))
            common_medians.update(imputation.get("domain_baselines", {}))
            member_medians = [common_medians for _ in models]
        if not isinstance(member_medians, list) or len(member_medians) != len(models):
            raise ValueError("Artifact must contain training medians for each ensemble member.")
        self.member_imputation_values = [dict(values) for values in member_medians]
        thresholds = metadata.get("risk_thresholds", {})
        self.medium_threshold = float(thresholds.get("medium", 0.35))
        self.high_threshold = float(thresholds.get("high", 0.70))
        if (
            not self.feature_names
            or not self.medium_threshold < self.high_threshold
            or self.medium_threshold <= 0.0
            or self.high_threshold >= 1.0
        ):
            raise ValueError("Artifact metadata contains invalid features or risk thresholds.")
        self._explainers: list[shap.TreeExplainer] | None = None

    @classmethod
    def from_artifact(
        cls,
        artifact_path: str | Path,
        *,
        allow_research_artifact: bool = False,
    ) -> "SepsisService":
        """Load a trusted, locally produced model artifact."""
        path = Path(artifact_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Sepsis model artifact not found at {path}. "
                "Run python -m backend.train_sepsis before starting the prediction API."
            )
        artifact = joblib.load(path)
        if not isinstance(artifact, dict):
            raise ValueError("Sepsis model artifact has an invalid root structure.")
        return cls(artifact, allow_research_artifact=allow_research_artifact)

    def _explain(
        self,
        member_features: list[pd.DataFrame],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if self._explainers is None:
            self._explainers = [shap.TreeExplainer(model) for model in self.models]
        contributions = np.zeros(len(self.feature_names), dtype=float)
        for explainer, features in zip(self._explainers, member_features):
            shap_values = explainer(features)
            values = np.asarray(shap_values.values)
            if values.ndim == 3:
                values = values[:, :, -1]
            contributions += values.reshape(-1, len(self.feature_names))[0]
        contributions /= len(self._explainers)

        ranked = [
            {"feature": feature, "impact": round(float(impact), 6)}
            for feature, impact in zip(self.feature_names, contributions)
        ]
        positive = sorted(
            (item for item in ranked if item["impact"] > 0),
            key=lambda item: item["impact"],
            reverse=True,
        )[:5]
        negative = sorted(
            (item for item in ranked if item["impact"] < 0),
            key=lambda item: item["impact"],
        )[:5]
        return positive, negative

    def predict(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Return one prediction with input completeness and model-dispersion data."""
        member_features: list[pd.DataFrame] = []
        provided: list[str] | None = None
        imputed: list[str] | None = None
        member_probabilities_list: list[float] = []
        for model, medians in zip(self.models, self.member_imputation_values):
            features, member_provided, member_imputed = prepare_prediction_payload(
                payload,
                self.feature_names,
                medians,
            )
            if provided is None:
                provided = member_provided
                imputed = member_imputed
            member_features.append(features)
            member_probabilities_list.append(
                float(model.predict_proba(features)[0, 1])
            )
        if provided is None or imputed is None:
            raise RuntimeError("Model artifact has no usable ensemble members.")
        member_probabilities = np.asarray(member_probabilities_list, dtype=float)
        if not np.isfinite(member_probabilities).all():
            raise RuntimeError("The model ensemble returned a non-finite prediction.")
        probability = float(member_probabilities.mean())
        lower, upper = np.percentile(member_probabilities, [2.5, 97.5]).tolist()
        positive, negative = self._explain(member_features)

        if probability >= self.high_threshold:
            tier = "High"
            risk_level = "High Risk"
        elif probability >= self.medium_threshold:
            tier = "Medium"
            risk_level = "Moderate Risk"
        else:
            tier = "Low"
            risk_level = "Low Risk"
        completeness = len(provided) / len(self.feature_names)

        return {
            "sepsis_prediction": int(probability >= self.high_threshold),
            "sepsis_probability": round(probability, 6),
            "probability_interpretation": (
                "Uncalibrated model score; do not interpret as a calibrated "
                "individual disease probability."
            ),
            "risk_level": risk_level,
            "risk_tier": tier,
            "deployment_status": (
                "clinically_approved" if self.clinically_approved else "research_only"
            ),
            "decision_threshold": self.high_threshold,
            "risk_thresholds": {
                "medium": self.medium_threshold,
                "high": self.high_threshold,
            },
            "data_completeness": {
                "score": round(completeness, 4),
                "provided_feature_count": len(provided),
                "required_feature_count": len(self.feature_names),
                "provided_features": provided,
                "imputed_features": imputed,
            },
            "confidence_metrics": {
                "data_completeness_score": round(completeness, 4),
                "ensemble_size": len(self.models),
                "ensemble_model_spread": round(float(upper - lower), 6),
                "note": (
                    "Input completeness is not predictive confidence. The "
                    "ensemble range is exploratory and not clinically calibrated."
                ),
            },
            "model_uncertainty_interval": {
                "lower": round(float(lower), 6),
                "upper": round(float(upper), 6),
                "percentiles": [2.5, 97.5],
                "method": "Cross-validation fold-model score percentile range",
                "interpretation": INTERVAL_WARNING,
            },
            "top_positive_contributions": positive,
            "top_negative_contributions": negative,
            "top_contributing_factors": sorted(
                positive + negative,
                key=lambda item: abs(item["impact"]),
                reverse=True,
            )[:5],
            "explanation_note": (
                "SHAP values describe model contribution, not clinical causation "
                "or a change in calibrated disease probability."
            ),
            "medical_disclaimer": MEDICAL_DISCLAIMER,
            "model_version": self.metadata.get("model_version", "unknown"),
        }
