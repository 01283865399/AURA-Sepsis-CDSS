"""Train multiclass symptom models on the augmented and classic symptom data."""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from scipy import sparse
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from tqdm import tqdm
from xgboost import XGBClassifier

from _training_common import (
    MODELS_DIR,
    RAW_DIR,
    RANDOM_SEED,
    configure_logging,
    deduplicate_unambiguous_profiles,
    evaluate_classifier,
    normalize_feature_name,
    normalized_name,
    seed_everything,
)


LOG = logging.getLogger("train_symptoms")
MIN_CLASS_PROFILES = 10
MIN_CLASS_ROWS = 50
BIOMEDICAL_MODEL = "dmis-lab/biobert-base-cased-v1.2"


def load_symptom_file(path: Path, target_column: str) -> tuple[pd.DataFrame, pd.Series]:
    if not path.is_file():
        raise FileNotFoundError(f"Required symptoms dataset not found: {path}")
    frame = pd.read_csv(path, low_memory=False)
    if target_column not in frame:
        raise ValueError(
            f"Expected target {target_column!r} in {path.name}; columns={list(frame.columns)}"
        )
    labels = frame.pop(target_column).astype("string").str.strip()
    frame = frame.drop(columns=[c for c in frame if c.lower().startswith("unnamed:")])
    frame.columns = [normalize_feature_name(column) for column in frame.columns]
    if len(set(frame.columns)) != len(frame.columns):
        frame = frame.T.groupby(level=0, sort=False).max().T
    for column in frame:
        frame[column] = (
            pd.to_numeric(frame[column], errors="coerce").fillna(0).gt(0).astype("uint8")
        )
    return frame, labels


def load_and_merge(
    min_class_rows: int = MIN_CLASS_ROWS,
    min_class_profiles: int = MIN_CLASS_PROFILES,
) -> tuple[sparse.csr_matrix, np.ndarray, list[str], list[str]]:
    augmented_path = RAW_DIR / "symptoms" / "Final_Augmented_dataset_Diseases_and_Symptoms.csv"
    classic_path = RAW_DIR / "symptoms" / "Training.csv"
    augmented_x, augmented_y = load_symptom_file(augmented_path, "diseases")
    classic_x, classic_y = load_symptom_file(classic_path, "prognosis")

    feature_names = sorted(set(augmented_x.columns) | set(classic_x.columns))
    augmented_x = augmented_x.reindex(columns=feature_names, fill_value=0)
    classic_x = classic_x.reindex(columns=feature_names, fill_value=0)
    x_frame = pd.concat([augmented_x, classic_x], ignore_index=True)
    labels = pd.concat([augmented_y, classic_y], ignore_index=True)
    valid = labels.notna() & labels.str.len().gt(0)
    x_frame = x_frame.loc[valid]
    labels = labels.loc[valid].map(normalized_name)
    row_counts = labels.value_counts()
    x_frame, labels, profile_stats = deduplicate_unambiguous_profiles(
        x_frame.reset_index(drop=True), labels.reset_index(drop=True)
    )
    counts = labels.value_counts()
    common_classes = row_counts[row_counts >= min_class_rows].index
    keep = counts[
        counts.index.isin(common_classes) & counts.ge(min_class_profiles)
    ].index
    remove_n = int(labels.isin(keep).sum())
    LOG.info(
        "Merged %s rows (%s augmented + %s classic); removed %s rows from "
        "%s conflicting profiles and %s repeated profiles; retaining %s classes "
        "with >=%s raw rows and >=%s distinct unambiguous profiles; dropping %s rows.",
        f"{profile_stats['input_rows']:,}",
        f"{len(augmented_y):,}",
        f"{len(classic_y):,}",
        f"{profile_stats['rows_in_ambiguous_profiles_removed']:,}",
        f"{profile_stats['ambiguous_profiles_removed']:,}",
        f"{profile_stats['duplicate_rows_removed']:,}",
        len(keep),
        min_class_rows,
        min_class_profiles,
        len(labels) - remove_n,
    )
    keep_rows = labels.isin(keep)
    x_frame = x_frame.loc[keep_rows]
    labels = labels.loc[keep_rows]
    if labels.nunique() < 2:
        raise ValueError("At least two diseases must remain after rare-class filtering.")
    encoder = LabelEncoder()
    encoded = encoder.fit_transform(labels)
    matrix = sparse.csr_matrix(x_frame.to_numpy(dtype=np.float32, copy=False))
    return matrix, encoded, list(encoder.classes_), feature_names


