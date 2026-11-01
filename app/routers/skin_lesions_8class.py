from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import PredictionResponse
from app.routers._image_common import diagnose_uploaded_image


router = APIRouter(prefix="/api/v1/diagnose", tags=["skin_lesions_8class"])


@router.post("/skin_lesions_8class", response_model=PredictionResponse)
async def diagnose_skin_lesions_8class(
    image: UploadFile = File(...),
    top_k: int = Form(default=5, ge=1, le=5),
) -> PredictionResponse:
    return await diagnose_uploaded_image("skin_lesions_8class", image, top_k)
