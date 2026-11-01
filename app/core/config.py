"""Environment-backed settings for the research API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:4173,http://127.0.0.1:4173",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        raise ValueError("CORS_ORIGINS must contain at least one allowed origin.")
    if "*" in origins and len(origins) > 1:
        raise ValueError("CORS_ORIGINS cannot mix a wildcard with explicit origins.")
    return origins


@dataclass(frozen=True)
class Settings:
    root: Path
    cors_origins: list[str]
    supabase_url: str | None
    supabase_key: str | None
    supabase_table: str


def get_settings() -> Settings:
    url = os.getenv("SUPABASE_URL", "").strip() or None
    key = os.getenv("SUPABASE_KEY", "").strip() or None
    if (url is None) != (key is None):
        raise ValueError("Set both SUPABASE_URL and SUPABASE_KEY, or leave both unset.")
    table = os.getenv("SUPABASE_PREDICTIONS_TABLE", "diagnosis_predictions").strip()
    if not table:
        raise ValueError("SUPABASE_PREDICTIONS_TABLE cannot be empty.")
    return Settings(
        root=ROOT,
        cors_origins=_origins(),
        supabase_url=url,
        supabase_key=key,
        supabase_table=table,
    )


settings = get_settings()
