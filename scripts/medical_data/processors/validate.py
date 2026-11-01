"""Validate acquisition provenance and prevent raw imports becoming published."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def validate_raw_tree(raw_root: Path) -> list[str]:
    errors: list[str] = []
    for artifact in sorted(raw_root.rglob("*")):
        if (
            not artifact.is_file()
            or artifact.name == ".gitkeep"
            or artifact.name.endswith(".metadata.json")
            or artifact.suffix == ".part"
        ):
            continue
        sidecar = artifact.with_suffix(artifact.suffix + ".metadata.json")
        if not sidecar.is_file():
            errors.append(f"{artifact}: provenance sidecar missing")
            continue
        try:
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{sidecar}: unreadable provenance ({exc})")
            continue
        if urlparse(str(metadata.get("source_url", ""))).scheme != "https":
            errors.append(f"{sidecar}: source_url must be HTTPS")
        digest = hashlib.sha256()
        with artifact.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if metadata.get("sha256") != digest.hexdigest():
            errors.append(f"{artifact}: SHA-256 does not match its provenance sidecar")
        if not metadata.get("license_note") or not metadata.get("license_status"):
            errors.append(f"{sidecar}: license note/status missing")
    return errors


def validate_processed_records(records: list[dict[str, Any]]) -> list[str]:
    errors = []
    for index, record in enumerate(records):
        if record.get("content_status") == "published":
            errors.append(f"record[{index}]: acquisition pipeline cannot publish clinical content")
        sources = record.get("references", [])
        if not isinstance(sources, list) or not sources:
            errors.append(f"record[{index}]: source reference missing")
            continue
        if not any(
            isinstance(source, dict)
            and urlparse(str(source.get("url", ""))).scheme == "https"
            and source.get("source")
            and source.get("title")
            for source in sources
        ):
            errors.append(f"record[{index}]: no complete HTTPS source reference")
    return errors
