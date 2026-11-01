"""Lazy, review-only access to the full multi-source build package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


COMPLETE_CONTENT_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "medical_content"
    / "final"
    / "complete"
)
COLLECTION_FILES = {
    "conditions": "conditions.json",
    "symptoms": "symptoms.json",
    "symptom_terms": "symptom_terms.json",
    "symptom2disease_reports": "symptom2disease_reports.json",
    "associations": "associations.json",
    "qa": "qa.json",
    "icd10_index": "icd10_index.json",
    "specialists": "specialists.json",
    "emergency_signs": "emergency_signs.json",
    "references": "references.json",
}
IDENTIFIER_FIELDS = {
    "conditions": "condition_id",
    "symptoms": "phenotype_id",
    "symptom_terms": "symptom_id",
    "symptom2disease_reports": "report_id",
    "associations": "association_id",
    "qa": "qa_id",
    "icd10_index": "code",
    "references": "reference_id",
}
NOTICE_AR = (
    "حزمة بيانات مصدرية أولية غير مراجعة سريريًا؛ لا تستخدم للتشخيص أو العلاج. "
    "مفاهيم HPO ليست أعراضًا سريرية معتمدة، والترجمات العربية غير متاحة."
)
NOTICE_EN = (
    "Source-derived draft package; not clinically reviewed and not for diagnosis "
    "or treatment. HPO concepts are not approved clinical symptoms; Arabic translations are unavailable."
)


class MedicalContentCompleteDataError(RuntimeError):
    """The complete review-only build is missing or fails its safety gate."""


class MedicalContentCompleteDraftService:
    """Read the complete build without exposing it as published clinical content."""

    def __init__(self, content_dir: Path = COMPLETE_CONTENT_DIR) -> None:
        self.content_dir = content_dir
        self._collections: dict[str, list[dict[str, Any]]] = {}
        self._indices: dict[str, dict[str, dict[str, Any]]] = {}
        self._stats: dict[str, Any] | None = None

    def _load_collection(self, collection: str) -> list[dict[str, Any]]:
        if collection not in COLLECTION_FILES:
            raise KeyError(f"Unknown complete-draft collection: {collection}")
        if collection not in self._collections:
            path = self.content_dir / COLLECTION_FILES[collection]
            try:
                records = json.loads(path.read_text(encoding="utf-8-sig"))
            except FileNotFoundError as exc:
                raise MedicalContentCompleteDataError(
                    f"Complete medical-content collection is missing: {path}"
                ) from exc
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise MedicalContentCompleteDataError(
                    f"Cannot read complete medical-content collection: {path}"
                ) from exc
            if not isinstance(records, list) or any(
                not isinstance(record, dict) for record in records
            ):
                raise MedicalContentCompleteDataError(
                    f"Expected an array of objects in {path}"
                )
            for record in records:
                if (
                    record.get("content_status") != "draft"
                    or record.get("review_status") != "unreviewed"
                    or record.get("clinical_review_required") is not True
                    or record.get("not_for_clinical_use") is not True
                ):
                    raise MedicalContentCompleteDataError(
                        f"Refusing to expose an ungated record from {path}"
                    )
            self._collections[collection] = records
        return self._collections[collection]

    def _load_stats(self) -> dict[str, Any]:
        if self._stats is None:
            path = self.content_dir / "stats.json"
            try:
                stats = json.loads(path.read_text(encoding="utf-8-sig"))
            except FileNotFoundError as exc:
                raise MedicalContentCompleteDataError(
                    f"Complete medical-content statistics are missing: {path}"
                ) from exc
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise MedicalContentCompleteDataError(
                    f"Cannot read complete medical-content statistics: {path}"
                ) from exc
            if (
                not isinstance(stats, dict)
                or stats.get("safety", {}).get("not_for_clinical_use") is not True
            ):
                raise MedicalContentCompleteDataError(
                    "Refusing to expose build statistics without the safety gate."
                )
            self._stats = stats
        return self._stats

    def _get_index(self, collection: str) -> dict[str, dict[str, Any]]:
        if collection not in IDENTIFIER_FIELDS:
            raise KeyError(f"Collection does not support record lookup: {collection}")
        if collection not in self._indices:
            field = IDENTIFIER_FIELDS[collection]
            index: dict[str, dict[str, Any]] = {}
            for record in self._load_collection(collection):
                identifier = record.get(field)
                if not isinstance(identifier, str) or not identifier:
                    raise MedicalContentCompleteDataError(
                        f"Record in {collection} lacks {field}."
                    )
                if identifier in index:
                    raise MedicalContentCompleteDataError(
                        f"Duplicate {field} in {collection}: {identifier}"
                    )
                index[identifier] = record
            self._indices[collection] = index
        return self._indices[collection]

    def summary(self) -> dict[str, Any]:
        stats = self._load_stats()
        return {
            "content_status": "draft_only",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "counts": stats["output_counts"],
            "clinical_symptom_approved": 0,
            "arabic_translations_available": 0,
            "notice_ar": NOTICE_AR,
            "notice_en": NOTICE_EN,
        }

    def list_records(
        self, collection: str, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        records = self._load_collection(collection)
        return {
            "collection": collection,
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "records": records[offset : offset + limit],
            "content_status": "draft_only",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "notice_ar": NOTICE_AR,
            "notice_en": NOTICE_EN,
        }

    def get_record(self, collection: str, record_id: str) -> dict[str, Any] | None:
        record = self._get_index(collection).get(record_id)
        if record is None:
            return None
        return {
            "collection": collection,
            "record": record,
            "record_id": record_id,
            "identifier_field": IDENTIFIER_FIELDS[collection],
            "content_status": "draft_only",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "notice_ar": NOTICE_AR,
            "notice_en": NOTICE_EN,
        }

    def search_qa(
        self, query: str, offset: int = 0, limit: int = 20
    ) -> dict[str, Any]:
        normalized = query.strip().casefold()
        if not normalized:
            return {
                **self.list_records("qa", offset, limit),
                "total": 0,
                "records": [],
                "query": query,
            }
        matches = [
            record
            for record in self._load_collection("qa")
            if normalized in record["question_en"].casefold()
            or normalized in record["answer_en"].casefold()
        ]
        return {
            **self.list_records("qa", 0, 1),
            "total": len(matches),
            "offset": offset,
            "limit": limit,
            "records": matches[offset : offset + limit],
            "query": query,
        }


medical_content_complete_draft_service = MedicalContentCompleteDraftService()
