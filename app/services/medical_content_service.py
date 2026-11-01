"""Source-gated access to medical content; never infer missing clinical facts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from data.medical_content.loader import load_content
from data.medical_content.validator import validate_content, validate_content_dir


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


class MedicalContentService:
    """Load the governed content package and expose only reviewed records."""

    def __init__(self, content_dir: Path) -> None:
        self.content_dir = content_dir
        self.content = load_content(content_dir)
        errors = validate_content(self.content)
        if errors:
            raise ValueError("Invalid medical content package: " + "; ".join(errors))
        self.conditions = self.content["conditions"]
        self.symptoms = self.content["symptoms"]
        self.specialists = self.content["specialists"]
        self.emergency = self.content["emergency_signs"]
        self.drugs = self.content["drugs"]
        self.references = self.content["references"]
        self.disclaimers = self.content["disclaimers"]

    @staticmethod
    def _is_reviewed(record: dict[str, Any]) -> bool:
        return (
            record.get("content_status") == "published"
            and record.get("review_status") == "clinically_reviewed"
        )

    @staticmethod
    def _name_matches(record: dict[str, Any], value: str) -> bool:
        target = _normalize(value)
        names = [
            record.get(key)
            for key in (
                "condition_id", "condition_en", "condition_ar", "name_en",
                "name_ar", "symptom_id", "specialist_id", "sign_id",
                "sign_en", "sign_ar",
            )
        ]
        for key in ("synonyms_en", "synonyms_ar", "aliases"):
            aliases = record.get(key, [])
            if isinstance(aliases, list):
                names.extend(aliases)
        return any(isinstance(name, str) and _normalize(name) == target for name in names)

    def get_condition_info(self, condition: str) -> dict[str, Any] | None:
        for record in self.conditions:
            if self._name_matches(record, condition) and self._is_reviewed(record):
                return record
        return None

    def enrich_prediction(self, prediction: dict[str, Any]) -> dict[str, Any]:
        """Return reviewed matching content, or explicitly report no coverage."""
        label = str(prediction.get("condition", ""))
        condition = self.get_condition_info(label)
        if condition is None:
            return {
                "condition": label,
                "available": False,
                "status": "no_reviewed_match",
                "notice": self.disclaimers["content_coverage"]["en"],
                "notice_ar": self.disclaimers["content_coverage"]["ar"],
            }
        return {
            "condition": label,
            "available": True,
            "status": "clinically_reviewed",
            "content": condition,
        }

    def get_symptoms_info(self, symptoms: list[str]) -> list[dict[str, Any]]:
        matches = []
        for symptom in symptoms:
            record = next(
                (
                    item for item in self.symptoms
                    if self._name_matches(item, symptom) and self._is_reviewed(item)
                ),
                None,
            )
            if record is not None:
                matches.append(record)
        return matches

    def get_specialist(self, condition: str) -> dict[str, Any] | None:
        record = self.get_condition_info(condition)
        if record is None:
            return None
        specialist_data = record.get("specialist", {})
        specialist_id = specialist_data.get("primary_id") if isinstance(specialist_data, dict) else None
        return next(
            (
                item for item in self.specialists
                if item.get("specialist_id") == specialist_id and self._is_reviewed(item)
            ),
            None,
        )

    def check_emergency(self, symptoms: list[str]) -> dict[str, Any]:
        matched = [
            record for record in self.emergency
            if self._is_reviewed(record)
            and any(self._name_matches(record, symptom) for symptom in symptoms)
        ]
        return {
            "review_status": "reviewed_signs_matched" if matched else "not_assessed",
            "matched_signs": matched,
            "notice": (
                "A missing match does not rule out an emergency. Contact local emergency services "
                "for immediate danger."
            ),
        }

    def get_differential_info(self, conditions: list[str]) -> list[dict[str, Any]]:
        return [
            info
            for condition in conditions
            if (info := self.get_condition_info(condition)) is not None
        ]

    def get_precautions(self, condition: str) -> list[str]:
        record = self.get_condition_info(condition)
        if record is None:
            return []
        values = record.get("precautions_ar", [])
        return values if isinstance(values, list) else []

    def get_prevention(self, condition: str) -> dict[str, Any] | None:
        record = self.get_condition_info(condition)
        prevention = record.get("prevention") if record else None
        return prevention if isinstance(prevention, dict) else None

    def get_references(self, condition: str) -> list[dict[str, Any]]:
        record = self.get_condition_info(condition)
        references = record.get("references", []) if record else []
        return references if isinstance(references, list) else []

    def get_urgency(
        self, condition: str, symptoms: list[str], confidence: float
    ) -> dict[str, Any]:
        record = self.get_condition_info(condition)
        return {
            "clinical_urgency": record.get("urgency_level") if record else None,
            "review_status": "clinically_reviewed" if record else "not_assessed",
            "model_score_is_clinical_urgency": False,
            "confidence_used_for_triage": False,
            "emergency_check": self.check_emergency(symptoms),
        }

    def get_coverage(self) -> dict[str, Any]:
        return validate_content_dir(self.content_dir)


medical_service = MedicalContentService(
    Path(__file__).resolve().parents[2] / "data" / "medical_content"
)
