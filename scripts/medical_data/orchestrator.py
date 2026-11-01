"""Command line acquisition and draft normalization pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from scripts.medical_data.config import SOURCES
from scripts.medical_data.downloaders import (
    DiseaseOntologyDownloader,
    HPODownloader,
    ICD10Downloader,
    LOINCDownloader,
    MedlinePlusDownloader,
    MedQuADDownloader,
    MeSHDownloader,
    OpenFDADownloader,
    PubMedDownloader,
    RxNormDownloader,
    SNOMEDDownloader,
)
from scripts.medical_data.downloaders.base import DownloadError
from scripts.medical_data.processors.merge import merge_exact
from scripts.medical_data.processors.normalize import (
    parse_hpo,
    parse_medlineplus,
    parse_obo,
    parse_pubmed_xml,
)
from scripts.medical_data.processors.validate import (
    validate_processed_records,
    validate_raw_tree,
)


ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "data" / "medical_content"
RAW_ROOT = CONTENT_ROOT / "raw"
PROCESSED_ROOT = CONTENT_ROOT / "processed"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _sidecar_for(path: Path) -> dict[str, Any]:
    metadata_path = path.with_suffix(path.suffix + ".metadata.json")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _relative_artifacts(source: str) -> list[str]:
    source_dir = RAW_ROOT / source
    if not source_dir.is_dir():
        return []
    return [
        path.relative_to(ROOT).as_posix()
        for path in sorted(source_dir.iterdir())
        if path.is_file()
        and path.name != ".gitkeep"
        and not path.name.endswith(".metadata.json")
        and not path.name.endswith(".part")
    ]


def _count_rxnorm_concepts(value: Any) -> int:
    if isinstance(value, dict):
        own = int(bool(value.get("rxcui") and value.get("name")))
        return own + sum(_count_rxnorm_concepts(child) for child in value.values())
    if isinstance(value, list):
        return sum(_count_rxnorm_concepts(child) for child in value)
    return 0


def _summarize_download(source: str, result: Any, args: argparse.Namespace) -> dict[str, Any]:
    """Keep raw medical payloads in raw artifacts, not in run reports or stdout."""
    artifacts = _relative_artifacts(source)
    summary: dict[str, Any] = {"artifacts": artifacts}
    if source == "medlineplus":
        condition_file = getattr(args, "medlineplus_condition_file", None)
        if condition_file:
            summary.update(
                condition_count=len(result),
                matched_condition_ids=sorted(
                    condition_id
                    for condition_id, record in result.items()
                    if record["result_status"] == "matched"
                ),
                languages=list(
                    getattr(args, "medlineplus_languages", None) or ("en", "es")
                ),
            )
        else:
            summary.update(
                query_count=len(args.medlineplus_codes),
                matched_codes=sorted(result),
            )
    elif source == "openfda":
        summary["record_count"] = len(result)
    elif source == "rxnorm":
        searches = result.get("searches", [])
        summary.update(
            search_count=len(searches),
            concept_count=sum(_count_rxnorm_concepts(item) for item in searches),
            interaction_query_count=len(result.get("interactions", {})),
        )
    elif source == "mesh":
        summary.update(
            query_count=len(result),
            descriptor_count=sum(len(items) for items in result.values()),
        )
    elif source == "pubmed":
        summary.update(
            query=result.get("query"),
            citation_count=len(result.get("pmids", [])),
            abstract_batch_count=result.get("batch_count", 0),
        )
    elif isinstance(result, Path):
        summary["imported_artifact"] = result.relative_to(ROOT).as_posix() if result.is_relative_to(ROOT) else result.name
    elif isinstance(result, dict):
        for key in ("release", "sha256", "term_graph_count", "license_spdx", "branch", "integrable"):
            if key in result:
                summary[key] = result[key]
    elif isinstance(result, list):
        summary["record_count"] = len(result)
    return summary


def process_downloads() -> dict[str, int]:
    """Produce provenance-bearing draft extracts; never publish to live content."""
    counts: dict[str, int] = {}
    condition_records: list[dict[str, Any]] = []
    for path in sorted((RAW_ROOT / "disease_ontology").glob("*.obo")):
        metadata = _sidecar_for(path)
        records = parse_obo(path.read_text(encoding="utf-8"), metadata["final_url"])
        condition_records.extend(records)
    merged_conditions = merge_exact(condition_records)
    if merged_conditions:
        errors = validate_processed_records(merged_conditions)
        if errors:
            raise ValueError("Processed Disease Ontology records failed validation: " + "; ".join(errors[:10]))
        _atomic_json(
            PROCESSED_ROOT / "conditions" / "disease_ontology_candidates.json",
            {
                "records": merged_conditions,
                "source_release": metadata.get("source_version"),
                "source_sha256": metadata.get("sha256"),
                "content_status": "draft_only",
                "clinical_review_required": True,
            },
        )
        counts["disease_ontology_candidates"] = len(merged_conditions)

    hpo_records: list[dict[str, Any]] = []
    for path in sorted((RAW_ROOT / "hpo").glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        metadata = _sidecar_for(path)
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        non_hpo_nodes_excluded = sum(
            1
            for graph in document.get("graphs", [])
            if isinstance(graph, dict)
            for node in graph.get("nodes", [])
            if isinstance(node, dict)
            and isinstance(node.get("id"), str)
            and node["id"].startswith("http")
            and not node["id"].rsplit("/", 1)[-1].startswith("HP_")
            and isinstance(node.get("lbl"), str)
            and bool(node["lbl"].strip())
        )
        hpo_records.extend(
            parse_hpo(
                document,
                metadata["source_url"],
                release_tag=metadata.get("source_version"),
            )
        )
    if hpo_records:
        _atomic_json(
            PROCESSED_ROOT / "symptoms" / "hpo_phenotype_concepts.json",
            {
                "records": hpo_records,
                "source_release": metadata.get("source_version"),
                "source_sha256": metadata.get("sha256"),
                "non_hpo_graph_nodes_excluded": non_hpo_nodes_excluded,
                "content_status": "draft_only",
                "note": "Phenotype ontology concepts are not asserted to be symptoms.",
                "clinical_review_required": True,
            },
        )
        counts["hpo_phenotype_concepts"] = len(hpo_records)

    medline_records = []
    for path in sorted((RAW_ROOT / "medlineplus").glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        metadata = _sidecar_for(path)
        medline_records.extend(
            parse_medlineplus(
                json.loads(path.read_text(encoding="utf-8-sig")),
                metadata["request_url"],
            )
        )
    if medline_records:
        _atomic_json(
            PROCESSED_ROOT / "conditions" / "medlineplus_connect_results.json",
            {
                "records": medline_records,
                "content_status": "draft_only",
                "clinical_review_required": True,
            },
        )
        counts["medlineplus_connect_results"] = len(medline_records)

    citations = []
    for path in sorted((RAW_ROOT / "pubmed").glob("abstracts_*.xml")):
        metadata = _sidecar_for(path)
        citations.extend(parse_pubmed_xml(path.read_bytes(), metadata["source_url"]))
    if citations:
        citations = merge_exact(citations)
        _atomic_json(
            PROCESSED_ROOT / "qa" / "pubmed_citations.json",
            {
                "records": citations,
                "content_status": "draft_only",
                "note": "Citation metadata only; article text and abstracts are not published.",
            },
        )
        counts["pubmed_citations"] = len(citations)

    openfda_records = []
    for path in sorted((RAW_ROOT / "openfda").glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        metadata = _sidecar_for(path)
        for label in document.get("results", []):
            openfda = label.get("openfda", {}) if isinstance(label, dict) else {}
            set_id = openfda.get("spl_set_id")
            if not set_id:
                continue
            brand_names = openfda.get("brand_name", [])
            generic_names = openfda.get("generic_name", [])
            if isinstance(brand_names, str):
                brand_names = [brand_names]
            if isinstance(generic_names, str):
                generic_names = [generic_names]
            openfda_records.append(
                {
                    "drug_id": f"openfda_spl_set_id:{set_id}",
                    "name_source_text": (brand_names or generic_names or [None])[0],
                    "generic_names_source_text": generic_names,
                    "brand_names_source_text": brand_names,
                    "indications_source_text": label.get("indications_and_usage"),
                    "warnings_source_text": label.get("warnings") or label.get("warnings_and_cautions"),
                    "source_query": metadata.get("search"),
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "references": [
                        {
                            "source": "openFDA",
                            "title": "FDA-submitted Structured Product Label",
                            "url": "https://open.fda.gov/apis/drug/label/",
                        }
                    ],
                    "license_status": metadata.get("license_status"),
                }
            )
    if openfda_records:
        openfda_records = merge_exact(openfda_records)
        errors = validate_processed_records(openfda_records)
        if errors:
            raise ValueError("Processed openFDA records failed validation: " + "; ".join(errors[:10]))
        _atomic_json(
            PROCESSED_ROOT / "drugs" / "openfda_label_drafts.json",
            {
                "records": openfda_records,
                "content_status": "draft_only",
                "note": "FDA-submitted labels require item-level verification and clinical review.",
                "clinical_review_required": True,
            },
        )
        counts["openfda_label_drafts"] = len(openfda_records)

    mesh_records = []
    for path in sorted((RAW_ROOT / "mesh").glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        metadata = _sidecar_for(path)
        for item in json.loads(path.read_text(encoding="utf-8-sig")):
            if not isinstance(item, dict):
                continue
            mesh_records.append(
                {
                    "mesh_id": item.get("resource"),
                    "name_source_text": item.get("label"),
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "references": [
                        {
                            "source": "Medical Subject Headings",
                            "title": f"MeSH lookup: {metadata.get('query', '')}",
                            "url": "https://meshb.nlm.nih.gov/",
                        }
                    ],
                }
            )
    if mesh_records:
        _atomic_json(
            PROCESSED_ROOT / "conditions" / "mesh_descriptor_candidates.json",
            {
                "records": mesh_records,
                "content_status": "draft_only",
                "note": "MeSH descriptors are terminology records, not condition assessments.",
            },
        )
        counts["mesh_descriptor_candidates"] = len(mesh_records)

    rxnorm_records = []
    for path in sorted((RAW_ROOT / "rxnorm").glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        metadata = _sidecar_for(path)
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        for concept in _walk_rxnorm_concepts(document):
            rxnorm_records.append(
                {
                    "drug_id": f"RXCUI:{concept['rxcui']}",
                    "rxcui": concept["rxcui"],
                    "name_source_text": concept["name"],
                    "tty_source_text": concept.get("tty"),
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "references": [
                        {
                            "source": "NLM RxNorm",
                            "title": "RxNorm API result",
                            "url": "https://rxnav.nlm.nih.gov/RxNormAPIs.html",
                        }
                    ],
                    "license_status": metadata.get("license_status"),
                }
            )
    if rxnorm_records:
        rxnorm_records = merge_exact(rxnorm_records)
        _atomic_json(
            PROCESSED_ROOT / "drugs" / "rxnorm_concept_candidates.json",
            {
                "records": rxnorm_records,
                "content_status": "draft_only",
                "note": "RxNorm concepts are not prescribing or safety recommendations.",
                "clinical_review_required": True,
            },
        )
        counts["rxnorm_concept_candidates"] = len(rxnorm_records)

    interaction_records = []
    for path in sorted((RAW_ROOT / "rxnorm").glob("interactions_*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        metadata = _sidecar_for(path)
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        for interaction in _walk_rxnorm_interactions(document):
            interaction_records.append(
                {
                    "interaction_id": interaction["interaction_id"],
                    "source_rxcui": metadata.get("rxcui"),
                    "severity_source_text": interaction.get("severity"),
                    "description_source_text": interaction.get("description"),
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "references": [
                        {
                            "source": "NLM RxNav",
                            "title": "RxNav drug interaction API result",
                            "url": "https://rxnav.nlm.nih.gov/RxNormAPIs.html",
                        }
                    ],
                    "license_status": metadata.get("license_status"),
                }
            )
    if interaction_records:
        interaction_records = merge_exact(interaction_records)
        _atomic_json(
            PROCESSED_ROOT / "drugs" / "rxnorm_interaction_candidates.json",
            {
                "records": interaction_records,
                "content_status": "draft_only",
                "note": "Potential interactions require clinical/pharmacist verification.",
                "clinical_review_required": True,
            },
        )
        counts["rxnorm_interaction_candidates"] = len(interaction_records)

    loinc_rows = _read_loinc_archives()
    if loinc_rows:
        _atomic_json(
            PROCESSED_ROOT / "labs" / "loinc_candidates.json",
            {
                "records": loinc_rows,
                "content_status": "draft_only",
                "note": "LOINC labels and codes are not laboratory reference intervals.",
                "clinical_review_required": True,
            },
        )
        counts["loinc_candidates"] = len(loinc_rows)
    return counts


def _read_loinc_archives() -> list[dict[str, Any]]:
    import zipfile

    records = []
    for archive_path in sorted((RAW_ROOT / "loinc").glob("*.zip")):
        metadata = _sidecar_for(archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            table = next(
                (name for name in archive.namelist() if Path(name).name.casefold() == "loinc.csv"),
                None,
            )
            if table is None:
                continue
            with archive.open(table) as stream:
                text_stream = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
                for row in csv.DictReader(text_stream):
                    code = row.get("LOINC_NUM")
                    long_name = row.get("LONG_COMMON_NAME") or row.get("COMPONENT")
                    if not code or not long_name:
                        continue
                    records.append(
                        {
                            "test_id": f"LOINC:{code}",
                            "loinc_code": code,
                            "name_en": long_name,
                            "content_status": "draft",
                            "review_status": "unreviewed",
                            "references": [
                                {
                                    "source": "LOINC",
                                    "title": "LOINC table",
                                    "url": "https://loinc.org/downloads/",
                                }
                            ],
                            "license_status": metadata.get("license_status"),
                        }
                    )
    return merge_exact(records)


def _walk_rxnorm_concepts(value: Any):
    if isinstance(value, dict):
        if value.get("rxcui") and value.get("name"):
            yield {
                "rxcui": str(value["rxcui"]),
                "name": str(value["name"]),
                "tty": value.get("tty"),
            }
        for child in value.values():
            yield from _walk_rxnorm_concepts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_rxnorm_concepts(child)


def _walk_rxnorm_interactions(value: Any):
    if isinstance(value, dict):
        if value.get("interactionTypeGroup"):
            for group in value["interactionTypeGroup"]:
                for interaction_type in group.get("interactionType", []):
                    for item in interaction_type.get("interaction", []):
                        pair = item.get("minConcept", [])
                        pair_key = "-".join(
                            sorted(str(concept.get("rxcui", "")) for concept in pair)
                        )
                        if pair_key.strip("-"):
                            yield {
                                "interaction_id": f"rxnav:{pair_key}",
                                "severity": item.get("severity"),
                                "description": item.get("description"),
                            }
        for child in value.values():
            yield from _walk_rxnorm_interactions(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_rxnorm_interactions(child)


def acquire(args: argparse.Namespace) -> dict[str, Any]:
    selected = args.sources
    if not selected:
        raise ValueError("Choose one or more sources with --sources.")
    unknown = sorted(set(selected) - set(SOURCES))
    if unknown:
        raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

    results: dict[str, Any] = {}
    source_errors: dict[str, str] = {}
    downloaders = {
        "disease_ontology": lambda: DiseaseOntologyDownloader(RAW_ROOT).fetch_all(),
        "hpo": lambda: HPODownloader(RAW_ROOT).fetch_all(),
        "icd10": lambda: ICD10Downloader(RAW_ROOT).fetch_all(),
        "loinc": lambda: LOINCDownloader(RAW_ROOT).fetch_all(),
        "snomed": lambda: SNOMEDDownloader(RAW_ROOT).fetch_all(),
        "medquad": lambda: MedQuADDownloader(RAW_ROOT).fetch_all(
            allow_unverified_license=args.allow_unverified_license
        ),
        "medlineplus": lambda: MedlinePlusDownloader(RAW_ROOT).fetch_all(
            args.medlineplus_codes, lang=args.language
        ),
        "openfda": lambda: OpenFDADownloader(RAW_ROOT).fetch_all(
            args.openfda_search, max_results=args.max_results
        ),
        "rxnorm": lambda: (
            {
                "searches": [
                    RxNormDownloader(RAW_ROOT).search_drug(name)
                    for name in args.rxnorm_names
                ],
                "interactions": RxNormDownloader(RAW_ROOT).fetch_all(args.rxcuis),
            }
        ),
        "mesh": lambda: MeSHDownloader(RAW_ROOT).fetch_all(args.mesh_terms),
        "pubmed": lambda: PubMedDownloader(RAW_ROOT).fetch_all(
            args.pubmed_query, max_results=args.max_results
        ),
    }
    if getattr(args, "medlineplus_condition_file", None):
        condition_file = args.medlineplus_condition_file

        def fetch_medlineplus_conditions() -> dict[str, dict[str, Any]]:
            try:
                document = json.loads(condition_file.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Cannot read MedlinePlus condition input: {condition_file}"
                ) from exc
            records = document.get("records") if isinstance(document, dict) else document
            if not isinstance(records, list) or any(
                not isinstance(record, dict) for record in records
            ):
                raise ValueError(
                    "MedlinePlus condition input must be an array of condition objects."
                )
            content_candidates = [
                record
                for record in records
                if record.get("record_type") == "condition_content_candidate"
            ]
            if content_candidates:
                records = content_candidates
            languages = tuple(
                getattr(args, "medlineplus_languages", None) or ("en", "es")
            )
            downloader = MedlinePlusDownloader(RAW_ROOT)
            results = downloader.fetch_conditions(records, languages=languages)
            downloader.save_results(results)
            return results

        downloaders["medlineplus"] = fetch_medlineplus_conditions
    for source in selected:
        try:
            result = downloaders[source]()
            results[source] = _summarize_download(source, result, args)
        except (DownloadError, PermissionError, RuntimeError, ValueError, OSError) as exc:
            source_errors[source] = str(exc)

    processed = process_downloads()
    raw_errors = [
        error
        for source in selected
        for error in validate_raw_tree(RAW_ROOT / source)
    ]
    report = {
        "sources": results,
        "source_errors": source_errors,
        "status": "partial" if source_errors else "complete",
        "processed_draft_counts": processed,
        "raw_validation_errors": raw_errors,
        "clinical_content_published": False,
        "research_only": True,
    }
    report["run_id"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    _atomic_json(PROCESSED_ROOT / "acquisition_report.json", report)
    if raw_errors:
        raise ValueError("Raw provenance validation failed: " + "; ".join(raw_errors[:10]))
    return report


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire medical data from official APIs into a provenance-tracked raw area."
    )
    parser.add_argument(
        "--sources",
        help="Comma-separated source IDs. Use --list-sources to inspect requirements.",
    )
    parser.add_argument("--list-sources", action="store_true")
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="Regenerate processed source candidates from existing raw artifacts without downloading.",
    )
    parser.add_argument("--medlineplus-codes", nargs="*", default=[])
    parser.add_argument(
        "--medlineplus-condition-file",
        type=Path,
        help="JSON condition array (or object with records array) with exact ICD-10-CM codes.",
    )
    parser.add_argument(
        "--medlineplus-languages",
        nargs="+",
        choices=("en", "es"),
        help="Languages for condition-file lookups; Connect does not support Arabic.",
    )
    parser.add_argument("--language", choices=("en", "es"), default="en")
    parser.add_argument("--openfda-search", default="")
    parser.add_argument("--rxnorm-names", nargs="*", default=[])
    parser.add_argument("--rxcuis", nargs="*", default=[])
    parser.add_argument("--mesh-terms", nargs="*", default=[])
    parser.add_argument("--pubmed-query", default="")
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--allow-unverified-license", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.list_sources:
        for source in SOURCES.values():
            print(
                f"{source.source_id}: {source.title} | {source.raw_format} | "
                f"{source.access_note} | license: {source.license_note}"
            )
        return 0
    if args.process_only:
        print(json.dumps({"status": "processed", "counts": process_downloads()}, indent=2))
        return 0
    if not args.sources:
        parser.error("--sources is required unless --list-sources is used.")
    args.sources = [source.strip() for source in args.sources.split(",") if source.strip()]
    if "medlineplus" in args.sources and not (
        args.medlineplus_codes or args.medlineplus_condition_file
    ):
        parser.error(
            "Use --medlineplus-codes or --medlineplus-condition-file with MedlinePlus Connect."
        )
    if args.medlineplus_condition_file and args.medlineplus_codes:
        parser.error(
            "Use either --medlineplus-codes or --medlineplus-condition-file, not both."
        )
    if "openfda" in args.sources and not args.openfda_search:
        parser.error("--openfda-search is required for openFDA.")
    if "rxnorm" in args.sources and not (args.rxnorm_names or args.rxcuis):
        parser.error("Use --rxnorm-names and/or --rxcuis with RxNorm.")
    if "mesh" in args.sources and not args.mesh_terms:
        parser.error("--mesh-terms is required for MeSH.")
    if "pubmed" in args.sources and not args.pubmed_query:
        parser.error("--pubmed-query is required for PubMed.")
    if len(args.medlineplus_codes) > 500:
        parser.error("Limit MedlinePlus to 500 code lookups per run.")
    if len(args.rxnorm_names) > 100 or len(args.rxcuis) > 100:
        parser.error("Limit RxNorm to 100 drug names and 100 RxCUIs per run.")
    if len(args.mesh_terms) > 100:
        parser.error("Limit MeSH to 100 terms per run.")
    report = acquire(args)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 2 if report["source_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
