from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.medical_data.importers.disease_symptom import (
    convert_disease_symptom_tsv,
    write_candidates,
)


class ImportIntegrationTests(unittest.TestCase):
    def test_candidate_file_is_explicitly_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.tsv"
            source.write_text(
                "disease_id\tdisease_label\tsymptom_id\tsymptom_label\n"
                "DOID:820\tmyocarditis\tSYMP:0000061\tinflammation\n",
                encoding="utf-8",
            )
            records, _ = convert_disease_symptom_tsv(source)
            output = root / "processed" / "symptoms" / "candidates.json"
            write_candidates(records, output)
            payload = output.read_text(encoding="utf-8")

        self.assertIn('"content_status": "draft_only"', payload)
        self.assertIn('"clinical_review_required": true', payload)
        self.assertIn('"clinical_symptom_approved": false', payload)
        self.assertNotIn('"content_status": "published"', payload)


if __name__ == "__main__":
    unittest.main()
