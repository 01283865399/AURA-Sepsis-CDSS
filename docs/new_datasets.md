# Newly imported research datasets

The source bundle was found in `New data/` at the repository root. Its five
distinct datasets are registered in `configs/dataset_registry.json`; the
duplicated TB archive was SHA-256 checked and is preserved separately, not
counted or trained twice. COVID-19 radiography masks and accompanying dataset
metadata are retained, while only the class `images/` folders are used for
classification.

A complete file/folder and byte-size listing is saved in
[`new_data_inventory.csv`](./new_data_inventory.csv).

## Training and artifacts

Run the complete new-dataset training workflow:

```powershell
.\venv\Scripts\python.exe .\scripts\09_train_new_datasets.py
```

Run only one dataset by adding `--dataset` and one of
`skin_lesions_8class`, `isic_2019`, `covid19_radiography`,
`tb_chest_radiography`, or `indian_liver_patient`. Image classifiers use
ImageNet-pretrained EfficientNet-B0 features and train a classifier head for
five deterministic epochs. The tabular liver classifier uses XGBoost. Reports,
weighted precision/recall/F1, supported top-k accuracy, confusion matrices,
and `metadata.json` are written under `models/<dataset>/`.

`scripts/run_all.py` includes this workflow before the consolidated evaluation
step. It also supports the existing full workflow; `--serve` starts the API
after all configured download, training, and evaluation tasks finish.

## Inference endpoints

Image endpoints accept `multipart/form-data` with an `image` file and optional
`top_k` field:

- `POST /api/v1/diagnose/skin_lesions_8class`
- `POST /api/v1/diagnose/isic_2019`
- `POST /api/v1/diagnose/covid19_radiography`
- `POST /api/v1/diagnose/tb_chest_radiography`

The liver endpoint accepts JSON with `AGE`, `GENDER`, `TB`, `DB`, `ALK`,
`SGPT`, `SGOT`, `TP`, `ALB`, and `AG` fields:

- `POST /api/v1/diagnose/indian_liver_patient`

These endpoints are research-only and are not clinically validated diagnoses.
They must not replace qualified clinical review or local medical protocols.
