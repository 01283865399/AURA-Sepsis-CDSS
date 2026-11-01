"""Build source-faithful, review-only medical content from approved inputs."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PROCESSED_ROOT = ROOT / "data" / "medical_content" / "processed"
OUTPUT_ROOT = ROOT / "data" / "medical_content" / "final"
SOURCE_PATHS = {
    "conditions": PROCESSED_ROOT / "final" / "conditions.json",
    "phenotypes": PROCESSED_ROOT / "final" / "phenotype_concepts.json",
    "icd10_index": PROCESSED_ROOT / "final" / "icd10cm_condition_index.json",
    "associations": PROCESSED_ROOT / "symptoms" / "disease_symptom_association_candidates.json",
}
EXPECTED_COUNTS = {
    "conditions": 12_335,
    "phenotypes": 19_894,
    "icd10_index": 2_479,
    "associations": 2_222,
}
EXPECTED_SOURCE_METADATA = {
    "disease_ontology": {
        "release": "v2026-09-30",
        "sha256": "51e717b6b9f5d391f2793f9e16faf9c8629a661ab8f21c3a024458129f182ad2",
        "url": "https://raw.githubusercontent.com/DiseaseOntology/HumanDiseaseOntology/v2026-09-30/src/ontology/doid.obo",
    },
    "hpo": {
        "release": "v2026-09-01",
        "sha256": "43ea5d7cc26282b9c613adeff194e88f4672f58f5ce1a8ededbe233ce17cf0a7",
    },
    "disease_symptom": {
        "release": "2026-08-31",
        "sha256": "20bb1b62a6a22e66ca1ef2748e032c322709495987c5a26e5e8a05b3d80a4aff",
        "url": "https://github.com/DiseaseOntology/HumanDiseaseOntology/blob/v2026-08-31/DOreports/requested/disease-symptom.tsv",
    },
}
IMPORT_DATE = date.today().isoformat()


def _read_list(path: Path, key: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if key is not None:
        if not isinstance(document, dict) or not isinstance(document.get(key), list):
            raise ValueError(f"Expected a '{key}' array in {path}")
        records = document[key]
        metadata = {name: value for name, value in document.items() if name != key}
    else:
        if not isinstance(document, list):
            raise ValueError(f"Expected a JSON array in {path}")
        records = document
        metadata = {}
    if any(not isinstance(record, dict) for record in records):
        raise ValueError(f"Every record in {path} must be a JSON object")
    return records, metadata


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _codes_by_condition(
    index: list[dict[str, Any]],
    selected_ids: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    mappings: dict[str, list[dict[str, Any]]] = {}
    for code_entry in index:
        code = code_entry.get("code")
        coding_system = code_entry.get("coding_system")
        source_urls = code_entry.get("source_urls", [])
        if not isinstance(code, str) or not isinstance(coding_system, str):
            continue
        for condition_id in code_entry.get("condition_ids", []):
            if not isinstance(condition_id, str):
                continue
            if selected_ids is not None and condition_id not in selected_ids:
                continue
            mapping = {
                "coding_system": coding_system,
                "code": code,
                "mapping_status": code_entry.get("mapping_status", "source_asserted_unverified"),
                "source": code_entry.get("source", "Disease Ontology ICD10CM xref"),
                "source_urls": source_urls if isinstance(source_urls, list) else [],
            }
            if mapping not in mappings.setdefault(condition_id, []):
                mappings[condition_id].append(mapping)
    for records in mappings.values():
        records.sort(key=lambda record: (record["coding_system"], record["code"]))
    return mappings


def build_final_content(
    conditions: list[dict[str, Any]],
    phenotypes: list[dict[str, Any]],
    icd10_index: list[dict[str, Any]],
    associations: list[dict[str, Any]],
    *,
    require_expected_counts: bool = True,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Create bounded term selections without synthesizing clinical fields."""
    input_counts = {
        "conditions": len(conditions),
        "phenotypes": len(phenotypes),
        "icd10_index": len(icd10_index),
        "associations": len(associations),
    }
    if require_expected_counts:
        for name, expected in EXPECTED_COUNTS.items():
            if input_counts[name] != expected:
                raise ValueError(
                    f"Unexpected {name} source count: expected {expected}, got {input_counts[name]}"
                )
    if require_expected_counts:
        source_groups = (
            ("disease_ontology", conditions, "source_release", "source_sha256"),
            ("hpo", phenotypes, "source_release", "source_sha256"),
            ("disease_symptom", associations, "source_release", "source_sha256"),
        )
        for source_name, records, release_key, checksum_key in source_groups:
            expected_source = EXPECTED_SOURCE_METADATA[source_name]
            releases = {record.get(release_key) for record in records}
            checksums = {record.get(checksum_key) for record in records}
            if releases != {expected_source["release"]} or checksums != {expected_source["sha256"]}:
                raise ValueError(f"Unexpected source release/checksum for {source_name}")
        expected_do_url = EXPECTED_SOURCE_METADATA["disease_ontology"]["url"]
        expected_association_url = EXPECTED_SOURCE_METADATA["disease_symptom"]["url"]
        for entry in icd10_index:
            if (
                entry.get("source") != "Disease Ontology ICD10CM xref"
                or expected_do_url not in entry.get("source_urls", [])
            ):
                raise ValueError("ICD-10-CM crosswalk lacks the expected Disease Ontology source URL")
        for association in associations:
            if association.get("source_file_url") != expected_association_url:
                raise ValueError("Disease-symptom association has an unexpected source URL")

    source_condition_by_id: dict[str, dict[str, Any]] = {}
    for condition in conditions:
        condition_id = condition.get("condition_id")
        if isinstance(condition_id, str):
            if condition_id in source_condition_by_id:
                raise ValueError(f"Duplicate source condition ID: {condition_id}")
            source_condition_by_id[condition_id] = condition
    source_phenotype_by_id: dict[str, dict[str, Any]] = {}
    for phenotype in phenotypes:
        phenotype_id = phenotype.get("phenotype_id")
        if isinstance(phenotype_id, str):
            if phenotype_id in source_phenotype_by_id:
                raise ValueError(f"Duplicate source phenotype ID: {phenotype_id}")
            source_phenotype_by_id[phenotype_id] = phenotype

    source_codes = _codes_by_condition(icd10_index)
    associations_by_doid: dict[str, list[dict[str, Any]]] = {}
    labels_by_symptom_id: dict[str, set[str]] = {}
    for association in associations:
        disease_id = association.get("condition_source_id")
        symptom_id = association.get("symptom_source_id")
        symptom_label = association.get("symptom_name_source_text")
        if not all(isinstance(value, str) and value.strip() for value in (disease_id, symptom_id, symptom_label)):
            raise ValueError("Source association has a missing source identifier or label")
        associations_by_doid.setdefault(disease_id, []).append(association)
        labels_by_symptom_id.setdefault(symptom_id, set()).add(symptom_label.strip())

    def condition_priority(condition: dict[str, Any]) -> tuple[int, int, int, str]:
        condition_id = str(condition["condition_id"])
        doid = str(condition["ontology_id"])
        return (
            -len(associations_by_doid.get(doid, [])),
            -int(bool(source_codes.get(condition_id))),
            -int(bool(condition.get("definition_source_text"))),
            doid,
        )

    selected_conditions = sorted(
        (
            condition
            for condition in conditions
            if condition.get("record_type") == "disease_ontology_condition"
            and condition.get("is_obsolete") is not True
            and isinstance(condition.get("condition_en"), str)
            and condition["condition_en"].strip()
        ),
        key=condition_priority,
    )[:500]
    selected_doid_ids = {
        str(record["ontology_id"]): str(record["condition_id"])
        for record in selected_conditions
    }

    disease_records: list[dict[str, Any]] = []
    for condition in selected_conditions:
        condition_id = str(condition["condition_id"])
        doid = str(condition["ontology_id"])
        direct_associations = associations_by_doid.get(doid, [])
        source_references = condition.get("references", [])
        disease_records.append(
            {
                "condition_id": condition_id,
                "condition_en": condition["condition_en"].strip(),
                "condition_ar": None,
                "record_type": "disease_ontology_term_draft",
                "ontology_id": doid,
                "category": None,
                "body_system": None,
                "description": {
                    "short_ar": None,
                    "long_ar": None,
                    "short_en": None,
                    "long_en": condition.get("definition_source_text"),
                },
                "synonyms_en": condition.get("synonyms_en", []),
                "ontology_parents": condition.get("ontology_parents", []),
                "external_xrefs": condition.get("external_xrefs", []),
                "icd10_crosswalks": source_codes.get(condition_id, []),
                "icd10_codes": [
                    mapping["code"] for mapping in source_codes.get(condition_id, [])
                ],
                "icd10_code": (
                    source_codes[condition_id][0]["code"]
                    if len(source_codes.get(condition_id, [])) == 1
                    else None
                ),
                "symptom_association_ids": [
                    str(record["association_id"]) for record in direct_associations
                ],
                "risk_factors": None,
                "complications": None,
                "diagnosis": None,
                "treatment": None,
                "prevention": None,
                "prognosis": None,
                "specialist": None,
                "urgency_level": None,
                "references": source_references if isinstance(source_references, list) else [],
                "source": "Disease Ontology",
                "source_release": condition.get("source_release"),
                "source_sha256": condition.get("source_sha256"),
                "imported_at": IMPORT_DATE,
                "content_status": "draft",
                "review_status": "unreviewed",
                "clinical_review_required": True,
                "clinically_complete": False,
                "not_for_clinical_use": True,
            }
        )

    selected_phenotypes = sorted(
        (
            phenotype
            for phenotype in phenotypes
            if phenotype.get("record_type") == "phenotype_concept"
            and phenotype.get("clinical_symptom") is False
            and phenotype.get("symptom_catalog_eligible") is False
            and isinstance(phenotype.get("phenotype_id"), str)
            and isinstance(phenotype.get("name_en"), str)
            and phenotype["name_en"].strip()
        ),
        key=lambda record: str(record["phenotype_id"]),
    )[:1000]
    phenotype_records = [
        {
            **phenotype,
            "name_ar": None,
            "record_type": "phenotype_concept",
            "clinical_symptom": False,
            "symptom_catalog_eligible": False,
            "content_status": "draft",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "selection_policy": "first_1000_by_phenotype_id_for_review_not_clinical_priority",
            "imported_at": IMPORT_DATE,
        }
        for phenotype in selected_phenotypes
    ]

    symptoms_by_id: dict[str, dict[str, Any]] = {}
    symptom_key_by_source_id: dict[str, str] = {}
    disease_sources_by_symptom: dict[str, set[str]] = {}
    for association in associations:
        disease_sources_by_symptom.setdefault(
            str(association["symptom_source_id"]), set()
        ).add(str(association["condition_source_id"]))
    for symptom_id, label_variants in sorted(labels_by_symptom_id.items()):
        sorted_labels = sorted(label_variants)
        normalized_symptom_id = symptom_id.casefold().replace(":", "_")
        symptom_key_by_source_id[symptom_id] = normalized_symptom_id
        symptoms_by_id[normalized_symptom_id] = {
            "symptom_id": normalized_symptom_id,
            "source_symptom_id": symptom_id,
            "name_en": sorted_labels[0],
            "name_ar": None,
            "source_label_variants": sorted_labels,
            "record_type": "ontology_symptom_term_candidate",
            "category": None,
            "body_system": None,
            "severity": None,
            "description_ar": None,
            "description_en": None,
            "related_condition_ids": [],
            "related_condition_source_ids": sorted(
                disease_sources_by_symptom[symptom_id]
            ),
            "references": [
                {
                    "source": "Disease Ontology",
                    "title": "Disease Ontology disease-symptom associations",
                    "url": (
                        associations[0].get("source_file_url")
                        if associations
                        else ""
                    ),
                }
            ],
            "source": "Disease Ontology",
            "source_release": "2026-08-31",
            "source_sha256": associations[0].get("source_sha256") if associations else None,
            "imported_at": IMPORT_DATE,
            "content_status": "draft",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "clinically_complete": False,
            "not_for_clinical_use": True,
        }

    relationship_records: list[dict[str, Any]] = []
    unselected_condition_links = 0
    for association in associations:
        disease_id = str(association["condition_source_id"])
        symptom_id = str(association["symptom_source_id"])
        condition_id = selected_doid_ids.get(disease_id)
        if condition_id is None:
            unselected_condition_links += 1
        else:
            symptoms_by_id[symptom_key_by_source_id[symptom_id]]["related_condition_ids"].append(
                condition_id
            )
        relationship_records.append(
            {
                "association_id": association["association_id"],
                "condition_id": condition_id,
                "condition_source_id": disease_id,
                "symptom_id": symptom_id.casefold().replace(":", "_"),
                "symptom_source_id": symptom_id,
                "condition_name_source_text": association["condition_name_source_text"],
                "symptom_name_source_text": association["symptom_name_source_text"],
                "record_type": "disease_symptom_association",
                "association_status": "source_asserted_unreviewed",
                "source": association["source"],
                "source_release": association["source_release"],
                "source_url": association["source_file_url"],
                "source_sha256": association["source_sha256"],
                "imported_at": IMPORT_DATE,
                "content_status": "draft",
                "review_status": "unreviewed",
                "clinical_symptom_approved": False,
                "clinical_review_required": True,
                "not_for_clinical_use": True,
            }
        )
    for symptom in symptoms_by_id.values():
        symptom["related_condition_ids"] = sorted(set(symptom["related_condition_ids"]))
    symptoms = list(symptoms_by_id.values())

    output = {
        "conditions": disease_records,
        "symptoms": symptoms,
        "phenotype_concepts": phenotype_records,
        "associations": relationship_records,
    }
    report = {
        "content_status": "draft_only",
        "clinical_review_required": True,
        "not_for_clinical_use": True,
        "source_counts": input_counts,
        "output_counts": {key: len(value) for key, value in output.items()},
        "arabic_translation": {
            "conditions_with_arabic": sum(bool(record["condition_ar"]) for record in disease_records),
            "symptoms_with_arabic": sum(bool(record["name_ar"]) for record in symptoms),
            "phenotypes_with_arabic": sum(bool(record["name_ar"]) for record in phenotype_records),
            "status": "not_available_in_the_four_source_files; no translations were invented",
        },
        "condition_selection": {
            "policy": "prefer source-linked disease associations, then source ICD mapping, then source definition, with stable DOID tie-break",
            "selected_with_icd10cm": sum(bool(record["icd10_crosswalks"]) for record in disease_records),
            "selected_with_source_definition": sum(
                bool(record["description"]["long_en"]) for record in disease_records
            ),
            "selected_with_symptom_associations": sum(
                bool(record["symptom_association_ids"]) for record in disease_records
            ),
            "missing_clinical_fields_left_null": [
                "category", "body_system", "risk_factors", "complications", "diagnosis",
                "treatment", "prevention", "prognosis", "specialist", "urgency_level",
                "Arabic labels and descriptions",
            ],
        },
        "phenotype_selection": {
            "policy": "first 1,000 active phenotype concepts by stable HP identifier; not clinical prioritization",
            "clinical_symptoms_asserted": 0,
        },
        "relationship_integrity": {
            "input_relation_count": len(associations),
            "output_relation_count": len(relationship_records),
            "relations_with_condition_in_500_subset": len(relationship_records) - unselected_condition_links,
            "relations_to_conditions_outside_500_subset": unselected_condition_links,
            "source_asserted_symptom_term_count": len(symptoms),
            "label_variants_across_source_rows": sum(
                max(0, len(labels) - 1) for labels in labels_by_symptom_id.values()
            ),
        },
        "icd10cm": {
            "coding_system": "ICD-10-CM",
            "source_asserted_unverified_mappings": sum(
                len(record["icd10_crosswalks"]) for record in disease_records
            ),
            "note": "Mappings retain exact Disease Ontology ICD10CM xrefs; they are not independently verified as WHO ICD-10.",
        },
        "sources": [
            {"name": "Disease Ontology", "release": "v2026-09-30"},
            {"name": "Human Phenotype Ontology", "release": "v2026-09-01"},
            {"name": "Disease Ontology disease-symptom table", "release": "2026-08-31"},
        ],
        "api_policy": "Separate review-only endpoints; not served as approved clinical content.",
    }
    return output, report


def build_from_sources(
    processed_root: Path = PROCESSED_ROOT,
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    condition_records, _ = _read_list(processed_root / "final" / "conditions.json")
    phenotype_records, _ = _read_list(processed_root / "final" / "phenotype_concepts.json")
    code_index, _ = _read_list(processed_root / "final" / "icd10cm_condition_index.json")
    association_records, _ = _read_list(
        processed_root / "symptoms" / "disease_symptom_association_candidates.json",
        key="records",
    )
    output, report = build_final_content(
        condition_records,
        phenotype_records,
        code_index,
        association_records,
    )
    for collection, records in output.items():
        _atomic_json(output_root / f"{collection}.json", records)
    _atomic_json(output_root / "import_report.json", report)
    return report


def main() -> int:
    report = build_from_sources()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
