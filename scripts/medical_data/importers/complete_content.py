"""Build a source-faithful, review-only package from all available datasets."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from datasets import load_from_disk


ROOT = Path(__file__).resolve().parents[3]
CONTENT_ROOT = ROOT / "data" / "medical_content"
OUTPUT_ROOT = CONTENT_ROOT / "final" / "complete"
LOG = logging.getLogger(__name__)
IMPORT_DATE = date.today().isoformat()
MEDQUAD_DATASET_URL = (
    "https://huggingface.co/datasets/mukulb/"
    "clustered_MEDQUAD_dataset_with_groups/tree/4a6fb9dbde295a762653c85b5fec5c9963937680"
)
NOT_FOR_CLINICAL_USE = True

SOURCE_PATHS = {
    "conditions": CONTENT_ROOT / "processed" / "final" / "conditions.json",
    "phenotypes": CONTENT_ROOT / "processed" / "final" / "phenotype_concepts.json",
    "associations": CONTENT_ROOT / "processed" / "symptoms" / "disease_symptom_association_candidates.json",
    "icd10_index": CONTENT_ROOT / "processed" / "final" / "icd10cm_condition_index.json",
    "healthcare_rag": CONTENT_ROOT / "raw" / "healthcare_rag" / "healthcare_rag_dataset.csv",
    "symptom2disease": CONTENT_ROOT / "raw" / "symptom2disease" / "Symptom2Disease.csv",
    "medquad": CONTENT_ROOT / "raw" / "medquad",
}
EXPECTED_COUNTS = {
    "conditions": 12_335,
    "phenotypes": 19_894,
    "associations": 2_222,
    "icd10_index": 2_479,
    "healthcare_rag": 409,
    "symptom2disease": 1_200,
    "medquad": 16_407,
}
STATUS_FIELDS = {
    "content_status": "draft",
    "review_status": "unreviewed",
    "clinical_review_required": True,
    "not_for_clinical_use": True,
}


class MedicalDataBuildError(RuntimeError):
    """A source is missing, malformed, or inconsistent with its expected shape."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MedicalDataBuildError(f"Cannot read JSON source: {path}") from exc


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise MedicalDataBuildError(f"Cannot read CSV source: {path}") from exc
    if not rows:
        raise MedicalDataBuildError(f"CSV source has no data rows: {path}")
    return rows


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _valid_http_url(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"https?://\S+", value))


def _check_count(name: str, actual: int, strict: bool) -> None:
    expected = EXPECTED_COUNTS[name]
    if strict and actual != expected:
        raise MedicalDataBuildError(
            f"Unexpected {name} count: expected {expected}, got {actual}"
        )
    if actual != expected:
        LOG.warning("Source count differs for %s: expected %d, got %d", name, expected, actual)


def _source_status() -> dict[str, Any]:
    return {
        **STATUS_FIELDS,
        "translation_status": "not_translated",
        "clinical_validation_status": "not_clinically_reviewed",
    }


def _load_inputs(strict_counts: bool = True) -> dict[str, Any]:
    conditions = _read_json(SOURCE_PATHS["conditions"])
    phenotypes = _read_json(SOURCE_PATHS["phenotypes"])
    association_document = _read_json(SOURCE_PATHS["associations"])
    icd_index = _read_json(SOURCE_PATHS["icd10_index"])
    if not isinstance(conditions, list) or not isinstance(phenotypes, list):
        raise MedicalDataBuildError("Disease Ontology and HPO sources must be JSON arrays.")
    if not isinstance(association_document, dict) or not isinstance(
        association_document.get("records"), list
    ):
        raise MedicalDataBuildError("Disease-symptom source must contain a records array.")
    if not isinstance(icd_index, list):
        raise MedicalDataBuildError("ICD-10-CM source must be a JSON array.")

    healthcare_rag = _read_csv(SOURCE_PATHS["healthcare_rag"])
    symptom2disease = _read_csv(SOURCE_PATHS["symptom2disease"])
    try:
        medquad = load_from_disk(str(SOURCE_PATHS["medquad"]))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise MedicalDataBuildError(
            f"Cannot load the local MedQuAD dataset at {SOURCE_PATHS['medquad']}"
        ) from exc
    if "train" not in medquad:
        raise MedicalDataBuildError("MedQuAD source must contain its train split.")
    medquad_rows = medquad["train"]

    counts = {
        "conditions": len(conditions),
        "phenotypes": len(phenotypes),
        "associations": len(association_document["records"]),
        "icd10_index": len(icd_index),
        "healthcare_rag": len(healthcare_rag),
        "symptom2disease": len(symptom2disease),
        "medquad": len(medquad_rows),
    }
    for name, count in counts.items():
        _check_count(name, count, strict=strict_counts)
    return {
        "conditions": conditions,
        "phenotypes": phenotypes,
        "associations": association_document["records"],
        "association_metadata": {
            key: value for key, value in association_document.items() if key != "records"
        },
        "icd10_index": icd_index,
        "healthcare_rag": healthcare_rag,
        "symptom2disease": symptom2disease,
        "medquad": medquad_rows,
        "input_counts": counts,
    }


