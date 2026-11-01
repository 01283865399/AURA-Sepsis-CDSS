# Import guide

Run from the repository root with its configured Python environment:

```powershell
.\venv\Scripts\python.exe -m scripts.import_all_new_data
```

The command scans every regular file under `New folder`, writes a full
metadata-only inventory to `docs/medical_data/new_folder_inventory.csv`, writes
the readable findings to `docs/medical_data/NEW_FOLDER_AUDIT.md`, and saves a
machine-readable report to the ignored generated-data directory
`data/medical_content/processed/import_report.json`.

The one transformable input is the Disease Ontology `disease-symptom.tsv`
source association table. Exact DOID/SYMP identifiers and source labels are
retained in the review-only artifact
`data/medical_content/processed/symptoms/disease_symptom_association_candidates.json`.
No other file is copied into a medical catalog. In particular, the command
does not download data, call external services, translate names, fill missing
values, infer mappings, or publish records.

The output conforms to
`data/medical_content/schemas/disease_symptom_association_candidate_schema.json`.
The original source folder remains unchanged. Generated candidate files are
not consumed by the API or the live medical-content loader. Run tests
separately with the project's normal test runner after changes.
