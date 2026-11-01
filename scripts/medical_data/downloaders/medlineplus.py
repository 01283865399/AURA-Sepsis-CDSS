"""MedlinePlus Connect code-lookup client (not a bulk condition database)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

from scripts.medical_data.downloaders.base import BaseDownloader, DownloadError


class MedlinePlusDownloader(BaseDownloader):
    BASE_URL = "https://connect.medlineplus.gov/service"
    ICD10CM_OID = "2.16.840.1.113883.6.90"
    SUPPORTED_LANGUAGES = {"en", "es"}
    MAX_CODES_PER_RUN = 500
    LOGGER = logging.getLogger(__name__)

    def __init__(self, raw_root, **kwargs):
        super().__init__("medlineplus", raw_root, **kwargs)

    @staticmethod
    def _atom_value(value: Any) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            result = value.get("_value")
            if isinstance(result, str):
                return result.strip() or None
        return None

    @classmethod
    def parse_response(cls, data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract the first Connect match without inventing missing fields."""
        feed = data.get("feed")
        if not isinstance(feed, dict):
            raise ValueError("MedlinePlus Connect response has no feed object.")
        entries = feed.get("entry", [])
        if entries is None:
            return None
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            raise ValueError("MedlinePlus Connect feed.entry must be an object or array.")
        if not entries:
            return None
        entry = entries[0]
        if not isinstance(entry, dict):
            raise ValueError("MedlinePlus Connect entry must be an object.")
        feed_author = feed.get("author")
        entry_author = entry.get("author")
        author = entry_author if entry_author is not None else feed_author

        links = entry.get("link", [])
        if isinstance(links, dict):
            links = [links]
        if not isinstance(links, list):
            links = []
        href = next(
            (
                link.get("href")
                for link in links
                if isinstance(link, dict) and isinstance(link.get("href"), str)
            ),
            None,
        )
        if isinstance(author, list):
            author = author[0] if author else None
        author_name = author.get("name") if isinstance(author, dict) else None
        return {
            "title": cls._atom_value(entry.get("title")),
            "summary": cls._atom_value(entry.get("summary")),
            "url": href,
            "updated": cls._atom_value(entry.get("updated"))
            or cls._atom_value(feed.get("updated")),
            "author": cls._atom_value(author_name),
            "attribution": cls._atom_value(entry.get("attribution")),
            "source_record_id": cls._atom_value(entry.get("id")),
        }

    def fetch_condition(self, icd10_code: str, lang: str = "en") -> Any | None:
        if not icd10_code or not icd10_code.strip():
            raise ValueError("A known ICD-10-CM code is required.")
        language = lang.casefold()
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError("MedlinePlus Connect supports en and es; Arabic is not supported by this service.")
        params = {
            "mainSearchCriteria.v.c": icd10_code.strip(),
            "mainSearchCriteria.v.cs": self.ICD10CM_OID,
            "informationRecipient.languageCode.c": language,
            "knowledgeResponseType": "application/json",
        }
        data, final_url = self.request_json(self.BASE_URL, params=params)
        if not isinstance(data, dict):
            raise DownloadError("MedlinePlus Connect returned a non-object JSON response.")
        try:
            self.parse_response(data)
        except ValueError as exc:
            raise DownloadError(str(exc)) from exc
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.save_raw(
            body,
            f"{icd10_code.strip().replace('.', '_')}_{language}.json",
            request_url=f"{self.BASE_URL}?{urlencode(params)}",
            final_url=final_url,
            content_type="application/json",
            license_status="item_level_terms_and_attribution_review_required",
            extra_metadata={"query_code": icd10_code.strip(), "language": language},
        )
        if self.parse_response(data) is None:
            return None
        return data

    def fetch_all(self, icd10_codes: list[str], lang: str = "en") -> dict[str, Any]:
        results: dict[str, Any] = {}
        for index, code in enumerate(dict.fromkeys(icd10_codes)):
            if index:
                time.sleep(0.3)
            data = self.fetch_condition(code, lang=lang)
            if data is not None:
                results[code] = data
        return results

    @staticmethod
    def _codes_for_condition(condition: dict[str, Any]) -> list[str]:
        codes: list[str] = []
        single_code = condition.get("icd10_code")
        if isinstance(single_code, str) and single_code.strip():
            codes.append(single_code.strip())
        multiple_codes = condition.get("icd10_codes", [])
        if isinstance(multiple_codes, list):
            codes.extend(
                code.strip()
                for code in multiple_codes
                if isinstance(code, str) and code.strip()
            )
        crosswalks = condition.get("icd10_crosswalks", [])
        if isinstance(crosswalks, list):
            codes.extend(
                mapping["code"].strip()
                for mapping in crosswalks
                if isinstance(mapping, dict)
                and mapping.get("coding_system") == "ICD-10-CM"
                and isinstance(mapping.get("code"), str)
                and mapping["code"].strip()
            )
        return list(dict.fromkeys(codes))

    def fetch_conditions(
        self,
        conditions: Iterable[dict[str, Any]],
        *,
        languages: tuple[str, ...] = ("en", "es"),
        delay_seconds: float = 0.5,
    ) -> dict[str, dict[str, Any]]:
        """Fetch source links for condition records using exact ICD-10-CM codes."""
        if not 0 <= delay_seconds <= 60:
            raise ValueError("delay_seconds must be between 0 and 60.")
        normalized_languages = tuple(dict.fromkeys(language.casefold() for language in languages))
        if not normalized_languages or any(
            language not in self.SUPPORTED_LANGUAGES for language in normalized_languages
        ):
            raise ValueError("MedlinePlus Connect supports only en and es; Arabic is unsupported.")

        condition_list = list(conditions)
        codes_by_condition: dict[str, list[str]] = {}
        condition_ids_by_code: dict[str, list[str]] = {}
        for condition in condition_list:
            condition_id = condition.get("condition_id")
            if not isinstance(condition_id, str) or not condition_id.strip():
                raise ValueError("Every condition must have a non-empty condition_id.")
            codes = self._codes_for_condition(condition)
            codes_by_condition[condition_id] = codes
            for code in codes:
                condition_ids_by_code.setdefault(code, []).append(condition_id)

        unique_codes = list(condition_ids_by_code)
        if len(unique_codes) > self.MAX_CODES_PER_RUN:
            raise ValueError(
                f"At most {self.MAX_CODES_PER_RUN} unique ICD-10-CM codes can be fetched per run."
            )

        fetched: dict[tuple[str, str], dict[str, Any] | None] = {}
        request_count = len(unique_codes) * len(normalized_languages)
        completed_requests = 0
        for code in unique_codes:
            for language in normalized_languages:
                if completed_requests and delay_seconds:
                    time.sleep(delay_seconds)
                document = self.fetch_condition(code, lang=language)
                fetched[(code, language)] = (
                    self.parse_response(document) if document is not None else None
                )
                completed_requests += 1
                self.LOGGER.info(
                    "MedlinePlus Connect lookup %d/%d completed for %s (%s)",
                    completed_requests,
                    request_count,
                    code,
                    language,
                )

        results: dict[str, dict[str, Any]] = {}
        for condition in condition_list:
            condition_id = condition["condition_id"]
            codes = codes_by_condition[condition_id]
            code_results = []
            for code in codes:
                code_results.append(
                    {
                        "icd10_code": code,
                        "source_condition_ids": condition_ids_by_code[code],
                        "languages": {
                            language: fetched[(code, language)]
                            for language in normalized_languages
                        },
                    }
                )
            results[condition_id] = {
                "condition_id": condition_id,
                "icd10_codes": codes,
                "source": "MedlinePlus Connect",
                "source_url": self.BASE_URL,
                "content_status": "draft",
                "review_status": "unreviewed",
                "clinical_review_required": True,
                "not_for_clinical_use": True,
                "license_status": "item_level_terms_and_attribution_review_required",
                "code_results": code_results,
                "result_status": (
                    "no_icd10_cm_code"
                    if not codes
                    else (
                        "matched"
                        if any(
                            fetched[(code, language)] is not None
                            for code in codes
                            for language in normalized_languages
                        )
                        else "no_medlineplus_match"
                    )
                ),
            }
        return results

    def save_results(
        self,
        results: dict[str, dict[str, Any]],
        filename: str = "medlineplus_condition_results.json",
    ) -> Path:
        """Save normalized lookup results without declaring them public domain."""
        document = {
            "source": "MedlinePlus Connect",
            "source_url": self.BASE_URL,
            "license_status": "item_level_terms_and_attribution_review_required",
            "translation_status": "english_and_spanish_only; no_arabic_connect_response",
            "content_status": "draft",
            "review_status": "unreviewed",
            "clinical_review_required": True,
            "not_for_clinical_use": True,
            "count": len(results),
            "records": results,
        }
        body = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        return self.save_raw(
            body,
            filename,
            request_url=self.BASE_URL,
            content_type="application/json",
            license_status="item_level_terms_and_attribution_review_required",
            extra_metadata={
                "record_count": len(results),
                "artifact_kind": "normalized_lookup_summary",
            },
        )
