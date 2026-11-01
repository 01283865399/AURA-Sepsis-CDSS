"""Integrity checks for source-backed medical content records."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from data.medical_content.loader import COLLECTION_FILES, load_content


CONTENT_TARGETS = {
    "conditions": 200,
    "symptoms": 132,
    "specialists": 25,
    "emergency_signs": 30,
    "drugs": 100,
    "lab_tests": 50,
}


def _record_identifier(record: dict[str, Any]) -> Any:
    for key in (
        "condition_id", "symptom_id", "specialist_id", "sign_id", "red_flag_id", "drug_id",
        "reference_id", "citation_id", "guideline_id", "test_id", "id",
    ):
        if record.get(key):
            return record[key]
    return None


def _has_https_reference(record: dict[str, Any]) -> bool:
    references = record.get("references")
    if not isinstance(references, list) or not references:
        return False
    for reference in references:
        if not isinstance(reference, dict) or not reference.get("source") or not reference.get("title"):
            continue
        try:
            parsed_url = urlparse(str(reference.get("url", "")))
        except ValueError:
            continue
        if parsed_url.scheme == "https" and parsed_url.netloc:
            return True
    return False


def validate_content(content: dict[str, Any]) -> list[str]:
    """Return integrity errors; draft records may be incomplete, published may not."""
    errors: list[str] = []
    collections = (*COLLECTION_FILES, "guidelines")
    published_required = {
        "conditions": (
            "condition_id", "condition_en", "condition_ar", "category",
            "description", "symptoms", "risk_factors", "complications",
            "diagnosis", "treatment", "prevention", "prognosis", "specialist",
            "urgency_level", "when_to_see_doctor_ar", "references",
        ),
        "symptoms": (
            "symptom_id", "name_en", "name_ar", "category",
            "description_ar", "description_en", "red_flags_ar", "red_flags_en",
            "urgency_default",
        ),
        "specialists": ("specialist_id", "name_en", "name_ar", "description_ar"),
        "emergency_signs": ("sign_id", "sign_ar", "sign_en", "urgency", "action_en"),
        "red_flags": ("red_flag_id", "name_ar", "name_en", "references"),
        "drugs": ("drug_id", "name_en", "name_ar", "generic_name", "references"),
        "interactions": ("interaction_id", "drug_ids", "severity", "references"),
        "lab_tests": ("test_id", "name_ar", "unit", "references"),
        "imaging_protocols": ("protocol_id", "name_en", "name_ar", "references"),
        "guidelines": ("guideline_id", "source", "year", "title_ar", "url"),
        "references": ("reference_id", "source", "title", "url"),
        "citations": ("citation_id", "source", "title", "url"),
    }
    for collection in collections:
        records = content.get(collection)
        if not isinstance(records, list):
            errors.append(f"{collection}: expected an array")
            continue
        seen: set[str] = set()
        for index, record in enumerate(records):
            location = f"{collection}[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{location}: expected an object")
                continue
            record_id = _record_identifier(record)
            if not isinstance(record_id, str) or not record_id.strip():
                errors.append(f"{location}: missing stable identifier")
            elif record_id in seen:
                errors.append(f"{location}: duplicate identifier '{record_id}'")
            else:
                seen.add(record_id)

            status = record.get("content_status")
            if status not in ("draft", "published"):
                errors.append(f"{location}: content_status must be draft or published")
            if status == "published":
                missing_fields = [
                    field for field in published_required.get(collection, ())
                    if field not in record or record[field] in (None, "", [])
                ]
                if missing_fields:
                    errors.append(
                        f"{location}: published content is missing "
                        + ", ".join(missing_fields)
                    )
                source_backed = (
                    _has_https_reference(record)
                    if collection not in {"references", "citations"}
                    else _has_https_reference({"references": [record]})
                )
                if not source_backed:
                    errors.append(f"{location}: published content requires an HTTPS source reference")
                if record.get("review_status") != "clinically_reviewed":
                    errors.append(f"{location}: published content requires clinical review")
                if not record.get("reviewed_by"):
                    errors.append(f"{location}: published content requires reviewer identity")
                try:
                    date.fromisoformat(str(record.get("last_reviewed", "")))
                except ValueError:
                    errors.append(f"{location}: published content requires ISO last_reviewed date")

    disclaimers = content.get("disclaimers")
    if not isinstance(disclaimers, dict) or not isinstance(disclaimers.get("general"), dict):
        errors.append("disclaimers: required bilingual general notice is missing")
    else:
        general = disclaimers["general"]
        if not all(isinstance(general.get(language), str) and general[language].strip() for language in ("ar", "en")):
            errors.append("disclaimers.general: both Arabic and English text are required")
    return errors


def validate_content_dir(content_dir: Path) -> dict[str, Any]:
    """Load and validate the package, reporting both errors and honest coverage."""
    content = load_content(content_dir)
    errors = validate_content(content)
    counts = {
        name: len(content[name])
        for name in COLLECTION_FILES
    }
    counts["guidelines"] = len(content["guidelines"])
    for collection in ("conditions", "symptoms", "specialists", "emergency_signs", "drugs", "lab_tests", "guidelines"):
        counts[f"published_{collection}"] = sum(
            1
            for record in content[collection]
            if isinstance(record, dict) and record.get("content_status") == "published"
        )
    deficits = {
        name: max(0, target - counts.get(f"published_{name}", 0))
        for name, target in CONTENT_TARGETS.items()
        if counts.get(f"published_{name}", 0) < target
    }
    return {
        "valid": not errors,
        "errors": errors,
        "counts": counts,
        "targets": CONTENT_TARGETS,
        "deficits": deficits,
        "coverage_status": "incomplete" if deficits else "requires_clinical_review",
        "content_dir": str(content_dir),
        "research_only": True,
    }
