# Build and quality process

## Rebuild

From the repository root:

```powershell
.\venv\Scripts\python.exe -m scripts.medical_data.importers.complete_content
```

The importer validates the seven expected source record counts before
producing output. Each JSON file is written through a temporary sibling file
and atomically replaced. Every output record carries draft, unreviewed,
clinical-review-required, and not-for-clinical-use flags.

## Transformations

1. Include all non-obsolete Disease Ontology terms as condition records.
2. Select 500 content candidates by exact ICD-code-linked Healthcare RAG
   material, explicit DO-SYMP relation count, then source definition and stable
   DOID. This is not a clinical popularity measure. Other terms are lookup-only.
3. Retain RAG content as separate source documents with their claims and
   source-specific URLs; an exact code match is still marked unverified.
4. Select 1,000 HPO terms in stable ID order. Keep `clinical_symptom: false`.
5. Preserve unique SYMP terms and all DO-SYMP links under their original
   identifiers. Do not create an HPO-to-SYMP crosswalk.
6. Keep Symptom2Disease text as narrative examples; do not interpret text as
   validated symptoms or labels as diagnoses.
7. Convert MedQuAD `query`, `answers`, and `group_name` to question, answer,
   and category. IDs use the stable split row number; original item-level URLs
   are absent and remain null.
8. Merge ICD code entries by exact code string. Preserve mappings as source
   assertions, not as independent code validation.
9. Leave unsupported Arabic translations, red flags, specialists, and
   body-system categories unavailable.

`stats.json` contains input counts and checksums, per-field missing/unique
counts for CSV and MedQuAD fields, output counts, duplicate question count,
selection policy, source limitations, and safety gates.

## Release boundary

This build is not a release-ready or clinically complete catalog. Review source
licenses, verify source documents and mappings, perform qualified clinical
review, and commission medically qualified Arabic translation before any
clinical use. The build does not modify the published content package or use
these records to enrich predictions.
