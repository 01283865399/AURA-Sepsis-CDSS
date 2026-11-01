from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.predictors import ModelUnavailableError, predict_tabular
from app.core.responses import make_response
from app.models.schemas import HeartRequest, PredictionResponse


router = APIRouter(prefix="/api/v1/diagnose", tags=["heart"])


@router.post("/heart", response_model=PredictionResponse)
def diagnose_heart(request: HeartRequest) -> PredictionResponse:
    try:
        model_name, predictions = predict_tabular(
            "heart",
            request.model_dump(exclude={"top_k"}),
            request.top_k,
        )
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return make_response("heart", model_name, predictions)
