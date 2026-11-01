"""MedQuAD rights-gated GitHub archive downloader."""

from __future__ import annotations

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class MedQuADDownloader(BaseDownloader):
    REPOSITORY_API = "https://api.github.com/repos/abachaa/MedQuAD"

    def __init__(self, raw_root, **kwargs):
        super().__init__("medquad", raw_root, **kwargs)

    def fetch_all(self, *, allow_unverified_license: bool = False) -> dict:
        repository, repository_url = self.request_json(self.REPOSITORY_API)
        license_data = repository.get("license") or {}
        spdx = license_data.get("spdx_id", "NOASSERTION")
        if spdx in {"NOASSERTION", "NONE"} and not allow_unverified_license:
            raise PermissionError(
                "MedQuAD repository license is unresolved (GitHub reports NOASSERTION). "
                "Obtain rights confirmation before downloading or using the dataset."
            )
        branch = repository.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise DownloadError("MedQuAD repository metadata has no default branch.")
        archive_url = f"https://api.github.com/repos/abachaa/MedQuAD/zipball/{branch}"
        body, content_type, final_url = self.request_bytes(
            archive_url, headers={"Accept": "application/vnd.github+json"}
        )
        output = self.save_raw(
            body,
            f"MedQuAD-{branch}.zip",
            request_url=archive_url,
            final_url=final_url,
            content_type=content_type,
            source_version=branch,
            license_status="unverified_rights_review_copy" if spdx in {"NOASSERTION", "NONE"} else f"repo_license_{spdx}",
            extra_metadata={"repository_api_url": repository_url, "repository_license_spdx": spdx},
        )
        return {
            "branch": branch,
            "license_spdx": spdx,
            "path": str(output),
            "integrable": spdx not in {"NOASSERTION", "NONE"},
        }
