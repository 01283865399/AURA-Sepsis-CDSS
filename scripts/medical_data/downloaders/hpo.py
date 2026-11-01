"""Fetch the current Human Phenotype Ontology release asset."""

from __future__ import annotations

import json

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class HPODownloader(BaseDownloader):
    RELEASE_API = "https://api.github.com/repos/obophenotype/human-phenotype-ontology/releases/latest"

    def __init__(self, raw_root, **kwargs):
        super().__init__("hpo", raw_root, **kwargs)

    def fetch_all(self) -> dict:
        release, release_url = self.request_json(self.RELEASE_API)
        tag = release.get("tag_name")
        assets = release.get("assets", [])
        asset = next(
            (
                item for item in assets
                if item.get("name") in {"hp-base.json", "hp.json"}
            ),
            None,
        )
        if not tag or not asset or not asset.get("browser_download_url"):
            raise DownloadError("HPO release does not expose a supported hp-base.json or hp.json asset.")
        asset_url = asset["browser_download_url"]
        body, content_type, final_url = self.request_bytes(asset_url)
        try:
            document = json.loads(body.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise DownloadError("HPO release asset is not valid UTF-8 JSON.") from exc
        if not isinstance(document, dict) or not isinstance(document.get("graphs"), list):
            raise DownloadError("HPO release asset is not a recognized JSON ontology.")
        output = self.save_raw(
            body,
            f"hp-{tag}.json",
            request_url=asset_url,
            final_url=final_url,
            content_type=content_type,
            source_version=tag,
            license_status="release_terms_review_required",
            extra_metadata={"release_api_url": release_url},
        )
        return {"release": tag, "path": str(output), "term_graph_count": len(document["graphs"])}
