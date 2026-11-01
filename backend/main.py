from datetime import datetime, timezone
from io import BytesIO
import base64
import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
import logging
from pathlib import Path
import tempfile
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator
import numpy as np
from dotenv import load_dotenv
from .sepsis_service import ModelNotApprovedError, SepsisService

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
MODEL_DIR = BACKEND_DIR / "models"
load_dotenv(PROJECT_ROOT / ".env")

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "early-sepsis-matplotlib"),
)

from PIL import Image, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from torchvision import transforms
import torch
import torchxrayvision as xrv

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None

app = FastAPI(
    title="Early Sepsis Prediction API",
    version="1.0",
    description=(
        "Research and development API. Patient storage must be configured "
        "separately and is not approved for clinical deployment."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "SEPSIS_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:5174,http://127.0.0.1:5174,"
            "http://localhost:4173,http://127.0.0.1:4173",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sepsis_service: SepsisService | None = None
logger = logging.getLogger(__name__)
_supabase_client = None
AUTH_DB = DATA_DIR / "auth.sqlite3"
AUTH_ROLES = {"admin", "doctor", "researcher", "nurse", "viewer"}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class GeminiChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    tool_results: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    patient_id: str | None = Field(default=None, max_length=64)
    patient_context_consent: bool = False


class GeminiChatResponse(BaseModel):
    message: str
    model: str
    grounded: bool = True
    research_only: bool = True
    sources: list[str] = []


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)
    role: Literal["researcher", "viewer"] = "viewer"


class AdminCreateUserRequest(RegisterRequest):
    role: Literal["admin", "doctor", "researcher", "nurse", "viewer"] = "viewer"


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    username: str
    role: str


PROJECT_KNOWLEDGE = """
This is AURA Sepsis AI, a research-only clinical decision-support workspace.
It contains exploratory routes for sepsis risk estimation, chest X-ray screening,
symptom ranking, DDXPlus differential diagnosis, diabetes, heart, kidney and
liver indicators, skin-lesion image classification, COVID-19 and TB radiography,
and laboratory-report OCR. Model results are estimates or screening signals,
not diagnoses, treatment instructions, triage decisions, or calibrated
individual probabilities. Qualified clinicians must review all outputs and
local protocols always take priority.

The project uses a legacy clinical API and a separate model API. Browser history
is local to the current browser and is not a medical record. Do not request or
repeat names, identifiers, full medical records, secrets, or images of real
patients. Do not claim that a model is clinically validated, approved, or able
to rule out disease. If a user describes an emergency, advise contacting local
emergency services or a qualified clinician rather than making a diagnosis.
Answer in the user's language. Clearly distinguish project-grounded facts from
general medical education, and say when the project data does not support an
answer.
""".strip()


def _auth_connection() -> sqlite3.Connection:
    AUTH_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(AUTH_DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
            role TEXT NOT NULL, created_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS ai_audit_log (
            id TEXT PRIMARY KEY, username TEXT NOT NULL, role TEXT NOT NULL,
            patient_id TEXT, used_patient_context INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if admin_username and len(admin_password) >= 12 and not connection.execute(
        "SELECT 1 FROM users WHERE username = ?", (admin_username,)
    ).fetchone():
        connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (admin_username, _password_hash(admin_password), datetime.now(timezone.utc).isoformat()),
        )
    connection.commit()
    return connection


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds)
        )
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(
            candidate, base64.urlsafe_b64decode(digest)
        )
    except (ValueError, TypeError):
        return False


def _token_encode(username: str, role: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": username, "role": role, "exp": int(datetime.now(timezone.utc).timestamp()) + 8 * 3600}
    encoded = lambda value: base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()
    body = f"{encoded(header)}.{encoded(payload)}"
    secret = os.environ.get("AUTH_JWT_SECRET", "").strip()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="AUTH_JWT_SECRET must contain at least 32 characters.")
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required.")
    try:
        body, encoded_signature = authorization[7:].rsplit(".", 1)
        secret = os.environ.get("AUTH_JWT_SECRET", "").strip()
        if len(secret) < 32:
            raise ValueError("JWT secret is not configured")
        expected = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(expected, encoded_signature):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(body.split(".")[1] + "=="))
        if payload["exp"] < int(datetime.now(timezone.utc).timestamp()) or payload["role"] not in AUTH_ROLES:
            raise ValueError("Expired or invalid token")
        return {"username": payload["sub"], "role": payload["role"]}
    except (ValueError, KeyError, IndexError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.") from error


def _retrieve_project_context(query: str, limit: int = 5) -> tuple[str, list[str]]:
    content_root = PROJECT_ROOT / "data" / "medical_content"
    candidates: list[tuple[int, str, str]] = []
    sources = (
        ("final/conditions.json", "conditions"),
        ("conditions/all_conditions.json", "conditions"),
        ("symptoms/all_symptoms.json", "symptoms"),
        ("medications/interactions.json", "interactions"),
        ("guidelines/who_guidelines.json", "WHO guidelines"),
        ("guidelines/cdc_guidelines.json", "CDC guidelines"),
        ("emergency/red_flags.json", "red flags"),
        ("emergency/triage_rules.json", "triage rules"),
        ("../models/symptoms/model_metadata.json", "symptoms model metadata"),
        ("../models/heart/xgboost_evaluation.json", "heart model evaluation"),
        ("../models/kidney/xgboost_evaluation.json", "kidney model evaluation"),
        ("../docs/medical_data/DATA_SOURCES.md", "project data sources"),
        ("../New folder/archive (2)/healthcare_rag_dataset.csv", "healthcare RAG dataset"),
    )
    terms = set(re.findall(r"[a-z0-9_]{3,}", query.lower()))
    for relative, label in sources:
        path = PROJECT_ROOT / relative[3:] if relative.startswith("../") else content_root / relative
        if not path.exists():
            continue
        try:
            raw = path.read_text(encoding="utf-8-sig")
            try:
                document = json.loads(raw)
                text = json.dumps(document, ensure_ascii=False)
            except json.JSONDecodeError:
                text = raw
        except (OSError, UnicodeError):
            logger.warning("Skipping unreadable RAG source %s", path)
            continue
        score = sum(text.lower().count(term) for term in terms)
        if score:
            candidates.append((score, label, text[:4000]))
    candidates.sort(reverse=True)
    selected = candidates[:limit]
    return "\n\n".join(f"[{label}]\n{snippet}" for _, label, snippet in selected), [label for _, label, _ in selected]


def _deidentified_patient_context(patient_id: str) -> str:
    record = get_patient(patient_id)
    return (
        f"De-identified patient context: age={record.age}, gender={record.gender}, "
        f"bed context omitted, risk_tier={record.risk_tier}, vital_signs={record.vital_signs}."
    )


def _gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


MEDICAL_AGENT_TOOL = {
    "type": "function",
    "name": "analyze_medical_data",
    "description": (
        "Use this tool when the user requests analysis of an X-ray image, "
        "symptoms, or vital-sign measurements."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "analysis_type": {
                "type": "string",
                "enum": ["xray", "symptoms", "sepsis", "diabetes"],
                "description": "The requested medical analysis type.",
            },
            "file_attached": {
                "type": "boolean",
                "description": "Whether the user attached an image.",
            },
            "clinical_notes": {
                "type": "string",
                "description": "Symptoms, measurements, or other user-provided notes.",
            },
        },
        "required": ["analysis_type", "file_attached", "clinical_notes"],
    },
}

MEDICAL_AGENT_INSTRUCTIONS = """
You are a compassionate and professional Arabic medical AI assistant for a
research-only clinical decision-support platform. When you receive results
from analyze_medical_data, do not merely list percentages or measurements:
explain the highest signals in simple, reassuring medical language, state what
they may indicate and what they do not prove, and ask one or two relevant
follow-up questions (for example, whether the user has cough or fever).
Always say that model outputs are screening signals, not a final diagnosis,
and never claim that a patient is stable, healthy, or ruled out based on a
model result alone. Do not prescribe treatment. Respond in Arabic unless the
user clearly asks for another language, and use readable Markdown.
""".strip()


