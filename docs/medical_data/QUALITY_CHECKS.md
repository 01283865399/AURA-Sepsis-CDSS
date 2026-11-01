# Quality checks

`scripts/import_all_new_data.py` scans all regular files and records their
relative path, byte size, detected format, category, ingestion disposition,
record count when measurable, field names, and format-specific quality facts.
CSV/TSV checks include row widths, blank values, and exact duplicate rows.
JSON roots and list/node counts, XML element counts/parse errors, OBO term
counts, ARFF row widths, and text line counts are recorded where applicable.
UTF-8 replacement characters are counted in decoded tabular/text rows.
Parquet schemas are reported when Parquet assets exist; this audit found none.
The audit found no image files.

Key source-level observations:

- The directory contains 11,629 files across 46 nested directories, totaling
  2,619,352,924 bytes.
- The 248,126-row enriched diagnosis/test CSV contains 57,342 exact duplicate
  rows; every row has a `<think>` reasoning field. These strings are not
  treated as verified rationale.
- The 409-row RAG CSV has 37 missing `source_url` values and 13 missing
  `reading_level_score` values. No missing values were synthesized.
- The MedQuAD XML scan found 47,441 Question and 47,441 Answer elements.
  Elements can be present but empty; per-file nonempty answer counts are in
  the inventory. Ten files contain neither element; reuse restrictions still
  require review.
- The DDXPlus-format file has 1,292,579 six-field data rows. It is a synthetic
  benchmark according to its own header, not evidence for medical advice.
- DO disease/symptom links use exact IDs; all are retained as unreviewed
  candidates and are not available to users.

The full per-file quality data is in
[`new_folder_inventory.csv`](./new_folder_inventory.csv). A row excerpt is not
duplicated into the report. No values are silently coerced or completed.
