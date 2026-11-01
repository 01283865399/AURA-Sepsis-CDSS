"""Train and evaluate Random Forest and XGBoost on the kidney dataset."""

from __future__ import annotations

import logging
import os

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
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
    source = RAW_DIR / "kidney" / "kidney_disease.csv"
    if not source.is_file():
        raise FileNotFoundError(f"Required kidney dataset not found: {source}")
    frame = pd.read_csv(source, low_memory=False)
    if "classification" not in frame:
        raise ValueError(
            f"Expected target column 'classification'; found {list(frame.columns)}"
        )

    target = (
        frame.pop("classification")
        .astype("string")
        .str.strip()
        .str.casefold()
        .str.replace(r"\s+", "", regex=True)
    )
    normalized = target.replace({"ckd": "kidney_disease", "notckd": "no_kidney_disease"})
    valid = normalized.isin({"kidney_disease", "no_kidney_disease"})
    if not valid.all():
        bad_values = sorted(str(value) for value in normalized[~valid].dropna().unique())
        if bad_values:
            raise ValueError(f"Unexpected kidney target values: {bad_values}")
    x = frame.loc[valid].drop(columns=["id"], errors="ignore")
    y = (normalized.loc[valid] == "kidney_disease").astype("int64")
    if y.nunique() != 2:
        raise ValueError("Kidney target did not contain both disease classes.")

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
    preprocessor, numeric, _, clean_train = make_tabular_preprocessor(x_train)
    clean_test = clean_features_like_training(x_test, numeric)

    out = MODELS_DIR / "kidney"
    counts = y_train.value_counts()
    model_factories = {
        "random_forest": RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=max(1, min(os.cpu_count() or 1, 8)),
            random_state=RANDOM_SEED,
        ),
        "xgboost": XGBClassifier(
            n_estimators=350,
            max_depth=3,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.85,
            scale_pos_weight=float(counts.get(0, 0)) / max(int(counts.get(1, 0)), 1),
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            device="cpu",
            n_jobs=max(1, min(os.cpu_count() or 1, 8)),
            random_state=RANDOM_SEED,
        ),
    }
    for name, classifier in model_factories.items():
        model = Pipeline(
            [("preprocessor", preprocessor), ("classifier", classifier)]
        )
        model.fit(clean_train, y_train)
        metrics = evaluate_classifier(
            name, model, clean_test, y_test, ["no_kidney_disease", "kidney_disease"], out
        )
        save_joblib_bundle(
            out / f"{name}.joblib",
            model=model,
            class_names=["no_kidney_disease", "kidney_disease"],
            feature_names=list(x.columns),
            metadata={
                "model_name": "Random Forest" if name == "random_forest" else "XGBoost",
                "dataset": str(source.relative_to(RAW_DIR)),
                "rows": len(frame),
                "profile_deduplication": profile_stats,
                "random_seed": RANDOM_SEED,
                "metrics": {key: value for key, value in metrics.items() if key != "classification_report"},
            },
        )

    logging.getLogger(__name__).info("Saved kidney models to %s", out)


if __name__ == "__main__":
    main()