def _function_call_from_response(result: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    output = result.get("output")
    if isinstance(output, list):
        candidates.extend(item for item in output if isinstance(item, dict))
    steps = result.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            candidates.append(step)
            content = step.get("content")
            if isinstance(content, list):
                candidates.extend(item for item in content if isinstance(item, dict))
    for item in candidates:
        item_type = item.get("type")
        if item_type in {"function_call", "functionCall"} or "functionCall" in item:
            call = item.get("functionCall", item)
            return {
                "id": item.get("id") or item.get("call_id") or call.get("id", "medical-data-call"),
                "name": call.get("name") or item.get("name"),
                "arguments": call.get("arguments") or call.get("args") or item.get("arguments") or {},
            }
    return None


def _gemini_text(result: dict[str, Any]) -> str:
    text = result.get("output_text", "")
    if not text:
        output = result.get("output")
        if isinstance(output, list):
            text = " ".join(
                str(part.get("text", ""))
                for part in output
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
            )
    if not text:
        for step in reversed(result.get("steps", [])):
            if isinstance(step, dict) and step.get("type") == "model_output":
                text = " ".join(
                    part.get("text", "")
                    for part in step.get("content", [])
                    if isinstance(part, dict)
                )
                if text:
                    break
    return str(text).strip()


def _gemini_request(api_key: str, model: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = UrlRequest(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        logger.warning("Gemini request failed with HTTP %s: %s", error.code, detail[:500])
        raise HTTPException(status_code=502, detail="Gemini could not complete the request.") from error
    except URLError as error:
        logger.warning("Gemini request failed: %s", error)
        raise HTTPException(status_code=502, detail="Gemini is unreachable right now.") from error
    except (TimeoutError, json.JSONDecodeError) as error:
        logger.warning("Invalid Gemini response: %s", error)
        raise HTTPException(status_code=502, detail="Gemini returned an invalid response.") from error


def _tool_result_fallback(tool_results: list[dict[str, Any]]) -> str:
    """Keep the analyzed result visible if the explanatory model is unavailable."""
    parts: list[str] = [
        "اكتمل التحليل، لكن تعذر توليد الشرح التفاعلي من Gemini.",
        "هذه مخرجات الفحص الآلي وليست تشخيصاً نهائياً؛ راجع الصورة أو البيانات الأصلية مع مختص.",
    ]
    for item in tool_results:
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        summary = result.get("clinical_summary") or result.get("message")
        if isinstance(summary, str) and summary.strip():
            parts.append(summary.strip())
        scores = result.get("target_scores")
        if isinstance(scores, dict) and scores:
            ordered = sorted(
                (
                    (str(name), float(value))
                    for name, value in scores.items()
                    if isinstance(value, (int, float))
                ),
                key=lambda item: item[1],
                reverse=True,
            )
            if ordered:
                parts.append(
                    "**أعلى الإشارات التشغيلية:**\n"
                    + "\n".join(f"- {name}: {score:.1f}/100" for name, score in ordered[:3])
                )
        recommendations = result.get("recommendations")
        if isinstance(recommendations, list):
            verified = [str(value).strip() for value in recommendations if str(value).strip()]
            if verified:
                parts.append("**الخطوات المقترحة:**\n" + "\n".join(f"- {value}" for value in verified))
    return "\n\n".join(parts)


def _call_gemini(
    messages: list[ChatMessage],
    context: str,
    tool_results: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    api_key = _gemini_api_key()
    if not api_key:
        if tool_results:
            logger.warning("Gemini is not configured; returning the supplied medical tool result.")
            return _tool_result_fallback(tool_results), os.environ.get("GEMINI_MODEL", "unavailable").strip()
        raise HTTPException(
            status_code=503,
            detail="Gemini is not configured. Set GEMINI_API_KEY in the backend environment.",
        )

    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
    transcript = "\n".join(
        f"{'User' if item.role == 'user' else 'Assistant'}: {item.content}"
        for item in messages
    )
    supplied_results = tool_results or []
    if supplied_results:
        transcript += (
            "\n\nMedical tool results from the application (explain these; "
            "do not invent missing values):\n"
            + json.dumps(supplied_results, ensure_ascii=False)
        )
    payload = {
        "model": model,
        "system_instruction": f"{PROJECT_KNOWLEDGE}\n\n{MEDICAL_AGENT_INSTRUCTIONS}",
        "tools": [MEDICAL_AGENT_TOOL],
        "input": (
            f"Project data context:\n{context}\n\nConversation:\n{transcript}\n\n"
            "Answer the last user message only."
        ),
    }
    try:
        result = _gemini_request(api_key, model, payload)
    except HTTPException:
        if supplied_results:
            logger.warning("Gemini failed before explaining a medical tool result; using raw-result fallback.")
            return _tool_result_fallback(supplied_results), model
        raise
    function_call = _function_call_from_response(result)
    if function_call and function_call.get("name") == "analyze_medical_data":
        function_result = (
            {"status": "results_received", "tool_results": supplied_results}
            if supplied_results
            else {
                "status": "waiting_for_upload",
                "message": (
                    "Ask the user to upload the image or enter the clinical "
                    "measurements using the dedicated chat controls. No analysis "
                    "was executed by this function call."
                ),
            }
        )
        follow_up_payload = {
            **payload,
            "input": [
                {"role": "user", "content": payload["input"]},
                {
                    "type": "function_call",
                    "id": function_call["id"],
                    "name": function_call["name"],
                    "arguments": function_call["arguments"],
                },
                {
                    "type": "function_result",
                    "call_id": function_call["id"],
                    "result": function_result,
                },
            ],
        }
        try:
            result = _gemini_request(api_key, model, follow_up_payload)
        except HTTPException:
            logger.warning("Gemini explanation failed after medical tool result; using raw-result fallback.")
            return _tool_result_fallback(supplied_results), model

    text = _gemini_text(result)
    if not text:
        if supplied_results:
            logger.warning("Gemini returned no explanation after medical tool result; using raw-result fallback.")
            return _tool_result_fallback(supplied_results), model
        logger.warning("Gemini response did not contain text: %s", result)
        raise HTTPException(status_code=502, detail="Gemini returned an empty answer.")
    return text, model


def get_sepsis_service() -> SepsisService:
    global sepsis_service
    if sepsis_service is None:
        artifact_path = MODEL_DIR / "sepsis_model.joblib"
        try:
            allow_research = os.environ.get("SEPSIS_ALLOW_RESEARCH_MODEL", "").lower() == "true"
            sepsis_service = SepsisService.from_artifact(
                artifact_path,
                allow_research_artifact=allow_research,
            )
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The grouped sepsis model has not been trained yet. "
                    "Run python -m backend.train_sepsis to create "
                    "backend/models/sepsis_model.joblib."
                ),
            ) from error
        except ModelNotApprovedError as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The model is blocked because clinical validation and deployment "
                    "approval are absent. The explicit SEPSIS_ALLOW_RESEARCH_MODEL=true "
                    "override is for research demonstrations only."
                ),
            ) from error
    return sepsis_service

XRAY_TARGETS = ("Pneumonia", "Atelectasis", "Effusion", "Consolidation")
xray_model = None
xray_transform = None
xray_model_error = None
try:
    xray_model = xrv.models.DenseNet(weights="densenet121-res224-all").cpu().eval()
    xray_transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((224, 224), antialias=True),
        transforms.ToTensor(),
    ])
except Exception as error:
    xray_model_error = f"{type(error).__name__}: {error}"

# تعريف شكل البيانات المستقبلة لكل مريض
class PatientVitals(BaseModel):
    model_config = ConfigDict(extra="allow")

    HR: float = 80.0
    O2Sat: float = 98.0
    Temp: float = 36.5
    SBP: float = 120.0
    MAP: float = 80.0
    DBP: float = 70.0
    Resp: float = 18.0
    Age: float = 60.0
    Gender: int = 1
    ICULOS: int = 10
    # يمكن إضافة بقية المتغيرات بقيم افتراضية لتسهيل الاختبار
    WBC: float = 9.0
    Platelets: float = 200.0


class PatientCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=0, le=120)
    bed_number: str = Field(min_length=1, max_length=32)
    gender: Literal["Female", "Male"] = "Female"


class PatientRecord(BaseModel):
    patient_id: str
    name: str
    age: int
    bed_number: str
    gender: Literal["Female", "Male"]
    risk_tier: str = "Not assessed"
    vital_signs: dict[str, float]
    created_at: str


def _connect_patient_database() -> sqlite3.Connection:
    """Open the local development database for the patient directory."""
    database_path = Path(
        os.environ.get(
            "SEPSIS_PATIENT_DB",
            str(DATA_DIR / "patients.sqlite3"),
        )
    ).expanduser()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
            bed_number TEXT NOT NULL,
            gender TEXT NOT NULL CHECK (gender IN ('Female', 'Male')),
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def _patient_storage_backend() -> Literal["sqlite", "supabase"]:
    backend = os.environ.get("PATIENT_STORAGE_BACKEND", "sqlite").strip().lower()
    if backend not in {"sqlite", "supabase"}:
        raise HTTPException(
            status_code=500,
            detail="PATIENT_STORAGE_BACKEND must be 'sqlite' or 'supabase'.",
        )
    return backend


def _get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    project_url = os.environ.get("SUPABASE_URL", "").strip()
    secret_key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not project_url or not secret_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase storage is selected but SUPABASE_URL and a server-side "
                "SUPABASE_SECRET_KEY are not configured."
            ),
        )

    try:
        from supabase import create_client

        _supabase_client = create_client(project_url, secret_key)
    except ImportError as error:
        logger.exception("Supabase Python client is not installed.")
        raise HTTPException(
            status_code=503,
            detail="Supabase storage is unavailable because its Python client is not installed.",
        ) from error
    except Exception as error:
        logger.exception("Could not initialize the Supabase patient store.")
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the configured Supabase patient store.",
        ) from error
    return _supabase_client


def _patient_store_unavailable(error: Exception) -> HTTPException:
    logger.error(
        "Patient storage request failed.",
        exc_info=(type(error), error, error.__traceback__),
    )
    return HTTPException(
        status_code=503,
        detail="Patient storage is temporarily unavailable. Please try again later.",
    )


def _patient_record(row: sqlite3.Row) -> PatientRecord:
    gender = row["gender"]
    return PatientRecord(
        patient_id=row["patient_id"],
        name=row["name"],
        age=row["age"],
        bed_number=row["bed_number"],
        gender=gender,
        vital_signs={"Age": float(row["age"]), "Gender": 1.0 if gender == "Male" else 0.0},
        created_at=row["created_at"],
    )


def _supabase_patient_record(row: dict) -> PatientRecord:
    """Validate a row returned by Supabase before exposing it through the API."""
    return PatientRecord.model_validate(row)


