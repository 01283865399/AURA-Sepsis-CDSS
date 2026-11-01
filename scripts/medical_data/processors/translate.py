"""Translation boundary: no machine-generated translations are published."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def translate_record(
    record: dict[str, Any], *, target_language: str = "ar", enabled: bool = False
) -> dict[str, Any]:
    """Preserve original content; translation requires a separate reviewed workflow."""
    if target_language not in {"ar", "en"}:
        raise ValueError("Only Arabic and English are supported target language codes.")
    result: dict[str, Any] = deepcopy(record)
    result["translation_status"] = "not_requested" if not enabled else "requires_human_review"
    if enabled:
        result["translation_blocked_reason"] = (
            "No translation provider is configured. Source text must not be "
            "represented as a verified translation."
        )
    return result
