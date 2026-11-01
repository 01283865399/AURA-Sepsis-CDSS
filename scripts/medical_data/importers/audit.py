"""Inventory supplied datasets without promoting unreviewed facts."""

from __future__ import annotations

import csv
import gzip
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".rq", ".yml", ".yaml", ".mk", ".properties",
    ".gitignore", ".obo", ".tsv", ".csv", ".arff",
}
TABULAR_EXTENSIONS = {".csv", ".tsv"}
JSON_RECORD_KEYS = ("records", "items", "data", "nodes", "terms", "conditions", "symptoms")
EMPTY_MARKERS = {"", "na", "n/a", "null", "none", "nan"}


def classify_path(relative_path: str) -> dict[str, str]:
    """Assign a domain category and a conservative ingestion disposition."""
    path = relative_path.replace("\\", "/")
    lower = path.casefold()
    if "/medquad-master/" in f"/{lower}/":
        return {
            "category": "qa",
            "disposition": "rights_review_required",
            "note": (
                "MedQuAD carries a CC BY 4.0 file, but its own README excludes "
                "answers in the three MedlinePlus subsets for copyright reasons."
            ),
        }
    if "humandiseaseontology" in lower:
        if "disease-symptom.tsv" in lower:
            return {
                "category": "symptoms",
                "disposition": "review_candidate",
                "note": "Exact Disease Ontology disease-to-SYMP association table; older duplicate release.",
            }
        if "icd10" in lower or lower.endswith(".obo") or lower.endswith(".owl") or lower.endswith(".json"):
            return {
                "category": "conditions",
                "disposition": "duplicate_source_not_imported",
                "note": "Disease Ontology snapshot is older than the release already processed by AURA.",
            }
        return {
            "category": "other",
            "disposition": "source_repository_only",
            "note": "Repository build, report, translation, or documentation artifact; not a live catalog.",
        }
    if "archive (1)/combined_diseases_symptoms_2_enriched_with_exams_v2.csv" in lower:
        return {
            "category": "other",
            "disposition": "clinical_validation_blocked",
            "note": (
                "Mixed diagnosis/test recommendations include generated <think> reasoning, "
                "no record-level evidence links, and duplicate rows."
            ),
        }
    if "archive (2)/healthcare_rag_dataset.csv" in lower:
        return {
            "category": "other",
            "disposition": "source_validation_blocked",
            "note": (
                "Mixed FAQ/guideline summaries make clinical claims; row-level evidence "
                "and source URL completeness have not been verified."
            ),
        }
    if Path(path).name == "dataset_":
        return {
            "category": "other",
            "disposition": "research_only",
            "note": "DDXPlus-format synthetic differential-diagnosis benchmark; not clinical reference content.",
        }
    return {
        "category": "other",
        "disposition": "not_medical_catalog_content",
        "note": "Repository or auxiliary artifact; retain as source material only.",
    }


def _sniff_type(path: Path, prefix: bytes) -> str:
    suffix = path.suffix.casefold()
    if prefix.startswith(b"PAR1"):
        return "parquet"
    if prefix.startswith(b"PK\x03\x04"):
        return "zip"
    if prefix.startswith(b"\x1f\x8b"):
        return "gzip"
    if prefix.startswith(b"%PDF-"):
        return "pdf"
    if prefix.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM")):
        return "image"
    if suffix in {".owl", ".xml"} or prefix.lstrip().startswith(b"<?xml"):
        return "xml"
    if suffix == ".obo":
        return "obo"
    if suffix in TABULAR_EXTENSIONS:
        return "csv" if suffix == ".csv" else "tsv"
    if suffix == ".arff" or path.name == "dataset_":
        return "arff"
    if suffix == ".json":
        return "json"
    if suffix == ".gz":
        return "gzip"
    if suffix in TEXT_EXTENSIONS or not suffix:
        return "text"
    return "binary_or_unknown"


def _json_shape(document: Any) -> tuple[int | None, list[str]]:
    if isinstance(document, list):
        return len(document), ["root:list"]
    if not isinstance(document, dict):
        return None, [f"root:{type(document).__name__}"]
    keys = list(document.keys())[:40]
    for key in JSON_RECORD_KEYS:
        value = document.get(key)
        if isinstance(value, list):
            return len(value), keys
        if isinstance(value, dict):
            for child_key in ("nodes", "terms", "records", "items"):
                child = value.get(child_key)
                if isinstance(child, list):
                    return len(child), keys + [f"{key}.{child_key}"]
    graphs = document.get("graphs")
    if isinstance(graphs, list):
        return sum(len(graph.get("nodes", [])) for graph in graphs if isinstance(graph, dict)), keys
    return None, keys


def _json_collection(document: Any) -> list[Any] | None:
    if isinstance(document, list):
        return document
    if not isinstance(document, dict):
        return None
    for key in JSON_RECORD_KEYS:
        value = document.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for child_key in ("nodes", "terms", "records", "items"):
                child = value.get(child_key)
                if isinstance(child, list):
                    return child
    graphs = document.get("graphs")
    if isinstance(graphs, list):
        return [
            node
            for graph in graphs
            if isinstance(graph, dict)
            for node in graph.get("nodes", [])
        ]
    return None


