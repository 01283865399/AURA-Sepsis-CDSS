# New-folder import coverage

Audit performed on 2026-10-05 from the local `New folder` directory.

| Content | Observed | Staged | Live/API |
|---|---:|---:|---:|
| Files / directories | 11,629 / 46 | inventory only | no |
| DDXPlus synthetic benchmark rows | 1,292,579 | 0 | 0 |
| Enriched diagnosis/test CSV rows | 248,126 | 0 | 0 |
| Mixed RAG CSV documents | 409 | 0 | 0 |
| MedQuAD question-answer elements | 47,441 / 47,441; only 16,407 answer elements have text | 0 | 0 |
| Disease Ontology disease-symptom associations | 2,222 rows / 863 diseases / 300 symptom IDs | 2,222 review-only candidates | 0 |
| Other catalog categories (drugs, labs, specialists, emergency) | No independently source-verified candidate identified | 0 | 0 |

The generated `data/medical_content/processed/import_report.json` records exact
candidate, duplicate, invalid-row, and exclusion counts for the association
table and includes a source-file checksum. `docs/medical_data/NEW_FOLDER_AUDIT.md`
summarizes the latest full scan.

These counts measure files/rows, not clinical readiness or predictive
accuracy. Existing live medical-content coverage is intentionally unaffected.