class ImageValidationSummary(BaseModel):
    analysis_status: Literal[
        "preview_only",
        "ocr_extracted",
        "ocr_unavailable",
        "ocr_no_values",
        "xray_model_unavailable",
        "xray_analyzed",
        "unrecognized_image",
    ]
    analysis_type: Literal["auto", "xray", "lab"] = "auto"
    image_format: str
    image_dimensions: dict[str, int]
    file_size_bytes: int
    extracted_vitals: dict[str, float] = Field(default_factory=dict)
    findings: str | None = None
    infection_site: str | None = None
    confidence_score: float | None = None
    confidence_note: str | None = None
    target_scores: dict[str, float] = Field(default_factory=dict)
    model_name: str | None = None
    clinical_summary: str | None = None
    recommendations: list[str] = Field(default_factory=list)


class FullReportRequest(BaseModel):
    vitals: PatientVitals
    image_validation: ImageValidationSummary | None = None


class PDFDataCompleteness(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    provided_feature_count: int = Field(ge=0)
    required_feature_count: int = Field(gt=0)
    provided_features: list[str] = Field(default_factory=list)
    imputed_features: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_feature_counts(self):
        if self.provided_feature_count + len(self.imputed_features) != self.required_feature_count:
            raise ValueError("Provided and imputed feature counts must equal required_feature_count.")
        if self.provided_feature_count != len(self.provided_features):
            raise ValueError("provided_features must match provided_feature_count.")
        return self


class PDFShapContribution(BaseModel):
    feature: str = Field(min_length=1, max_length=100)
    impact: float = Field(allow_inf_nan=False)


class PDFUncertaintyInterval(BaseModel):
    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.lower > self.upper:
            raise ValueError("Interval lower bound must not exceed upper bound.")
        return self


class PDFExportRequest(BaseModel):
    lang: Literal["en", "ar"] = "en"
    risk_tier: Literal["Low", "Medium", "High"]
    sepsis_probability: float = Field(ge=0.0, le=1.0)
    data_completeness: PDFDataCompleteness
    top_shap_contributions: list[PDFShapContribution] = Field(max_length=10)
    risk_thresholds: dict[str, float] = Field(default_factory=dict)
    uncertainty_interval: PDFUncertaintyInterval | None = None
    model_version: str = Field(default="unknown", max_length=100)


class PatientReportExportRequest(BaseModel):
    lang: Literal["en", "ar"] = "en"
    vitals: PatientVitals
    image_validation: ImageValidationSummary | None = None


_ARABIC_PDF_FONT_NAME = "SepsisArabic"


def _register_arabic_pdf_font() -> str:
    """Register a UTF-8 TTF font suitable for Arabic PDF text."""
    if _ARABIC_PDF_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return _ARABIC_PDF_FONT_NAME
    configured_font = os.environ.get("SEPSIS_ARABIC_FONT")
    candidates = [
        Path(configured_font) if configured_font else None,
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\Amiri-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    font_path = next((path for path in candidates if path and path.is_file()), None)
    if font_path is None:
        raise RuntimeError(
            "Arabic PDF export requires an Arabic-capable TTF font. "
            "Set SEPSIS_ARABIC_FONT to a font file such as Arial or Amiri."
        )
    pdfmetrics.registerFont(TTFont(_ARABIC_PDF_FONT_NAME, str(font_path)))
    return _ARABIC_PDF_FONT_NAME


def _pdf_localize(text: str, lang: Literal["en", "ar"]) -> str:
    """Escape text and shape Arabic glyphs for ReportLab's left-to-right canvas."""
    if lang == "en":
        return escape(text)
    if arabic_reshaper is None or get_display is None:
        raise RuntimeError(
            "Arabic PDF export requires arabic-reshaper and python-bidi."
        )
    shaped = arabic_reshaper.reshape(text)
    return escape(get_display(shaped, base_dir="R"))


def create_cds_pdf_report(
    request: PDFExportRequest,
    *,
    deployment_status: Literal["research_only", "clinically_approved"],
) -> bytes:
    """Render a single-page CDS PDF with provenance in a compact footer."""
    lang = request.lang
    is_arabic = lang == "ar"
    font_name = _register_arabic_pdf_font() if is_arabic else "Helvetica"
    localized: dict[str, dict[str, str]] = {
        "en": {
            "title": "Sepsis Clinical Decision Support Report",
            "summary": "Assessment summary",
            "tier": "Model risk tier",
            "score": "Model score",
            "completeness": "Input completeness",
            "provided": "Features supplied",
            "model": "Model version",
            "imputed": "Imputed features",
            "thresholds": "Configured score thresholds",
            "uncertainty": "Model uncertainty",
            "uncertainty_text": "Exploratory ensemble score range: {lower:.1%} to {upper:.1%}. This is not a calibrated confidence interval or a clinical probability interval.",
            "shap": "Top SHAP feature contributions",
            "feature": "Feature",
            "contribution": "Model contribution",
            "raises": "Raises model output",
            "lowers": "Lowers model output",
            "no_change": "No change",
            "no_shap": "No SHAP contributions were supplied.",
            "footer_status_research": "RESEARCH USE · NOT CLINICALLY VALIDATED",
            "footer_status_approved": "CLINICAL STATUS · APPROVED",
            "footer_notice": "Not an official record, diagnosis, or treatment recommendation. Scores are uncalibrated and must not be used alone for care decisions. Verify source data and interpret with a qualified clinician. SHAP shows model contribution, not causation; completeness and model spread are not confidence measures.",
        },
        "ar": {
            "title": "تقرير دعم القرار السريري للإنتان",
            "summary": "ملخص التقييم",
            "tier": "مستوى خطورة النموذج",
            "score": "درجة النموذج",
            "completeness": "اكتمال البيانات المدخلة",
            "provided": "المؤشرات المدخلة",
            "model": "إصدار النموذج",
            "imputed": "المؤشرات المقدّرة",
            "thresholds": "حدود درجات الخطورة المعتمدة",
            "uncertainty": "عدم يقين النموذج",
            "uncertainty_text": "نطاق درجات النماذج الاستكشافي: {lower:.1%} إلى {upper:.1%}. هذا ليس فاصل ثقة معايرًا ولا نطاق احتمال سريريًا.",
            "shap": "أبرز مساهمات مؤشرات SHAP",
            "feature": "المؤشر",
            "contribution": "مساهمة النموذج",
            "raises": "يرفع ناتج النموذج",
            "lowers": "يخفض ناتج النموذج",
            "no_change": "لا تغيير",
            "no_shap": "لم تُرسل مساهمات SHAP.",
            "footer_status_research": "للاستخدام البحثي · لم يتم التحقق السريري",
            "footer_status_approved": "حالة الاعتماد السريري · معتمد",
            "footer_notice": "ليس سجلًا رسميًا أو تشخيصًا أو توصية علاجية. الدرجات غير معايرة ولا تستخدم منفردة لقرارات الرعاية. تحقّق من البيانات الأصلية وفسّر النتائج مع طبيب مؤهل. توضح SHAP مساهمة النموذج ولا تثبت السببية؛ كما أن اكتمال البيانات وتفاوت النموذج ليسا مقياسي ثقة.",
        },
    }[lang]
    arabic_feature_labels = {
        "HR": "معدل ضربات القلب",
        "Heart rate": "معدل ضربات القلب",
        "O2Sat": "تشبع الأكسجين",
        "Oxygen saturation": "تشبع الأكسجين",
        "Temp": "درجة الحرارة",
        "Temperature": "درجة الحرارة",
        "SBP": "ضغط الدم الانقباضي",
        "Systolic blood pressure": "ضغط الدم الانقباضي",
        "MAP": "متوسط الضغط الشرياني",
        "Mean arterial pressure": "متوسط الضغط الشرياني",
        "DBP": "ضغط الدم الانبساطي",
        "Diastolic blood pressure": "ضغط الدم الانبساطي",
        "Resp": "معدل التنفس",
        "Respiratory rate": "معدل التنفس",
        "Age": "العمر",
        "Gender": "الجنس",
        "ICULOS": "مدة الإقامة بالعناية المركزة",
        "WBC": "كريات الدم البيضاء",
        "White blood cells": "كريات الدم البيضاء",
        "Platelets": "الصفائح الدموية",
        "Lactate": "اللاكتات",
        "Creatinine": "الكرياتينين",
        "Glucose": "الجلوكوز",
        "Hgb": "الهيموجلوبين",
        "Hct": "الهيماتوكريت",
        "FiO2": "الأكسجين المستنشق",
        "pH": "الأس الهيدروجيني",
    }

    def text(value: str) -> str:
        return _pdf_localize(value, lang)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.95 * inch,
        title="Sepsis Clinical Decision Support Report",
        author="AURA Sepsis AI",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=15 if is_arabic else 16,
        leading=19,
        textColor=colors.HexColor("#17324a"),
        alignment=TA_RIGHT if is_arabic else TA_CENTER,
        spaceAfter=5,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#17324a"),
        alignment=TA_RIGHT if is_arabic else TA_LEFT,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#33485a"),
        alignment=TA_RIGHT if is_arabic else TA_LEFT,
    )
    footer_status_style = ParagraphStyle(
        "FooterStatus",
        fontName=font_name,
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#29485f"),
        alignment=TA_RIGHT if is_arabic else TA_LEFT,
        spaceAfter=2,
    )
    footer_notice_style = ParagraphStyle(
        "FooterNotice",
        parent=body_style,
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#536879"),
    )

    story = [Paragraph(text(localized["title"]), title_style), Spacer(1, 5)]

    completeness = request.data_completeness
    summary_rows = [
        [text(localized["tier"]), text(request.risk_tier if not is_arabic else {"Low": "منخفض", "Medium": "متوسط", "High": "مرتفع"}[request.risk_tier]), text(localized["score"]), f"{request.sepsis_probability:.1%}"],
        [
            text(localized["completeness"]),
            f"{completeness.score:.1%}",
            text(localized["provided"]),
            f"{completeness.provided_feature_count}/{completeness.required_feature_count}",
        ],
        [text(localized["model"]), text(request.model_version), text(localized["imputed"]), str(len(completeness.imputed_features))],
    ]
    if request.risk_thresholds:
        threshold_labels = {
            "low": "منخفض",
            "medium": "متوسط",
            "high": "مرتفع",
        }
        threshold_text = ", ".join(
            f"{text(threshold_labels.get(key.lower(), key.title()) if is_arabic else key.title())}: {value:.1%}"
            for key, value in sorted(request.risk_thresholds.items())
        )
        summary_rows.append([text(localized["thresholds"]), Paragraph(threshold_text, body_style), "", ""])
    summary_table = Table(
        summary_rows,
        colWidths=[1.4 * inch, 1.95 * inch, 1.25 * inch, 2.0 * inch],
        hAlign="RIGHT" if is_arabic else "LEFT",
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#edf3f7")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#52687a")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#52687a")),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2e9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("SPAN", (1, -1), (3, -1)) if request.risk_thresholds else ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
    ]))
    story.extend([Paragraph(text(localized["summary"]), section_style), summary_table])

    if request.uncertainty_interval is not None:
        interval = request.uncertainty_interval
        story.extend([
            Paragraph(text(localized["uncertainty"]), section_style),
            Paragraph(
                text(localized["uncertainty_text"].format(
                    lower=interval.lower, upper=interval.upper
                )),
                body_style,
            ),
        ])

    story.append(Paragraph(text(localized["shap"]), section_style))
    if request.top_shap_contributions:
        direction_title = "الاتجاه" if is_arabic else "Direction"
        contribution_rows = [[
            text(localized["feature"]),
            text(localized["contribution"]),
            text(direction_title),
        ]]
        for contribution in request.top_shap_contributions[:5]:
            impact = contribution.impact
            feature_name = (
                arabic_feature_labels.get(contribution.feature, contribution.feature)
                if is_arabic
                else contribution.feature
            )
            contribution_rows.append([
                Paragraph(text(feature_name), body_style),
                f"{impact:+.4f}",
                Paragraph(
                    text(localized["raises"] if impact > 0 else localized["lowers"] if impact < 0 else localized["no_change"]),
                    body_style,
                ),
            ])
        contribution_table = Table(
            contribution_rows,
            colWidths=[3.3 * inch, 1.45 * inch, 1.85 * inch],
            hAlign="RIGHT" if is_arabic else "LEFT",
        )
        contribution_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0f5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324a")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2e9")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(contribution_table)
    else:
        story.append(Paragraph(text(localized["no_shap"]), body_style))

    def draw_footer(canvas, pdf_document) -> None:
        status_key = (
            "footer_status_approved"
            if deployment_status == "clinically_approved"
            else "footer_status_research"
        )
        status_paragraph = Paragraph(text(localized[status_key]), footer_status_style)
        notice_paragraph = Paragraph(text(localized["footer_notice"]), footer_notice_style)
        footer_width = pdf_document.width - 18
        _, status_height = status_paragraph.wrap(footer_width, 0.65 * inch)
        _, notice_height = notice_paragraph.wrap(footer_width, 0.65 * inch)
        footer_x = pdf_document.leftMargin + 9
        footer_y = 0.23 * inch
        box_height = status_height + notice_height + 16

        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#f3f6f8"))
        canvas.setStrokeColor(colors.HexColor("#d8e2e9"))
        canvas.roundRect(
            pdf_document.leftMargin,
            footer_y - 5,
            pdf_document.width,
            box_height,
            5,
            stroke=1,
            fill=1,
        )
        status_paragraph.drawOn(canvas, footer_x, footer_y + notice_height + 3)
        notice_paragraph.drawOn(canvas, footer_x, footer_y)
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()