def report_probabilities(
    model: Any,
    x: sparse.csr_matrix,
    y: np.ndarray,
    class_names: Sequence[str],
    out: Path,
    model_name: str,
) -> dict[str, Any]:
    return evaluate_classifier(
        model_name, model, x, y, class_names, out, top_k=True
    )


def validation_top1(model: Any, x_val: sparse.csr_matrix, y_val: np.ndarray) -> float:
    probabilities = np.asarray(model.predict_proba(x_val))
    predicted_classes = np.asarray(getattr(model, "classes_", np.arange(probabilities.shape[1])))
    return float(np.mean(predicted_classes[probabilities.argmax(axis=1)] == y_val))


def save_bundle(
    path: Path,
    model: Any,
    class_names: Sequence[str],
    feature_names: Sequence[str],
    model_name: str,
    metrics: dict[str, Any],
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    joblib.dump(
        {
            "model": model,
            "class_names": list(class_names),
            "feature_names": list(feature_names),
            "model_name": model_name,
            "metrics": metrics,
        },
        temporary,
        compress=3,
    )
    temporary.replace(path)


class SymptomTextDataset:
    """Build BioBERT symptom text lazily from the sparse multi-hot matrix."""

    def __init__(self, x: sparse.csr_matrix, y: np.ndarray, feature_names: Sequence[str]):
        self.x = x
        self.y = y
        self.feature_names = feature_names

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, index: int) -> tuple[str, int]:
        start, end = self.x.indptr[index : index + 2]
        symptoms = " ".join(
            self.feature_names[int(column)].replace("_", " ")
            for column in self.x.indices[start:end]
        )
        return f"reported symptoms: {symptoms}", int(self.y[index])


