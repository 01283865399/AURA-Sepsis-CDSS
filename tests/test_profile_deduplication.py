"""Tests for preventing repeated or conflicting profiles from crossing splits."""

from __future__ import annotations

import unittest

import pandas as pd


from scripts._training_common import deduplicate_unambiguous_profiles


class ProfileDeduplicationTests(unittest.TestCase):
    def test_repeated_profiles_are_collapsed_and_conflicts_removed(self) -> None:
        features = pd.DataFrame(
            {
                "symptom_a": [1, 1, 0, 0, 1],
                "symptom_b": [0, 0, 1, 1, 1],
            }
        )
        labels = pd.Series(
            ["condition_a", "condition_a", "condition_b", "condition_c", "condition_b"]
        )

        clean_features, clean_labels, stats = deduplicate_unambiguous_profiles(
            features, labels
        )

        self.assertEqual(len(clean_features), 2)
        self.assertEqual(clean_labels.tolist(), ["condition_a", "condition_b"])
        self.assertEqual(stats["duplicate_rows_removed"], 1)
        self.assertEqual(stats["ambiguous_profiles_removed"], 1)
        self.assertEqual(stats["rows_in_ambiguous_profiles_removed"], 2)
        self.assertEqual(
            pd.util.hash_pandas_object(clean_features, index=False).nunique(), 2
        )

    def test_mismatched_feature_and_label_rows_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "row counts do not match"):
            deduplicate_unambiguous_profiles(
                pd.DataFrame({"feature": [1]}), pd.Series([0, 1])
            )


if __name__ == "__main__":
    unittest.main()
