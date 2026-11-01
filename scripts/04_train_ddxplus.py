"""Train the 512-256-128-49 DDXPlus model using streamed CSV batches."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from tqdm import tqdm

from _training_common import MODELS_DIR, RAW_DIR, RANDOM_SEED, configure_logging, seed_everything


LOG = logging.getLogger("train_ddxplus")
INPUT_SIZE = 512
EVIDENCE_FEATURES = INPUT_SIZE - 2
CSV_COLUMNS = ["AGE", "SEX", "PATHOLOGY", "EVIDENCES"]
SPLITS = ("train", "validate", "test")


def load_metadata() -> tuple[list[str], dict[str, Any]]:
    data_dir = RAW_DIR / "ddxplus_data"
    conditions_path = data_dir / "release_conditions.json"
    evidences_path = data_dir / "release_evidences.json"
    if not conditions_path.is_file() or not evidences_path.is_file():
        raise FileNotFoundError(
            "DDXPlus metadata is missing. Run scripts/02_download_ddxplus.ps1 first."
        )
    conditions = json.loads(conditions_path.read_text(encoding="utf-8"))
    evidences = json.loads(evidences_path.read_text(encoding="utf-8"))
    if not isinstance(conditions, dict) or not isinstance(evidences, dict):
        raise ValueError("Unexpected DDXPlus metadata format; expected JSON objects.")
    class_names = sorted(str(name) for name in conditions)
    if len(class_names) != 49:
        raise ValueError(f"Expected 49 DDXPlus pathologies; metadata contains {len(class_names)}.")
    return class_names, evidences


def evidence_token_to_definition(evidences: dict[str, Any]) -> dict[str, set[str]]:
    known: dict[str, set[str]] = {}
    for code, definition in evidences.items():
        if definition.get("data_type") == "B":
            known[str(code)] = {str(code)}
        else:
            values = definition.get("possible-values", [])
            known[str(code)] = {f"{code}_@_{value}" for value in values}
    return known


def parse_evidence(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError) as exc:
                raise ValueError(
                    f"Could not parse DDXPlus evidence record: {value[:160]}"
                ) from exc
    else:
        parsed = value
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"Invalid DDXPlus evidence record: {str(value)[:160]}")
    return parsed


def scan_training_set(
    csv_path: Path,
    class_index: dict[str, int],
    known_evidence: dict[str, set[str]],
    chunk_size: int,
) -> tuple[Counter[str], Counter[int], int]:
    feature_counts: Counter[str] = Counter()
    label_counts: Counter[int] = Counter()
    rows = 0
    chunks = pd.read_csv(
        csv_path, usecols=CSV_COLUMNS, chunksize=chunk_size, low_memory=False
    )
    for chunk in tqdm(chunks, desc="Indexing DDXPlus", unit="chunk"):
        for age, sex, pathology, raw_evidence in chunk.itertuples(index=False, name=None):
            label_key = str(pathology).strip().casefold()
            if label_key not in class_index:
                raise ValueError(f"Unknown DDXPlus pathology label: {label_key!r}")
            numeric_age = float(age)
            if not math.isfinite(numeric_age) or not 0 <= numeric_age <= 120:
                raise ValueError(f"Invalid age in DDXPlus training row: {age!r}")
            if str(sex).upper() not in {"F", "M"}:
                raise ValueError(f"Invalid sex value in DDXPlus training row: {sex!r}")
            for token in parse_evidence(raw_evidence):
                base_code = token.split("_@_", 1)[0]
                if base_code not in known_evidence:
                    raise ValueError(f"Unknown DDXPlus evidence code in training data: {token!r}")
                if token not in known_evidence[base_code]:
                    raise ValueError(f"Invalid DDXPlus evidence value in training data: {token!r}")
                feature_counts[token] += 1
            label_counts[class_index[label_key]] += 1
            rows += 1
    if rows == 0:
        raise ValueError(f"Training CSV contains no patient rows: {csv_path}")
    return feature_counts, label_counts, rows


def make_feature_vocab(evidences: dict[str, Any]) -> dict[str, list[int]]:
    """Represent binary/categorical values directly and hash every multi-choice value."""
    binary_codes = sorted(
        str(code)
        for code, definition in evidences.items()
        if definition.get("data_type") == "B"
    )
    categorical_tokens = sorted(
        f"{code}_@_{value}"
        for code, definition in evidences.items()
        if definition.get("data_type") == "C"
        for value in definition.get("possible-values", [])
    )
    multi_tokens = sorted(
        f"{code}_@_{value}"
        for code, definition in evidences.items()
        if definition.get("data_type") == "M"
        for value in definition.get("possible-values", [])
    )
    direct_features = len(binary_codes) + len(categorical_tokens)
    hashed_features = EVIDENCE_FEATURES - direct_features
    if direct_features >= EVIDENCE_FEATURES or EVIDENCE_FEATURES - direct_features < 3 or not multi_tokens:
        raise ValueError(
            "DDXPlus evidence schema cannot fit binary and categorical values "
            "in the configured 512-feature model."
        )
    vocabulary: dict[str, list[int]] = {}
    next_index = 2
    for code in binary_codes:
        vocabulary[code] = [next_index]
        next_index += 1
    for token in categorical_tokens:
        vocabulary[token] = [next_index]
        next_index += 1
    band_sizes = [
        hashed_features // 3 + (1 if band < hashed_features % 3 else 0)
        for band in range(3)
    ]
    band_starts = [
        next_index,
        next_index + band_sizes[0],
        next_index + band_sizes[0] + band_sizes[1],
    ]
    for token in multi_tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        vocabulary[token] = [
            start
            + int.from_bytes(digest[band * 8 : (band + 1) * 8], byteorder="big")
            % band_sizes[band]
            for band, start in enumerate(band_starts)
        ]
    return vocabulary


class FocalLoss:
    def __new__(cls, torch: Any, alpha: Any, gamma: float = 2.0) -> Any:
        class _FocalLoss(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.register_buffer("alpha", alpha)
                self.gamma = gamma

            def forward(self, logits: Any, targets: Any) -> Any:
                log_probabilities = torch.nn.functional.log_softmax(logits, dim=1)
                probabilities = log_probabilities.exp()
                target_log_probability = log_probabilities.gather(
                    1, targets.unsqueeze(1)
                ).squeeze(1)
                target_probability = probabilities.gather(
                    1, targets.unsqueeze(1)
                ).squeeze(1)
                weights = self.alpha.gather(0, targets)
                return (
                    -weights
                    * (1.0 - target_probability).pow(self.gamma)
                    * target_log_probability
                ).mean()

        return _FocalLoss()


def make_model(torch: Any, num_classes: int) -> Any:
    return torch.nn.Sequential(
        torch.nn.Linear(INPUT_SIZE, 256),
        torch.nn.ReLU(),
        torch.nn.Dropout(0.2),
        torch.nn.Linear(256, 128),
        torch.nn.ReLU(),
        torch.nn.Dropout(0.2),
        torch.nn.Linear(128, num_classes),
    )


def stream_batches(
    path: Path,
    batch_size: int,
    feature_vocab: dict[str, list[int]],
    class_index: dict[str, int],
    chunk_size: int,
    torch: Any,
) -> Iterator[tuple[Any, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing DDXPlus CSV {path}. Run scripts/02_download_ddxplus.ps1 first."
        )
    features: list[np.ndarray] = []
    labels: list[int] = []
    for chunk in pd.read_csv(
        path, usecols=CSV_COLUMNS, chunksize=chunk_size, low_memory=False
    ):
        for age, sex, pathology, raw_evidence in chunk.itertuples(index=False, name=None):
            vector = np.zeros(INPUT_SIZE, dtype=np.float32)
            vector[0] = float(age) / 120.0
            vector[1] = 1.0 if str(sex).upper() == "M" else 0.0
            for token in parse_evidence(raw_evidence):
                indices = feature_vocab.get(token)
                if indices is not None:
                    for index in indices:
                        vector[index] = 1.0
            features.append(vector)
            try:
                labels.append(class_index[str(pathology).strip().casefold()])
            except KeyError as exc:
                raise ValueError(f"Unknown DDXPlus pathology label: {pathology!r}") from exc
            if len(features) == batch_size:
                yield torch.from_numpy(np.stack(features)), torch.tensor(labels, dtype=torch.long)
                features.clear()
                labels.clear()
    if features:
        yield torch.from_numpy(np.stack(features)), torch.tensor(labels, dtype=torch.long)


def evaluate_model(
    model: Any,
    path: Path,
    *,
    split_name: str,
    batch_size: int,
    feature_vocab: dict[str, list[int]],
    class_index: dict[str, int],
    class_names: list[str],
    chunk_size: int,
    torch: Any,
    device: Any,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    model.eval()
    probabilities: list[np.ndarray] = []
    truths: list[np.ndarray] = []
    loss_sum = 0.0
    total = 0
    with torch.inference_mode():
        batches = stream_batches(
            path, batch_size, feature_vocab, class_index, chunk_size, torch
        )
        for x_batch, y_batch in tqdm(batches, desc=f"Evaluating {split_name}", unit="batch"):
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)
            logits = model(x_batch)
            loss_sum += float(torch.nn.functional.cross_entropy(logits, y_batch).item()) * len(
                y_batch
            )
            batch_probabilities = torch.softmax(logits, dim=1).cpu().numpy()
            probabilities.append(batch_probabilities)
            truths.append(y_batch.cpu().numpy())
            total += len(y_batch)
    if not total:
        raise ValueError(f"DDXPlus {split_name} split contains no patient rows.")

    y_true = np.concatenate(truths)
    y_proba = np.concatenate(probabilities)
    y_pred = y_proba.argmax(axis=1)
    report = classification_report(
        y_true,
        y_pred,
        labels=np.arange(len(class_names)),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    top_k: dict[str, float] = {}
    top_indices = np.argsort(y_proba, axis=1)[:, ::-1]
    for k in (1, 3, 5, 10):
        top_k[str(k)] = float(
            np.mean(np.any(top_indices[:, :k] == y_true[:, None], axis=1))
        )
    metrics: dict[str, Any] = {
        "split": split_name,
        "rows": total,
        "loss": loss_sum / total,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_weighted": float(
            precision_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "recall_weighted": float(
            recall_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "top_k_accuracy": top_k,
        "classification_report": report,
        "confusion_matrix_file": "confusion_matrix.csv",
    }
    return metrics, y_true, y_pred


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=20_000)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.patience, args.chunk_size) < 1:
        parser.error("epochs, batch-size, patience, and chunk-size must all be positive.")

    configure_logging()
    seed_everything()
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("DDXPlus training requires the declared PyTorch dependency.") from exc
    torch.set_num_threads(max(1, min(os.cpu_count() or 1, 8)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    LOG.info("Using device=%s; PyTorch=%s", device, torch.__version__)
    if device.type == "cpu":
        LOG.warning(
            "CUDA is unavailable; 1M-row DDXPlus training may take a long time on CPU."
        )

    data_dir = RAW_DIR / "ddxplus_data"
    class_names, evidence_metadata = load_metadata()
    class_index = {name: index for index, name in enumerate(class_names)}
    normalized_classes = {name.casefold(): name for name in class_names}
    class_index_normalized = {
        key: class_index[canonical] for key, canonical in normalized_classes.items()
    }
    known_evidence = evidence_token_to_definition(evidence_metadata)
    train_path = data_dir / "release_train_patients.csv"
    feature_counts, label_counts, train_rows = scan_training_set(
        train_path, class_index_normalized, known_evidence, args.chunk_size
    )
    feature_vocab = make_feature_vocab(evidence_metadata)
    unexpected_tokens = set(feature_counts).difference(feature_vocab)
    if unexpected_tokens:
        raise ValueError(
            f"Training data contains evidence tokens missing from the feature map: "
            f"{sorted(unexpected_tokens)[:10]}"
        )
    multi_tokens = [
        token
        for token in feature_vocab
        if "_@_" in token
        and evidence_metadata[token.split("_@_", 1)[0]].get("data_type") == "M"
    ]
    multi_indices = {
        index for token in multi_tokens for index in feature_vocab[token]
    }
    multi_signatures = {tuple(feature_vocab[token]) for token in multi_tokens}
    LOG.info(
        "Training rows=%s; pathology labels=%s; observed evidence tokens=%s; "
        "mapped tokens=%s; occupied multi-choice buckets=%s; "
        "colliding multi-choice signatures=%s / input=%s",
        f"{train_rows:,}",
        len(label_counts),
        len(feature_counts),
        len(feature_vocab),
        len(multi_indices),
        len(multi_tokens) - len(multi_signatures),
        INPUT_SIZE,
    )
    if len(label_counts) != len(class_names):
        raise ValueError(
            f"Expected all {len(class_names)} pathologies in training data; "
            f"found {len(label_counts)}."
        )

    counts = np.asarray(
        [label_counts.get(index, 0) for index in range(len(class_names))],
        dtype=np.float64,
    )
    if np.any(counts == 0):
        raise ValueError("At least one DDXPlus training pathology has no samples.")
    class_weights = train_rows / (len(class_names) * counts)
    class_weights = np.clip(class_weights, 0.25, 10.0)
    class_weights /= class_weights.mean()
    alpha = torch.tensor(class_weights, dtype=torch.float32, device=device)
    model = make_model(torch, len(class_names)).to(device)
    criterion = FocalLoss(torch, alpha, gamma=2.0).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=1e-4
    )
    out = MODELS_DIR / "ddxplus"
    out.mkdir(parents=True, exist_ok=True)
    validation_path = data_dir / "release_validate_patients.csv"
    best_loss = math.inf
    best_state: dict[str, Any] | None = None
    stale_epochs = 0

    for epoch in range(args.epochs):
        model.train()
        epoch_loss = 0.0
        seen = 0
        batches = stream_batches(
            train_path,
            args.batch_size,
            feature_vocab,
            class_index_normalized,
            args.chunk_size,
            torch,
        )
        for x_batch, y_batch in tqdm(
            batches, desc=f"Training DDXPlus epoch {epoch + 1}", unit="batch"
        ):
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x_batch), y_batch)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"Non-finite DDXPlus focal loss in epoch {epoch + 1}.")
            loss.backward()
            optimizer.step()
            count = len(y_batch)
            epoch_loss += float(loss.detach().item()) * count
            seen += count

        validation, _, _ = evaluate_model(
            model,
            validation_path,
            split_name="validation",
            batch_size=args.batch_size,
            feature_vocab=feature_vocab,
            class_index=class_index_normalized,
            class_names=class_names,
            chunk_size=args.chunk_size,
            torch=torch,
            device=device,
        )
        LOG.info(
            "Epoch %d/%d: train_loss=%.5f validation_loss=%.5f accuracy=%.4f",
            epoch + 1,
            args.epochs,
            epoch_loss / max(seen, 1),
            validation["loss"],
            validation["accuracy"],
        )
        if validation["loss"] < best_loss:
            best_loss = float(validation["loss"])
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= args.patience:
                LOG.info("Early stopping after epoch %d.", epoch + 1)
                break
    if best_state is None:
        raise RuntimeError("DDXPlus training produced no valid checkpoint.")
    model.load_state_dict(best_state)
    model.to(device)

    test_metrics, y_true, y_pred = evaluate_model(
        model,
        data_dir / "release_test_patients.csv",
        split_name="test",
        batch_size=args.batch_size,
        feature_vocab=feature_vocab,
        class_index=class_index_normalized,
        class_names=class_names,
        chunk_size=args.chunk_size,
        torch=torch,
        device=device,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=np.arange(len(class_names)))
    pd.DataFrame(matrix, index=class_names, columns=class_names).to_csv(
        out / "confusion_matrix.csv", encoding="utf-8"
    )
    with (out / "test_report.json").open("w", encoding="utf-8") as stream:
        json.dump(test_metrics, stream, ensure_ascii=False, indent=2)
    print("\n=== DDXPlus held-out test report ===")
    print(
        classification_report(
            y_true,
            y_pred,
            labels=np.arange(len(class_names)),
            target_names=class_names,
            zero_division=0,
        )
    )
    print(
        "Top-K accuracy: "
        + json.dumps(test_metrics["top_k_accuracy"], ensure_ascii=False)
    )
    print(f"Confusion matrix: {out / 'confusion_matrix.csv'}")

    temporary = out / "model_state.pt.tmp"
    torch.save(model.state_dict(), temporary)
    os.replace(temporary, out / "model_state.pt")
    artifacts = {
        "architecture": [INPUT_SIZE, 256, 128, len(class_names)],
        "feature_vocab": feature_vocab,
        "encoding": {
            "binary": "one-hot presence",
            "categorical": "one-hot possible values",
            "multi_choice": "three-band stable SHA-256 feature hashing",
            "multi_choice_hash_buckets": len(multi_indices),
            "multi_choice_signature_collisions": len(multi_tokens) - len(multi_signatures),
        },
        "class_names": class_names,
        "known_evidence": {key: sorted(values) for key, values in known_evidence.items()},
        "test_metrics": {
            key: value for key, value in test_metrics.items() if key != "classification_report"
        },
        "random_seed": RANDOM_SEED,
    }
    (out / "metadata.json").write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    LOG.info("Saved DDXPlus model and metrics to %s", out)


if __name__ == "__main__":
    main()
