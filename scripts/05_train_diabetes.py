"""Train and evaluate the research diabetes classifier on the full CSV."""

from __future__ import annotations

import logging
import os

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from _training_common import (
    MODELS_DIR,
    RAW_DIR,
    RANDOM_SEED,
    clean_features_like_training,
    configure_logging,
    deduplicate_unambiguous_profiles,
    evaluate_classifier,
    make_tabular_preprocessor,
    save_joblib_bundle,
    seed_everything,
)


def main() -> None:
    configure_logging()
    seed_everything()
    source = RAW_DIR / "diabetes" / "diabetes_prediction_dataset.csv"
    if not source.is_file():
        raise FileNotFoundError(f"Required diabetes dataset not found: {source}")
    frame = pd.read_csv(source, low_memory=False)
    if "diabetes" not in frame:
        raise ValueError(f"Expected target column 'diabetes'; found {list(frame.columns)}")

    y = pd.to_numeric(frame.pop("diabetes"), errors="coerce")
    valid = y.notna()
    x = frame.loc[valid].drop(columns=["id"], errors="ignore")
    y = y.loc[valid].astype("int64")
    if set(y.unique()) != {0, 1}:
        raise ValueError(f"Expected binary diabetes labels 0/1; found {sorted(y.unique())}")

    x, y, profile_stats = deduplicate_unambiguous_profiles(x, y)
    logging.getLogger(__name__).info(
        "Removed %s duplicate rows and %s rows from conflicting feature profiles; "
        "using %s unique profiles.",
        profile_stats["duplicate_rows_removed"],
        profile_stats["rows_in_ambiguous_profiles_removed"],
        profile_stats["retained_unique_profiles"],
    )
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )
    preprocessor, numeric, categorical, clean_train = make_tabular_preprocessor(x_train)
    clean_test = clean_features_like_training(x_test, numeric)
    positives = int((y_train == 1).sum())
    negatives = int((y_train == 0).sum())
    if positives == 0:
        raise ValueError("No positive diabetes samples are present in the training split.")

    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                XGBClassifier(
                    n_estimators=400,
                    max_depth=6,
                    learning_rate=0.05,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    min_child_weight=2,
                    reg_lambda=1.0,
                    scale_pos_weight=negatives / positives,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    tree_method="hist",
                    device="cpu",
                    n_jobs=max(1, min(os.cpu_count() or 1, 8)),
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )
    model.fit(clean_train, y_train)
    out = MODELS_DIR / "diabetes"
    metrics = evaluate_classifier(
        "xgboost", model, clean_test, y_test, ["no_diabetes", "diabetes"], out
    )
    save_joblib_bundle(
        out / "model.joblib",
        model=model,
        preprocessor=None,
        class_names=["no_diabetes", "diabetes"],
        feature_names=list(x.columns),
        metadata={
            "model_name": "XGBoost",
            "dataset": str(source.relative_to(RAW_DIR)),
            "rows": len(frame),
            "profile_deduplication": profile_stats,
            "scale_pos_weight": negatives / positives,
            "random_seed": RANDOM_SEED,
            "metrics": {key: value for key, value in metrics.items() if key != "classification_report"},
        },
    )
    logging.getLogger(__name__).info("Saved diabetes model to %s", out)


if __name__ == "__main__":
    main()