def _json_quality(document: Any) -> dict[str, Any]:
    quality: dict[str, Any] = {"json_root_type": type(document).__name__}
    collection = _json_collection(document)
    if collection is None:
        return quality
    present: Counter[str] = Counter()
    explicit_empty: Counter[str] = Counter()
    identifiers: dict[str, Counter[str]] = {}
    candidate_identifier_keys = (
        "id", "@id", "condition_id", "symptom_id", "phenotype_id", "doid", "rxcui"
    )
    object_count = 0
    for item in collection:
        if not isinstance(item, dict):
            continue
        object_count += 1
        for key, value in item.items():
            present[key] += 1
            if value is None or (isinstance(value, str) and value.strip().casefold() in EMPTY_MARKERS):
                explicit_empty[key] += 1
        for key in candidate_identifier_keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                identifiers.setdefault(key, Counter())[value] += 1
                break
    quality["object_record_count"] = object_count
    quality["missing_values_in_object_records"] = {
        key: object_count - present[key] + explicit_empty[key]
        for key in present
        if object_count - present[key] + explicit_empty[key]
    }
    quality["object_records_without_identifier"] = sum(
        1
        for item in collection
        if isinstance(item, dict)
        and not any(
            isinstance(item.get(key), str) and item[key].strip()
            for key in candidate_identifier_keys
        )
    )
    quality["duplicate_candidate_identifiers"] = {
        key: sum(count - 1 for count in values.values() if count > 1)
        for key, values in identifiers.items()
        if any(count > 1 for count in values.values())
    }
    return quality


