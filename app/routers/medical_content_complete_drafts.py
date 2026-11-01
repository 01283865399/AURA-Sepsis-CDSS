"""Read-only API for the complete but unreviewed source-derived build."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    MedicalContentDraftPage,
    MedicalContentDraftRecord,
    MedicalContentDraftSearchPage,
    MedicalContentDraftSummary,
)
from app.services.medical_content_complete_service import (
    COLLECTION_FILES,
    MedicalContentCompleteDataError,
    medical_content_complete_draft_service,
)


router = APIRouter(
    prefix="/api/v1/medical-content/complete-drafts",
    tags=["medical content drafts"],
)


def _guard_data(func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except MedicalContentCompleteDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/coverage", response_model=MedicalContentDraftSummary)
def complete_draft_coverage() -> dict[str, Any]:
    return _guard_data(medical_content_complete_draft_service.summary)


@router.get("/qa/search", response_model=MedicalContentDraftSearchPage)
def search_complete_draft_qa(
    q: str = Query(min_length=1, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    if not q.strip():
        raise HTTPException(status_code=422, detail="Search query cannot be blank.")
    return _guard_data(
        medical_content_complete_draft_service.search_qa, q, offset, limit
    )


@router.get("/{collection}", response_model=MedicalContentDraftPage)
def list_complete_draft_records(
    collection: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    if collection not in COLLECTION_FILES:
        raise HTTPException(status_code=404, detail="Unknown complete-draft collection.")
    return _guard_data(
        medical_content_complete_draft_service.list_records,
        collection,
        offset,
        limit,
    )


@router.get(
    "/{collection}/{record_id}", response_model=MedicalContentDraftRecord
)
def get_complete_draft_record(
    collection: str, record_id: str
) -> dict[str, Any]:
    if collection not in COLLECTION_FILES:
        raise HTTPException(status_code=404, detail="Unknown complete-draft collection.")
    result = _guard_data(
        medical_content_complete_draft_service.get_record, collection, record_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Complete-draft record not found.")
    return result
