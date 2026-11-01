"""Bounded openFDA label search downloader."""

from __future__ import annotations

import os
import hashlib
import json
import time
from typing import Any
from urllib.parse import urlencode

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class OpenFDADownloader(BaseDownloader):
    BASE_URL = "https://api.fda.gov/drug/label.json"

    def __init__(self, raw_root, **kwargs):
        super().__init__("openfda", raw_root, **kwargs)

    def fetch_all(self, search: str, max_results: int = 100) -> list[dict[str, Any]]:
        if not search or not search.strip():
            raise ValueError("A bounded explicit openFDA search expression is required.")
        if not 1 <= max_results <= 25_000:
            raise ValueError("max_results must be between 1 and 25000.")
        api_key = os.environ.get("OPENFDA_API_KEY")
        results: list[dict[str, Any]] = []
        offset = 0
        while offset < max_results:
            limit = min(1000, max_results - offset)
            params = {"search": search.strip(), "limit": limit, "skip": offset}
            if api_key:
                params["api_key"] = api_key
            try:
                page, final_url = self.request_json(self.BASE_URL, params=params)
            except DownloadError as exc:
                if "HTTP 404" in str(exc) and not results:
                    return []
                raise
            page_records = page.get("results", [])
            if not isinstance(page_records, list):
                raise DownloadError("openFDA response has no results array.")
            encoded = json.dumps(page, ensure_ascii=False).encode("utf-8")
            query_id = hashlib.sha256(search.strip().encode()).hexdigest()[:12]
            self.save_raw(
                encoded,
                f"{query_id}_offset_{offset}.json",
                request_url=f"{self.BASE_URL}?{urlencode({key: value for key, value in params.items() if key != 'api_key'})}",
                final_url=final_url,
                content_type="application/json",
                license_status="openfda_terms_review_required",
                extra_metadata={"search": search.strip(), "offset": offset, "page_size": len(page_records)},
            )
            results.extend(item for item in page_records if isinstance(item, dict))
            if len(page_records) < limit:
                break
            offset += len(page_records)
            time.sleep(0.25)
        return results[:max_results]
