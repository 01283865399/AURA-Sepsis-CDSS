from __future__ import annotations

from fastapi import File, HTTPException, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.predictors import (
    InvalidModelInputError,
    ModelUnavailableError,
    predict_image,
)
from app.core.responses import make_response
from app.models.schemas import ImagePredictionRequest, PredictionResponse


MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


async def diagnose_uploaded_image(
    dataset: str,
    image_file: UploadFile = File(...),
    top_k: int = 5,
) -> PredictionResponse:
    content_type = image_file.content_type
    if content_type not in (None, "application/octet-stream") and not content_type.startswith(
        "image/"
    ):
        await image_file.close()
        raise HTTPException(status_code=415, detail="Upload a valid image file.")
    try:
        image_bytes = await image_file.read(MAX_IMAGE_UPLOAD_BYTES + 1)
    finally:
        await image_file.close()
    if len(image_bytes) > MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MiB upload limit.")
    try:
        request = ImagePredictionRequest(image=image_bytes, top_k=top_k)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        model_name, predictions = await run_in_threadpool(
            predict_image, dataset, request.image, request.top_k
        )
    except InvalidModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return make_response(dataset, model_name, predictions)
