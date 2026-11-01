from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import PredictionResponse
from app.routers._image_common import diagnose_uploaded_image


router = APIRouter(prefix="/api/v1/diagnose", tags=["tb_chest_radiography"])


@router.post("/tb_chest_radiography", response_model=PredictionResponse)
async def diagnose_tb_chest_radiography(
    image: UploadFile = File(...),
    top_k: int = Form(default=2, ge=1, le=5),
) -> PredictionResponse:
    return await diagnose_uploaded_image("tb_chest_radiography", image, top_k)
