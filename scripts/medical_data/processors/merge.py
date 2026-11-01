"""Merge only records sharing an exact, source-provided identifier."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


IDENTIFIER_KEYS = (
    "condition_id", "symptom_id", "drug_id", "test_id", "citation_id", "id"
)


def source_identifier(record: dict[str, Any]) -> tuple[str, str] | None:
    for key in IDENTIFIER_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return key, value.strip()
    return None


def merge_exact(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine duplicate exact identifiers; never merge on labels or similarity."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    unkeyed: list[dict[str, Any]] = []
    for record in records:
        identifier = source_identifier(record)
        if identifier is None:
            unkeyed.append(deepcopy(record))
            continue
        existing = merged.get(identifier)
        if existing is None:
            merged[identifier] = deepcopy(record)
            continue
        for key, value in record.items():
            if key == "sources":
                current = existing.setdefault("sources", [])
                current.extend(item for item in value if item not in current)
            elif key not in existing or existing[key] in (None, "", []):
                existing[key] = deepcopy(value)
            elif existing[key] != value:
                conflicts = existing.setdefault("_source_conflicts", {})
                variants = conflicts.setdefault(key, [deepcopy(existing[key])])
                if value not in variants:
                    variants.append(deepcopy(value))
    return [*merged.values(), *unkeyed]
