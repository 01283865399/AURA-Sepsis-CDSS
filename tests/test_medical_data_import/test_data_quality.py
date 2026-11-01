from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.medical_data.importers.audit import classify_path, scan_tree


class ImportDataQualityTests(unittest.TestCase):
    def test_scan_captures_table_schema_missing_data_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.csv").write_text(
                "id,value\n1,ok\n1,ok\n2,\n",
                encoding="utf-8",
            )
            report = scan_tree(root)

        self.assertEqual(report["file_count"], 1)
        item = report["files"][0]
        self.assertEqual(item["detected_type"], "csv")
        self.assertEqual(item["records"], 3)
        self.assertEqual(item["fields"], ["id", "value"])
        self.assertEqual(item["quality"]["duplicate_rows"], 1)
        self.assertEqual(item["quality"]["missing_values"], {"value": 1})

    def test_scan_counts_json_missing_fields_and_empty_xml_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.json").write_text(
                '{"records":[{"id":"one","name":"term"},{"id":"two","name":""}]}',
                encoding="utf-8",
            )
            (root / "sample.xml").write_text(
                "<Document><Question>Question text</Question><Answer/></Document>",
                encoding="utf-8",
            )
            report = scan_tree(root)

        by_path = {item["path"]: item for item in report["files"]}
        self.assertEqual(by_path["sample.json"]["records"], 2)
        self.assertEqual(
            by_path["sample.json"]["quality"]["missing_values_in_object_records"],
            {"name": 1},
        )
        self.assertEqual(by_path["sample.xml"]["quality"]["nonempty_question_elements"], 1)
        self.assertEqual(by_path["sample.xml"]["quality"]["nonempty_answer_elements"], 0)
        self.assertEqual(by_path["sample.xml"]["quality"]["empty_answers"], 1)

    def test_scan_reports_arff_schema_and_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "dataset_").write_text(
                "@RELATION test\n"
                "@ATTRIBUTE AGE INTEGER\n"
                "@ATTRIBUTE PATHOLOGY STRING\n"
                "@DATA\n"
                "22,'example'\n"
                "?,?\n",
                encoding="utf-8",
            )
            report = scan_tree(root)

        item = report["files"][0]
        self.assertEqual(item["detected_type"], "arff")
        self.assertEqual(item["records"], 2)
        self.assertEqual(item["fields"], ["AGE", "PATHOLOGY"])
        self.assertEqual(item["quality"]["missing_values"], {"AGE": 1, "PATHOLOGY": 1})

    def test_known_medical_datasets_are_gated(self) -> None:
        cases = {
            "dataset_": ("other", "research_only"),
            "archive (1)/combined_diseases_symptoms_2_enriched_with_exams_v2.csv": (
                "other",
                "clinical_validation_blocked",
            ),
            "archive (2)/healthcare_rag_dataset.csv": (
                "other",
                "source_validation_blocked",
            ),
            "MedQuAD-master/MedQuAD-master/2_GARD_QA/one.xml": (
                "qa",
                "rights_review_required",
            ),
            "HumanDiseaseOntology/reports/requested/disease-symptom.tsv": (
                "symptoms",
                "review_candidate",
            ),
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                classification = classify_path(path)
                self.assertEqual(
                    (classification["category"], classification["disposition"]),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
