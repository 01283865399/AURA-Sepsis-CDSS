"""Load the medical content package from its checked-in JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MedicalContentLoadError(RuntimeError):
    """Medical content is missing or cannot be parsed safely."""


COLLECTION_FILES = {
    "conditions": ("conditions", "all_conditions.json", "conditions"),
    "symptoms": ("symptoms", "all_symptoms.json", "symptoms"),
    "specialists": ("specialists", "specialists.json", "specialists"),
    "emergency_signs": ("emergency", "emergency_signs.json", "emergency_signs"),
    "red_flags": ("emergency", "red_flags.json", "red_flags"),
    "drugs": ("medications", "common_drugs.json", "drugs"),
    "interactions": ("medications", "interactions.json", "interactions"),
    "lab_tests": ("tests", "lab_reference_ranges.json", "lab_tests"),
    "imaging_protocols": ("tests", "imaging_protocols.json", "imaging_protocols"),
    "references": ("references", "medical_references.json", "references"),
    "citations": ("references", "citations.json", "citations"),
}
GUIDELINE_FILES = (
    ("who_guidelines.json", "WHO"),
    ("cdc_guidelines.json", "CDC"),
    ("nice_guidelines.json", "NICE"),
    ("esc_guidelines.json", "ESC"),
    ("ada_guidelines.json", "ADA"),
    ("kdigo_guidelines.json", "KDIGO"),
)


def load_json(path: Path) -> dict[str, Any]:
    """Read one UTF-8 JSON object, surfacing file and format errors."""
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MedicalContentLoadError(f"Cannot load medical content file: {path}") from exc
    if not isinstance(value, dict):
        raise MedicalContentLoadError(f"Medical content root must be an object: {path}")
    return value


def load_content(content_dir: Path) -> dict[str, Any]:
    """Load all required collections and standalone catalog documents."""
    content: dict[str, Any] = {}
    for name, (folder, filename, key) in COLLECTION_FILES.items():
        path = content_dir / folder / filename
        document = load_json(path)
        records = document.get(key)
        if name == "lab_tests" and isinstance(records, dict):
            flattened = []
            for panel, tests in records.items():
                if not isinstance(tests, dict):
                    raise MedicalContentLoadError(
                        f"Expected an object of tests in panel '{panel}' in {path}."
                    )
                for test_id, test in tests.items():
                    if not isinstance(test, dict):
                        raise MedicalContentLoadError(
                            f"Expected an object for lab test '{test_id}' in {path}."
                        )
                    flattened.append({"test_id": test_id, "panel": panel, **test})
            records = flattened
        if not isinstance(records, list):
            raise MedicalContentLoadError(
                f"Expected a JSON array at '{key}' in {path}."
            )
        content[name] = records

    content["guidelines"] = []
    for filename, source in GUIDELINE_FILES:
        document = load_json(content_dir / "guidelines" / filename)
        records = document.get("guidelines")
        if not isinstance(records, list):
            raise MedicalContentLoadError(
                f"Expected a JSON array at 'guidelines' in {filename}."
            )
        if any(not isinstance(record, dict) for record in records):
            raise MedicalContentLoadError(
                f"Every guideline record must be an object in {filename}."
            )
        content["guidelines"].extend(
            {**record, "source": record.get("source", source)}
            for record in records
        )

    for name, relative_path in (
        ("disclaimers", Path("disclaimers") / "all_disclaimers.json"),
        ("severity_map", Path("symptoms") / "severity_map.json"),
        ("symptoms_by_body_system", Path("symptoms") / "by_body_system.json"),
        ("triage_rules", Path("emergency") / "triage_rules.json"),
    ):
        content[name] = load_json(content_dir / relative_path)
    return content
