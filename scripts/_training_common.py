"""Shared deterministic preprocessing and evaluation for the disease models."""

from __future__ import annotations

import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MODELS_DIR = ROOT / "models"
RANDOM_SEED = 42
LOG = logging.getLogger("medical_research")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def seed_everything(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        LOG.warning("PyTorch unavailable; only Python and NumPy seeds were set.")


def normalized_name(value: object) -> str:
    """Normalize case and separators without attempting medical synonym mapping."""
    import re

    text = str(value).strip().casefold()
    text = re.sub(r"[\s_]+", " ", text)
    return re.sub(r"\s+", " ", text)


def normalize_feature_name(value: object) -> str:
    import re

    return re.sub(r"[\s_]+", "_", str(value).strip().casefold()).strip("_")


def clean_tabular_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    for column in result.select_dtypes(include=["object", "string"]).columns:
        values = result[column].astype("object")
        values = values.map(lambda value: value.strip() if isinstance(value, str) else value)
        result[column] = values.replace(
            {"": np.nan, "?": np.nan, "nan": np.nan, "NaN": np.nan, "NA": np.nan}
        )
    return result


def clean_features_like_training(
    frame: pd.DataFrame, numeric_columns: Sequence[str]
) -> pd.DataFrame:
    clean = clean_tabular_frame(frame)
    for column in numeric_columns:
        if column in clean:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")
    return clean


def deduplicate_unambiguous_profiles(
    features: pd.DataFrame, labels: pd.Series
) -> tuple[pd.DataFrame, pd.Series, dict[str, int]]:
    """Remove conflicting and repeated feature profiles before splitting."""
    if len(features) != len(labels):
        raise ValueError("Feature and label row counts do not match.")
    if features.empty:
        raise ValueError("Cannot deduplicate an empty dataset.")

    profile_ids = pd.util.hash_pandas_object(features, index=False)
    profile_labels = pd.DataFrame(
        {"profile": profile_ids.to_numpy(), "label": labels.astype(str).to_numpy()}
    )
    labels_per_profile = profile_labels.groupby("profile", sort=False)["label"].nunique()
    ambiguous_profiles = labels_per_profile[labels_per_profile > 1].index
    ambiguous_mask = profile_ids.isin(ambiguous_profiles).to_numpy()
    unambiguous_mask = ~ambiguous_mask

    unambiguous_profiles = profile_ids[unambiguous_mask]
    unique_mask = ~unambiguous_profiles.duplicated(keep="first").to_numpy()
    keep_mask = unambiguous_mask.copy()
    keep_mask[unambiguous_mask] = unique_mask

    retained_features = features.iloc[keep_mask].reset_index(drop=True)
    retained_labels = labels.iloc[keep_mask].reset_index(drop=True)
    stats = {
        "input_rows": int(len(features)),
        "ambiguous_profiles_removed": int(len(ambiguous_profiles)),
        "rows_in_ambiguous_profiles_removed": int(ambiguous_mask.sum()),
        "duplicate_rows_removed": int(unambiguous_mask.sum() - unique_mask.sum()),
        "retained_unique_profiles": int(len(retained_features)),
    }
    if retained_features.empty:
        raise ValueError("No unambiguous feature profiles remain after deduplication.")
    return retained_features, retained_labels, stats


def make_tabular_preprocessor(
    frame: pd.DataFrame, *, scale_numeric: bool = False
) -> tuple[ColumnTransformer, list[str], list[str], pd.DataFrame]:
    """Infer numeric columns safely, including numeric strings with '?' missing values."""
    clean = clean_tabular_frame(frame)
    numeric: list[str] = []
    categorical: list[str] = []
    for column in clean.columns:
        values = clean[column]
        if pd.api.types.is_numeric_dtype(values.dtype):
            numeric.append(column)
            clean[column] = pd.to_numeric(values, errors="coerce")
            continue
        converted = pd.to_numeric(values, errors="coerce")
        present = int(values.notna().sum())
        valid = int(converted.notna().sum())
        if present == 0 or valid / present >= 0.8:
            numeric.append(column)
            clean[column] = converted
        else:
            categorical.append(column)

    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric:
        numeric_steps: list[tuple[str, Any]] = [
            ("imputer", SimpleImputer(strategy="median", add_indicator=True))
        ]
        if scale_numeric:
            numeric_steps.append(("scaler", StandardScaler()))
        transformers.append(("numeric", Pipeline(numeric_steps), numeric))
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(
                                handle_unknown="ignore", sparse_output=True
                            ),
                        ),
                    ]
                ),
                categorical,
            )
        )
    if not transformers:
        raise ValueError("The dataset has no usable feature columns.")

    preprocessor = ColumnTransformer(
        transformers, remainder="drop", sparse_threshold=1.0
    )
    return preprocessor, numeric, categorical, clean


