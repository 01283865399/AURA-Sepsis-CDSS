"""Bounded NCBI E-utilities citation and abstract downloader."""

from __future__ import annotations

import os
import hashlib
import json
import time
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class PubMedDownloader(BaseDownloader):
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, raw_root, **kwargs):
        super().__init__("pubmed", raw_root, **kwargs)

    def fetch_all(
        self,
        query: str,
        *,
        max_results: int = 100,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("An explicit PubMed query is required.")
        if not 1 <= max_results <= 5000:
            raise ValueError("max_results must be between 1 and 5000.")
        if not 1 <= batch_size <= 200:
            raise ValueError("batch_size must be between 1 and 200.")
        common = {
            "tool": "aura_medical_data_pipeline",
            "email": os.environ.get("NCBI_EMAIL"),
            "api_key": os.environ.get("NCBI_API_KEY"),
        }
        search_params = {
            **common,
            "db": "pubmed",
            "term": query.strip(),
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance",
        }
        search_params = {key: value for key, value in search_params.items() if value is not None}
        search_url = f"{self.BASE_URL}/esearch.fcgi"
        search_data, search_final_url = self.request_json(search_url, params=search_params)
        search_result = search_data.get("esearchresult", {})
        ids = search_result.get("idlist", [])
        if not isinstance(ids, list):
            raise DownloadError("PubMed ESearch returned an invalid id list.")
        ids = [str(item) for item in ids[:max_results]]
        self.save_raw(
            json.dumps(search_data, ensure_ascii=False).encode(),
            f"search_{hashlib.sha256(query.encode()).hexdigest()[:12]}.json",
            request_url=f"{search_url}?{urlencode({key: value for key, value in search_params.items() if key not in {'api_key', 'email'}})}",
            final_url=search_final_url,
            content_type="application/json",
            license_status="citation_metadata_item_rights_review_required",
            extra_metadata={"query": query.strip(), "record_count": len(ids)},
        )
        fetched: list[bytes] = []
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            params = {
                **common,
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract",
            }
            params = {key: value for key, value in params.items() if value is not None}
            url = f"{self.BASE_URL}/efetch.fcgi"
            body, content_type, final_url = self.request_bytes(url, params=params)
            try:
                ElementTree.fromstring(body)
            except ElementTree.ParseError as exc:
                raise DownloadError("PubMed EFetch returned invalid XML.") from exc
            self.save_raw(
                body,
                f"abstracts_{start}_{start + len(batch) - 1}.xml",
                request_url=f"{url}?{urlencode({**{key: value for key, value in params.items() if key not in {'api_key', 'email'}}, 'id_count': len(batch)})}",
                final_url=final_url,
                content_type=content_type,
                license_status="abstract_full_text_rights_review_required",
                extra_metadata={"pmids": batch},
            )
            fetched.append(body)
            time.sleep(0.11 if common.get("api_key") else 0.34)
        return {"query": query.strip(), "pmids": ids, "batch_count": len(fetched)}
