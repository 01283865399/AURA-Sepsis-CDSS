# Symptoms model: data-quality audit

## Current status

The earlier perfect scores recorded for the 4,920-row symptom dataset are not
accepted as reliable estimates of generalization. Repeated symptom profiles can
appear in both sides of a row-wise split, and identical profiles can carry
conflicting disease labels. The earlier report's "ready for use" conclusion is
withdrawn.

The training pipeline now removes conflicting feature profiles, collapses
same-label duplicate profiles, and requires both at least 50 source rows and
10 distinct unambiguous symptom profiles per disease before creating a
stratified train/validation/test split. Each remaining symptom profile therefore
occurs in exactly one split. The results must still be treated as research-only:
the source data is not a prospectively collected clinical cohort and this
procedure does not establish external or clinical validity.

## Audit findings

The local augmented file contains 246,945 rows; the classic training file
contains 4,920 rows. After merging their normalized binary symptom features,
the pipeline observed 12,634 feature profiles associated with more than one
disease label. Those profiles accounted for 39,728 rows and are excluded.
Another 54,579 repeated rows were collapsed. The current thresholds retain 527
disease labels and 156,276 unique profiles for model training and evaluation.

These counts describe data cleaning, not model performance. Updated held-out
metrics are only available after the corrected training job completes and
should not be compared directly with the old leaked-split scores.
