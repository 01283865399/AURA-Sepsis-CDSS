"""Convert source formats into draft records while retaining exact provenance."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _source_reference(source: str, title: str, url: str) -> dict[str, str]:
    return {"source": source, "title": title, "url": url}


def _obo_unquote(value: str) -> str:
    try:
        decoded = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value
    return decoded if isinstance(decoded, str) else value


def parse_obo(text: str, source_url: str) -> list[dict[str, Any]]:
    """Extract explicit DO content and source-native cross-references."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def finish() -> None:
        if current is None or not current.get("id", "").startswith("DOID:"):
            return
        term_id = current["id"]
        label = current.get("name", "")
        xrefs = current.get("xrefs", [])
        icd10cm_xrefs = [item for item in xrefs if item.casefold().startswith("icd10cm:")]
        icd10cm_codes = []
        for xref in icd10cm_xrefs:
            if ":" not in xref:
                continue
            code = xref.split(":", 1)[1].strip().strip('"')
            if code:
                icd10cm_codes.append(code)
        records.append(
            {
                "condition_id": term_id.casefold().replace(":", "_"),
                "condition_en": label,
                "ontology_id": term_id,
                "definition_source_text": current.get("def"),
                "synonyms_en": current.get("synonyms", []),
                "ontology_parents": current.get("parents", []),
                "external_xrefs": xrefs,
                "icd10cm_codes": icd10cm_codes,
                "is_obsolete": current.get("is_obsolete", False),
                "replaced_by": current.get("replaced_by"),
                "content_status": "draft",
                "review_status": "unreviewed",
                "references": [
                    _source_reference("Disease Ontology", f"Disease Ontology term {term_id}", source_url)
                ],
            }
        )

    for line in text.splitlines():
        if line == "[Term]":
            finish()
            current = {"synonyms": [], "xrefs": [], "parents": []}
            continue
        if line.startswith("["):
            finish()
            current = None
            continue
        if current is None or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key in {"id", "name", "def", "is_obsolete", "replaced_by"}:
            if key == "def":
                match = re.match(r'"((?:[^"\\]|\\.)*)"', value)
                if match:
                    current[key] = _obo_unquote(match.group(1))
            elif key == "is_obsolete":
                current[key] = value == "true"
            elif key == "replaced_by":
                current[key] = value.split(" ! ", 1)[0]
            else:
                current[key] = value
        elif key == "synonym":
            match = re.match(r'"((?:[^"\\]|\\.)*)"', value)
            if match:
                current["synonyms"].append(_obo_unquote(match.group(1)))
        elif key == "xref":
            xref = value.split(" ! ", 1)[0].strip()
            if xref:
                current["xrefs"].append(xref)
        elif key == "is_a":
            parent = value.split(" ! ", 1)[0].strip()
            if parent:
                current["parents"].append(parent)
    finish()
    return records


def parse_hpo(
    document: dict[str, Any],
    source_url: str,
    release_tag: str | None = None,
) -> list[dict[str, Any]]:
    """Extract HPO phenotype concepts, not clinical symptom assertions."""
    terms: list[dict[str, Any]] = []
    for graph in document.get("graphs", []):
        if not isinstance(graph, dict):
            continue
        for node in graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            term_id = node.get("id")
            label = node.get("lbl")
            if not isinstance(term_id, str) or not term_id.startswith("http"):
                continue
            if not isinstance(label, str) or not label.strip():
                continue
            meta = node.get("meta", {})
            definition = meta.get("definition", {}) if isinstance(meta, dict) else {}
            synonyms = meta.get("synonyms", []) if isinstance(meta, dict) else []
            xrefs = meta.get("xrefs", []) if isinstance(meta, dict) else []
            deprecated = bool(meta.get("deprecated")) if isinstance(meta, dict) else False
            phenotype_id = term_id.rsplit("/", 1)[-1]
            if phenotype_id.startswith("HP_"):
                phenotype_id = phenotype_id.replace("HP_", "HP:", 1)
            if not phenotype_id.startswith("HP:"):
                continue
            purl_id = phenotype_id.replace(":", "_", 1)
            release_url = (
                f"https://github.com/obophenotype/human-phenotype-ontology/releases/tag/{release_tag}"
                if release_tag
                else "https://hpo.jax.org/"
            )
            terms.append(
                {
                    "phenotype_id": phenotype_id,
                    "name_en": label,
                    "definition_source_text": definition.get("val") if isinstance(definition, dict) else None,
                    "source_url": f"https://purl.obolibrary.org/obo/{phenotype_id}",
                    "synonyms_en": [
                        synonym["val"]
                        for synonym in synonyms
                        if isinstance(synonym, dict) and isinstance(synonym.get("val"), str)
                    ],
                    "external_xrefs": [
                        xref["val"]
                        for xref in xrefs
                        if isinstance(xref, dict) and isinstance(xref.get("val"), str)
                    ],
                    "is_deprecated": deprecated,
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "references": [
                        _source_reference(
                            "Human Phenotype Ontology term",
                            label,
                            f"https://purl.obolibrary.org/obo/{purl_id}",
                        ),
                        _source_reference(
                            "Human Phenotype Ontology source artifact",
                            release_tag or "HPO source artifact",
                            source_url,
                        ),
                        _source_reference(
                            "Human Phenotype Ontology release",
                            release_tag or "HPO",
                            release_url,
                        ),
                    ],
                }
            )
    return terms


def parse_medlineplus(document: dict[str, Any], request_url: str) -> list[dict[str, Any]]:
    """Keep Connect entry payloads source-shaped and explicitly non-published."""
    feed = document.get("feed", {})
    entries = feed.get("entry", []) if isinstance(feed, dict) else []
    if isinstance(entries, dict):
        entries = [entries]
    return [
        {
            "source_record_id": entry.get("id"),
            "title_source_text": entry.get("title"),
            "summary_source_text": entry.get("summary"),
            "source_url": entry.get("link"),
            "query_url": request_url,
            "content_status": "draft",
            "review_status": "unreviewed",
            "references": [
                _source_reference(
                    "MedlinePlus Connect",
                    str(entry.get("title", "MedlinePlus result")),
                    str(entry.get("link", request_url)),
                )
            ],
        }
        for entry in entries
        if isinstance(entry, dict)
    ]


def parse_pubmed_xml(xml_body: bytes, source_url: str) -> list[dict[str, Any]]:
    """Extract citation metadata only; article text remains subject to item rights."""
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml_body)
    citations = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")
        title_node = article.find(".//ArticleTitle")
        title = "".join(title_node.itertext()) if title_node is not None else None
        if not pmid or not title:
            continue
        citations.append(
            {
                "citation_id": f"PMID:{pmid}",
                "source": "PubMed",
                "title": title,
                "pmid": pmid,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "content_status": "draft",
                "review_status": "unreviewed",
                "references": [_source_reference("PubMed", title, source_url)],
            }
        )
    return citations


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value
