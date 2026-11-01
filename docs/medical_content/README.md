# Medical content build

This repository contains a generated, source-derived **review package**, not a
production clinical knowledge base. Nothing under `data/medical_content/final/complete/`
is clinically reviewed or approved for diagnosis, treatment, or triage.

Build it from the checked-in local sources with:

```powershell
.\venv\Scripts\python.exe -m scripts.medical_data.importers.complete_content
```

The command writes under `data/medical_content/final/complete/` so it does not
overwrite the earlier, smaller review snapshot under `data/medical_content/final/`.
Counts, checksums, field quality, source limitations, and transformation status
are recorded in `stats.json`.

Available API routes are under `/api/v1/medical-content/complete-drafts/`.
They are intentionally separate from the published catalog and model prediction
enrichment. See [API](./API.md), [sources](./SOURCES.md), and
[build process](./BUILD_PROCESS.md).

## What the datasets support

- 12,335 source disease terms, including 500 prioritized content candidates and
  11,835 lookup-only terms. Candidate ordering is based on source-linked RAG
  material, association count, and source definitions; it is **not** a
  prevalence or frequency ranking.
- 1,000 HPO phenotype concepts. They are not asserted to be symptoms.
- 300 distinct source `SYMP` terms plus all 2,222 explicit source associations.
- 1,200 Symptom2Disease patient-narrative rows kept as dataset examples, not
  verified symptom assertions or disease diagnoses.
- 16,407 MedQuAD-derived Q&A rows.

Arabic fields remain null because none of these local source files provides
verified Arabic. No external translation service is invoked. Emergency signs
and specialist mappings remain empty because the sources do not support
clinically reviewed catalogs for those concepts.
