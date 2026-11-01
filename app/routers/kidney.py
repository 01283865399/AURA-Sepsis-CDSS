from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.predictors import ModelUnavailableError, predict_tabular
from app.core.responses import make_response
from app.models.schemas import KidneyRequest, PredictionResponse


router = APIRouter(prefix="/api/v1/diagnose", tags=["kidney"])


@router.post("/kidney", response_model=PredictionResponse)
def diagnose_kidney(request: KidneyRequest) -> PredictionResponse:
    features = request.model_dump(exclude={"top_k"})
    if not any(value is not None for value in features.values()):
        raise HTTPException(
            status_code=422, detail="Provide at least one kidney feature."
        )
    try:
        model_name, predictions = predict_tabular(
            "kidney",
            features,
            request.top_k,
        )
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return make_response("kidney", model_name, predictions)
