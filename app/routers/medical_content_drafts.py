"""Read-only API for source-backed, unreviewed medical-content drafts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    MedicalContentDraftPage,
    MedicalContentDraftRecord,
    MedicalContentDraftSummary,
)
from app.services.medical_content_draft_service import (
    MedicalContentDraftDataError,
    medical_content_draft_service,
)


router = APIRouter(
    prefix="/api/v1/medical-content/final",
    tags=["medical content drafts"],
)
VALID_COLLECTIONS = {"conditions", "symptoms", "phenotype_concepts", "associations"}


def _guard_data(func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except MedicalContentDraftDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/coverage", response_model=MedicalContentDraftSummary)
def final_content_coverage() -> dict[str, Any]:
    """Return draft counts separately from clinically reviewed catalog coverage."""
    return _guard_data(medical_content_draft_service.summary)


@router.get("/{collection}", response_model=MedicalContentDraftPage)
def list_final_content(
    collection: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    condition_id: str | None = None,
    symptom_id: str | None = None,
) -> dict[str, Any]:
    if collection not in VALID_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Unknown medical draft collection.")
    if (condition_id is not None or symptom_id is not None) and collection != "associations":
        raise HTTPException(
            status_code=422,
            detail="condition_id and symptom_id filters are supported only for associations.",
        )
    return _guard_data(
        medical_content_draft_service.list_records,
        collection,
        offset,
        limit,
        condition_id,
        symptom_id,
    )


@router.get("/{collection}/{record_id}", response_model=MedicalContentDraftRecord)
def get_final_content_record(collection: str, record_id: str) -> dict[str, Any]:
    if collection not in VALID_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Unknown medical draft collection.")
    result = _guard_data(medical_content_draft_service.get_record, collection, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Medical draft record not found.")
    return result