def _rag_by_code(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = _clean_text(row.get("icd10_code"))
        if code:
            grouped[code].append(row)
    return grouped


def _condition_codes(index: list[dict[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for entry in index:
        code = entry.get("code")
        ids = entry.get("condition_ids")
        if isinstance(code, str) and isinstance(ids, list):
            for condition_id in ids:
                if isinstance(condition_id, str) and code not in result[condition_id]:
                    result[condition_id].append(code)
    return result


def _build_conditions(
    source_conditions: list[dict[str, Any]],
    source_index: list[dict[str, Any]],
    associations: list[dict[str, Any]],
    rag_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    codes_by_condition = _condition_codes(source_index)
    rag_by_code = _rag_by_code(rag_rows)
    association_counts = Counter(
        association.get("condition_source_id")
        for association in associations
        if isinstance(association.get("condition_source_id"), str)
    )

    eligible: list[dict[str, Any]] = []
    for record in source_conditions:
        condition_id = record.get("condition_id")
        if (
            record.get("record_type") != "disease_ontology_condition"
            or record.get("is_obsolete") is True
            or not isinstance(condition_id, str)
            or not isinstance(record.get("condition_en"), str)
            or not record["condition_en"].strip()
        ):
            continue
        matching_docs = [
            doc
            for code in codes_by_condition.get(condition_id, [])
            for doc in rag_by_code.get(code, [])
        ]
        eligible.append(
            {
                "source": record,
                "documents": matching_docs,
                "association_count": association_counts.get(record.get("ontology_id"), 0),
            }
        )

    eligible.sort(
        key=lambda item: (
            -int(bool(item["documents"])),
            -item["association_count"],
            -int(bool(item["source"].get("definition_source_text"))),
            str(item["source"].get("ontology_id", "")),
        )
    )
    full_content_ids = {
        str(item["source"]["condition_id"])
        for item in eligible[:500]
    }
    results: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    for item in eligible:
        record = item["source"]
        condition_id = str(record["condition_id"])
        documents = item["documents"] if condition_id in full_content_ids else []
        document_urls = sorted(
            {
                _clean_text(document.get("source_url"))
                for document in documents
                if _valid_http_url(_clean_text(document.get("source_url")))
            }
        )
        is_full_candidate = condition_id in full_content_ids
        normalized: dict[str, Any] = {
            "condition_id": condition_id,
            "condition_en": _clean_text(record.get("condition_en")),
            "condition_ar": None,
            "ontology_id": record.get("ontology_id"),
            "record_type": (
                "condition_content_candidate" if is_full_candidate else "condition_lookup_term"
            ),
            "has_source_enrichment": bool(documents),
            "icd10_codes": codes_by_condition.get(condition_id, []),
            "source": "disease_ontology",
            "source_references": record.get("references", []),
            **_source_status(),
        }
        if is_full_candidate:
            normalized.update(
                {
                    "description": {
                        "short_ar": None,
                        "long_ar": None,
                        "short_en": None,
                        "long_en": _clean_text(record.get("definition_source_text")),
                        "etiology_ar": None,
                    },
                    "synonyms_en": record.get("synonyms_en", []),
                    "ontology_parents": record.get("ontology_parents", []),
                    "external_xrefs": record.get("external_xrefs", []),
                    "symptom_association_ids": [
                        association.get("association_id")
                        for association in associations
                        if association.get("condition_source_id") == record.get("ontology_id")
                    ],
                    "risk_factors": None,
                    "complications": None,
                    "diagnosis": None,
                    "treatment": None,
                    "prevention": None,
                    "prognosis": None,
                    "specialist": None,
                    "urgency_level": None,
                    "healthcare_rag_documents": [
                        {
                            "document_id": _clean_text(document.get("doc_id")),
                            "title": _clean_text(document.get("title")),
                            "category": _clean_text(document.get("category")),
                            "document_type": _clean_text(document.get("document_type")),
                            "content_en": _clean_text(document.get("content_text")),
                            "symptoms_en": _clean_text(document.get("symptoms")),
                            "treatments_en": _clean_text(document.get("treatments")),
                            "risk_factors_en": _clean_text(document.get("risk_factors")),
                            "prevention_en": _clean_text(document.get("prevention")),
                            "source_name": _clean_text(document.get("source_name")),
                            "source_url": _clean_text(document.get("source_url")),
                            "source_claimed_review_status": _clean_text(
                                document.get("review_status")
                            ),
                            "source_claimed_evidence_level": _clean_text(
                                document.get("evidence_level")
                            ),
                            "source_mapping_status": "exact_icd10_code_match_unverified",
                            **_source_status(),
                        }
                        for document in documents
                    ],
                    "enrichment_source_urls": document_urls,
                    "references": record.get("references", []),
                    "selection_policy": (
                        "exact ICD-10-CM code-linked Healthcare RAG records, then "
                        "source association count, then source definition; not prevalence"
                    ),
                }
            )
            for document in documents:
                category = _clean_text(document.get("category"))
                if category:
                    category_counts[category] += 1
        results.append(normalized)

    if len(results) != len(eligible):
        raise MedicalDataBuildError("Condition normalization unexpectedly changed the row count.")
    return results, {
        "records": len(results),
        "content_candidate_records": len(full_content_ids),
        "candidate_records_with_exact_code_linked_rag": sum(
            bool(item["documents"]) for item in eligible[:500]
        ),
        "lookup_only_records": len(results) - len(full_content_ids),
        "source_definitions_available": sum(
            bool(item["source"].get("definition_source_text")) for item in eligible
        ),
        "healthcare_rag_category_counts": dict(sorted(category_counts.items())),
        "ranking_is_not_prevalence": True,
    }


def _build_phenotypes(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [
        item
        for item in source
        if item.get("record_type") == "phenotype_concept"
        and item.get("clinical_symptom") is False
        and item.get("symptom_catalog_eligible") is False
        and isinstance(item.get("phenotype_id"), str)
        and isinstance(item.get("name_en"), str)
        and item["name_en"].strip()
    ]
    eligible.sort(key=lambda item: str(item["phenotype_id"]))
    return [
        {
            **item,
            "name_en": _clean_text(item.get("name_en")),
            "name_ar": None,
            "clinical_symptom": False,
            "symptom_catalog_eligible": False,
            "selection_policy": "first_1000_by_stable_HPO_ID; not clinical symptom ranking",
            "imported_at": IMPORT_DATE,
            **_source_status(),
        }
        for item in eligible[:1_000]
    ]


def _build_symptom_terms(
    associations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, set[str]] = defaultdict(set)
    conditions_by_symptom: dict[str, set[str]] = defaultdict(set)
    for association in associations:
        symptom_id = association.get("symptom_source_id")
        label = _clean_text(association.get("symptom_name_source_text"))
        condition_id = association.get("condition_source_id")
        if not isinstance(symptom_id, str) or label is None:
            raise MedicalDataBuildError("Association lacks an exact source symptom ID or label.")
        by_id[symptom_id].add(label)
        if isinstance(condition_id, str):
            conditions_by_symptom[symptom_id].add(condition_id)
    results = []
    for source_id in sorted(by_id):
        labels = sorted(by_id[source_id], key=lambda value: (value.casefold(), value))
        normalized_id = source_id.casefold().replace(":", "_")
        results.append(
            {
                "symptom_id": normalized_id,
                "source_symptom_id": source_id,
                "name_en": labels[0],
                "name_ar": None,
                "source_label_variants": labels,
                "record_type": "ontology_symptom_term_candidate",
                "clinical_symptom_approved": False,
                "related_condition_source_ids": sorted(conditions_by_symptom[source_id]),
                "category": None,
                "body_system": None,
                "severity": None,
                "description_en": None,
                "description_ar": None,
                "selection_policy": "all unique SYMP IDs from source associations",
                "source": "Disease Ontology disease-symptom association table",
                "imported_at": IMPORT_DATE,
                **_source_status(),
            }
        )
    return results


def _build_associations(
    associations: list[dict[str, Any]],
    condition_ids: set[str],
    symptom_ids: set[str],
) -> list[dict[str, Any]]:
    results = []
    for source in associations:
        doid = source.get("condition_source_id")
        symp_id = source.get("symptom_source_id")
        symptom_id = (
            symp_id.casefold().replace(":", "_") if isinstance(symp_id, str) else None
        )
        if (
            not isinstance(source.get("association_id"), str)
            or not isinstance(doid, str)
            or not isinstance(symp_id, str)
            or symptom_id not in symptom_ids
        ):
            raise MedicalDataBuildError("Association has invalid or unresolvable source identifiers.")
        condition_id = doid.casefold().replace(":", "_")
        results.append(
            {
                "association_id": source["association_id"],
                "condition_id": condition_id if condition_id in condition_ids else None,
                "condition_source_id": doid,
                "condition_name_source_text": _clean_text(
                    source.get("condition_name_source_text")
                ),
                "symptom_id": symptom_id,
                "symptom_source_id": symp_id,
                "symptom_name_source_text": _clean_text(
                    source.get("symptom_name_source_text")
                ),
                "association_status": "source_asserted_unreviewed",
                "source": source.get("source"),
                "source_release": source.get("source_release"),
                "source_url": source.get("source_file_url"),
                "source_sha256": source.get("source_sha256"),
                **_source_status(),
            }
        )
    return results


def _build_symptom2disease_reports(
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    results = []
    for index, row in enumerate(rows):
        label = _clean_text(row.get("label"))
        narrative = _clean_text(row.get("text"))
        source_row_id = _clean_text(row.get(""))
        if label is None or narrative is None:
            raise MedicalDataBuildError(f"Symptom2Disease row {index} has empty source data.")
        results.append(
            {
                "report_id": f"symptom2disease_{index:05d}",
                "source_label": label,
                "patient_narrative_en": narrative,
                "record_type": "dataset_narrative_not_symptom_assertion",
                "source_row_id": source_row_id,
                "condition_mapping": None,
                "source_row_index": index,
                "source_dataset_url": (
                    "https://www.kaggle.com/datasets/anthonytherrien/"
                    "symptom2disease"
                ),
                "source_license_status": "not_verified_in_local_source_files",
                **_source_status(),
            }
        )
    return results


def _build_qa(dataset: Any) -> list[dict[str, Any]]:
    results = []
    required_columns = {"query", "answers", "group_name"}
    if not required_columns.issubset(set(dataset.column_names)):
        raise MedicalDataBuildError(
            f"MedQuAD source lacks required fields: {sorted(required_columns - set(dataset.column_names))}"
        )
    for index, row in enumerate(dataset):
        question = _clean_text(row.get("query"))
        answer = _clean_text(row.get("answers"))
        if question is None or answer is None:
            raise MedicalDataBuildError(f"MedQuAD row {index} has an empty question or answer.")
        results.append(
            {
                "qa_id": f"medquad_train_{index:08d}",
                "question_en": question,
                "question_ar": None,
                "answer_en": answer,
                "answer_ar": None,
                "category": _clean_text(row.get("group_name")),
                "source": "MedQuAD-derived HuggingFace dataset",
                "source_dataset_url": MEDQUAD_DATASET_URL,
                "url": None,
                "url_status": (
                    "record_specific_original_url_not_present_in_supplied_dataset"
                ),
                "source_license_status": "not_declared_in_dataset_metadata",
                "source_row_index": index,
                **_source_status(),
            }
        )
    return results


def _build_icd_index(
    source_index: list[dict[str, Any]], rag_rows: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for entry in source_index:
        code = _clean_text(entry.get("code"))
        if code is None:
            raise MedicalDataBuildError("ICD-10-CM index entry has no code.")
        by_code[code] = {
            "coding_system": entry.get("coding_system"),
            "code": code,
            "condition_ids": sorted(
                set(item for item in entry.get("condition_ids", []) if isinstance(item, str))
            ),
            "mappings": [
                {
                    "source": entry.get("source"),
                    "source_urls": entry.get("source_urls", []),
                    "mapping_status": entry.get(
                        "mapping_status", "source_asserted_unverified"
                    ),
                }
            ],
            "healthcare_rag_document_ids": [],
            **_source_status(),
        }
    added_codes = set()
    for row in rag_rows:
        code = _clean_text(row.get("icd10_code"))
        if code is None:
            continue
        current = by_code.setdefault(
            code,
            {
                "coding_system": "ICD-10-CM (source-asserted; not independently verified)",
                "code": code,
                "condition_ids": [],
                "mappings": [],
                "healthcare_rag_document_ids": [],
                **_source_status(),
            },
        )
        doc_id = _clean_text(row.get("doc_id"))
        if doc_id and doc_id not in current["healthcare_rag_document_ids"]:
            current["healthcare_rag_document_ids"].append(doc_id)
        if code not in added_codes:
            current["mappings"].append(
                {
                    "source": "Healthcare RAG CSV icd10_code field",
                    "source_urls": (
                        [_clean_text(row["source_url"])]
                        if _valid_http_url(_clean_text(row.get("source_url")))
                        else []
                    ),
                    "mapping_status": "source_asserted_unverified",
                }
            )
            added_codes.add(code)
    result = [by_code[code] for code in sorted(by_code)]
    return result, {
        "source_index_entries": len(source_index),
        "merged_unique_codes": len(result),
        "healthcare_rag_codes_added": len(set(_clean_text(row.get("icd10_code")) for row in rag_rows) - set(entry.get("code") for entry in source_index)),
        "mapping_verification": "unverified source assertions; not certified ICD validation",
    }


def _build_references(
    conditions: list[dict[str, Any]],
    rag_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    references: dict[tuple[str, str], dict[str, Any]] = {}
    for condition in conditions:
        for reference in condition.get("source_references", []):
            if not isinstance(reference, dict):
                continue
            url = reference.get("url")
            source = reference.get("source")
            if isinstance(url, str) and isinstance(source, str):
                references[(source, url)] = reference
        for document in condition.get("healthcare_rag_documents", []):
            url = document.get("source_url")
            source = document.get("source_name")
            if isinstance(url, str) and isinstance(source, str):
                references[(source, url)] = {
                    "source": source,
                    "title": document.get("title"),
                    "url": url,
                    "status": "source_claim_not_independently_verified",
                }
    references[("MedQuAD-derived dataset", MEDQUAD_DATASET_URL)] = {
        "source": "MedQuAD-derived HuggingFace dataset",
        "title": "clustered_MEDQUAD_dataset_with_groups",
        "url": MEDQUAD_DATASET_URL,
        "license_status": "not_declared_in_local_dataset_metadata",
    }
    for row in rag_rows:
        source = _clean_text(row.get("source_name"))
        url = _clean_text(row.get("source_url"))
        if source and _valid_http_url(url):
            references[(source, url)] = {
                "source": source,
                "url": url,
                "status": "source_claim_not_independently_verified",
            }
    return [
        {
            **references[key],
            "reference_id": _stable_id("ref", key[0] + "\n" + key[1]),
            **_source_status(),
        }
        for key in sorted(references)
    ]


def _file_audit(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return {
        "path": str(path.relative_to(ROOT)),
        "size_bytes": size,
        "sha256": digest.hexdigest(),
    }


def _csv_quality(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0, "columns": {}}
    columns: dict[str, Any] = {}
    for field in rows[0]:
        values = [_clean_text(row.get(field)) for row in rows]
        columns[field] = {
            "missing": sum(value is None for value in values),
            "distinct_nonempty": len({value for value in values if value is not None}),
        }
    return {"rows": len(rows), "columns": columns}


def _validate_outputs(outputs: dict[str, Any]) -> None:
    id_keys = {
        "conditions": "condition_id",
        "symptoms": "phenotype_id",
        "symptom_terms": "symptom_id",
        "associations": "association_id",
        "qa": "qa_id",
        "icd10_index": "code",
        "symptom2disease_reports": "report_id",
    }
    for collection, key in id_keys.items():
        records = outputs[collection]
        ids = [record.get(key) for record in records]
        if any(not isinstance(value, str) or not value for value in ids):
            raise MedicalDataBuildError(f"{collection} contains a record without {key}.")
        if len(ids) != len(set(ids)):
            raise MedicalDataBuildError(f"{collection} contains duplicate {key} values.")
        if any(record.get("not_for_clinical_use") is not True for record in records):
            raise MedicalDataBuildError(f"{collection} contains a record without the safety gate.")
    for record in outputs["qa"]:
        if record["question_ar"] is not None or record["answer_ar"] is not None:
            raise MedicalDataBuildError("Arabic fields must remain null without verified translation.")
    for record in outputs["symptoms"]:
        if record.get("clinical_symptom") is not False:
            raise MedicalDataBuildError("HPO concepts must not be promoted as clinical symptoms.")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def build_complete_content(
    *, output_dir: Path = OUTPUT_ROOT, strict_counts: bool = True
) -> dict[str, Any]:
    """Build all available source-derived records; never translate or infer facts."""
    inputs = _load_inputs(strict_counts=strict_counts)

    conditions, condition_stats = _build_conditions(
        inputs["conditions"],
        inputs["icd10_index"],
        inputs["associations"],
        inputs["healthcare_rag"],
    )
    phenotypes = _build_phenotypes(inputs["phenotypes"])
    symptom_terms = _build_symptom_terms(inputs["associations"])
    condition_ids = {record["condition_id"] for record in conditions}
    symptom_ids = {record["symptom_id"] for record in symptom_terms}
    associations = _build_associations(
        inputs["associations"], condition_ids, symptom_ids
    )
    qa = _build_qa(inputs["medquad"])
    icd_index, icd_stats = _build_icd_index(
        inputs["icd10_index"], inputs["healthcare_rag"]
    )
    symptom2disease_reports = _build_symptom2disease_reports(
        inputs["symptom2disease"]
    )
    by_category: dict[str, list[str]] = defaultdict(list)
    for condition in conditions:
        category_values = {
            document["category"]
            for document in condition.get("healthcare_rag_documents", [])
            if document.get("category")
        }
        category = sorted(category_values)[0] if category_values else "unclassified"
        by_category[category].append(condition["condition_id"])
    outputs: dict[str, Any] = {
        "conditions": conditions,
        "symptoms": phenotypes,
        "symptom_terms": symptom_terms,
        "associations": associations,
        "qa": qa,
        "icd10_index": icd_index,
        "symptom2disease_reports": symptom2disease_reports,
        "conditions_by_category": dict(sorted(by_category.items())),
        "symptoms_by_system": {},
        "specialists": [],
        "emergency_signs": [],
    }
    _validate_outputs(outputs)

    references = _build_references(conditions, inputs["healthcare_rag"])
    output_counts = {
        "conditions": len(conditions),
        "conditions_by_category_groups": len(outputs["conditions_by_category"]),
        "symptoms": len(phenotypes),
        "symptoms_by_system_groups": len(outputs["symptoms_by_system"]),
        "symptom_terms": len(symptom_terms),
        "symptom2disease_reports": len(symptom2disease_reports),
        "associations": len(associations),
        "qa": len(qa),
        "icd10_index": len(icd_index),
        "specialists": len(outputs["specialists"]),
        "emergency_signs": len(outputs["emergency_signs"]),
        "references": len(references),
    }
    relationship_stats = {
        "total": len(associations),
        "linked_to_source_condition_term": sum(
            record["condition_id"] is not None for record in associations
        ),
        "condition_id_not_in_active_term_set": sum(
            record["condition_id"] is None for record in associations
        ),
        "linked_to_source_symptom_term": sum(
            record["symptom_id"] in symptom_ids for record in associations
        ),
    }
    qa_duplicate_questions = len(qa) - len(
        {record["question_en"].casefold() for record in qa}
    )
    source_audit = {
        "generated_at": IMPORT_DATE,
        "input_counts": inputs["input_counts"],
        "source_files": {
            "conditions": _file_audit(SOURCE_PATHS["conditions"]),
            "phenotypes": _file_audit(SOURCE_PATHS["phenotypes"]),
            "associations": _file_audit(SOURCE_PATHS["associations"]),
            "icd10_index": _file_audit(SOURCE_PATHS["icd10_index"]),
            "healthcare_rag": _file_audit(SOURCE_PATHS["healthcare_rag"]),
            "symptom2disease": _file_audit(SOURCE_PATHS["symptom2disease"]),
            "medquad": [
                _file_audit(path)
                for path in sorted(SOURCE_PATHS["medquad"].rglob("*"))
                if path.is_file() and path.name != ".gitkeep"
            ],
        },
        "inputs": {
            "disease_ontology": {
                "path": str(SOURCE_PATHS["conditions"].relative_to(ROOT)),
                "url": "https://github.com/DiseaseOntology/HumanDiseaseOntology",
                "license_status": "source-specific license must be reviewed before redistribution",
            },
            "hpo": {
                "path": str(SOURCE_PATHS["phenotypes"].relative_to(ROOT)),
                "url": "https://hpo.jax.org/",
                "license_status": "source-specific license must be reviewed before redistribution",
            },
            "disease_symptom": inputs["association_metadata"],
            "healthcare_rag": {
                "path": str(SOURCE_PATHS["healthcare_rag"].relative_to(ROOT)),
                "distinct_icd10_codes": len(_rag_by_code(inputs["healthcare_rag"])),
                "source_url_missing_rows": sum(
                    not _valid_http_url(_clean_text(row.get("source_url")))
                    for row in inputs["healthcare_rag"]
                ),
                "review_status_counts": dict(
                    Counter(row.get("review_status", "") for row in inputs["healthcare_rag"])
                ),
                "field_quality": _csv_quality(inputs["healthcare_rag"]),
                "license_status": "not verified in local source files",
                "editorial_claims_independently_verified": False,
            },
            "symptom2disease": {
                "path": str(SOURCE_PATHS["symptom2disease"].relative_to(ROOT)),
                "distinct_source_labels": len(
                    {_clean_text(row.get("label")) for row in inputs["symptom2disease"]}
                ),
                "distinct_narratives": len(
                    {_clean_text(row.get("text")) for row in inputs["symptom2disease"]}
                ),
                "field_quality": _csv_quality(inputs["symptom2disease"]),
                "license_status": "not verified in local source files",
            },
            "medquad": {
                "path": str(SOURCE_PATHS["medquad"].relative_to(ROOT)),
                "url": MEDQUAD_DATASET_URL,
                "split": "train",
                "license_status": "not declared in local dataset metadata",
                "record_specific_original_urls_available": False,
                "duplicate_questions": qa_duplicate_questions,
                "field_quality": {
                    field: {
                        "missing": sum(
                            _clean_text(row.get(field)) is None
                            for row in inputs["medquad"]
                        ),
                        "distinct_nonempty": len(
                            {
                                _clean_text(row.get(field))
                                for row in inputs["medquad"]
                                if _clean_text(row.get(field)) is not None
                            }
                        ),
                    }
                    for field in inputs["medquad"].column_names
                },
            },
            "icd10_index": icd_stats,
        },
        "output_counts": output_counts,
        "condition_selection": condition_stats,
        "relationship_integrity": relationship_stats,
        "symptom_interpretation": {
            "hpo_records_are_clinical_symptoms": False,
            "hpo_selection_count": len(phenotypes),
            "unique_symp_terms": len(symptom_terms),
            "symptom2disease_records_are_symptom_assertions": False,
            "association_count": len(associations),
        },
        "arabic_translation": {
            "translated_records": 0,
            "status": "not translated; no Arabic text was present in the supplied sources",
            "external_translation_service_used": False,
        },
        "non_generated_catalogs": {
            "specialists": {
                "count": 0,
                "reason": "No source provides an explicit, attributable specialist mapping.",
            },
            "emergency_signs": {
                "count": 0,
                "reason": (
                    "No source supplies clinically reviewed emergency/red-flag rules; "
                    "general symptoms were not reclassified as emergencies."
                ),
            },
            "symptoms_by_system": {
                "count": 0,
                "reason": "The selected HPO records do not contain a validated body-system field.",
            },
        },
        "safety": {
            "content_status": "draft",
            "review_status": "unreviewed",
            "not_for_clinical_use": True,
            "published_catalog_modified": False,
            "source_claims_independently_verified": False,
        },
    }
    outputs["references"] = references
    outputs["stats"] = source_audit

    json_outputs = {
        "conditions.json": outputs["conditions"],
        "conditions_by_category.json": outputs["conditions_by_category"],
        "symptoms.json": outputs["symptoms"],
        "symptoms_by_system.json": outputs["symptoms_by_system"],
        "symptom_terms.json": outputs["symptom_terms"],
        "symptom2disease_reports.json": outputs["symptom2disease_reports"],
        "associations.json": outputs["associations"],
        "qa.json": outputs["qa"],
        "icd10_index.json": outputs["icd10_index"],
        "specialists.json": outputs["specialists"],
        "emergency_signs.json": outputs["emergency_signs"],
        "references.json": references,
        "stats.json": source_audit,
    }
    for filename, value in json_outputs.items():
        _atomic_json(output_dir / filename, value)
        LOG.info("Wrote %s (%d records)", output_dir / filename, len(value))
    return source_audit


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = build_complete_content()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
