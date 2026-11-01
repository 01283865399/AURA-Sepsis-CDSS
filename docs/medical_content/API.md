# Complete-build review API

All endpoints are read-only and isolated under
`/api/v1/medical-content/complete-drafts/`. Responses explicitly identify
unreviewed draft data and warn against clinical use.

| Method and path | Purpose |
|---|---|
| `GET /coverage` | Build counts and review-only notice |
| `GET /conditions?offset=0&limit=50` | Browse conditions; `limit` is 1–100 |
| `GET /conditions/{condition_id}` | Retrieve one source term |
| `GET /symptoms?offset=0&limit=50` | Browse HPO phenotype concepts (not approved symptoms) |
| `GET /symptom_terms?offset=0&limit=50` | Browse source SYMP term candidates |
| `GET /associations?offset=0&limit=50` | Browse DO-SYMP relations |
| `GET /qa?offset=0&limit=50` | Browse MedQuAD-derived Q&A candidates |
| `GET /qa/search?q=...&offset=0&limit=20` | Case-insensitive substring search over English questions and answers |
| `GET /icd10_index?offset=0&limit=50` | Browse source-asserted ICD code mappings |
| `GET /symptom2disease_reports?offset=0&limit=50` | Browse unverified source narratives |

The other listable collections are `specialists`, `emergency_signs`, and
`references`. Empty specialist and emergency-sign catalogs are intentional:
the available files do not substantiate reviewed entries. The live
`/api/v1/medical-content/coverage` endpoint and prediction enrichment remain
unchanged.
