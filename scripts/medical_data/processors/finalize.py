"""Build review-required final drafts from downloaded ontology candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[3]
PROCESSED_ROOT = ROOT / "data" / "medical_content" / "processed"
FINAL_ROOT = PROCESSED_ROOT / "final"
ICD10CM_OID = "2.16.840.1.113883.6.90"


def _read_records(path: Path, source: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {source} candidate file: {path}")
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    records = document.get("records") if isinstance(document, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"{source} candidate file must contain a records array: {path}")
    return document


def _unique(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def _xref_parts(xref: str) -> tuple[str, str] | None:
    system, separator, code = xref.partition(":")
    if not separator:
        return None
    code = code.split(" ! ", 1)[0].strip().strip('"')
    return (system.strip(), code) if system.strip() and code else None


def _condition_key(doid: str) -> str:
    return doid.casefold().replace(":", "_")


def _query_code(query_url: Any) -> str | None:
    if not isinstance(query_url, str):
        return None
    query = parse_qs(urlparse(query_url).query)
    code_values = query.get("mainSearchCriteria.v.c", [])
    system_values = query.get("mainSearchCriteria.v.cs", [])
    if not code_values or not system_values or system_values[0] != ICD10CM_OID:
        return None
    code = code_values[0].strip()
    return code or None


def _entry_title(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict) and isinstance(value.get("_value"), str):
        return value["_value"].strip() or None
    return None


def _entry_urls(value: Any) -> list[str]:
    entries = value if isinstance(value, list) else [value]
    return [
        entry["href"]
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("href"), str)
        and urlparse(entry["href"]).scheme == "https"
    ]


def build_final_drafts(
    condition_document: dict[str, Any],
    hpo_document: dict[str, Any],
    medlineplus_document: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Clean source candidates, retaining only source-explicit mappings."""
    report: dict[str, Any] = {
        "content_status": "draft_only",
        "clinical_review_required": True,
        "clinical_symptom_assertions_created": 0,
        "mapping_policy": (
            "Only exact source xrefs and exact ICD-10-CM query codes are linked; "
            "no label similarity, inferred codes, or clinical approval is applied."
        ),
    }
    conditions_by_doid: dict[str, dict[str, Any]] = {}
    condition_excluded = {"obsolete": 0, "missing_identifier": 0, "missing_label": 0}
    duplicate_doids = 0

    for candidate in condition_document["records"]:
        if not isinstance(candidate, dict):
            condition_excluded["missing_identifier"] += 1
            continue
        doid = candidate.get("ontology_id")
        label = candidate.get("condition_en")
        if not isinstance(doid, str) or not doid.startswith("DOID:"):
            condition_excluded["missing_identifier"] += 1
            continue
        if candidate.get("is_obsolete") is True:
            condition_excluded["obsolete"] += 1
            continue
        if not isinstance(label, str) or not label.strip():
            condition_excluded["missing_label"] += 1
            continue

        if doid in conditions_by_doid:
            duplicate_doids += 1
            continue

        codes = _unique(candidate.get("icd10cm_codes"))
        xrefs = _unique(candidate.get("external_xrefs"))
        candidate_references = candidate.get("references", [])
        references = candidate_references if isinstance(candidate_references, list) else []
        source_urls = _unique(
            [
                reference["url"]
                for reference in references
                if isinstance(reference, dict)
                and isinstance(reference.get("url"), str)
                and urlparse(reference["url"]).scheme == "https"
            ]
        )
        xrefs_by_code: dict[str, str] = {}
        for xref in xrefs:
            parts = _xref_parts(xref)
            if parts is not None and parts[0].casefold() == "icd10cm":
                xrefs_by_code.setdefault(parts[1], xref)
        conditions_by_doid[doid] = {
            "condition_id": _condition_key(doid),
            "condition_en": label.strip(),
            "condition_ar": None,
            "record_type": "disease_ontology_condition",
            "ontology_id": doid,
            "definition_source_text": candidate.get("definition_source_text"),
            "synonyms_en": _unique(candidate.get("synonyms_en")),
            "ontology_parents": _unique(candidate.get("ontology_parents")),
            "external_xrefs": xrefs,
            "icd10_crosswalks": [
                {
                    "coding_system": "ICD-10-CM",
                    "code": code,
                    "source_xref": xrefs_by_code.get(code, f"ICD10CM:{code}"),
                    "source_urls": source_urls,
                    "mapping_status": "source_asserted_unverified",
                }
                for code in codes
            ],
            "related_phenotype_ids": [],
            "supporting_source_links": [],
            "references": references if isinstance(references, list) else [],
            "source_release": condition_document.get("source_release"),
            "source_sha256": condition_document.get("source_sha256"),
            "content_status": "draft",
            "review_status": "unreviewed",
            "clinical_review_required": True,
        }

    conditions_by_code: dict[str, list[str]] = {}
    conditions_by_id: dict[str, dict[str, Any]] = {}
    for doid, condition in conditions_by_doid.items():
        conditions_by_id[condition["condition_id"]] = condition
        for mapping in condition["icd10_crosswalks"]:
            conditions_by_code.setdefault(mapping["code"], []).append(_condition_key(doid))

    phenotype_document_records = hpo_document["records"]
    phenotypes: list[dict[str, Any]] = []
    phenotype_excluded = {
        "deprecated": 0,
        "missing_identifier": 0,
        "missing_label": 0,
        "non_hpo_graph_nodes": int(hpo_document.get("non_hpo_graph_nodes_excluded", 0)),
    }
    duplicate_phenotype_ids = 0
    seen_phenotype_ids: set[str] = set()
    exact_hpo_doid_links = 0
    hpo_icd_xref_count = 0

    for candidate in phenotype_document_records:
        if not isinstance(candidate, dict):
            phenotype_excluded["missing_identifier"] += 1
            continue
        phenotype_id = candidate.get("phenotype_id")
        label = candidate.get("name_en")
        if not isinstance(phenotype_id, str) or not phenotype_id.startswith("HP:"):
            phenotype_excluded["missing_identifier"] += 1
            continue
        if candidate.get("is_deprecated") is True:
            phenotype_excluded["deprecated"] += 1
            continue
        if not isinstance(label, str) or not label.strip():
            phenotype_excluded["missing_label"] += 1
            continue
        if phenotype_id in seen_phenotype_ids:
            duplicate_phenotype_ids += 1
            continue
        seen_phenotype_ids.add(phenotype_id)

        xrefs = _unique(candidate.get("external_xrefs"))
        code_xrefs: list[dict[str, str]] = []
        linked_condition_ids: list[str] = []
        for xref in xrefs:
            parts = _xref_parts(xref)
            if parts is None:
                continue
            system, code = parts
            if system.casefold() in {"icd-10", "icd10", "icd10cm"}:
                code_xrefs.append(
                    {"coding_system": system, "code": code, "source_xref": xref}
                )
            if system.casefold() == "doid":
                condition = conditions_by_doid.get(f"{system}:{code}")
                if condition is not None:
                    linked_condition_ids.append(condition["condition_id"])
        linked_condition_ids = list(dict.fromkeys(linked_condition_ids))
        exact_hpo_doid_links += len(linked_condition_ids)
        hpo_icd_xref_count += len(code_xrefs)

        phenotypes.append(
            {
                "phenotype_id": phenotype_id,
                "name_en": label.strip(),
                "name_ar": None,
                "record_type": "phenotype_concept",
                "clinical_symptom": False,
                "symptom_catalog_eligible": False,
                "definition_source_text": candidate.get("definition_source_text"),
                "synonyms_en": _unique(candidate.get("synonyms_en")),
                "external_xrefs": xrefs,
                "icd_code_xrefs": code_xrefs,
                "related_condition_ids": linked_condition_ids,
                "references": candidate.get("references", [])
                if isinstance(candidate.get("references"), list)
                else [],
                "source_release": hpo_document.get("source_release"),
                "source_sha256": hpo_document.get("source_sha256"),
                "content_status": "draft",
                "review_status": "unreviewed",
                "clinical_review_required": True,
            }
        )

    # Create the reciprocal relationship only for explicit HPO DOID xrefs.
    for phenotype in phenotypes:
        for condition_id in phenotype["related_condition_ids"]:
            condition = conditions_by_id.get(condition_id)
            if condition is not None:
                condition["related_phenotype_ids"].append(phenotype["phenotype_id"])

    medlineplus_link_count = 0
    unmatched_medlineplus_code_count = 0
    if medlineplus_document:
        for candidate in medlineplus_document.get("records", []):
            if not isinstance(candidate, dict):
                continue
            code = _query_code(candidate.get("query_url"))
            if code is None:
                continue
            condition_ids = conditions_by_code.get(code, [])
            if not condition_ids:
                unmatched_medlineplus_code_count += 1
                continue
            title = _entry_title(candidate.get("title_source_text"))
            urls = _entry_urls(candidate.get("source_url"))
            for condition_id in condition_ids:
                condition = conditions_by_id.get(condition_id)
                if condition is None:
                    continue
                for url in urls:
                    link = {
                        "source": "MedlinePlus Connect",
                        "title": title or "MedlinePlus Connect result",
                        "url": url,
                        "matched_query_code": code,
                        "coding_system": "ICD-10-CM",
                    }
                    if link not in condition["supporting_source_links"]:
                        condition["supporting_source_links"].append(link)
                        medlineplus_link_count += 1

    conditions = list(conditions_by_doid.values())
    for condition in conditions:
        condition["related_phenotype_ids"] = _unique(condition["related_phenotype_ids"])
    conditions.sort(key=lambda item: item["ontology_id"])
    phenotypes.sort(key=lambda item: item["phenotype_id"])
    icd10_index = [
        {
            "coding_system": "ICD-10-CM",
            "code": code,
            "condition_ids": sorted(set(condition_ids)),
            "mapping_status": "source_asserted_unverified",
            "source": "Disease Ontology ICD10CM xref",
            "source_urls": sorted(
                {
                    url
                    for condition_id in set(condition_ids)
                    for mapping in conditions_by_id[condition_id]["icd10_crosswalks"]
                    if mapping["code"] == code
                    for url in mapping["source_urls"]
                }
            ),
        }
        for code, condition_ids in sorted(conditions_by_code.items())
    ]

    report.update(
        {
            "source_releases": {
                "disease_ontology": condition_document.get("source_release"),
                "hpo": hpo_document.get("source_release"),
            },
            "candidate_counts": {
                "disease_ontology": len(condition_document["records"]),
                "hpo": len(phenotype_document_records),
            },
            "output_counts": {
                "conditions": len(conditions),
                "phenotype_concepts": len(phenotypes),
                "icd10cm_condition_codes": len(icd10_index),
                "icd10cm_condition_mappings": sum(
                    len(item["condition_ids"]) for item in icd10_index
                ),
                "hpo_direct_icd_xrefs": hpo_icd_xref_count,
                "exact_hpo_doid_links": exact_hpo_doid_links,
                "medlineplus_exact_code_links": medlineplus_link_count,
            },
            "excluded": {
                "conditions": condition_excluded,
                "phenotypes": phenotype_excluded,
                "duplicate_disease_ontology_ids": duplicate_doids,
                "duplicate_hpo_ids": duplicate_phenotype_ids,
                "medlineplus_records_with_unmatched_exact_code": unmatched_medlineplus_code_count,
            },
            "limitations": [
                "ICD-10-CM codes are Disease Ontology source cross-references, not an independently validated WHO ICD-10 import.",
                "HPO concepts remain phenotype concepts and are not approved clinical symptoms.",
                "No Arabic translations or clinical advice were created.",
                "All records remain drafts requiring qualified clinical and licensing review.",
            ],
        }
    )
    return conditions, phenotypes, icd10_index, report


def finalize_from_processed(processed_root: Path = PROCESSED_ROOT) -> dict[str, Any]:
    condition_document = _read_records(
        processed_root / "conditions" / "disease_ontology_candidates.json",
        "Disease Ontology",
    )
    hpo_path = processed_root / "symptoms" / "hpo_candidates.json"
    if not hpo_path.is_file():
        hpo_path = processed_root / "symptoms" / "hpo_phenotype_concepts.json"
    hpo_document = _read_records(hpo_path, "HPO")
    medline_path = processed_root / "conditions" / "medlineplus_connect_results.json"
    medlineplus_document = _read_records(medline_path, "MedlinePlus") if medline_path.is_file() else None
    conditions, phenotypes, icd10_index, report = build_final_drafts(
        condition_document,
        hpo_document,
        medlineplus_document,
    )

    FINAL_ROOT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "conditions.json": conditions,
        "phenotype_concepts.json": phenotypes,
        "icd10cm_condition_index.json": icd10_index,
        "finalization_report.json": report,
    }
    for filename, payload in outputs.items():
        path = FINAL_ROOT / filename
        temporary = path.with_name(path.name + ".part")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise
    return report


def main() -> int:
    report = finalize_from_processed()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
