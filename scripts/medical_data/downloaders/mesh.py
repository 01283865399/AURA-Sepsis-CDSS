"""Targeted NLM MeSH descriptor lookup."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlencode

from scripts.medical_data.downloaders.base import BaseDownloader


class MeSHDownloader(BaseDownloader):
    BASE_URL = "https://id.nlm.nih.gov/mesh/lookup/descriptor"

    def __init__(self, raw_root, **kwargs):
        super().__init__("mesh", raw_root, **kwargs)

    def fetch_descriptor(self, term: str, limit: int = 10) -> list[dict[str, Any]]:
        if not term.strip():
            raise ValueError("A MeSH descriptor term is required.")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        data, final_url = self.request_json(
            self.BASE_URL,
            params={"label": term.strip(), "match": "exact", "limit": limit},
            headers={"Accept": "application/json"},
        )
        if not isinstance(data, list):
            raise ValueError("MeSH lookup did not return a descriptor array.")
        self.save_raw(
            json.dumps(data, ensure_ascii=False).encode(),
            f"descriptor_{hashlib.sha256(term.encode()).hexdigest()[:12]}.json",
            request_url=f"{self.BASE_URL}?{urlencode({'label': term.strip(), 'match': 'exact', 'limit': limit})}",
            final_url=final_url,
            content_type="application/json",
            license_status="nlm_terms_review_required",
            extra_metadata={"query": term.strip()},
        )
        return data

    def fetch_all(self, terms: list[str]) -> dict[str, list[dict[str, Any]]]:
        return {term: self.fetch_descriptor(term) for term in terms}
