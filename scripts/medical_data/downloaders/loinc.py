"""Import a locally downloaded LOINC archive under its governing license."""

from __future__ import annotations

import os
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class LOINCDownloader(BaseDownloader):
    def __init__(self, raw_root, **kwargs):
        super().__init__("loinc", raw_root, **kwargs)

    def fetch_all(self, source_path: Path | None = None) -> Path:
        configured = source_path or (
            Path(os.environ["AURA_LOINC_ARCHIVE"])
            if os.environ.get("AURA_LOINC_ARCHIVE")
            else None
        )
        if configured is None:
            raise RuntimeError(
                "LOINC download requires a licensed archive obtained from loinc.org. "
                "Set AURA_LOINC_ARCHIVE; credentials are not collected by this tool."
            )
        try:
            with ZipFile(configured) as archive:
                if archive.testzip() is not None:
                    raise DownloadError("LOINC archive contains a corrupt member.")
                if not any(name.lower().endswith((".csv", ".txt")) for name in archive.namelist()):
                    raise DownloadError("LOINC archive does not contain expected table files.")
        except BadZipFile as exc:
            raise DownloadError("Configured LOINC file is not a valid ZIP archive.") from exc
        return self.import_local_file(
            configured,
            configured.name,
            license_status="licensed_user_file_terms_must_be_verified",
        )
