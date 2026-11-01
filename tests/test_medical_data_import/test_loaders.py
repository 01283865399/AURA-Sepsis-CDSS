from __future__ import annotations

import unittest

from app.services.medical_content_service import MedicalContentService


class ImportLoaderGateTests(unittest.TestCase):
    def test_unreviewed_candidate_is_never_considered_published(self) -> None:
        self.assertFalse(
            MedicalContentService._is_reviewed(
                {
                    "content_status": "draft",
                    "review_status": "unreviewed",
                    "association_status": "source_asserted_unreviewed",
                }
            )
        )

    def test_only_both_publication_and_clinical_review_open_the_gate(self) -> None:
        self.assertTrue(
            MedicalContentService._is_reviewed(
                {
                    "content_status": "published",
                    "review_status": "clinically_reviewed",
                }
            )
        )
        self.assertFalse(
            MedicalContentService._is_reviewed(
                {
                    "content_status": "published",
                    "review_status": "unreviewed",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
