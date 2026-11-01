# New-folder data sources

The audited source root contains two supplied CSV datasets, a DDXPlus-format
synthetic benchmark file, a Disease Ontology repository snapshot, and a
MedQuAD repository snapshot. The complete file-level path/size/format list is
in [`new_folder_inventory.csv`](./new_folder_inventory.csv).

| Source | Observed content | License/provenance evidence | Import decision |
|---|---|---|---|
| `dataset_` | 1,292,579 DDXPlus-format synthetic cases; six attributes; 49 pathology labels in the observed file | Header describes synthetic patients and asserts CC-BY, but does not include enough citation/attribution metadata here | Research-only; not a clinical fact catalog |
| `archive (1)/combined_diseases_symptoms_2_enriched_with_exams_v2.csv` | 248,126 disease/symptom inputs, candidate diagnoses, test suggestions, and reasoning strings; 192,260 rows self-label `inconclusive`, 55,866 self-label `supported` | No record-level evidence URLs or license evidence in the file | Blocked from clinical import |
| `archive (2)/healthcare_rag_dataset.csv` | 409 mixed FAQ, treatment, prevention, symptom, and clinical-summary rows | 37 rows have no source URL; `evidence_level` and `review_status` values were not independently verified | Blocked pending source and clinical review |
| Human Disease Ontology snapshot | Release dated 2026-08-31, including a disease-to-symptom table | Repository LICENSE is CC0 1.0; ontology header declares the same | The ontology release is older than the 2026-09-30 AURA copy; only its exact relation table is staged for review |
| MedQuAD snapshot | 11,274 XML files, 47,441 Question and 47,441 Answer elements detected; answer elements in three MedlinePlus subsets are empty | Local LICENSE says CC BY 4.0, while the upstream repository was reported as `NOASSERTION`; README explicitly excludes answers in three MedlinePlus subsets to respect copyright | Rights review required per source/subset; no Q&A text imported |

The repository may contain ancillary code, SPARQL, reports, translations, old
ontology exports, and test artifacts. They are inventoried but not treated as
clinical records. A license file for a dataset compilation does not by itself
establish reuse rights for every underlying source item.
