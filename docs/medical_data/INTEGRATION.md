# Integration and publication gates

The current AURA loader reads its governed catalog files, not arbitrary files
from `processed/`. The medical-content service exposes a record only when
`content_status == "published"` and `review_status == "clinically_reviewed"`.
Coverage remains a report of approved content, not of downloaded rows.

The new DO disease-to-symptom relation is written under
`data/medical_content/processed/symptoms/` as a draft candidate. It does not
change `data/medical_content/conditions/`, the approved symptom catalog, the
medical-content service, or API routes. This prevents an ontology edge or
benchmark label from being mistaken for a patient-facing assertion.

The supplied mixed RAG/diagnosis datasets are not served as chatbot answers.
MedQuAD is not served until rights for each constituent source are confirmed.
When source evidence, terminology compatibility, licensing, and qualified
clinical review are complete, a separate controlled promotion into the live
catalog can be considered and validated through existing content tests.

No API schema or route was expanded to serve these unreviewed candidates.
Existing coverage stays unchanged; no symptom, treatment, test, or emergency
recommendation is inferred from model training data.
