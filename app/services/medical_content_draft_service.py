"""Read-only access to source-derived medical drafts, never the live catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FINAL_CONTENT_DIR = Path(__file__).resolve().parents[2] / "data" / "medical_content" / "final"
COLLECTION_FILES = {
    "conditions": "conditions.json",
    "symptoms": "symptoms.json",
    "phenotype_concepts": "phenotype_concepts.json",
    "associations": "associations.json",
}
NOTICE_AR = (
    "بيانات بحثية أولية غير مراجعة سريريًا؛ لا تُستخدم للتشخيص أو العلاج. "
    "الحقول العربية غير المتاحة في المصدر تُركت فارغة عمدًا."
)
NOTICE_EN = (
    "Source-derived research drafts; not clinically reviewed and not for diagnosis "
    "or treatment. Arabic values absent from the source are intentionally null."
)


class MedicalContentDraftDataError(RuntimeError):
    """Final review-only data is missing, invalid, or unsafe to expose."""


class MedicalContentDraftService:
    """Load final draft snapshots and enforce their non-clinical status."""

    def __init__(self, content_dir: Path = FINAL_CONTENT_DIR) -> None:
        self.content_dir = content_dir
        self._collections: dict[str, list[dict[str, Any]]] | None = None
        self._by_id: dict[str, dict[str, dict[str, Any]]] | None = None

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if self._collections is not None:
            return self._collections
        loaded: dict[str, list[dict[str, Any]]] = {}
        for collection, filename in COLLECTION_FILES.items():
            path = self.content_dir / filename
            try:
                document = json.loads(path.read_text(encoding="utf-8-sig"))
            except FileNotFoundError as exc:
                raise MedicalContentDraftDataError(
                    f"Review-only medical data file is missing: {path}"
                ) from exc
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise MedicalContentDraftDataError(
                    f"Cannot read review-only medical data file: {path}"
                ) from exc
            if not isinstance(document, list) or any(not isinstance(record, dict) for record in document):
                raise MedicalContentDraftDataError(
                    f"Review-only medical data must be a JSON array of objects: {path}"
                )
            for record in document:
                if (
                    record.get("content_status") != "draft"
                    or record.get("review_status") != "unreviewed"
                    or record.get("clinical_review_required") is not True
                    or record.get("not_for_clinical_use") is not True
                ):
                    raise MedicalContentDraftDataError(
                        f"Refusing to expose a record without the review-only gate: {path}"
                    )
            loaded[collection] = document
        self._collections = loaded
        return loaded

    def _indices(self) -> dict[str, dict[str, dict[str, Any]]]:
        if self._by_id is None:
            key_by_collection = {
                "conditions": "condition_id",
                "symptoms": "symptom_id",
                "phenotype_concepts": "phenotype_id",
                "associations": "association_id",
            }
            indices: dict[str, dict[str, dict[str, Any]]] = {}
            for collection, records in self._load().items():
                key = key_by_collection[collection]
                index: dict[str, dict[str, Any]] = {}
                for record in records:
                    record_id = record.get(key)
                    if not isinstance(record_id, str) or not record_id:
                        raise MedicalContentDraftDataError(
                            f"Missing {key} in review-only {collection} record"
                        )
                    if record_id in index:
                        raise MedicalContentDraftDataError(
                            f"Duplicate {key} in review-only {collection}: {record_id}"
                        )
                    index[record_id] = record
                indices[collection] = index
            self._by_id = indices
        return self._by_id

    def summary(self) -> dict[str, Any]:
        records = self._load()
        return {
            "content_status": "draft_only",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "counts": {collection: len(items) for collection, items in records.items()},
            "clinical_symptom_approved": 0,
            "arabic_translations_available": 0,
            "notice_ar": NOTICE_AR,
            "notice_en": NOTICE_EN,
        }

    def list_records(
        self,
        collection: str,
        offset: int = 0,
        limit: int = 50,
        condition_id: str | None = None,
        symptom_id: str | None = None,
    ) -> dict[str, Any]:
        if collection not in COLLECTION_FILES:
            raise KeyError(f"Unknown medical draft collection: {collection}")
        records = self._load()[collection]
        if collection == "associations":
            if condition_id is not None:
                records = [
                    record for record in records
                    if record.get("condition_id") == condition_id
                    or record.get("condition_source_id") == condition_id
                ]
            if symptom_id is not None:
                records = [
                    record for record in records
                    if record.get("symptom_id") == symptom_id
                    or record.get("symptom_source_id") == symptom_id
                ]
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
        if collection not in COLLECTION_FILES:
            raise KeyError(f"Unknown medical draft collection: {collection}")
        key = {
            "conditions": "condition_id",
            "symptoms": "symptom_id",
            "phenotype_concepts": "phenotype_id",
            "associations": "association_id",
        }[collection]
        record = self._indices()[collection].get(record_id)
        if record is None:
            return None
        return {
            "collection": collection,
            "record": record,
            "record_id": record_id,
            "identifier_field": key,
            "content_status": "draft_only",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "notice_ar": NOTICE_AR,
            "notice_en": NOTICE_EN,
        }


medical_content_draft_service = MedicalContentDraftService()
