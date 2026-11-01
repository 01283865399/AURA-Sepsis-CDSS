"""Import licensed SNOMED CT RF2 archives without exposing them to public API."""

from __future__ import annotations

import os
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class SNOMEDDownloader(BaseDownloader):
    def __init__(self, raw_root, **kwargs):
        super().__init__("snomed", raw_root, **kwargs)

    def fetch_all(self, source_path: Path | None = None) -> Path:
        configured = source_path or (
            Path(os.environ["AURA_SNOMED_RF2_FILE"])
            if os.environ.get("AURA_SNOMED_RF2_FILE")
            else None
        )
        if configured is None:
            raise RuntimeError(
                "SNOMED CT is an optional licensed source. Obtain an authorized RF2 "
                "release and set AURA_SNOMED_RF2_FILE."
            )
        try:
            with ZipFile(configured) as archive:
                names = archive.namelist()
                if archive.testzip() is not None:
                    raise DownloadError("SNOMED archive contains a corrupt member.")
                if not any(name.endswith("sct2_Description_Full-en.txt") for name in names):
                    raise DownloadError("SNOMED archive is missing the expected RF2 Description file.")
        except BadZipFile as exc:
            raise DownloadError("Configured SNOMED file is not a valid ZIP archive.") from exc
        return self.import_local_file(
            configured,
            configured.name,
            license_status="licensed_user_file_terms_must_be_verified",
        )