@app.post("/export-pdf")
def export_pdf(request: PDFExportRequest, lang: Literal["en", "ar"] | None = None) -> Response:
    if lang is not None:
        request.lang = lang
    service = get_sepsis_service()
    deployment_status: Literal["research_only", "clinically_approved"] = (
        "clinically_approved" if service.clinically_approved else "research_only"
    )
    pdf_content = create_cds_pdf_report(
        request,
        deployment_status=deployment_status,
    )
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="Sepsis_Clinical_Report.pdf"'
        },
    )


def create_patient_pdf_report(
    report: dict,
    *,
    lang: Literal["en", "ar"],
) -> bytes:
    """Render the comprehensive patient report as a downloadable PDF."""
    is_arabic = lang == "ar"
    font_name = _register_arabic_pdf_font() if is_arabic else "Helvetica"
    arabic_text = {
        "Male": "ذكر",
        "Female": "أنثى",
        "Low Risk": "خطورة منخفضة",
        "Moderate Risk": "خطورة متوسطة",
        "High Risk": "خطورة مرتفعة",
        "ICU monitoring context supplied by the operator; not independently verified.": "سياق مراقبة العناية المركزة أدخله المشغّل ولم يتم التحقق منه بشكل مستقل.",
        "Request prompt in-person review by the treating clinician and verify the current observations against the patient record.": "اطلب مراجعة مباشرة وسريعة من الطبيب المعالج وتحقق من المؤشرات الحالية بمقارنتها بسجل المريض.",
        "If clinical concern is present, follow the institution's sepsis screening and escalation pathway.": "إذا وُجد قلق سريري، فاتبع مسار مؤسستك لفحص الإنتان والتصعيد.",
        "Clinical monitoring and any further actions remain the responsibility of the treating team.": "تظل المراقبة السريرية وأي إجراءات إضافية مسؤولية فريق الرعاية المعالج.",
        "Review available CBC, metabolic results, lactate, and cultures in their clinical context; repeat or order tests only when directed by the treating clinician or local protocol.": "راجع نتائج تعداد الدم الكامل والفحوصات الاستقلابية واللاكتات والمزارع في سياقها السريري؛ ولا تكرر الفحوصات أو تطلبها إلا بتوجيه الطبيب المعالج أو البروتوكول المحلي.",
        "Arrange timely clinician review and compare the current observations with the patient's baseline and recent trend.": "رتّب مراجعة الطبيب في الوقت المناسب وقارن المؤشرات الحالية بخط الأساس والاتجاهات الحديثة للمريض.",
        "Escalate according to local protocol if the patient is deteriorating or the treating team is concerned.": "صعّد الرعاية وفق البروتوكول المحلي إذا تدهورت حالة المريض أو كان فريق الرعاية قلقًا.",
        "Review recent laboratory results and trends; repeat testing only when clinically indicated by the treating team or local protocol.": "راجع نتائج المختبر الحديثة واتجاهاتها؛ ولا تكرر الفحوصات إلا عند وجود داعٍ سريري يحدده فريق الرعاية أو البروتوكول المحلي.",
        "No immediate action is inferred from this model score alone; continue the clinician's existing monitoring plan.": "لا تُستنتج حاجة إلى إجراء فوري من درجة النموذج وحدها؛ واصل خطة المراقبة التي وضعها الطبيب.",
        "Reassess promptly if the patient's condition changes or clinical concern persists despite a low model estimate.": "أعد التقييم سريعًا إذا تغيرت حالة المريض أو استمر القلق السريري رغم انخفاض تقدير النموذج.",
        "No automatic repeat testing is recommended by this report; follow the existing clinical plan and local protocol.": "لا يوصي هذا التقرير تلقائيًا بتكرار الفحوصات؛ اتبع الخطة السريرية الحالية والبروتوكول المحلي.",
        "The chest X-ray model flagged a screening finding; obtain qualified radiology review and correlate clinically. This result does not confirm an infection source or prescribe treatment.": "رصد نموذج الأشعة السينية للصدر مؤشرًا يستدعي الفحص؛ اطلب مراجعة اختصاصي أشعة مؤهل واربط النتيجة بالسياق السريري. لا تؤكد هذه النتيجة مصدر عدوى ولا تصف علاجًا.",
        "The uploaded image was validated for preview only. No imaging findings or infection site are available; obtain qualified radiology or clinician review if imaging is clinically indicated.": "تم التحقق من الصورة المرفوعة للمعاينة فقط. لا تتوفر نتائج تصوير أو موضع عدوى؛ اطلب مراجعة اختصاصي أشعة أو طبيب مؤهل إذا كان التصوير مطلوبًا سريريًا.",
        "OCR produced candidate lab values only. Verify them against the source report; no radiological interpretation was performed.": "استخرج OCR قيمًا مخبرية مرشحة فقط. تحقق منها بمقارنتها بالتقرير الأصلي؛ لم يتم إجراء تفسير إشعاعي.",
        "No laboratory values were extracted. Review the image manually and verify any transcribed values against the source document.": "لم يتم استخراج قيم مخبرية. راجع الصورة يدويًا وتحقق من أي قيم منسوخة بمقارنتها بالمستند الأصلي.",
        "No image was attached; imaging should be considered only by the treating clinician when clinically indicated.": "لم تُرفق صورة؛ وينبغي أن يقرر الطبيب المعالج إجراء التصوير عند وجود داعٍ سريري فقط.",
        "No final clinical diagnosis is generated by this decision-support report.": "لا يصدر هذا التقرير الداعم للقرار تشخيصًا سريريًا نهائيًا.",
    }

    def text(value: object) -> str:
        value_text = str(value)
        if lang == "ar":
            value_text = arabic_text.get(value_text, value_text)
        return _pdf_localize(value_text, lang)
    labels = {
        "en": {
            "title": "Patient Assessment Report",
            "summary": "Patient summary",
            "age": "Age",
            "gender": "Gender",
            "context": "Admission context",
            "observations": "Vital signs and laboratory results",
            "measurement": "Measurement",
            "value": "Value",
            "reference": "General reference",
            "risk": "Sepsis model estimate",
            "risk_tier": "Risk tier",
            "score": "Model score",
            "completeness": "Input completeness",
            "features": "Features supplied",
            "shap": "Top model contributions (SHAP)",
            "feature": "Feature",
            "impact": "Contribution",
            "image": "Medical image review",
            "no_image": "No image was provided for review.",
            "guidance": "Clinical review guidance",
            "actions": "Immediate review",
            "follow_up": "Laboratory and imaging follow-up",
            "status_research": "RESEARCH USE · NOT CLINICALLY VALIDATED",
            "status_approved": "CLINICAL STATUS · APPROVED",
            "notice": "Not an official record, diagnosis, or treatment recommendation. Scores are uncalibrated and must not be used alone for care decisions. Verify source data and interpret with a qualified clinician. SHAP describes model contribution, not causation.",
            "direction_up": "Raises model output",
            "direction_down": "Lowers model output",
        },
        "ar": {
            "title": "تقرير تقييم المريض",
            "summary": "ملخص المريض",
            "age": "العمر",
            "gender": "الجنس",
            "context": "سياق الدخول",
            "observations": "العلامات الحيوية ونتائج المختبر",
            "measurement": "المؤشر",
            "value": "القيمة",
            "reference": "المرجع العام",
            "risk": "تقدير نموذج الإنتان",
            "risk_tier": "مستوى الخطورة",
            "score": "درجة النموذج",
            "completeness": "اكتمال البيانات",
            "features": "المؤشرات المدخلة",
            "shap": "أبرز مساهمات النموذج (SHAP)",
            "feature": "المؤشر",
            "impact": "المساهمة",
            "image": "مراجعة الصورة الطبية",
            "no_image": "لم تُقدّم صورة للمراجعة.",
            "guidance": "إرشادات المراجعة السريرية",
            "actions": "المراجعة الفورية",
            "follow_up": "متابعة المختبر والتصوير",
            "status_research": "للاستخدام البحثي · لم يتم التحقق السريري",
            "status_approved": "حالة الاعتماد السريري · معتمد",
            "notice": "ليس سجلًا رسميًا أو تشخيصًا أو توصية علاجية. الدرجات غير معايرة ولا تستخدم منفردة لقرارات الرعاية. تحقّق من البيانات وفسّرها مع طبيب مؤهل. توضح SHAP مساهمة النموذج ولا تثبت السببية.",
            "direction_up": "يرفع ناتج النموذج",
            "direction_down": "يخفض ناتج النموذج",
        },
    }[lang]
    feature_ar = {
        "HR": "معدل ضربات القلب",
        "O2Sat": "تشبع الأكسجين",
        "Temp": "درجة الحرارة",
        "SBP": "ضغط الدم الانقباضي",
        "MAP": "متوسط الضغط الشرياني",
        "DBP": "ضغط الدم الانبساطي",
        "Resp": "معدل التنفس",
        "Age": "العمر",
        "Gender": "الجنس",
        "ICULOS": "مدة الإقامة بالعناية المركزة",
        "WBC": "كريات الدم البيضاء",
        "Platelets": "الصفائح الدموية",
        "Lactate": "اللاكتات",
        "Creatinine": "الكرياتينين",
        "Glucose": "الجلوكوز",
    }
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PatientReportTitle", parent=styles["Title"], fontName=font_name,
        fontSize=17 if not is_arabic else 15, leading=21,
        textColor=colors.HexColor("#17324a"),
        alignment=TA_RIGHT if is_arabic else TA_CENTER, spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "PatientReportSection", parent=styles["Heading2"], fontName=font_name,
        fontSize=11, leading=14, textColor=colors.HexColor("#17324a"),
        alignment=TA_RIGHT if is_arabic else TA_LEFT, spaceBefore=11, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "PatientReportBody", parent=styles["BodyText"], fontName=font_name,
        fontSize=8.5, leading=11, textColor=colors.HexColor("#33485a"),
        alignment=TA_RIGHT if is_arabic else TA_LEFT,
    )
    story.append(Paragraph(text(labels["title"]), title_style))

    patient = report["patient_summary"]
    story.append(Paragraph(text(labels["summary"]), section_style))
    summary = [
        [text(labels["age"]), str(patient.get("age_years") or "—"), text(labels["gender"]), text(patient.get("gender") or "—")],
        [text(labels["context"]), Paragraph(text(patient["admission_context"]), body_style), "", ""],
    ]
    summary_table = Table(summary, colWidths=[1.2 * inch, 1.5 * inch, 1.1 * inch, 2.8 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f7")),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#edf3f7")),
        ("SPAN", (1, 1), (3, 1)),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2e9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)

    assessment = report["sepsis_assessment"]
    completeness = assessment["data_completeness"]
    story.append(Paragraph(text(labels["risk"]), section_style))
    risk_rows = [
        [text(labels["risk_tier"]), text({"Low": "منخفض", "Medium": "متوسط", "High": "مرتفع"}.get(assessment["risk_tier"], assessment["risk_tier"]) if is_arabic else assessment["risk_tier"]),
         text(labels["score"]), f'{assessment["model_probability"]:.1%}'],
        [text(labels["completeness"]), f'{completeness["score"]:.1%}',
         text(labels["features"]), f'{completeness["provided_feature_count"]}/{completeness["required_feature_count"]}'],
    ]
    risk_table = Table(risk_rows, colWidths=[1.45 * inch, 1.7 * inch, 1.55 * inch, 1.9 * inch])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#edf3f7")),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor("#a4434f") if assessment["risk_tier"] == "High" else colors.HexColor("#24735f")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2e9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(risk_table)

    observations = report["vital_signs_and_lab_biomarkers"]["observations"]
    if observations:
        story.append(Paragraph(text(labels["observations"]), section_style))
        observation_rows = [[text(labels["measurement"]), text(labels["value"]), text(labels["reference"])]]
        for item in observations:
            feature = feature_ar.get(item["feature"], item["feature"]) if is_arabic else item["feature"]
            reference = item.get("general_adult_reference_range")
            reference_text = (
                f'{reference["lower"]}–{reference["upper"]} {item.get("unit", "")}'
                if reference else "—"
            )
            observation_rows.append([
                Paragraph(text(feature), body_style),
                Paragraph(text(f'{item["value"]} {item.get("unit") or ""}'), body_style),
                Paragraph(text(reference_text), body_style),
            ])
        observations_table = Table(
            observation_rows,
            colWidths=[2.5 * inch, 1.7 * inch, 2.4 * inch],
            repeatRows=1,
        )
        observations_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0f5")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2e9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(observations_table)

    contributions = report["explainable_ai"]["top_contributing_factors"][:5]
    story.append(Paragraph(text(labels["shap"]), section_style))
    shap_rows = [[text(labels["feature"]), text(labels["impact"])]]
    for factor in contributions:
        feature = feature_ar.get(factor["feature"], factor["feature"]) if is_arabic else factor["feature"]
        shap_rows.append([
            Paragraph(text(feature), body_style),
            f'{factor["impact"]:+.4f} · {text(labels["direction_up"] if factor["impact"] >= 0 else labels["direction_down"])}',
        ])
    shap_table = Table(shap_rows, colWidths=[3.5 * inch, 3.1 * inch], repeatRows=1)
    shap_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0f5")),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8e2e9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(shap_table)

    image = report["medical_image_review"]
    story.append(Paragraph(text(labels["image"]), section_style))
    image_status = image["status"]
    if image_status == "not_provided":
        story.append(Paragraph(text(labels["no_image"]), body_style))
    else:
        image_summary = image.get("clinical_summary") or image.get("findings") or labels["no_image"]
        story.append(Paragraph(text(image_summary), body_style))
        if image.get("infection_site"):
            site_label = "Infection site" if not is_arabic else "موضع العدوى"
            story.append(Paragraph(f"{text(site_label)}: {text(image['infection_site'])}", body_style))
        if image.get("confidence_score") is not None:
            score_label = "Screening score" if not is_arabic else "درجة الفحص"
            story.append(Paragraph(f"{text(score_label)}: {image['confidence_score']:.1f}/100", body_style))

    recommendations = report["clinical_recommendations"]
    story.append(Paragraph(text(labels["guidance"]), section_style))
    for heading, key in (
        (labels["actions"], "immediate_medical_action_bundle"),
        (labels["follow_up"], "lab_and_imaging_follow_up"),
    ):
        story.append(Paragraph(text(heading), body_style))
        for recommendation in recommendations[key]:
            story.append(Paragraph(f"• {text(recommendation)}", body_style))
            story.append(Spacer(1, 2))

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.95 * inch,
        title=labels["title"],
        author="AURA Sepsis AI",
    )
    footer_style = ParagraphStyle(
        "PatientReportFooter",
        fontName=font_name,
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#536879"),
        alignment=TA_RIGHT if is_arabic else TA_LEFT,
    )

    def draw_footer(canvas, pdf_document) -> None:
        approved = assessment["deployment_status"] == "clinically_approved"
        status_text = labels["status_approved"] if approved else labels["status_research"]
        status = Paragraph(text(status_text), footer_style)
        notice = Paragraph(text(labels["notice"]), footer_style)
        footer_width = pdf_document.width - 18
        _, status_height = status.wrap(footer_width, 0.65 * inch)
        _, notice_height = notice.wrap(footer_width, 0.65 * inch)
        x = pdf_document.leftMargin + 9
        y = 0.23 * inch
        box_height = status_height + notice_height + 16
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#f3f6f8"))
        canvas.setStrokeColor(colors.HexColor("#d8e2e9"))
        canvas.roundRect(pdf_document.leftMargin, y - 5, pdf_document.width, box_height, 5, stroke=1, fill=1)
        status.drawOn(canvas, x, y + notice_height + 3)
        notice.drawOn(canvas, x, y)
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output.getvalue()