def evaluate_classifier(
    name: str,
    model: Any,
    x_test: Any,
    y_test: Sequence[int] | np.ndarray,
    class_names: Sequence[str],
    output_dir: Path,
    *,
    top_k: bool = False,
) -> dict[str, Any]:
    """Print and persist scalar, per-class, and confusion-matrix test metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    truth = np.asarray(y_test, dtype=np.int64)
    predictions = np.asarray(model.predict(x_test), dtype=np.int64)
    labels = np.arange(len(class_names), dtype=np.int64)
    proba = model.predict_proba(x_test) if hasattr(model, "predict_proba") else None
    report = classification_report(
        truth,
        predictions,
        labels=labels,
        target_names=[str(label) for label in class_names],
        output_dict=True,
        zero_division=0,
    )
    metrics: dict[str, Any] = {
        "model": name,
        "test_rows": int(len(truth)),
        "accuracy": float(accuracy_score(truth, predictions)),
        "precision_weighted": float(
            precision_score(truth, predictions, average="weighted", zero_division=0)
        ),
        "recall_weighted": float(
            recall_score(truth, predictions, average="weighted", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(truth, predictions, average="weighted", zero_division=0)
        ),
        "classification_report": report,
        "class_names": [str(label) for label in class_names],
        "confusion_matrix_file": f"{name}_confusion_matrix.csv",
    }
    if top_k and proba is not None:
        class_positions = np.asarray(getattr(model, "classes_", labels), dtype=np.int64)
        requested = [k for k in (1, 3, 5, 10) if k <= proba.shape[1]]
        topk: dict[str, float] = {}
        order = np.argsort(proba, axis=1)[:, ::-1]
        for k in requested:
            top_predictions = class_positions[order[:, :k]]
            topk[str(k)] = float(
                np.mean(np.any(top_predictions == truth[:, None], axis=1))
            )
        metrics["top_k_accuracy"] = topk

    matrix = confusion_matrix(truth, predictions, labels=labels)
    pd.DataFrame(matrix, index=class_names, columns=class_names).to_csv(
        output_dir / f"{name}_confusion_matrix.csv", encoding="utf-8"
    )
    with (output_dir / f"{name}_evaluation.json").open("w", encoding="utf-8") as stream:
        json.dump(metrics, stream, ensure_ascii=False, indent=2)
    print(f"\n=== {name} test report ===")
    print(
        classification_report(
            truth,
            predictions,
            labels=labels,
            target_names=[str(label) for label in class_names],
            zero_division=0,
        )
    )
    if "top_k_accuracy" in metrics:
        for k, score in metrics["top_k_accuracy"].items():
            print(f"Top-{k} accuracy: {score:.4f} ({score:.2%})")
    print(f"Confusion matrix: {output_dir / f'{name}_confusion_matrix.csv'}")
    LOG.info("Saved %s metrics to %s", name, output_dir)
    return metrics


def save_joblib_bundle(
    path: Path,
    *,
    model: Any,
    class_names: Sequence[str],
    feature_names: Sequence[str],
    metadata: dict[str, Any] | None = None,
    preprocessor: Any | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": model,
        "preprocessor": preprocessor,
        "class_names": [str(name) for name in class_names],
        "feature_names": [str(name) for name in feature_names],
        "metadata": metadata or {},
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    joblib.dump(bundle, temporary, compress=3)
    os.replace(temporary, path)


def to_csr(values: pd.DataFrame) -> sparse.csr_matrix:
    """Convert binary/multi-hot symptom matrices to compact float32 CSR."""
    return sparse.csr_matrix(values.to_numpy(dtype=np.float32, copy=False))
