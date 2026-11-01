from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.medical_data.importers.disease_symptom import convert_disease_symptom_tsv


class ImportTransformerTests(unittest.TestCase):
    def test_exact_ids_are_preserved_and_duplicates_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "disease-symptom.tsv"
            path.write_text(
                "disease_id\tdisease_label\tsymptom_id\tsymptom_label\n"
                "DOID:1205\t allergic disease \tSYMP:0000900\t allergic reaction \n"
                "DOID:1205\tallergic disease\tSYMP:0000900\tallergic reaction\n"
                "DOID:820\tmyocarditis\tSYMP:0000061\tinflammation\n",
                encoding="utf-8",
            )
            records, report = convert_disease_symptom_tsv(path)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["association_id"], "doid_1205__symp_0000900")
        self.assertEqual(records[0]["condition_name_source_text"], "allergic disease")
        self.assertEqual(records[0]["symptom_source_id"], "SYMP:0000900")
        self.assertRegex(records[0]["imported_at"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertFalse(records[0]["clinical_symptom_approved"])
        self.assertEqual(report["counts"]["duplicate_associations"], 1)
        self.assertFalse(report["live_catalog_eligible"])

    def test_invalid_incomplete_and_empty_data_are_not_filled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "disease-symptom.tsv"
            path.write_text(
                "disease_id\tdisease_label\tsymptom_id\tsymptom_label\n"
                "DOID:1205\tallergic disease\t\t\n"
                "bad-id\tcondition\tSYMP:0000001\tsymptom\n",
                encoding="utf-8",
            )
            records, report = convert_disease_symptom_tsv(path)

        self.assertEqual(records, [])
        self.assertEqual(report["counts"]["incomplete_rows"], 1)
        self.assertEqual(report["counts"]["invalid_disease_ids"], 1)

    def test_wrong_schema_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wrong.tsv"
            path.write_text("condition\tsymptom\nx\ty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Expected TSV columns"):
                convert_disease_symptom_tsv(path)


if __name__ == "__main__":
    unittest.main()
