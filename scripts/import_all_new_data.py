"""Audit New folder and stage only source-explicit review candidates.

Run as ``python -m scripts.import_all_new_data`` from the repository root.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from scripts.medical_data.importers.audit import scan_tree
from scripts.medical_data.importers.disease_symptom import (
    convert_disease_symptom_tsv,
    write_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "New folder"
DOCS_DIR = ROOT / "docs" / "medical_data"
PROCESSED_DIR = ROOT / "data" / "medical_content" / "processed"
DISEASE_SYMPTOM_RELATIVE = Path(
    "HumanDiseaseOntology-2026-08-31",
    "HumanDiseaseOntology-2026-08-31",
    "DOreports",
    "requested",
    "disease-symptom.tsv",
)
DATE_STAMP = date.today().isoformat()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _write_inventory_csv(files: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    fields = (
        "path",
        "size_bytes",
        "extension",
        "detected_type",
        "category",
        "disposition",
        "records",
        "fields",
        "quality",
        "note",
    )
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for item in files:
                writer.writerow(
                    {
                        **item,
                        "fields": json.dumps(item["fields"], ensure_ascii=False),
                        "quality": json.dumps(item["quality"], ensure_ascii=False, sort_keys=True),
                    }
                )
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# New folder medical-data audit",
        "",
        f"Audit date: {DATE_STAMP}",
        f"Scanned root: `{report['root']}`",
        "",
        "## Inventory",
        "",
        f"- Directories: **{report['directory_count']}**",
        f"- Files: **{report['file_count']:,}**",
        f"- Total size: **{report['total_bytes']:,} bytes**",
        f"- Full per-file inventory: [`new_folder_inventory.csv`](new_folder_inventory.csv)",
        "",
        "### Detected formats",
        "",
        "| Format | Files |",
        "|---|---:|",
    ]
    lines.extend(f"| {kind} | {count:,} |" for kind, count in report["formats"].items())
    lines.extend(
        [
            "",
            "### File categories (counts are files, not records)",
            "",
            "| Category | Files |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {kind} | {count:,} |" for kind, count in report["categories"].items())
    lines.extend(
        [
            "",
            "### Directory tree",
            "",
        ]
    )
    lines.extend(f"- `{directory}/`" for directory in report["directories"])
    lines.extend(
        [
            "",
            "## Dataset findings",
            "",
            "| Source file / collection | Format | Records | Important fields | Quality / disposition |",
            "|---|---|---:|---|---|",
        ]
    )
    selected = [
        item
        for item in report["files"]
        if item["path"] == "dataset_"
        or item["path"].startswith("archive (")
        or "disease-symptom.tsv" in item["path"]
        or item["path"].endswith("src/ontology/doid.obo")
        or item["path"].endswith("MedQuAD-master/MedQuAD-master/LICENSE.txt")
        or item["path"].endswith("MedQuAD-master/MedQuAD-master/readme.txt")
    ]
    medquad = [
        item
        for item in report["files"]
        if item["path"].startswith("MedQuAD-master/MedQuAD-master/") and item["detected_type"] == "xml"
    ]
    if medquad:
        questions = sum(item["quality"].get("xml_elements", {}).get("Question", 0) for item in medquad)
        answers = sum(item["quality"].get("xml_elements", {}).get("Answer", 0) for item in medquad)
        nonempty_answers = sum(
            item["quality"].get("nonempty_answer_elements", 0) for item in medquad
        )
        categories = Counter(Path(item["path"]).parts[2] for item in medquad)
        lines.append(
            f"| MedQuAD XML corpus ({len(medquad):,} XML files; "
            f"{', '.join(f'{name}: {count:,}' for name, count in sorted(categories.items()))}) "
            f"| XML | {questions:,} question / {answers:,} answer elements; "
            f"{nonempty_answers:,} nonempty answers | "
            "Question, Answer, source/URL metadata | "
            "10 files have no question/answer elements; copyright exclusions apply to three subsets; "
            "rights review required |"
        )
        lines.extend(["", "MedQuAD QA elements by subset:", ""])
        lines.extend(
            [
                "| Subset | XML files | Question elements | Answer elements | Nonempty answers |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        subset_stats: dict[str, Counter[str]] = {}
        for item in medquad:
            subset = Path(item["path"]).parts[2]
            stats = subset_stats.setdefault(subset, Counter())
            stats["files"] += 1
            stats["questions"] += item["quality"].get("xml_elements", {}).get("Question", 0)
            stats["answers"] += item["quality"].get("xml_elements", {}).get("Answer", 0)
            stats["nonempty_answers"] += item["quality"].get("nonempty_answer_elements", 0)
        lines.extend(
            f"| {subset} | {stats['files']:,} | {stats['questions']:,} | "
            f"{stats['answers']:,} | {stats['nonempty_answers']:,} |"
            for subset, stats in sorted(subset_stats.items())
        )
    for item in selected:
        fields = ", ".join(item.get("fields", [])) or "—"
        if item["path"] == "dataset_":
            quality_text = "Synthetic benchmark per header; non-English labels; research-only"
        elif "combined_diseases_symptoms" in item["path"]:
            quality_text = "248,126 rows; 57,342 duplicate rows; every row has <think> reasoning; no evidence URLs"
        elif "healthcare_rag_dataset" in item["path"]:
            quality_text = "409 rows; 37 source URLs missing; mixed medical claims; source validation blocked"
        elif "disease-symptom.tsv" in item["path"]:
            quality_text = "Explicit DOID/SYMP associations; staged as unreviewed candidates only"
        elif "doid.obo" in item["path"]:
            quality_text = "CC0 source snapshot 2026-08-31; older than existing AURA source release"
        else:
            quality_text = item.get("note", "")
        lines.append(
            f"| `{item['path']}` | {item['detected_type']} | "
            f"{item.get('records') if item.get('records') is not None else 'n/a'} | "
            f"{fields.replace('|', '\\|')} | {quality_text} |"
        )
    lines.extend(
        [
            "",
            "## Import decision",
            "",
            "- **Staged candidate:** the 2,222-row Disease Ontology disease-to-SYMP table, "
            "retaining exact IDs and labels, as draft-only associations.",
            "- **Not promoted:** the 2026-08-31 ontology snapshot is older than the AURA "
            "2026-09-30 source already processed; no stale replacement was made.",
            "- **Quarantined from clinical catalogs:** the DDXPlus synthetic benchmark, "
            "mixed generated diagnosis/test CSV, and mixed RAG CSV.",
            "- **Not imported:** MedQuAD until rights are verified per source subset; its README "
            "states that MedlinePlus ADAM, drugs, and herbs/supplements answers were removed "
            "to respect copyright.",
            "- No data was added to live catalogs or made accessible to the API. Existing "
            "loader/service gates require clinically reviewed, published records.",
            "- No translation, medical fact completion, missing-value filling, or name-based "
            "linking was performed. Blank values remain reported as blanks.",
            "",
            "The first five rows of each CSV/TSV were inspected during the local audit. "
            "Verbatim row contents are intentionally not duplicated in this report. The "
            "inventory lists field names, row counts, and missing-value statistics.",
            "",
        ]
    )
    return "\n".join(lines)


def run_import(source_dir: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    source_dir = source_dir.resolve(strict=True)
    report = scan_tree(source_dir)
    table_path = source_dir / DISEASE_SYMPTOM_RELATIVE
    candidates, association_report = convert_disease_symptom_tsv(table_path)
    candidate_path = (
        PROCESSED_DIR / "symptoms" / "disease_symptom_association_candidates.json"
    )
    write_candidates(candidates, candidate_path)
    association_report["output_path"] = candidate_path.relative_to(ROOT).as_posix()
    report["integration"] = {
        "review_candidate": association_report,
        "automatically_promoted_records": 0,
        "live_catalog_modified": False,
        "api_exposure_modified": False,
        "other_sources_imported": [],
    }
    report["audit_date"] = DATE_STAMP

    inventory_path = DOCS_DIR / "new_folder_inventory.csv"
    markdown_path = DOCS_DIR / "NEW_FOLDER_AUDIT.md"
    report_path = PROCESSED_DIR / "import_report.json"
    report["report_paths"] = {
        "markdown": markdown_path.relative_to(ROOT).as_posix(),
        "inventory_csv": inventory_path.relative_to(ROOT).as_posix(),
        "json": report_path.relative_to(ROOT).as_posix(),
        "candidate_associations": candidate_path.relative_to(ROOT).as_posix(),
    }
    _write_inventory_csv(report["files"], inventory_path)
    _atomic_write(markdown_path, _markdown_report(report))
    _atomic_write(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit supplied datasets and stage only source-explicit draft candidates."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Directory to inventory (defaults to the repository's New folder).",
    )
    args = parser.parse_args(argv)
    report = run_import(args.source_dir)
    print(
        json.dumps(
            {
                "root": report["root"],
                "file_count": report["file_count"],
                "directory_count": report["directory_count"],
                "formats": report["formats"],
                "categories": report["categories"],
                "integration": report["integration"],
                "report_paths": report["report_paths"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
