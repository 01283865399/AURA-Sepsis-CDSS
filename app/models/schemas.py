"""Validated request and response types for each research inference endpoint."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Probability = Annotated[float, Field(ge=0.0, le=1.0)]
OptionalString = str | None
OptionalNumber = float | None
Binary = Literal[0, 1]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SymptomsRequest(RequestModel):
    symptoms: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        min_length=1, max_length=487
    )
    top_k: int = Field(default=5, ge=1, le=10)


class DDXPlusRequest(RequestModel):
    age: float = Field(ge=0, le=120)
    sex: Literal["F", "M"]
    evidences: list[Annotated[str, Field(pattern=r"^E_\d+(?:_@_.+)?$")]] = Field(
        min_length=1, max_length=972
    )
    top_k: int = Field(default=5, ge=1, le=10)


class DiabetesRequest(RequestModel):
    gender: Literal["Female", "Male", "Other"]
    age: float = Field(ge=0, le=120)
    hypertension: Binary
    heart_disease: Binary
    smoking_history: Literal[
        "No Info", "current", "ever", "former", "never", "not current"
    ]
    bmi: float = Field(ge=0, le=150)
    HbA1c_level: float = Field(ge=0, le=30)
    blood_glucose_level: float = Field(ge=0, le=2000)
    top_k: int = Field(default=2, ge=1, le=2)


class HeartRequest(RequestModel):
    age: float = Field(ge=0, le=120)
    sex: str = Field(min_length=1, max_length=24)
    dataset: OptionalString = None
    cp: OptionalString = None
    trestbps: OptionalNumber = Field(default=None, ge=0, le=400)
    chol: OptionalNumber = Field(default=None, ge=0, le=1500)
    fbs: OptionalNumber = Field(default=None, ge=0, le=1)
    restecg: OptionalString = None
    thalch: OptionalNumber = Field(default=None, ge=0, le=300)
    exang: OptionalNumber = Field(default=None, ge=0, le=1)
    oldpeak: OptionalNumber = Field(default=None, ge=-20, le=20)
    slope: OptionalString = None
    ca: OptionalNumber = Field(default=None, ge=0, le=10)
    thal: OptionalString = None
    top_k: int = Field(default=2, ge=1, le=2)


class KidneyRequest(RequestModel):
    age: OptionalNumber = Field(default=None, ge=0, le=120)
    bp: OptionalNumber = Field(default=None, ge=0, le=400)
    sg: OptionalNumber = Field(default=None, ge=0, le=2)
    al: OptionalNumber = Field(default=None, ge=0, le=10)
    su: OptionalNumber = Field(default=None, ge=0, le=10)
    rbc: OptionalString = None
    pc: OptionalString = None
    pcc: OptionalString = None
    ba: OptionalString = None
    bgr: OptionalNumber = Field(default=None, ge=0, le=2000)
    bu: OptionalNumber = Field(default=None, ge=0, le=1000)
    sc: OptionalNumber = Field(default=None, ge=0, le=100)
    sod: OptionalNumber = Field(default=None, ge=0, le=250)
    pot: OptionalNumber = Field(default=None, ge=0, le=30)
    hemo: OptionalNumber = Field(default=None, ge=0, le=40)
    pcv: OptionalString = None
    wc: OptionalString = None
    rc: OptionalString = None
    htn: OptionalString = None
    dm: OptionalString = None
    cad: OptionalString = None
    appet: OptionalString = None
    pe: OptionalString = None
    ane: OptionalString = None
    top_k: int = Field(default=2, ge=1, le=2)


class ImagePredictionRequest(RequestModel):
    image: bytes = Field(min_length=1, max_length=10 * 1024 * 1024)
    top_k: int = Field(default=5, ge=1, le=5)


class IndianLiverPatientRequest(RequestModel):
    age: float = Field(alias="AGE", ge=0, le=120, allow_inf_nan=False)
    gender: Literal[1, 2] = Field(alias="GENDER")
    total_bilirubin: float = Field(alias="TB", ge=0, allow_inf_nan=False)
    direct_bilirubin: float = Field(alias="DB", ge=0, allow_inf_nan=False)
    alkaline_phosphotase: float = Field(alias="ALK", ge=0, allow_inf_nan=False)
    sgpt: float = Field(alias="SGPT", ge=0, allow_inf_nan=False)
    sgot: float = Field(alias="SGOT", ge=0, allow_inf_nan=False)
    total_proteins: float = Field(alias="TP", ge=0, allow_inf_nan=False)
    albumin: float = Field(alias="ALB", ge=0, allow_inf_nan=False)
    albumin_globulin_ratio: float = Field(alias="AG", ge=0, allow_inf_nan=False)
    top_k: int = Field(default=2, ge=1, le=2)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class Prediction(BaseModel):
    condition: str
    probability: Probability


class PredictionResponse(BaseModel):
    endpoint: str
    model_name: str
    predictions: list[Prediction]
    medical_content: list[dict[str, Any]]
    persisted: bool
    research_only: Literal[True] = True
    notice: str = (
        "Research decision support only; not a diagnosis or a substitute for "
        "qualified clinical assessment."
    )


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    research_only: Literal[True] = True
    supabase_configured: bool


class MedicalContentDraftPage(BaseModel):
    collection: str
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    records: list[dict[str, Any]]
    content_status: Literal["draft_only"]
    review_status: Literal["unreviewed"]
    clinical_review_required: Literal[True]
    not_for_clinical_use: Literal[True]
    notice_ar: str
    notice_en: str


class MedicalContentDraftSearchPage(MedicalContentDraftPage):
    query: str


class MedicalContentDraftRecord(BaseModel):
    collection: str
    record: dict[str, Any]
    record_id: str
    identifier_field: str
    content_status: Literal["draft_only"]
    review_status: Literal["unreviewed"]
    clinical_review_required: Literal[True]
    not_for_clinical_use: Literal[True]
    notice_ar: str
    notice_en: str


class MedicalContentDraftSummary(BaseModel):
    content_status: Literal["draft_only"]
    review_status: Literal["unreviewed"]
    clinical_review_required: Literal[True]
    not_for_clinical_use: Literal[True]
    counts: dict[str, int]
    clinical_symptom_approved: Literal[0]
    arabic_translations_available: Literal[0]
    notice_ar: str
    notice_en: str
