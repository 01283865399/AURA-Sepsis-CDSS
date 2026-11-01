"""Preserve exact Disease Ontology disease-to-symptom association candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_URL = (
    "https://github.com/DiseaseOntology/HumanDiseaseOntology/"
    "blob/v2026-08-31/DOreports/requested/disease-symptom.tsv"
)
SOURCE_RELEASE = "2026-08-31"
IMPORT_DATE = date.today().isoformat()
REQUIRED_COLUMNS = ("disease_id", "disease_label", "symptom_id", "symptom_label")


def _record_id(disease_id: str, symptom_id: str) -> str:
    return f"{disease_id.casefold().replace(':', '_')}__{symptom_id.casefold().replace(':', '_')}"


def convert_disease_symptom_tsv(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert the tabular relation without inferring symptoms or translating labels."""
    counts: Counter[str] = Counter()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames is None or tuple(reader.fieldnames) != REQUIRED_COLUMNS:
            raise ValueError(
                f"Expected TSV columns {REQUIRED_COLUMNS!r}, got {reader.fieldnames!r}"
            )
        for row in reader:
            counts["input_rows"] += 1
            disease_id = (row.get("disease_id") or "").strip()
            disease_label = (row.get("disease_label") or "").strip()
            symptom_id = (row.get("symptom_id") or "").strip()
            symptom_label = (row.get("symptom_label") or "").strip()
            if not disease_id or not disease_label or not symptom_id or not symptom_label:
                counts["incomplete_rows"] += 1
                continue
            if not re.fullmatch(r"DOID:\d+", disease_id):
                counts["invalid_disease_ids"] += 1
                continue
            if not re.fullmatch(r"SYMP:\d+", symptom_id):
                counts["invalid_symptom_ids"] += 1
                continue
            pair = disease_id, symptom_id
            if pair in seen:
                counts["duplicate_associations"] += 1
                continue
            seen.add(pair)
            records.append(
                {
                    "association_id": _record_id(disease_id, symptom_id),
                    "condition_source_id": disease_id,
                    "condition_name_source_text": disease_label,
                    "symptom_source_id": symptom_id,
                    "symptom_name_source_text": symptom_label,
                    "record_type": "disease_symptom_association_candidate",
                    "association_status": "source_asserted_unreviewed",
                    "source": "Disease Ontology",
                    "source_release": SOURCE_RELEASE,
                    "source_file_url": SOURCE_URL,
                    "source_sha256": digest,
                    "imported_at": IMPORT_DATE,
                    "license_note": "CC0 1.0 Universal, as declared by Disease Ontology",
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "clinical_symptom_approved": False,
                    "clinical_review_required": True,
                }
            )
    counts["output_records"] = len(records)
    counts["unique_disease_ids"] = len({record["condition_source_id"] for record in records})
    counts["unique_symptom_ids"] = len({record["symptom_source_id"] for record in records})
    return records, {
        "source": "Disease Ontology disease-symptom association table",
        "source_url": SOURCE_URL,
        "source_release": SOURCE_RELEASE,
        "source_file": path.as_posix(),
        "source_sha256": digest,
        "license_note": "CC0 1.0 Universal, as declared by Disease Ontology",
        "counts": dict(counts),
        "clinical_review_required": True,
        "live_catalog_eligible": False,
        "note": (
            "Retained as explicit source associations only. These rows do not "
            "establish symptom severity, patient-specific relevance, or clinical approval."
        ),
    }


def write_candidates(records: list[dict[str, Any]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    try:
        temporary.write_text(
            json.dumps(
                {
                    "records": records,
                    "source_release": records[0]["source_release"] if records else SOURCE_RELEASE,
                    "source_url": records[0]["source_file_url"] if records else SOURCE_URL,
                    "source_sha256": records[0]["source_sha256"] if records else None,
                    "content_status": "draft_only",
                    "clinical_review_required": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
