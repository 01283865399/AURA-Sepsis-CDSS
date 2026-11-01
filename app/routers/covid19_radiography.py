from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import PredictionResponse
from app.routers._image_common import diagnose_uploaded_image


router = APIRouter(prefix="/api/v1/diagnose", tags=["covid19_radiography"])


@router.post("/covid19_radiography", response_model=PredictionResponse)
async def diagnose_covid19_radiography(
    image: UploadFile = File(...),
    top_k: int = Form(default=4, ge=1, le=5),
) -> PredictionResponse:
    return await diagnose_uploaded_image("covid19_radiography", image, top_k)
