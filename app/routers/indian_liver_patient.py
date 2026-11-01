from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.predictors import (
    InvalidModelInputError,
    ModelUnavailableError,
    predict_tabular,
)
from app.core.responses import make_response
from app.models.schemas import IndianLiverPatientRequest, PredictionResponse


router = APIRouter(prefix="/api/v1/diagnose", tags=["indian_liver_patient"])


@router.post("/indian_liver_patient", response_model=PredictionResponse)
def diagnose_indian_liver_patient(
    request: IndianLiverPatientRequest,
) -> PredictionResponse:
    features = request.model_dump(exclude={"top_k"}, by_alias=True)
    try:
        model_name, predictions = predict_tabular(
            "indian_liver_patient", features, request.top_k
        )
    except InvalidModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return make_response("indian_liver_patient", model_name, predictions)
