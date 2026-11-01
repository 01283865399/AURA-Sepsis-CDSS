"""Shared response construction with explicit persistence failures."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.core.persistence import PersistenceError, persist_prediction
from app.models.schemas import PredictionResponse
from app.services.medical_content_service import medical_service


LOG = logging.getLogger(__name__)


def make_response(
    endpoint: str, model_name: str, predictions: list[dict[str, Any]]
) -> PredictionResponse:
    try:
        persisted = persist_prediction(endpoint, model_name, predictions)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Prediction was computed, but Supabase persistence failed.",
        ) from exc
    LOG.info(
        "Completed research inference endpoint=%s model=%s persisted=%s",
        endpoint,
        model_name,
        persisted,
    )
    return PredictionResponse(
        endpoint=endpoint,
        model_name=model_name,
        predictions=predictions,
        medical_content=[
            medical_service.enrich_prediction(prediction)
            for prediction in predictions
        ],
        persisted=persisted,
    )
