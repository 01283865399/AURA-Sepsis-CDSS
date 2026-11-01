"""Consolidate the independent held-out test reports produced by training."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from _training_common import MODELS_DIR, ROOT, configure_logging


LOG = logging.getLogger("evaluate_all")
EXPECTED_REPORTS = {
    "symptoms/lightgbm": MODELS_DIR / "symptoms" / "lightgbm_evaluation.json",
    "symptoms/xgboost": MODELS_DIR / "symptoms" / "xgboost_evaluation.json",
    "symptoms/biobert": MODELS_DIR / "symptoms" / "biobert_evaluation.json",
    "ddxplus": MODELS_DIR / "ddxplus" / "test_report.json",
    "diabetes/xgboost": MODELS_DIR / "diabetes" / "xgboost_evaluation.json",
    "heart/random_forest": MODELS_DIR / "heart" / "random_forest_evaluation.json",
    "heart/xgboost": MODELS_DIR / "heart" / "xgboost_evaluation.json",
    "kidney/random_forest": MODELS_DIR / "kidney" / "random_forest_evaluation.json",
    "kidney/xgboost": MODELS_DIR / "kidney" / "xgboost_evaluation.json",
    "skin_lesions_8class/efficientnet_b0": (
        MODELS_DIR / "skin_lesions_8class" / "efficientnet_b0_evaluation.json"
    ),
    "isic_2019/efficientnet_b0": (
        MODELS_DIR / "isic_2019" / "efficientnet_b0_evaluation.json"
    ),
    "covid19_radiography/efficientnet_b0": (
        MODELS_DIR / "covid19_radiography" / "efficientnet_b0_evaluation.json"
    ),
    "tb_chest_radiography/efficientnet_b0": (
        MODELS_DIR / "tb_chest_radiography" / "efficientnet_b0_evaluation.json"
    ),
    "indian_liver_patient/xgboost": (
        MODELS_DIR / "indian_liver_patient" / "xgboost_evaluation.json"
    ),
}


def load_report(name: str, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing held-out report for {name}: {path}. "
            "Run the corresponding training script before evaluation."
        )
    with path.open("r", encoding="utf-8") as stream:
        report = json.load(stream)
    if not isinstance(report, dict) or "accuracy" not in report:
        raise ValueError(f"Invalid or incomplete evaluation report for {name}: {path}")
    model_name = report.get("model")
    matrix_name = (
        "confusion_matrix.csv"
        if name == "ddxplus"
        else f"{model_name}_confusion_matrix.csv"
    )
    matrix_path = path.parent / matrix_name
    if not matrix_path.is_file():
        raise FileNotFoundError(f"Missing confusion matrix for {name}: {matrix_path}")
    report["confusion_matrix_file"] = str(matrix_path.relative_to(ROOT))
    return report


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    configure_logging()
    reports = {name: load_report(name, path) for name, path in EXPECTED_REPORTS.items()}
    output_dir = MODELS_DIR / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "all_models_test_reports.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "purpose": "research prototype held-out evaluation",
                "reports": reports,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(destination)

    for name, report in reports.items():
        print(f"\n=== {name} (n={report.get('test_rows', report.get('rows', 'unknown'))}) ===")
        print(
            json.dumps(
                {
                    key: value
                    for key, value in report.items()
                    if key in {
                        "accuracy",
                        "precision_weighted",
                        "recall_weighted",
                        "f1_weighted",
                        "top_k_accuracy",
                        "loss",
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"Confusion matrix: {report['confusion_matrix_file']}")
        if "classification_report" in report:
            print(json.dumps(report["classification_report"], ensure_ascii=False, indent=2))
    LOG.info("Consolidated %d test reports into %s", len(reports), destination)


if __name__ == "__main__":
    main()