def _scan_tabular(path: Path, detected_type: str) -> dict[str, Any]:
    delimiter = "\t" if detected_type == "tsv" else ","
    missing: Counter[str] = Counter()
    row_widths: Counter[str] = Counter()
    duplicates: set[tuple[str, ...]] = set()
    duplicate_rows = 0
    replacement_chars = 0
    count = 0
    headers: list[str] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.reader(stream, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            return {"records": 0, "fields": [], "missing": {}, "row_widths": {}, "duplicate_rows": 0}
        for row in reader:
            count += 1
            row_widths[str(len(row))] += 1
            for index, name in enumerate(headers):
                if index >= len(row) or row[index].strip().casefold() in EMPTY_MARKERS:
                    missing[name] += 1
                if index < len(row):
                    replacement_chars += row[index].count("\ufffd")
            identity = tuple(cell.strip() for cell in row)
            if identity in duplicates:
                duplicate_rows += 1
            else:
                duplicates.add(identity)
    return {
        "records": count,
        "fields": headers,
        "missing_values": dict(missing),
        "row_widths": dict(row_widths),
        "duplicate_rows": duplicate_rows,
        "utf8_replacement_characters": replacement_chars,
    }


def _scan_xml(path: Path) -> dict[str, Any]:
    tags: Counter[str] = Counter()
    nonempty: Counter[str] = Counter()
    captures: list[dict[str, int | str]] = []
    parse_error = None
    try:
        for event, element in ElementTree.iterparse(path, events=("start", "end")):
            tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else str(element.tag)
            if event == "start":
                if tag in {"Question", "Answer"}:
                    captures.append({"tag": tag, "text_length": 0})
                continue
            if tag in {"Document", "Question", "Answer", "Disease", "doc"}:
                tags[tag] += 1
            text_length = len((element.text or "").strip()) + len((element.tail or "").strip())
            for capture in captures:
                capture["text_length"] = int(capture["text_length"]) + text_length
            if tag in {"Question", "Answer"}:
                capture_index = next(
                    (index for index in range(len(captures) - 1, -1, -1) if captures[index]["tag"] == tag),
                    None,
                )
                if capture_index is not None:
                    capture = captures.pop(capture_index)
                    if int(capture["text_length"]) > 0:
                        nonempty[tag] += 1
            element.clear()
    except (ElementTree.ParseError, OSError) as exc:
        parse_error = type(exc).__name__
    record_count = tags.get("Question") or tags.get("Document") or tags.get("Disease") or tags.get("doc")
    return {
        "records": record_count,
        "xml_elements": dict(tags),
        "nonempty_question_elements": nonempty.get("Question", 0),
        "nonempty_answer_elements": nonempty.get("Answer", 0),
        "parse_error": parse_error,
        "missing_answers": max(0, tags.get("Question", 0) - tags.get("Answer", 0)),
        "empty_answers": max(0, tags.get("Answer", 0) - nonempty.get("Answer", 0)),
    }


def _scan_arff(path: Path) -> dict[str, Any]:
    attributes: list[str] = []
    records = 0
    width_counts: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    parse_errors = 0
    replacement_chars = 0
    data_section = False
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        for line in stream:
            stripped = line.strip()
            if not data_section:
                if stripped.casefold().startswith("@attribute "):
                    match = re.match(r"@attribute\s+('(?:[^']|'')*'|\S+)", stripped, re.IGNORECASE)
                    if match:
                        attributes.append(match.group(1).strip("'"))
                elif stripped.casefold() == "@data":
                    data_section = True
                continue
            if not stripped or stripped.startswith("%"):
                continue
            records += 1
            replacement_chars += line.count("\ufffd")
            try:
                row = next(csv.reader([line], delimiter=",", quotechar="'", escapechar="\\"))
                width_counts[str(len(row))] += 1
                for index, value in enumerate(row):
                    if not value.strip() or value.strip() == "?":
                        field = attributes[index] if index < len(attributes) else f"column_{index + 1}"
                        missing[field] += 1
            except csv.Error:
                width_counts["parse_error"] += 1
                parse_errors += 1
    return {
        "records": records,
        "fields": attributes,
        "row_widths": dict(width_counts),
        "missing_values": dict(missing),
        "parse_errors": parse_errors,
        "utf8_replacement_characters": replacement_chars,
        "notes": ["Physical ARFF rows counted; values are not interpreted as clinical facts."],
    }


def _scan_obo(path: Path) -> dict[str, Any]:
    terms = 0
    active = 0
    labelled = 0
    in_term = False
    has_name = False
    obsolete = False

    def finish() -> None:
        nonlocal active, labelled
        if in_term and not obsolete:
            active += 1
            if has_name:
                labelled += 1

    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if line.strip() == "[Term]":
                finish()
                terms += 1
                in_term = True
                has_name = False
                obsolete = False
            elif line.startswith("[") and line.strip() != "[Term]":
                finish()
                in_term = False
            elif in_term and line.startswith("name: "):
                has_name = bool(line[6:].strip())
            elif in_term and line.strip() == "is_obsolete: true":
                obsolete = True
    finish()
    return {"records": terms, "active_named_terms": labelled, "active_terms": active}


def _scan_file(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    classification = classify_path(relative)
    with path.open("rb") as stream:
        prefix = stream.read(16)
    detected_type = _sniff_type(path, prefix)
    info: dict[str, Any] = {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "extension": path.suffix or "(none)",
        "detected_type": detected_type,
        **classification,
        "records": None,
        "fields": [],
        "quality": {},
    }
    if detected_type in {"csv", "tsv"}:
        stats = _scan_tabular(path, detected_type)
        info.update(records=stats.pop("records"), fields=stats.pop("fields"), quality=stats)
    elif detected_type == "json":
        try:
            with path.open("r", encoding="utf-8-sig") as stream:
                document = json.load(stream)
            records, keys = _json_shape(document)
            info.update(records=records, fields=keys, quality=_json_quality(document))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            info["quality"] = {"parse_error": type(exc).__name__}
    elif detected_type == "xml":
        info["quality"] = _scan_xml(path)
        info["records"] = info["quality"]["records"]
    elif detected_type == "obo":
        info["quality"] = _scan_obo(path)
        info["records"] = info["quality"]["records"]
    elif detected_type == "arff":
        info["quality"] = _scan_arff(path)
        info["records"] = info["quality"]["records"]
        info["fields"] = info["quality"]["fields"]
    elif detected_type == "zip":
        try:
            with zipfile.ZipFile(path) as archive:
                info["quality"] = {"archive_entries": len(archive.infolist())}
        except (OSError, zipfile.BadZipFile):
            info["quality"] = {"parse_error": "BadZipFile"}
    elif detected_type == "gzip":
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as stream:
                header = stream.readline().rstrip("\r\n")
            info["quality"] = {"compressed_text_header": header[:160]}
        except (OSError, EOFError):
            info["quality"] = {"parse_error": "gzip_read_error"}
    elif detected_type == "text":
        try:
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                lines = 0
                replacement_chars = 0
                for line in stream:
                    lines += 1
                    replacement_chars += line.count("\ufffd")
            info["records"] = lines
            info["quality"] = {
                "line_count": lines,
                "utf8_replacement_characters": replacement_chars,
            }
        except OSError as exc:
            info["quality"] = {"read_error": type(exc).__name__}
    return info


def scan_tree(root: Path) -> dict[str, Any]:
    """Scan all regular files and report structure, formats, and safe metadata."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    directories = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    )
    files = sorted(
        (_scan_file(path, root) for path in root.rglob("*") if path.is_file()),
        key=lambda item: item["path"].casefold(),
    )
    totals: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    dispositions: Counter[str] = Counter()
    for item in files:
        totals["files"] += 1
        totals["bytes"] += item["size_bytes"]
        formats[item["detected_type"]] += 1
        categories[item["category"]] += 1
        dispositions[item["disposition"]] += 1
    return {
        "root": str(root),
        "directory_count": len(directories),
        "directories": directories,
        "file_count": len(files),
        "total_bytes": totals["bytes"],
        "formats": dict(sorted(formats.items())),
        "categories": dict(sorted(categories.items())),
        "dispositions": dict(sorted(dispositions.items())),
        "files": files,
    }
