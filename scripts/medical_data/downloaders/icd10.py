"""Import a user-obtained WHO ICD-10 file without bypassing its license."""

from __future__ import annotations

import os
from pathlib import Path

from scripts.medical_data.downloaders.base import BaseDownloader


class ICD10Downloader(BaseDownloader):
    """WHO ICD-10 has no unauthenticated bulk endpoint assumed by this tool."""

    def __init__(self, raw_root, **kwargs):
        super().__init__("icd10", raw_root, **kwargs)

    def fetch_all(self, source_path: Path | None = None) -> Path:
        configured = source_path or (
            Path(os.environ["AURA_WHO_ICD10_FILE"])
            if os.environ.get("AURA_WHO_ICD10_FILE")
            else None
        )
        if configured is None:
            raise RuntimeError(
                "WHO ICD-10 is not downloaded automatically. Obtain the official export "
                "under applicable WHO terms, set AURA_WHO_ICD10_FILE, then retry."
            )
        return self.import_local_file(
            configured,
            configured.name,
            license_status="user_supplied_terms_must_be_verified",
        )
