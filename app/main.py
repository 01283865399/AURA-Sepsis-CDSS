"""FastAPI application for research-only medical decision support."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.models.schemas import HealthResponse
from app.services.medical_content_service import medical_service
from app.routers import (
    covid19_radiography,
    ddxplus,
    diabetes,
    heart,
    indian_liver_patient,
    isic_2019,
    medical_content_complete_drafts,
    medical_content_drafts,
    kidney,
    skin_lesions_8class,
    symptoms,
    tb_chest_radiography,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOG = logging.getLogger("medical_research_api")

app = FastAPI(
    title="AURA Research Decision Support API",
    version="1.0.0",
    description=(
        "Research-only model predictions. Outputs are not diagnoses, are not "
        "clinically validated, and must not be used as a substitute for qualified care."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

for endpoint_router in (
    symptoms.router,
    ddxplus.router,
    diabetes.router,
    heart.router,
    kidney.router,
    skin_lesions_8class.router,
    isic_2019.router,
    covid19_radiography.router,
    tb_chest_radiography.router,
    indian_liver_patient.router,
):
    app.include_router(endpoint_router)
app.include_router(medical_content_drafts.router)
app.include_router(medical_content_complete_drafts.router)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    configured = bool(settings.supabase_url and settings.supabase_key)
    if not configured:
        LOG.warning("Supabase is not configured; prediction summaries will not be persisted.")
    return HealthResponse(supabase_configured=configured)


@app.get("/api/v1/medical-content/coverage", tags=["medical content"])
def medical_content_coverage() -> dict[str, object]:
    """Report real medical-content coverage without implying clinical readiness."""
    return medical_service.get_coverage()
