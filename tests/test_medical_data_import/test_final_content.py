from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.medical_data.importers.final_content import (
    build_final_content,
    build_from_sources,
)


class FinalContentTests(unittest.TestCase):
    def test_builds_only_explicit_facts_and_preserves_exact_relationships(self) -> None:
        output, report = build_final_content(
            [
                {
                    "condition_id": "doid_1205",
                    "condition_en": "allergic disease",
                    "ontology_id": "DOID:1205",
                    "definition_source_text": "A source-authored definition.",
                    "synonyms_en": [],
                    "ontology_parents": [],
                    "external_xrefs": ["ICD10CM:T78.40"],
                    "references": [
                        {
                            "source": "Disease Ontology",
                            "title": "DOID:1205",
                            "url": "https://example.org/doid.obo",
                        }
                    ],
                    "source_release": "v-test",
                    "source_sha256": "abc",
                    "record_type": "disease_ontology_condition",
                    "is_obsolete": False,
                }
            ],
            [
                {
                    "phenotype_id": "HP:0000001",
                    "name_en": "A phenotype concept",
                    "name_ar": None,
                    "record_type": "phenotype_concept",
                    "clinical_symptom": False,
                    "symptom_catalog_eligible": False,
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "clinical_review_required": True,
                }
            ],
            [
                {
                    "coding_system": "ICD-10-CM",
                    "code": "T78.40",
                    "condition_ids": ["doid_1205"],
                    "mapping_status": "source_asserted_unverified",
                    "source": "Disease Ontology ICD10CM xref",
                    "source_urls": ["https://example.org/doid.obo"],
                }
            ],
            [
                {
                    "association_id": "doid_1205__symp_0000900",
                    "condition_source_id": "DOID:1205",
                    "condition_name_source_text": "allergic disease",
                    "symptom_source_id": "SYMP:0000900",
                    "symptom_name_source_text": "allergic reaction",
                    "source": "Disease Ontology",
                    "source_release": "2026-08-31",
                    "source_file_url": "https://example.org/disease-symptom.tsv",
                    "source_sha256": "c" * 64,
                }
            ],
            require_expected_counts=False,
        )

        self.assertEqual(len(output["conditions"]), 1)
        condition = output["conditions"][0]
        self.assertEqual(condition["description"]["long_en"], "A source-authored definition.")
        self.assertIsNone(condition["condition_ar"])
        self.assertIsNone(condition["treatment"])
        self.assertEqual(condition["icd10_crosswalks"][0]["code"], "T78.40")
        self.assertEqual(len(output["symptoms"]), 1)
        self.assertEqual(output["symptoms"][0]["source_symptom_id"], "SYMP:0000900")
        self.assertFalse(output["associations"][0]["clinical_symptom_approved"])
        self.assertEqual(output["associations"][0]["condition_id"], "doid_1205")
        self.assertEqual(report["output_counts"]["associations"], 1)
        self.assertEqual(report["arabic_translation"]["conditions_with_arabic"], 0)

    def test_wrong_source_counts_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unexpected conditions source count"):
            build_final_content([], [], [], [])

    def test_generated_snapshot_has_requested_counts_and_review_gates(self) -> None:
        report = build_from_sources()
        output_dir = Path("data/medical_content/final")
        expected = {
            "conditions": 500,
            "symptoms": 300,
            "phenotype_concepts": 1000,
            "associations": 2222,
        }
        for collection, count in expected.items():
            records = json.loads((output_dir / f"{collection}.json").read_text(encoding="utf-8"))
            self.assertEqual(len(records), count)
            self.assertTrue(all(record["content_status"] == "draft" for record in records))
            self.assertTrue(all(record["not_for_clinical_use"] for record in records))
        self.assertEqual(report["condition_selection"]["selected_with_source_definition"], 500)
        self.assertEqual(report["output_counts"]["associations"], 2222)
        self.assertEqual(report["arabic_translation"]["conditions_with_arabic"], 0)
        self.assertEqual(report["phenotype_selection"]["clinical_symptoms_asserted"], 0)

    def test_final_records_match_draft_schemas(self) -> None:
        root = Path("data/medical_content")
        pairs = (
            ("final_disease_draft_schema.json", "final/conditions.json"),
            ("final_symptom_term_draft_schema.json", "final/symptoms.json"),
            ("final_phenotype_draft_schema.json", "final/phenotype_concepts.json"),
            ("final_association_draft_schema.json", "final/associations.json"),
        )
        for schema_name, records_path in pairs:
            with self.subTest(records_path=records_path):
                schema = json.loads(
                    (root / "schemas" / schema_name).read_text(encoding="utf-8")
                )
                Draft202012Validator.check_schema(schema)
                validator = Draft202012Validator(schema)
                records = json.loads((root / records_path).read_text(encoding="utf-8"))
                error = next(
                    (
                        (index, validation_error.message)
                        for index, record in enumerate(records)
                        for validation_error in validator.iter_errors(record)
                    ),
                    None,
                )
                self.assertIsNone(error, error)


if __name__ == "__main__":
    unittest.main()
