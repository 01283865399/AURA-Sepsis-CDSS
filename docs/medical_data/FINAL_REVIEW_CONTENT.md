# Final source-derived medical content

Build the separate, review-only snapshot from the four processed source files:

```powershell
.\venv\Scripts\python.exe -m scripts.medical_data.importers.final_content
```

Outputs are written to `data/medical_content/final/`:

- `conditions.json`: 500 active DOID terms, selected to prioritize exact source
  disease-symptom associations, then ICD-10-CM xrefs, then source definitions.
  All 500 have a source definition; source names, definition text, references,
  and exact available crosswalks are retained.
- `symptoms.json`: 300 unique `SYMP` labels present in the supplied
  Disease Ontology association table. They remain unreviewed term candidates.
- `phenotype_concepts.json`: 1,000 HPO concepts selected by stable HP ID order.
  They are explicitly **not** approved symptoms and are not clinically ranked.
- `associations.json`: all 2,222 source disease-to-SYMP links. Relations whose
  disease is outside the 500-condition subset retain the exact source DOID and
  have a null subset `condition_id`; links are never guessed by name.
- `import_report.json`: output counts, ICD linkage, selection policy, omissions,
  and status.

## Important limits

The four approved inputs do not contain Arabic labels or translated clinical
descriptions: all Arabic fields are therefore `null`. No translation has been
invented. HPO phenotype concepts are not interchangeable with symptom
assertions; no HPO concept is labelled a clinical symptom here.

Disease Ontology provides terminology definitions, not a full clinical
monograph. Risk factors, diagnosis, treatment, prevention, prognosis,
specialist, urgency, category, and body system are left null because these
inputs do not substantiate them. The 500 records are not "complete diseases"
or fit for clinical decision-making.

ICD references preserve exact `ICD10CM:` source mappings. They are marked
`source_asserted_unverified`, not independently verified as WHO ICD-10.
Everything in this directory remains `draft` / `unreviewed` and is kept
separate from `data/medical_content/conditions/` and
`data/medical_content/symptoms/`.

## Draft API

These records are only exposed through a separate research-review namespace:

- `GET /api/v1/medical-content/final/coverage`
- `GET /api/v1/medical-content/final/conditions?offset=0&limit=50`
- `GET /api/v1/medical-content/final/conditions/{condition_id}`
- `GET /api/v1/medical-content/final/symptoms?offset=0&limit=50`
- `GET /api/v1/medical-content/final/phenotype_concepts?offset=0&limit=50`
- `GET /api/v1/medical-content/final/associations?condition_id=...&symptom_id=...`
- `GET /api/v1/medical-content/final/associations/{association_id}`

Responses carry `draft_only`, `unreviewed`, `clinical_review_required`, and
`not_for_clinical_use` indicators plus Arabic and English notices. These routes
do not change the published-catalog coverage endpoint or enrich model
predictions.
