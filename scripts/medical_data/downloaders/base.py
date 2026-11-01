"""Bounded HTTP and local-file acquisition with provenance and checksums."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.medical_data.config import SOURCES, SourceConfig


class DownloadError(RuntimeError):
    """A source request or provenance-safe file write failed."""


class BaseDownloader:
    MAX_RESPONSE_BYTES = 100 * 1024 * 1024

    def __init__(
        self,
        source_id: str,
        raw_root: Path,
        *,
        timeout: float = 30,
        retries: int = 3,
        user_agent: str = "AURA-Medical-Data-Acquisition/1.0 (research; contact project maintainer)",
    ) -> None:
        if source_id not in SOURCES:
            raise ValueError(f"Unknown medical data source: {source_id}")
        self.source: SourceConfig = SOURCES[source_id]
        self.raw_dir = raw_root / source_id
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent

    @staticmethod
    def _filename(value: str) -> str:
        basename = Path(value).name
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", basename).strip("._")
        if not safe or safe in {".", ".."}:
            raise ValueError("A safe non-empty output filename is required.")
        return safe[:180]

    @staticmethod
    def _safe_request_url(url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        sensitive_query_present = any(
            key.casefold() in {"sig", "signature", "jwt", "x-amz-signature"}
            for key, _ in query
        )
        if sensitive_query_present:
            return urllib.parse.urlunsplit(
                (parts.scheme, parts.netloc, parts.path, "", "")
            )
        safe_query = [
            (
                key,
                "[REDACTED]"
                if any(
                    secret in key.casefold()
                    for secret in ("key", "token", "secret", "signature")
                )
                else value,
            )
            for key, value in query
        ]
        return urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(safe_query), "")
        )

    def request_bytes(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str, str]:
        query = urllib.parse.urlencode(
            [(key, str(value)) for key, value in (params or {}).items() if value is not None],
            doseq=True,
        )
        request_url = f"{url}{'&' if '?' in url else '?'}{query}" if query else url
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        request = urllib.request.Request(request_url, headers=request_headers)
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read(self.MAX_RESPONSE_BYTES + 1)
                    if len(body) > self.MAX_RESPONSE_BYTES:
                        raise DownloadError(
                            f"Response from {self.source.source_id} exceeds the 100 MiB safety limit."
                        )
                    content_type = response.headers.get("Content-Type", "application/octet-stream")
                    return body, content_type, response.geturl()
            except urllib.error.HTTPError as exc:
                if exc.code not in (408, 425, 429, 500, 502, 503, 504) or attempt >= self.retries:
                    raise DownloadError(
                        f"{self.source.source_id} request failed with HTTP {exc.code}."
                    ) from exc
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(30, 2**attempt + random.random())
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt >= self.retries:
                    raise DownloadError(f"{self.source.source_id} request failed: {exc}") from exc
                delay = min(30, 2**attempt + random.random())
            time.sleep(delay)
        raise DownloadError(f"{self.source.source_id} request exhausted retries.")

    def request_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, str]:
        body, _, final_url = self.request_bytes(
            url, params=params, headers=headers
        )
        try:
            return json.loads(body.decode("utf-8-sig")), final_url
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise DownloadError(f"{self.source.source_id} returned invalid JSON.") from exc

    def save_raw(
        self,
        body: bytes,
        filename: str,
        *,
        request_url: str,
        final_url: str | None = None,
        content_type: str = "application/octet-stream",
        source_version: str | None = None,
        license_status: str = "review_required",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Path:
        output = self.raw_dir / self._filename(filename)
        temporary = output.with_name(output.name + ".part")
        digest = hashlib.sha256(body).hexdigest()
        try:
            temporary.write_bytes(body)
            os.replace(temporary, output)
            metadata = {
                "source_id": self.source.source_id,
                "source_title": self.source.title,
                "source_url": self.source.source_url,
                "request_url": self._safe_request_url(request_url),
                "final_url": self._safe_request_url(final_url or request_url),
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "source_version": source_version,
                "content_type": content_type,
                "byte_count": len(body),
                "sha256": digest,
                "license_note": self.source.license_note,
                "license_status": license_status,
                "access_note": self.source.access_note,
                **(extra_metadata or {}),
            }
            sidecar = output.with_suffix(output.suffix + ".metadata.json")
            sidecar.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise DownloadError(f"Cannot save source artifact: {output}") from exc
        return output

    def import_local_file(
        self,
        source_path: Path,
        filename: str,
        *,
        license_status: str,
        source_version: str | None = None,
    ) -> Path:
        if not source_path.is_file():
            raise FileNotFoundError(f"Source archive does not exist: {source_path}")
        if source_path.stat().st_size > 5 * 1024 * 1024 * 1024:
            raise DownloadError("Local source archive exceeds the 5 GiB import safety limit.")
        output = self.raw_dir / self._filename(filename)
        temporary = output.with_name(output.name + ".part")
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as source, temporary.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    target.write(chunk)
            os.replace(temporary, output)
            metadata = {
                "source_id": self.source.source_id,
                "source_title": self.source.title,
                "source_url": self.source.source_url,
                "request_url": self.source.source_url,
                "final_url": self.source.source_url,
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "source_version": source_version,
                "content_type": "application/zip" if filename.lower().endswith(".zip") else "application/octet-stream",
                "byte_count": output.stat().st_size,
                "sha256": digest.hexdigest(),
                "license_note": self.source.license_note,
                "license_status": license_status,
                "access_note": self.source.access_note,
                "imported_filename": source_path.name,
            }
            output.with_suffix(output.suffix + ".metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise DownloadError(f"Cannot import local source archive: {source_path}") from exc
        return output
