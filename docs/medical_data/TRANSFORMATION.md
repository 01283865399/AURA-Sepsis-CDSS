# Transformation rules

The importer uses an explicit source path allowlist. It does not infer a
dataset's meaning from labels or manufacture values for the condition, symptom,
drug, lab, or QA schemas.

For `DOreports/requested/disease-symptom.tsv`, the converter:

1. Requires the exact source columns `disease_id`, `disease_label`,
   `symptom_id`, and `symptom_label`.
2. Trims leading/trailing whitespace only.
3. Requires source identifiers shaped as `DOID:<digits>` and `SYMP:<digits>`.
4. Drops incomplete or invalid rows and counts them; it does not fill blanks.
5. Drops duplicate disease/symptom identifier pairs and counts them.
6. Derives a stable association key from the two source identifiers, while
   retaining both original identifiers and labels.
7. Records the source release, HTTPS source URL, CC0 declaration, and
   `draft`/`unreviewed` state.

The output is an association candidate, not an approved symptom dictionary:
severity, body system, description, Arabic name, and clinical relevance remain
unset. No relation is matched by text similarity.

Other datasets are left untransformed: the DDXPlus file is a synthetic
prediction benchmark; the large mixed diagnosis/test CSV includes unverified
reasoning; the RAG CSV has incomplete source URLs; the ontology copy is stale;
and MedQuAD requires item/subset rights handling.
