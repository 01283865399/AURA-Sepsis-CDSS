from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.predictors import (
    InvalidModelInputError,
    ModelUnavailableError,
    predict_symptoms,
)
from app.core.responses import make_response
from app.models.schemas import PredictionResponse, SymptomsRequest


router = APIRouter(prefix="/api/v1/diagnose", tags=["symptoms"])


@router.post("/symptoms", response_model=PredictionResponse)
def diagnose_symptoms(request: SymptomsRequest) -> PredictionResponse:
    try:
        model_name, predictions = predict_symptoms(request.symptoms, request.top_k)
    except InvalidModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return make_response("symptoms", model_name, predictions)
