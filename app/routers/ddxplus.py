from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.predictors import (
    InvalidModelInputError,
    ModelUnavailableError,
    predict_ddxplus,
)
from app.core.responses import make_response
from app.models.schemas import DDXPlusRequest, PredictionResponse


router = APIRouter(prefix="/api/v1/diagnose", tags=["ddxplus"])


@router.post("/ddxplus", response_model=PredictionResponse)
def diagnose_ddxplus(request: DDXPlusRequest) -> PredictionResponse:
    try:
        model_name, predictions = predict_ddxplus(
            request.age, request.sex, request.evidences, request.top_k
        )
    except InvalidModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return make_response("ddxplus", model_name, predictions)
