"""Fetch the current public Disease Ontology release from its project repo."""

from __future__ import annotations

import hashlib

from scripts.medical_data.downloaders.base import BaseDownloader


class DiseaseOntologyDownloader(BaseDownloader):
    RELEASE_API = "https://api.github.com/repos/DiseaseOntology/HumanDiseaseOntology/releases/latest"

    def __init__(self, raw_root, **kwargs):
        super().__init__("disease_ontology", raw_root, **kwargs)

    def fetch_all(self) -> dict:
        release, release_url = self.request_json(self.RELEASE_API)
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag:
            raise ValueError("Disease Ontology release API returned no release tag.")
        asset_url = (
            f"https://raw.githubusercontent.com/DiseaseOntology/"
            f"HumanDiseaseOntology/{tag}/src/ontology/doid.obo"
        )
        body, content_type, final_url = self.request_bytes(asset_url)
        if not body.startswith(b"format-version:"):
            raise ValueError("Disease Ontology download is not a valid OBO document.")
        output = self.save_raw(
            body,
            f"doid-{tag}.obo",
            request_url=asset_url,
            final_url=final_url,
            content_type=content_type,
            source_version=tag,
            license_status="release_terms_review_required",
            extra_metadata={"release_api_url": release_url, "release_published_at": release.get("published_at")},
        )
        return {"release": tag, "path": str(output), "sha256": hashlib.sha256(body).hexdigest()}