def train_biobert(
    x_train: sparse.csr_matrix,
    y_train: np.ndarray,
    x_val: sparse.csr_matrix,
    y_val: np.ndarray,
    x_test: sparse.csr_matrix,
    y_test: np.ndarray,
    feature_names: Sequence[str],
    class_names: Sequence[str],
    out: Path,
    *,
    model_name: str,
    epochs: int,
    batch_size: int,
    patience: int,
) -> tuple[dict[str, Any], float]:
    try:
        import torch
        from torch.utils.data import DataLoader
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "BioBERT requires the declared 'transformers' and 'torch' dependencies."
        ) from exc

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cpu":
        LOG.warning("CUDA is unavailable; fine-tuning BioBERT will run on CPU.")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(class_names),
        ignore_mismatched_sizes=True,
    )
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)

    def make_loader(x: sparse.csr_matrix, y: np.ndarray, shuffle: bool) -> DataLoader:
        dataset = SymptomTextDataset(x, y, feature_names)

        def collate(rows: list[tuple[str, int]]) -> dict[str, torch.Tensor]:
            texts, labels = zip(*rows, strict=True)
            encoded = tokenizer(
                list(texts),
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            encoded["labels"] = torch.tensor(labels, dtype=torch.long)
            return encoded

        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=0,
            collate_fn=collate,
            pin_memory=device.type == "cuda",
        )

    train_loader = make_loader(x_train, y_train, True)
    val_loader = make_loader(x_val, y_val, False)
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    stale_epochs = 0
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        seen = 0
        for batch in tqdm(
            train_loader, desc=f"Fine-tuning BioBERT epoch {epoch + 1}", unit="batch"
        ):
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            loss = model(**batch).loss
            if loss is None or not torch.isfinite(loss):
                raise FloatingPointError("BioBERT produced a non-finite training loss.")
            loss.backward()
            optimizer.step()
            size = int(batch["labels"].shape[0])
            total_loss += float(loss.detach().item()) * size
            seen += size

        model.eval()
        validation_loss = 0.0
        validation_seen = 0
        with torch.inference_mode():
            for batch in tqdm(val_loader, desc="Validating BioBERT", unit="batch"):
                batch = {key: value.to(device) for key, value in batch.items()}
                loss = model(**batch).loss
                size = int(batch["labels"].shape[0])
                validation_loss += float(loss.item()) * size
                validation_seen += size
        mean_val_loss = validation_loss / max(validation_seen, 1)
        LOG.info(
            "BioBERT epoch %d/%d: train_loss=%.5f validation_loss=%.5f",
            epoch + 1,
            epochs,
            total_loss / max(seen, 1),
            mean_val_loss,
        )
        if mean_val_loss < best_loss:
            best_loss = mean_val_loss
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= patience:
                LOG.info("BioBERT early stopping after %d epochs.", epoch + 1)
                break

    if best_state is None:
        raise RuntimeError("BioBERT did not produce a valid validation checkpoint.")
    model.load_state_dict(best_state)
    model.eval()

    def probabilities_for(loader: DataLoader) -> np.ndarray:
        output: list[np.ndarray] = []
        with torch.inference_mode():
            for batch in tqdm(loader, desc="BioBERT inference", unit="batch"):
                batch = {key: value.to(device) for key, value in batch.items()}
                logits = model(**{key: value for key, value in batch.items() if key != "labels"}).logits
                output.append(torch.softmax(logits, dim=1).cpu().numpy())
        return np.concatenate(output)

    validation_probabilities = probabilities_for(val_loader)
    validation_score = float(
        np.mean(validation_probabilities.argmax(axis=1) == y_val)
    )
    test_loader = make_loader(x_test, y_test, False)
    probabilities = probabilities_for(test_loader)

    class BioBertPredictionAdapter:
        classes_ = np.arange(len(class_names), dtype=np.int64)

        def predict_proba(self, _x: Any) -> np.ndarray:
            if len(_x) != len(probabilities):
                raise ValueError("BioBERT probabilities do not match the input rows.")
            return probabilities

        def predict(self, _x: Any) -> np.ndarray:
            if len(_x) != len(probabilities):
                raise ValueError("BioBERT predictions do not match the input rows.")
            return probabilities.argmax(axis=1)

    metrics = report_probabilities(
        BioBertPredictionAdapter(), x_test, y_test, class_names, out, "biobert"
    )
    checkpoint = out / "biobert"
    checkpoint.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(checkpoint)
    tokenizer.save_pretrained(checkpoint)
    with (checkpoint / "features_and_classes.json").open("w", encoding="utf-8") as stream:
        json.dump(
            {"feature_names": list(feature_names), "class_names": list(class_names)},
            stream,
            ensure_ascii=False,
            indent=2,
        )
    return metrics, validation_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-class-rows", type=int, default=MIN_CLASS_ROWS)
    parser.add_argument(
        "--min-class-profiles",
        type=int,
        default=MIN_CLASS_PROFILES,
        help="Minimum number of distinct, unambiguous symptom profiles per disease.",
    )
    parser.add_argument("--lightgbm-estimators", type=int, default=300)
    parser.add_argument("--xgboost-estimators", type=int, default=120)
    parser.add_argument("--biobert-model", default=BIOMEDICAL_MODEL)
    parser.add_argument("--biobert-epochs", type=int, default=2)
    parser.add_argument("--biobert-batch-size", type=int, default=16)
    parser.add_argument("--biobert-patience", type=int, default=1)
    parser.add_argument("--skip-biobert", action="store_true")
    args = parser.parse_args()
    if (
        args.min_class_rows < 2
        or args.min_class_profiles < MIN_CLASS_PROFILES
        or args.biobert_batch_size < 1
    ):
        parser.error(
            f"min-class-rows must be >=2, min-class-profiles must be >={MIN_CLASS_PROFILES} "
            "and biobert-batch-size must be >=1"
        )

    configure_logging()
    seed_everything()
    started = time.perf_counter()
    x, y, class_names, feature_names = load_and_merge(
        args.min_class_rows, args.min_class_profiles
    )
    all_indices = np.arange(len(y))
    train_indices, test_indices = train_test_split(
        all_indices,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=y,
    )
    train_indices, val_indices = train_test_split(
        train_indices,
        test_size=0.1,
        random_state=RANDOM_SEED,
        stratify=y[train_indices],
    )
    x_train, y_train = x[train_indices], y[train_indices]
    x_val, y_val = x[val_indices], y[val_indices]
    x_test, y_test = x[test_indices], y[test_indices]
    out = MODELS_DIR / "symptoms"
    out.mkdir(parents=True, exist_ok=True)
    all_metrics: dict[str, dict[str, Any]] = {}
    validation_scores: dict[str, float] = {}

    lightgbm = LGBMClassifier(
        objective="multiclass",
        n_estimators=args.lightgbm_estimators,
        learning_rate=0.05,
        max_depth=-1,
        num_leaves=31,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1,
        verbosity=-1,
    )
    lightgbm.fit(
        x_train,
        y_train,
        eval_set=[(x_val, y_val)],
        callbacks=[],
    )
    all_metrics["lightgbm"] = report_probabilities(
        lightgbm, x_test, y_test, class_names, out, "lightgbm"
    )
    validation_scores["lightgbm"] = validation_top1(lightgbm, x_val, y_val)
    save_bundle(out / "lightgbm.joblib", lightgbm, class_names, feature_names, "lightgbm", all_metrics["lightgbm"])

    xgboost = XGBClassifier(
        objective="multi:softprob",
        num_class=len(class_names),
        n_estimators=args.xgboost_estimators,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        tree_method="hist",
        device="cpu",
        eval_metric="mlogloss",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
    xgboost.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)
    all_metrics["xgboost"] = report_probabilities(
        xgboost, x_test, y_test, class_names, out, "xgboost"
    )
    validation_scores["xgboost"] = validation_top1(xgboost, x_val, y_val)
    save_bundle(out / "xgboost.joblib", xgboost, class_names, feature_names, "xgboost", all_metrics["xgboost"])

    if not args.skip_biobert:
        all_metrics["biobert"], validation_scores["biobert"] = train_biobert(
            x_train,
            y_train,
            x_val,
            y_val,
            x_test,
            y_test,
            feature_names,
            class_names,
            out,
            model_name=args.biobert_model,
            epochs=args.biobert_epochs,
            batch_size=args.biobert_batch_size,
            patience=args.biobert_patience,
        )

    if not validation_scores:
        raise RuntimeError("No model completed test evaluation.")
    winner = max(validation_scores, key=validation_scores.__getitem__)
    summary = {
        "selected_model": winner,
        "selection_metric": "validation_top_1_accuracy",
        "validation_top_1_accuracy": validation_scores,
        "test_metrics": all_metrics,
        "classes": class_names,
        "features": feature_names,
        "minimum_class_rows": args.min_class_rows,
        "minimum_class_profiles": args.min_class_profiles,
        "random_seed": RANDOM_SEED,
        "warning": "Research-only model; metrics are not clinical validation.",
    }
    with (out / "model_metadata.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    LOG.info(
        "Symptom training finished in %.1f minutes; selected %s by validation top-1 score.",
        (time.perf_counter() - started) / 60,
        winner,
    )


if __name__ == "__main__":
    main()
