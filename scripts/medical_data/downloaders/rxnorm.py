"""RxNorm search and RxNav interaction lookups for explicit drug identifiers."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from urllib.parse import quote

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class RxNormDownloader(BaseDownloader):
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"

    def __init__(self, raw_root, **kwargs):
        super().__init__("rxnorm", raw_root, **kwargs)

    def search_drug(self, name: str) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("A drug name is required.")
        data, final_url = self.request_json(
            f"{self.BASE_URL}/drugs.json", params={"name": name.strip()}
        )
        self.save_raw(
            json.dumps(data, ensure_ascii=False).encode(),
            f"search_{hashlib.sha256(name.encode()).hexdigest()[:12]}.json",
            request_url=f"{self.BASE_URL}/drugs.json?name={quote(name.strip())}",
            final_url=final_url,
            content_type="application/json",
            license_status="rxnorm_terms_review_required",
            extra_metadata={"query": name.strip()},
        )
        return data

    def fetch_interactions(self, rxcui: str) -> dict[str, Any]:
        if not rxcui.isdigit():
            raise ValueError("RxCUI must contain digits only.")
        url = f"{self.BASE_URL}/interaction/interaction.json"
        try:
            data, final_url = self.request_json(url, params={"rxcui": rxcui})
        except DownloadError as exc:
            raise DownloadError(
                "RxNav drug-interaction lookup failed; no interaction data was created. "
                f"Upstream result: {exc}"
            ) from exc
        self.save_raw(
            json.dumps(data, ensure_ascii=False).encode(),
            f"interactions_{rxcui}.json",
            request_url=f"{url}?rxcui={rxcui}",
            final_url=final_url,
            content_type="application/json",
            license_status="rxnav_terms_review_required",
            extra_metadata={"rxcui": rxcui},
        )
        return data

    def fetch_all(self, rxcuis: list[str]) -> dict[str, dict[str, Any]]:
        results = {}
        for index, rxcui in enumerate(dict.fromkeys(rxcuis)):
            if index:
                time.sleep(0.3)
            results[rxcui] = self.fetch_interactions(rxcui)
        return results
