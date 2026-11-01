"""Explicit Supabase persistence for inference summaries without raw patient inputs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import httpx
from postgrest.exceptions import APIError

from app.core.config import settings


LOG = logging.getLogger(__name__)


class PersistenceError(RuntimeError):
    """Supabase was configured but did not accept an inference record."""


@lru_cache(maxsize=1)
def _client() -> Any:
    if not settings.supabase_url or not settings.supabase_key:
        raise PersistenceError("Supabase credentials are not configured.")
    try:
        from supabase import create_client

        return create_client(settings.supabase_url, settings.supabase_key)
    except (ImportError, ValueError) as exc:
        raise PersistenceError("Could not initialize the Supabase client.") from exc


def persist_prediction(
    endpoint: str, model_name: str, predictions: list[dict[str, Any]]
) -> bool:
    if not settings.supabase_url or not settings.supabase_key:
        LOG.warning(
            "Prediction for %s was not persisted: SUPABASE_URL/SUPABASE_KEY are unset.",
            endpoint,
        )
        return False
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "model_name": model_name,
        "predictions": predictions,
        "research_only": True,
    }
    try:
        _client().table(settings.supabase_table).insert(record).execute()
    except (APIError, httpx.HTTPError, OSError) as exc:
        LOG.exception("Supabase insert failed for endpoint %s.", endpoint)
        raise PersistenceError("Supabase rejected the prediction record.") from exc
    LOG.info("Persisted inference summary for %s to Supabase.", endpoint)
    return True
