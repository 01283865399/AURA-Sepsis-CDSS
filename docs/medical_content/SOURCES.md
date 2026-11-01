# Source inventory and limitations

The build reads only these local inputs:

| Source | Local input | Observed shape | Build use | Important limitation |
|---|---|---:|---|---|
| Disease Ontology | `data/medical_content/processed/final/conditions.json` | 12,335 terms | English names, definitions, IDs, references | No Arabic translations or complete clinical monographs |
| HPO | `data/medical_content/processed/final/phenotype_concepts.json` | 19,894 concepts | First 1,000 stable IDs, retained as phenotype concepts | Not a clinical symptom catalog |
| DO-SYMP | `data/medical_content/processed/symptoms/disease_symptom_association_candidates.json` | 2,222 relations; 300 unique SYMP IDs | Exact source associations and term candidates | Source-asserted and unreviewed; no HPO-to-SYMP crosswalk |
| ICD-10-CM index | `data/medical_content/processed/final/icd10cm_condition_index.json` | 2,479 entries | Base code index | Mappings are source assertions and not independently verified |
| Healthcare RAG | `data/medical_content/raw/healthcare_rag/healthcare_rag_dataset.csv` | 409 rows; 31 codes and source names | Exact code-linked content candidates | 37 rows lack a source URL; local files do not establish license or validate review claims |
| Symptom2Disease | `data/medical_content/raw/symptom2disease/Symptom2Disease.csv` | 1,200 rows; 300 labels; 1,153 distinct narratives | Preserved as unverified narrative examples | Not converted into clinical symptom or diagnosis assertions; local license not verified |
| MedQuAD-derived HF dataset | `data/medical_content/raw/medquad/` | 16,407 train rows | English Q&A candidates | Local metadata has no license, citation, or item-level original URLs |

The build records SHA-256 checksums for every input file in `stats.json`.
Where supplied, a source URL is retained as provenance, not as proof that the
record is current, accurate, licensed for redistribution, or clinically
validated. The `Peer-Reviewed` and evidence-level labels found in the
Healthcare RAG CSV are retained as source claims only.

No value absent from a source is filled with a guessed clinical fact. In
particular, Arabic text, emergency flags, specialty referrals, prevalence
ranking, and clinical approval are not inferred.