@app.post("/export-patient-report-pdf")
def export_patient_report_pdf(request: PatientReportExportRequest) -> Response:
    report = generate_full_report(
        FullReportRequest(
            vitals=request.vitals,
            image_validation=request.image_validation,
        )
    )
    content = create_patient_pdf_report(report, lang=request.lang)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="Sepsis_Patient_Report.pdf"'
        },
    )


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest) -> AuthResponse:
    connection = _auth_connection()
    try:
        if connection.execute("SELECT 1 FROM users WHERE username = ?", (request.username,)).fetchone():
            raise HTTPException(status_code=409, detail="Username is already registered.")
        connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (request.username, _password_hash(request.password), request.role, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    return AuthResponse(access_token=_token_encode(request.username, request.role), username=request.username, role=request.role)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: LoginRequest) -> AuthResponse:
    connection = _auth_connection()
    try:
        row = connection.execute("SELECT * FROM users WHERE username = ?", (request.username,)).fetchone()
    finally:
        connection.close()
    if not row or not _password_matches(request.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return AuthResponse(access_token=_token_encode(row["username"], row["role"]), username=row["username"], role=row["role"])


@app.post("/api/auth/users", response_model=AuthResponse, status_code=201)
def admin_create_user(
    request: AdminCreateUserRequest,
    user: dict[str, str] = Depends(_current_user),
) -> AuthResponse:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign elevated roles.")
    connection = _auth_connection()
    try:
        if connection.execute("SELECT 1 FROM users WHERE username = ?", (request.username,)).fetchone():
            raise HTTPException(status_code=409, detail="Username is already registered.")
        connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (request.username, _password_hash(request.password), request.role, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    return AuthResponse(access_token=_token_encode(request.username, request.role), username=request.username, role=request.role)


@app.post("/api/ai/chat", response_model=GeminiChatResponse)
def ai_chat(request: GeminiChatRequest, user: dict[str, str] = Depends(_current_user)) -> GeminiChatResponse:
    if request.patient_id and user["role"] not in {"admin", "doctor", "nurse", "researcher"}:
        raise HTTPException(status_code=403, detail="Your role cannot use patient context.")
    if request.patient_id and not request.patient_context_consent:
        raise HTTPException(status_code=400, detail="Explicit patient-context consent is required.")
    knowledge, sources = _retrieve_project_context(request.messages[-1].content)
    context = knowledge or "No matching reviewed project source was found."
    if request.patient_id:
        context += "\n\n" + _deidentified_patient_context(request.patient_id)
    message, model = _call_gemini(request.messages, context, request.tool_results)
    connection = _auth_connection()
    try:
        connection.execute(
            "INSERT INTO ai_audit_log VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid4()), user["username"], user["role"], request.patient_id, int(bool(request.patient_id)), datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    return GeminiChatResponse(message=message, model=model, sources=sources)


@app.get("/")
def home():
    service = get_sepsis_service()
    deployment_approved = service.clinically_approved
    return {
        "message": "Sepsis prediction API is available for research use only."
        if not deployment_approved
        else "Sepsis prediction API is clinically approved.",
        "model_version": service.metadata.get("model_version", "unknown"),
        "service_status": "online",
        "clinical_status": "approved" if deployment_approved else "research_only",
        "deployment_approved": deployment_approved,
    }


@app.get("/api/patients", response_model=list[PatientRecord])
def list_patients() -> list[PatientRecord]:
    """List patient directory entries from the configured storage backend."""
    if _patient_storage_backend() == "supabase":
        try:
            response = _get_supabase_client().table("patients").select("*").order(
                "created_at",
                desc=True,
            ).execute()
            return [_supabase_patient_record(row) for row in response.data]
        except HTTPException:
            raise
        except Exception as error:
            raise _patient_store_unavailable(error) from error

    connection = _connect_patient_database()
    try:
        rows = connection.execute(
            "SELECT * FROM patients ORDER BY created_at DESC, patient_id"
        ).fetchall()
        return [_patient_record(row) for row in rows]
    finally:
        connection.close()


@app.post("/api/patients", response_model=PatientRecord, status_code=201)
def create_patient(request: PatientCreateRequest) -> PatientRecord:
    """Create a patient directory entry in the configured storage backend."""
    name = request.name.strip()
    bed_number = request.bed_number.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Patient name cannot be blank.")
    if not bed_number:
        raise HTTPException(status_code=422, detail="Bed number cannot be blank.")

    created_at = datetime.now(timezone.utc).isoformat()
    vital_signs = {
        "Age": float(request.age),
        "Gender": 1.0 if request.gender == "Male" else 0.0,
    }

    if _patient_storage_backend() == "supabase":
        row = {
            "name": name,
            "age": request.age,
            "bed_number": bed_number,
            "gender": request.gender,
            "risk_tier": "Not assessed",
            "vital_signs": vital_signs,
            "created_at": created_at,
        }
        try:
            response = _get_supabase_client().table("patients").insert(row).execute()
            if not response.data:
                raise RuntimeError("Supabase returned no row after patient creation.")
            return _supabase_patient_record(response.data[0])
        except HTTPException:
            raise
        except Exception as error:
            raise _patient_store_unavailable(error) from error

    patient_id = uuid4().hex
    connection = _connect_patient_database()
    try:
        connection.execute(
            """
            INSERT INTO patients (patient_id, name, age, bed_number, gender, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                name,
                request.age,
                bed_number,
                request.gender,
                created_at,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return PatientRecord(
        patient_id=patient_id,
        name=name,
        age=request.age,
        bed_number=bed_number,
        gender=request.gender,
        vital_signs=vital_signs,
        created_at=created_at,
    )


@app.get("/api/patients/{patient_id}", response_model=PatientRecord)
def get_patient(patient_id: str) -> PatientRecord:
    """Return a patient directory entry by its opaque identifier."""
    if _patient_storage_backend() == "supabase":
        try:
            response = _get_supabase_client().table("patients").select("*").eq(
                "patient_id",
                patient_id,
            ).limit(1).execute()
            if not response.data:
                raise HTTPException(status_code=404, detail="Patient not found.")
            return _supabase_patient_record(response.data[0])
        except HTTPException:
            raise
        except Exception as error:
            raise _patient_store_unavailable(error) from error

    connection = _connect_patient_database()
    try:
        row = connection.execute(
            "SELECT * FROM patients WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return _patient_record(row)


def simulated_value(mean: float, spread: float, minimum: float, maximum: float, digits: int = 1) -> float:
    value = min(maximum, max(minimum, random.gauss(mean, spread)))
    return round(value, digits)


@app.get("/simulate-sensor")
def simulate_sensor(condition: Literal["stable", "deteriorating"] = "stable"):
    """Return synthetic demo readings; these are not connected to patient devices."""
    if condition == "deteriorating":
        heart_rate = simulated_value(116, 8, 100, 140, 0)
        oxygen = simulated_value(91, 2, 85, 94, 0)
        temperature = simulated_value(38.8, 0.4, 38.0, 40.0)
        systolic = simulated_value(91, 8, 75, 105, 0)
        diastolic = simulated_value(56, 6, 42, 68, 0)
        respiratory = simulated_value(27, 3, 22, 34, 0)
        wbc = simulated_value(17, 3, 12, 25)
        platelets = simulated_value(118, 24, 70, 160, 0)
    else:
        heart_rate = simulated_value(76, 5, 60, 95, 0)
        oxygen = simulated_value(97, 1, 94, 100, 0)
        temperature = simulated_value(36.8, 0.2, 36.3, 37.4)
        systolic = simulated_value(120, 7, 100, 140, 0)
        diastolic = simulated_value(75, 5, 60, 90, 0)
        respiratory = simulated_value(16, 2, 12, 20, 0)
        wbc = simulated_value(8, 1.5, 4, 11)
        platelets = simulated_value(240, 30, 150, 400, 0)

    readings = {
        "HR": heart_rate,
        "O2Sat": oxygen,
        "Temp": temperature,
        "SBP": systolic,
        "MAP": round((systolic + 2 * diastolic) / 3, 1),
        "DBP": diastolic,
        "Resp": respiratory,
        "Age": 64.0,
        "Gender": 1,
        "ICULOS": 12,
        "WBC": wbc,
        "Platelets": platelets,
    }
    return {
        "simulation_only": True,
        "condition": condition,
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "readings": readings,
    }


LAB_LABEL_PATTERNS = {
    "WBC": r"\b(?:WBC|white\s+blood\s+cells?|leukocytes?)\b",
    "Platelets": r"\b(?:platelets?|PLT)\b",
    "Temp": r"\b(?:temperature|temp)\b",
    "HR": r"\b(?:heart\s+rate|HR|pulse)\b",
}
LAB_VALUE_LIMITS = {
    "WBC": (0.1, 300.0),
    "Platelets": (1.0, 3000.0),
    "Temp": (25.0, 45.0),
    "HR": (20.0, 250.0),
}


def parse_ocr_lab_values(ocr_text: str) -> dict[str, float]:
    extracted = {}
    number_pattern = r"([-+]?\d+(?:[.,]\d+)?)"
    for line in ocr_text.splitlines():
        for feature, label_pattern in LAB_LABEL_PATTERNS.items():
            label = re.search(label_pattern, line, flags=re.IGNORECASE)
            if not label:
                continue

            remaining_text = line[label.end():]
            value_match = re.search(rf"[:=]\s*{number_pattern}", remaining_text)
            if not value_match:
                value_match = re.match(rf"\s+{number_pattern}(?:\s|$)", remaining_text)
            if value_match:
                value = float(value_match.group(1).replace(",", "."))
                minimum, maximum = LAB_VALUE_LIMITS[feature]
                if minimum <= value <= maximum:
                    extracted[feature] = value
            break
    return extracted


_EASYOCR_READER = None


def run_lab_ocr(image_bytes: bytes) -> tuple[dict[str, float] | None, str | None, str | None]:
    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            if source_image.width * source_image.height > 25_000_000:
                return None, "Image dimensions exceed the OCR processing limit.", None
            image = source_image.convert("RGB")
            image.thumbnail((2600, 2600))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        return None, f"Image preprocessing failed ({type(error).__name__}).", None

    try:
        import easyocr

        global _EASYOCR_READER
        if _EASYOCR_READER is None:
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        recognized_lines = _EASYOCR_READER.readtext(
            np.asarray(image), detail=0, paragraph=True
        )
        ocr_text = "\n".join(str(line) for line in recognized_lines)
        return parse_ocr_lab_values(ocr_text), None, "EasyOCR"
    except ImportError:
        pass
    except Exception as easyocr_error:
        easyocr_failure = type(easyocr_error).__name__
    else:
        easyocr_failure = ""

    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        ocr_text = pytesseract.image_to_string(image.convert("L"), config="--psm 6")
        return parse_ocr_lab_values(ocr_text), None, "Tesseract"
    except ImportError:
        fallback_failure = "pytesseract is not installed"
    except Exception as tesseract_error:
        fallback_failure = f"Tesseract unavailable ({type(tesseract_error).__name__})"

    easyocr_detail = locals().get("easyocr_failure", "EasyOCR is not installed")
    return None, f"{easyocr_detail}; {fallback_failure}.", None


def analyze_chest_xray(image_bytes: bytes) -> dict | None:
    if xray_model is None or xray_transform is None:
        return None

    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            grayscale = source_image.convert("L")
            image_tensor = xray_transform(grayscale)
        # TorchXRayVision expects the grayscale [0, 1] image mapped to [-1024, 1024].
        model_input = ((image_tensor * 2.0) - 1.0).mul(1024.0).unsqueeze(0)
        with torch.inference_mode():
            outputs = xray_model(model_input).squeeze(0).cpu()
    except Exception:
        return None

    pathology_indices = {name: index for index, name in enumerate(xray_model.pathologies)}
    if any(name not in pathology_indices for name in XRAY_TARGETS):
        return None

    target_scores = {
        name: round(float(outputs[pathology_indices[name]]) * 100.0, 1)
        for name in XRAY_TARGETS
    }
    top_finding = max(target_scores, key=target_scores.get)
    top_score = target_scores[top_finding]
    above_operating_point = top_score >= 50.0
    if above_operating_point:
        findings = f"{top_finding} screening signal above the model operating point ({top_score:.1f}/100)."
        infection_site = (
            "Pleural space / thorax; laterality not determined"
            if top_finding == "Effusion"
            else "Pulmonary / thoracic region; laterality not determined"
        )
        clinical_summary = (
            f"The screening model flagged {top_finding}. This is not a confirmed infection or sepsis source; "
            "correlate with the clinical examination and a radiologist's interpretation."
        )
    else:
        findings = f"No selected target finding exceeded the model operating point; highest score: {top_finding} ({top_score:.1f}/100)."
        infection_site = None
        clinical_summary = (
            "The screening model did not flag a selected target finding above its operating point. "
            "This does not rule out disease and is not a sepsis assessment."
        )

    return {
        "analysis_status": "xray_analyzed",
        "analysis_type": "xray",
        "detected_content_type": "xray",
        "findings": findings,
        "infection_site": infection_site,
        "confidence_score": top_score,
        "confidence_note": "Normalized TorchXRayVision operating-point score (0-100), not calibrated diagnostic confidence or disease probability.",
        "target_scores": target_scores,
        "model_name": "torchxrayvision densenet121-res224-all",
        "clinical_summary": clinical_summary,
        "recommendations": [
            "Request review by a qualified radiologist or treating clinician; verify the image quality and projection.",
            "Correlate screening findings with the patient's clinical context; this model does not diagnose infection or prescribe antibiotics.",
        ],
    }


@app.post("/analyze-medical-image")
async def analyze_medical_image(
    request: Request,
    analysis_type: Literal["auto", "xray", "lab"] = Query(default="auto"),
):
    """Validate an image and optionally OCR a lab report; X-ray inference needs validated weights."""
    max_bytes = 10 * 1024 * 1024
    image_bytes = bytearray()
    async for chunk in request.stream():
        if len(image_bytes) + len(chunk) > max_bytes:
            raise HTTPException(status_code=413, detail="Image exceeds the 10 MB upload limit.")
        image_bytes.extend(chunk)

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Upload an image file to continue.")

    try:
        with Image.open(BytesIO(image_bytes)) as uploaded_image:
            image_format = uploaded_image.format
            uploaded_image.verify()
        with Image.open(BytesIO(image_bytes)) as uploaded_image:
            width, height = uploaded_image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=415, detail="The uploaded file is not a supported, valid image.") from error

    if image_format not in {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}:
        raise HTTPException(status_code=415, detail="Supported image formats: JPEG, PNG, WEBP, BMP, and TIFF.")

    extracted_vitals: dict[str, float] = {}
    prediction_preview = None
    ocr_engine = None
    xray_result = None

    if analysis_type == "xray":
        xray_result = analyze_chest_xray(bytes(image_bytes))
        if xray_result:
            analysis_status = "xray_analyzed"
            detected_content_type = "xray"
            clinical_summary = xray_result["clinical_summary"]
            recommendations = xray_result["recommendations"]
        else:
            analysis_status = "xray_model_unavailable"
            detected_content_type = "xray"
            clinical_summary = "The X-ray model is unavailable or inference failed. No image findings were generated."
            recommendations = [
                "Check that the pretrained TorchXRayVision weights loaded correctly and request a radiologist's interpretation.",
                "No infection site, diagnostic confidence, or medication recommendation is available.",
            ]
    else:
        extracted_vitals, ocr_error, ocr_engine = run_lab_ocr(bytes(image_bytes))
        if ocr_error:
            analysis_status = "ocr_unavailable"
            detected_content_type = None
            clinical_summary = "The image was validated, but lab-report OCR could not run in this environment. No values were extracted."
            recommendations = [
                "Install the optional OCR dependencies from "
                "backend/requirements-ocr.txt and restart the API.",
                "Verify all manually entered or OCR-extracted values against the original laboratory report.",
            ]
            extracted_vitals = {}
        elif extracted_vitals:
            analysis_status = "ocr_extracted"
            detected_content_type = "lab_report"
            clinical_summary = "OCR found candidate laboratory/vital values. Verify every value against the source image before clinical use."
            recommendations = [
                "Confirm each extracted value and unit against the original report before applying it to the patient record.",
                "The model output from OCR values is only a preview and is not a diagnosis or treatment recommendation.",
            ]
            prediction_preview = build_prediction(PatientVitals(**extracted_vitals))
        else:
            analysis_status = "ocr_no_values"
            detected_content_type = "lab_report" if analysis_type == "lab" else None
            clinical_summary = "OCR did not identify supported labeled values. No X-ray classification was attempted."
            recommendations = [
                "Check image orientation, legibility, and whether the selected type matches the file.",
                "Transcribe and verify values manually if they are needed for assessment.",
            ]

    return {
        "analysis_status": analysis_status,
        "analysis_type": analysis_type,
        "detected_content_type": detected_content_type,
        "image_format": image_format,
        "image_dimensions": {"width": width, "height": height},
        "file_size_bytes": len(image_bytes),
        "findings": xray_result["findings"] if xray_result else None,
        "infection_site": xray_result["infection_site"] if xray_result else None,
        "confidence_score": xray_result["confidence_score"] if xray_result else None,
        "confidence_note": xray_result["confidence_note"] if xray_result else None,
        "target_scores": xray_result["target_scores"] if xray_result else {},
        "model_name": xray_result["model_name"] if xray_result else None,
        "clinical_summary": clinical_summary,
        "recommendations": recommendations,
        "extracted_vitals": extracted_vitals,
        "sepsis_prediction_preview": prediction_preview,
        "ocr_engine": ocr_engine,
        "prediction_updated": False,
        "message": clinical_summary,
    }

@app.post("/predict")
def predict_sepsis(vitals: PatientVitals):
    return build_prediction(vitals)


def build_prediction(vitals: PatientVitals):
    submitted_values = vitals.model_dump(include=vitals.model_fields_set)
    try:
        return get_sepsis_service().predict(submitted_values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

def build_clinical_recommendations(
    probability: float,
    image_status: str,
    medium_threshold: float = 0.35,
    high_threshold: float = 0.70,
):
    if probability >= high_threshold:
        risk_band = "High Risk"
        immediate_actions = [
            "Request prompt in-person review by the treating clinician and verify the current observations against the patient record.",
            "If clinical concern is present, follow the institution's sepsis screening and escalation pathway.",
            "Clinical monitoring and any further actions remain the responsibility of the treating team.",
        ]
        follow_up = [
            "Review available CBC, metabolic results, lactate, and cultures in their clinical context; repeat or order tests only when directed by the treating clinician or local protocol.",
        ]
    elif probability >= medium_threshold:
        risk_band = "Moderate Risk"
        immediate_actions = [
            "Arrange timely clinician review and compare the current observations with the patient's baseline and recent trend.",
            "Escalate according to local protocol if the patient is deteriorating or the treating team is concerned.",
        ]
        follow_up = [
            "Review recent laboratory results and trends; repeat testing only when clinically indicated by the treating team or local protocol.",
        ]
    else:
        risk_band = "Low Risk"
        immediate_actions = [
            "No immediate action is inferred from this model score alone; continue the clinician's existing monitoring plan.",
            "Reassess promptly if the patient's condition changes or clinical concern persists despite a low model estimate.",
        ]
        follow_up = [
            "No automatic repeat testing is recommended by this report; follow the existing clinical plan and local protocol.",
        ]

    if image_status == "xray_analyzed":
        follow_up.append(
            "The chest X-ray model flagged a screening finding; obtain qualified radiology review and correlate clinically. This result does not confirm an infection source or prescribe treatment."
        )
    elif image_status in {"preview_only", "xray_model_unavailable"}:
        follow_up.append(
            "The uploaded image was validated for preview only. No imaging findings or infection site are available; obtain qualified radiology or clinician review if imaging is clinically indicated."
        )
    elif image_status == "ocr_extracted":
        follow_up.append(
            "OCR produced candidate lab values only. Verify them against the source report; no radiological interpretation was performed."
        )
    elif image_status in {"ocr_unavailable", "ocr_no_values", "unrecognized_image"}:
        follow_up.append(
            "No laboratory values were extracted. Review the image manually and verify any transcribed values against the source document."
        )
    else:
        follow_up.append("No image was attached; imaging should be considered only by the treating clinician when clinically indicated.")

    return {
        "risk_band": risk_band,
        "threshold_note": (
            f"Configured model-score bands: Low <{medium_threshold:.0%}, "
            f"Moderate {medium_threshold:.0%}–<{high_threshold:.0%}, "
            f"High ≥{high_threshold:.0%}. These thresholds are not clinically validated."
        ),
        "immediate_medical_action_bundle": immediate_actions,
        "lab_and_imaging_follow_up": follow_up,
        "medical_disclaimer": "For clinician review only. This software does not diagnose, order tests, or prescribe treatment. Verify the record and use clinical judgment and local protocols.",
    }


@app.post("/generate-full-report")
def generate_full_report(request: FullReportRequest):
    vitals = request.vitals
    prediction = build_prediction(vitals)
    data = vitals.model_dump(include=vitals.model_fields_set)
    reference_ranges = {
        "HR": ("bpm", 60, 100),
        "O2Sat": ("%", 94, 100),
        "Temp": ("°C", 36.5, 37.5),
        "SBP": ("mmHg", 90, 120),
        "DBP": ("mmHg", 60, 80),
        "MAP": ("mmHg", 70, 100),
        "Resp": ("breaths/min", 12, 20),
        "WBC": ("×10⁹/L", 4, 11),
        "Platelets": ("×10⁹/L", 150, 400),
    }
    observations = []
    for feature, value in data.items():
        reference = reference_ranges.get(feature)
        value_label = "Male" if feature == "Gender" and value == 1 else "Female" if feature == "Gender" else value
        unit = {"Age": "years", "Gender": "coded value (1=Male, 0=Female)", "ICULOS": "hours"}.get(feature, "")
        observation = {"feature": feature, "value": value_label, "unit": unit}
        if reference:
            unit, lower, upper = reference
            observation.update({
                "unit": unit,
                "general_adult_reference_range": {"lower": lower, "upper": upper},
                "relative_to_reference": "within broad reference" if lower <= value <= upper else "outside broad reference",
            })
        observations.append(observation)

    image_validation = request.image_validation
    if image_validation:
        image_status = image_validation.analysis_status
        if image_status == "xray_analyzed":
            image_clinical_summary = image_validation.clinical_summary or "A screening-model result was supplied; verify it with a radiologist."
            image_recommendations = image_validation.recommendations or [
                "Obtain qualified radiology review and correlate the image with clinical context."
            ]
            image_prediction_preview = None
        elif image_status == "ocr_extracted":
            image_clinical_summary = "OCR extracted candidate laboratory values only. Verify them against the original report; they do not constitute a diagnosis."
            image_recommendations = [
                "Confirm each extracted value and unit against the source report before using it.",
                "Any model estimate from OCR values is a separate preview and must be reviewed by the treating clinician.",
            ]
            image_prediction_preview = (
                build_prediction(PatientVitals(**image_validation.extracted_vitals))
                if image_validation.extracted_vitals else None
            )
        elif image_status == "xray_model_unavailable":
            image_clinical_summary = "No validated chest X-ray classifier is installed; no radiological findings or infection source were identified."
            image_recommendations = [
                "Request interpretation by a qualified radiologist or treating clinician when clinically indicated.",
                "No diagnosis or medication recommendation was generated from the image.",
            ]
            image_prediction_preview = None
        elif image_status == "ocr_unavailable":
            image_clinical_summary = "OCR could not run in this environment. No laboratory values were extracted."
            image_recommendations = [
                "Install the optional Python dependency from "
                "backend/requirements-ocr.txt and the Tesseract OCR executable, "
                "then restart the API.",
                "Verify any transcribed values against the original laboratory report.",
            ]
            image_prediction_preview = None
        else:
            image_clinical_summary = "The image was validated, but no supported labeled lab values were extracted and no X-ray classification was performed."
            image_recommendations = ["Review the image manually and verify any transcribed values against the source document."]
            image_prediction_preview = None

        image_review = {
            "status": image_status,
            "analysis_type": image_validation.analysis_type,
            "image_format": image_validation.image_format,
            "image_dimensions": image_validation.image_dimensions,
            "file_size_bytes": image_validation.file_size_bytes,
            "findings": image_validation.findings,
            "infection_site": image_validation.infection_site,
            "identified_infection_site": image_validation.infection_site,
            "confidence_score": image_validation.confidence_score,
            "confidence_note": image_validation.confidence_note,
            "target_scores": image_validation.target_scores,
            "model_name": image_validation.model_name,
            "clinical_summary": image_clinical_summary,
            "extracted_vitals": image_validation.extracted_vitals,
            "sepsis_prediction_preview": image_prediction_preview,
            "recommendations": image_recommendations,
            "note": image_clinical_summary,
        }
    else:
        image_review = {
            "status": "not_provided",
            "analysis_type": None,
            "findings": None,
            "infection_site": None,
            "identified_infection_site": None,
            "confidence_score": None,
            "clinical_summary": "No medical image was supplied for review.",
            "extracted_vitals": {},
            "sepsis_prediction_preview": None,
            "recommendations": ["No imaging interpretation or recommendation is available because no image was supplied."],
            "note": "No image validation was provided. No imaging diagnosis was generated.",
        }

    thresholds = prediction["risk_thresholds"]
    clinical_recommendations = build_clinical_recommendations(
        prediction["sepsis_probability"],
        image_review["status"],
        medium_threshold=thresholds["medium"],
        high_threshold=thresholds["high"],
    )

    return {
        "report_title": "AURA Sepsis AI - Comprehensive Clinical Decision Support Summary",
        "report_status": "DRAFT - NOT AN OFFICIAL MEDICAL RECORD OR DIAGNOSIS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "patient_summary": {
            "admission_context": "ICU monitoring context supplied by the operator; not independently verified.",
            "age_years": data.get("Age"),
            "gender": (
                "Male" if data["Gender"] == 1 else "Female"
            ) if "Gender" in data else None,
        },
        "vital_signs_and_lab_biomarkers": {
            "observations": observations,
            "reference_note": "Ranges are broad adult references for context only; they are not patient-specific targets or clinical interpretation.",
        },
        "sepsis_assessment": {
            "risk_level": prediction["risk_level"],
            "risk_tier": prediction["risk_tier"],
            "model_probability": prediction["sepsis_probability"],
            "probability_interpretation": prediction["probability_interpretation"],
            "deployment_status": prediction["deployment_status"],
            "model_threshold": prediction["decision_threshold"],
            "prediction": prediction["sepsis_prediction"],
            "data_completeness": prediction["data_completeness"],
            "confidence_metrics": prediction["confidence_metrics"],
            "model_uncertainty_interval": prediction["model_uncertainty_interval"],
            "risk_thresholds": prediction["risk_thresholds"],
            "deployment_status": prediction["deployment_status"],
            "model_version": prediction["model_version"],
            "note": "Model estimate only. It is not a diagnosis and must be interpreted by a qualified clinician.",
        },
        "explainable_ai": {
            "method": "SHAP",
            "top_contributing_factors": prediction["top_contributing_factors"],
            "note": "Feature contributions describe model behavior, not clinical causation.",
        },
        "medical_image_review": image_review,
        "clinical_impression": {
            "diagnosis": None,
            "statement": "No final clinical diagnosis is generated by this decision-support report.",
        },
        "clinical_recommendations": clinical_recommendations,
        "recommended_clinical_review": clinical_recommendations["immediate_medical_action_bundle"]
        + clinical_recommendations["lab_and_imaging_follow_up"],
        "disclaimer": "For research and decision-support review only. Not an official record, diagnosis, or treatment order. Not validated for autonomous monitoring or treatment decisions.",
    }