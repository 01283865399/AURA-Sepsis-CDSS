"""Train and evaluate the newly imported image and liver datasets."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
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
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from _training_common import (
    MODELS_DIR,
    RAW_DIR,
    RANDOM_SEED,
    ROOT,
    clean_features_like_training,
    configure_logging,
    evaluate_classifier,
    make_tabular_preprocessor,
    save_joblib_bundle,
    seed_everything,
)


LOG = logging.getLogger("train_new_datasets")
REGISTRY_PATH = ROOT / "configs" / "dataset_registry.json"
IMAGE_SIZE = 224
EPOCHS = 20
BATCH_SIZE = 32
EARLY_STOPPING_PATIENCE = 5
MINIMUM_PROMOTION_ACCURACY = 0.70
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
IMAGE_DATASETS = (
    "skin_lesions_8class",
    "isic_2019",
    "covid19_radiography",
    "tb_chest_radiography",
)


@dataclass(frozen=True)
class ImageSample:
    path: Path
    label: int


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        raise FileNotFoundError(f"Dataset registry is missing: {REGISTRY_PATH}")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if registry.get("schema_version") != 1 or not isinstance(
        registry.get("datasets"), list
    ):
        raise ValueError(f"Unsupported dataset registry format: {REGISTRY_PATH}")
    return registry


def scan_image_samples(spec: dict[str, Any]) -> tuple[list[ImageSample], list[str]]:
    dataset_root = RAW_DIR / spec["path"]
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"Image dataset folder is missing: {dataset_root}")
    class_dirs = sorted(
        path for path in dataset_root.iterdir() if path.is_dir()
    )
    if len(class_dirs) < 2:
        raise ValueError(f"Expected at least two class folders under {dataset_root}.")
    class_names = [path.name for path in class_dirs]
    image_subdirectory = spec.get("image_subdirectory")
    samples: list[ImageSample] = []
    for label, class_dir in enumerate(class_dirs):
        image_root = class_dir / image_subdirectory if image_subdirectory else class_dir
        if not image_root.is_dir():
            raise FileNotFoundError(f"Image folder is missing: {image_root}")
        paths = sorted(
            path
            for path in image_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        samples.extend(ImageSample(path=path, label=label) for path in paths)
    if not samples:
        raise ValueError(f"No supported images found in {dataset_root}.")
    counts = np.bincount(
        np.asarray([sample.label for sample in samples]), minlength=len(class_names)
    )
    if np.any(counts < 4):
        raise ValueError(
            f"At least four images per class are required for stratified splits: "
            f"{dict(zip(class_names, counts.tolist(), strict=True))}"
        )
    return samples, class_names


def _image_tensor(path: Path, transform: Any | None = None) -> Any:
    from PIL import Image

    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not decode training image: {path}") from exc
    scale = 256 / min(image.size)
    size = (round(image.width * scale), round(image.height * scale))
    image = image.resize(size, Image.Resampling.BICUBIC)
    left = (image.width - IMAGE_SIZE) // 2
    top = (image.height - IMAGE_SIZE) // 2
    image = image.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
    if transform is not None:
        return transform(image)

    import torch

    values = np.asarray(image, dtype=np.float32).copy() / 255.0
    tensor = torch.from_numpy(values).permute(2, 0, 1)
    mean = torch.tensor([0.485, 0.456, 0.406])[:, None, None]
    std = torch.tensor([0.229, 0.224, 0.225])[:, None, None]
    return (tensor - mean) / std


class ImageFeatureDataset:
    def __init__(
        self, samples: list[ImageSample], transform: Any | None = None
    ) -> None:
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Any, int]:
        import torch

        sample = self.samples[index]
        return _image_tensor(sample.path, self.transform), sample.label


def make_image_splits(
    samples: list[ImageSample],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = np.asarray([sample.label for sample in samples], dtype=np.int64)
    all_indices = np.arange(len(samples))
    train_validation, test_indices = train_test_split(
        all_indices,
        test_size=0.15,
        random_state=RANDOM_SEED,
        stratify=labels,
    )
    train_indices, validation_indices = train_test_split(
        train_validation,
        test_size=0.15 / 0.85,
        random_state=RANDOM_SEED,
        stratify=labels[train_validation],
    )
    return train_indices, validation_indices, test_indices


def available_memory_gib() -> float | None:
    try:
        import psutil
    except ImportError:
        return None
    return psutil.virtual_memory().available / (1024**3)


def image_loader_predictions(
    model: Any,
    loader: Any,
    device: Any,
    loss_function: Any | None = None,
) -> tuple[np.ndarray, np.ndarray, float | None]:
    import torch

    model.eval()
    probability_batches: list[np.ndarray] = []
    label_batches: list[np.ndarray] = []
    total_loss = 0.0
    total_rows = 0
    with torch.inference_mode():
        for images, labels in loader:
            logits = model(images.to(device))
            if loss_function is not None:
                total_loss += float(loss_function(logits, labels.to(device))) * len(labels)
            probability_batches.append(torch.softmax(logits, dim=1).cpu().numpy())
            label_batches.append(labels.numpy())
            total_rows += len(labels)
    probabilities = np.concatenate(probability_batches, axis=0)
    truth = np.concatenate(label_batches).astype(np.int64, copy=False)
    average_loss = total_loss / total_rows if loss_function is not None else None
    return truth, probabilities, average_loss


def image_test_metrics(
    model: Any,
    loader: Any,
    class_names: list[str],
    output_dir: Path,
    device: Any,
) -> dict[str, Any]:
    truth, probabilities, _ = image_loader_predictions(model, loader, device)
    predicted = probabilities.argmax(axis=1)
    report = classification_report(
        truth,
        predicted,
        labels=np.arange(len(class_names)),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    metrics: dict[str, Any] = {
        "model": "efficientnet_b0",
        "test_rows": int(len(truth)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "precision_weighted": float(
            precision_score(truth, predicted, average="weighted", zero_division=0)
        ),
        "recall_weighted": float(
            recall_score(truth, predicted, average="weighted", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(truth, predicted, average="weighted", zero_division=0)
        ),
        "class_names": class_names,
        "classification_report": report,
    }
    top_k_accuracy: dict[str, float] = {}
    ranking = np.argsort(probabilities, axis=1)[:, ::-1]
    for k in (1, 3, 5):
        if k <= probabilities.shape[1]:
            top_k_accuracy[str(k)] = float(
                np.mean(np.any(ranking[:, :k] == truth[:, None], axis=1))
            )
    metrics["top_k_accuracy"] = top_k_accuracy
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = confusion_matrix(
        truth, predicted, labels=np.arange(len(class_names))
    )
    pd.DataFrame(matrix, index=class_names, columns=class_names).to_csv(
        output_dir / "efficientnet_b0_confusion_matrix.csv",
        encoding="utf-8",
    )
    report_path = output_dir / "efficientnet_b0_evaluation.json"
    temporary_report = report_path.with_suffix(".json.tmp")
    temporary_report.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_report.replace(report_path)
    print(f"\n=== efficientnet_b0 held-out test report (n={len(truth)}) ===")
    print(
        classification_report(
            truth,
            predicted,
            labels=np.arange(len(class_names)),
            target_names=class_names,
            zero_division=0,
        )
    )
    for k in (1, 3, 5):
        score = top_k_accuracy.get(str(k))
        print(f"Top-{k} accuracy: {score:.4f}" if score is not None else f"Top-{k}: N/A")
    print(f"Confusion matrix: {output_dir / 'efficientnet_b0_confusion_matrix.csv'}")
    return metrics


def train_image_dataset(spec: dict[str, Any]) -> None:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, Subset
        from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
        from torchvision import transforms
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch and a compatible torchvision build are required for image training."
        ) from exc

    dataset_name = str(spec["name"])
    samples, class_names = scan_image_samples(spec)
    labels = np.asarray([sample.label for sample in samples], dtype=np.int64)
    train_indices, validation_indices, test_indices = make_image_splits(samples)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(max(1, min(os.cpu_count() or 1, 4)))
    memory_available = available_memory_gib()
    if memory_available is None:
        LOG.warning("psutil unavailable; using the conservative CPU batch size.")
    if device.type == "cuda":
        batch_size = BATCH_SIZE
    elif memory_available is None or memory_available < 3:
        batch_size = 8
    elif memory_available < 6:
        batch_size = 16
    else:
        batch_size = BATCH_SIZE

    normalize = transforms.Normalize(
        mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
    )
    training_transform = transforms.Compose(
        [
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(
                brightness=0.15, contrast=0.15, saturation=0.15, hue=0.02
            ),
            transforms.RandomAffine(
                degrees=0, translate=(0.05, 0.05), scale=(0.9, 1.1), shear=8
            ),
            transforms.ToTensor(),
            normalize,
        ]
    )
    evaluation_transform = transforms.Compose(
        [transforms.ToTensor(), normalize]
    )
    train_dataset = ImageFeatureDataset(samples, training_transform)
    evaluation_dataset = ImageFeatureDataset(samples, evaluation_transform)
    generator = torch.Generator().manual_seed(RANDOM_SEED)
    loader_options = {
        "batch_size": batch_size,
        "num_workers": 0,
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(
        Subset(train_dataset, train_indices.tolist()),
        shuffle=True,
        generator=generator,
        **loader_options,
    )
    validation_loader = DataLoader(
        Subset(evaluation_dataset, validation_indices.tolist()),
        shuffle=False,
        **loader_options,
    )
    test_loader = DataLoader(
        Subset(evaluation_dataset, test_indices.tolist()),
        shuffle=False,
        **loader_options,
    )
    weights = EfficientNet_B0_Weights.DEFAULT
    LOG.info(
        "Loading %s images=%d classes=%d device=%s pretrained=%s batch_size=%d "
        "available_memory_gib=%s",
        dataset_name,
        len(samples),
        len(class_names),
        device,
        weights.name,
        batch_size,
        f"{memory_available:.2f}" if memory_available is not None else "unknown",
    )
    model = efficientnet_b0(weights=weights)
    model.classifier[1] = nn.Linear(
        model.classifier[1].in_features, len(class_names)
    )
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    for stage in model.features[5:]:
        for parameter in stage.parameters():
            parameter.requires_grad = True
    model.to(device)

    class_counts = np.bincount(labels[train_indices], minlength=len(class_names))
    if np.any(class_counts == 0):
        raise ValueError(f"A training split is missing a class: {class_counts.tolist()}")
    class_weight_values = len(train_indices) / (len(class_names) * class_counts)
    class_weights = torch.tensor(
        class_weight_values,
        dtype=torch.float32,
        device=device,
    )
    loss_function = nn.CrossEntropyLoss(weight=class_weights)
    feature_parameters = [
        parameter for parameter in model.features.parameters() if parameter.requires_grad
    ]
    optimizer = torch.optim.AdamW(
        [
            {"params": feature_parameters, "lr": 1e-4},
            {"params": model.classifier.parameters(), "lr": 1e-3},
        ],
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2, min_lr=1e-6
    )
    best_validation_accuracy = -1.0
    best_state: dict[str, Any] | None = None
    epochs_without_improvement = 0
    completed_epochs = 0
    for epoch in range(EPOCHS):
        model.train()
        epoch_loss = 0.0
        for images, batch_labels in train_loader:
            images = images.to(device)
            batch_labels = batch_labels.to(device)
            logits = model(images)
            loss = loss_function(logits, batch_labels)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach()) * len(batch_labels)
        validation_truth, validation_probabilities, validation_loss = (
            image_loader_predictions(
                model, validation_loader, device, loss_function
            )
        )
        validation_predictions = validation_probabilities.argmax(axis=1)
        validation_accuracy = float(
            accuracy_score(validation_truth, validation_predictions)
        )
        validation_f1 = float(
            f1_score(
                validation_truth,
                validation_predictions,
                average="macro",
                zero_division=0,
            )
        )
        scheduler.step(validation_loss)
        completed_epochs = epoch + 1
        if validation_accuracy > best_validation_accuracy:
            best_validation_accuracy = validation_accuracy
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        LOG.info(
            "%s epoch=%d/%d loss=%.5f validation_loss=%.5f "
            "validation_accuracy=%.4f validation_macro_f1=%.4f "
            "lr=%.2e early_stop=%d/%d",
            dataset_name,
            completed_epochs,
            EPOCHS,
            epoch_loss / len(train_indices),
            validation_loss,
            validation_accuracy,
            validation_f1,
            optimizer.param_groups[-1]["lr"],
            epochs_without_improvement,
            EARLY_STOPPING_PATIENCE,
        )
        if epochs_without_improvement >= EARLY_STOPPING_PATIENCE:
            LOG.info("Early stopping %s after epoch %d", dataset_name, completed_epochs)
            break
        epoch_memory = available_memory_gib()
        LOG.info(
            "%s epoch=%d available_memory_gib=%s",
            dataset_name,
            completed_epochs,
            f"{epoch_memory:.2f}" if epoch_memory is not None else "unknown",
        )

    if best_state is None:
        raise RuntimeError(f"Training produced no best checkpoint for {dataset_name}.")
    model.load_state_dict(best_state, strict=True)

    output_dir = MODELS_DIR / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_evaluation_dir = output_dir / "candidate_evaluation"
    candidate_evaluation_dir.mkdir(parents=True, exist_ok=True)
    metrics = image_test_metrics(
        model,
        test_loader,
        class_names,
        candidate_evaluation_dir,
        device,
    )
    if metrics["accuracy"] <= MINIMUM_PROMOTION_ACCURACY:
        LOG.error(
            "%s candidate accuracy %.4f did not exceed promotion threshold %.2f; "
            "existing model and metadata were preserved. Candidate evaluation: %s",
            dataset_name,
            metrics["accuracy"],
            MINIMUM_PROMOTION_ACCURACY,
            candidate_evaluation_dir,
        )
        return

    checkpoint_path = output_dir / "efficientnet_b0.pt"
    temporary_checkpoint = checkpoint_path.with_suffix(".pt.tmp")
    torch.save(model.cpu().state_dict(), temporary_checkpoint)
    metadata = {
        "dataset": dataset_name,
        "architecture": "efficientnet_b0",
        "pretrained_weights": weights.name,
        "epochs": completed_epochs,
        "max_epochs": EPOCHS,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "batch_size": batch_size,
        "fine_tuned_stages": "features[5:] and classifier",
        "augmentation": [
            "random_horizontal_flip",
            "random_vertical_flip",
            "random_rotation_20_degrees",
            "color_jitter",
            "random_affine",
        ],
        "class_weights": {
            name: float(weight)
            for name, weight in zip(class_names, class_weight_values, strict=True)
        },
        "random_seed": RANDOM_SEED,
        "device": str(device),
        "image_count": len(samples),
        "class_counts": {
            name: int(count)
            for name, count in zip(
                class_names,
                np.bincount(labels, minlength=len(class_names)),
                strict=True,
            )
        },
        "classes": class_names,
        "features": ["RGB pixels, resized and center-cropped to 224x224"],
        "train_rows": int(len(train_indices)),
        "validation_rows": int(len(validation_indices)),
        "test_rows": int(len(test_indices)),
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision_weighted"],
        "recall": metrics["recall_weighted"],
        "f1": metrics["f1_weighted"],
        "top_k_accuracy": metrics["top_k_accuracy"],
        "confusion_matrix": "efficientnet_b0_confusion_matrix.csv",
    }
    temporary_metadata = output_dir / "metadata.json.tmp"
    temporary_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_checkpoint.replace(checkpoint_path)
    for artifact_name in (
        "efficientnet_b0_confusion_matrix.csv",
        "efficientnet_b0_evaluation.json",
    ):
        (candidate_evaluation_dir / artifact_name).replace(output_dir / artifact_name)
    temporary_metadata.replace(output_dir / "metadata.json")
    candidate_evaluation_dir.rmdir()
    LOG.info("Saved %s model and metadata to %s", dataset_name, output_dir)


def train_liver_dataset(spec: dict[str, Any]) -> None:
    dataset_name = str(spec["name"])
    source = RAW_DIR / spec["path"]
    if not source.is_file():
        raise FileNotFoundError(f"Tabular dataset file is missing: {source}")
    frame = pd.read_csv(source, low_memory=False)
    target = str(spec["target"])
    if target not in frame.columns:
        raise ValueError(f"Expected target column {target!r}; found {list(frame.columns)}")
    class_mapping = spec["class_mapping"]
    labels = pd.to_numeric(frame.pop(target), errors="coerce")
    valid_rows = labels.isin([int(label) for label in class_mapping])
    features = frame.loc[valid_rows].reset_index(drop=True)
    labels = labels.loc[valid_rows].astype(int).reset_index(drop=True)
    encoded = labels.map(
        {int(key): index for index, key in enumerate(class_mapping)}
    ).astype("int64")
    class_names = [class_mapping[key] for key in class_mapping]
    if features.empty or encoded.nunique() != len(class_names):
        raise ValueError("The liver dataset must contain at least one row for every class.")
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        encoded,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=encoded,
    )
    preprocessor, numeric_columns, _, clean_train = make_tabular_preprocessor(x_train)
    clean_test = clean_features_like_training(x_test, numeric_columns)
    negatives = int((y_train == 0).sum())
    positives = int((y_train == 1).sum())
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                XGBClassifier(
                    n_estimators=200,
                    max_depth=3,
                    learning_rate=0.04,
                    subsample=0.85,
                    colsample_bytree=0.9,
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
    output_dir = MODELS_DIR / dataset_name
    metrics = evaluate_classifier(
        "xgboost",
        model,
        clean_test,
        y_test,
        class_names,
        output_dir,
        top_k=True,
    )
    save_joblib_bundle(
        output_dir / "xgboost.joblib",
        model=model,
        class_names=class_names,
        feature_names=list(features.columns),
        metadata={
            "model_name": "XGBoost",
            "dataset": str(source.relative_to(RAW_DIR)),
            "rows": int(len(features)),
            "target": target,
            "class_mapping": class_mapping,
            "random_seed": RANDOM_SEED,
        },
    )
    metadata = {
        "dataset": dataset_name,
        "model": "XGBoost",
        "artifact": "xgboost.joblib",
        "random_seed": RANDOM_SEED,
        "rows": int(len(features)),
        "features": list(features.columns),
        "classes": class_names,
        "class_counts": {
            class_mapping[str(label)]: int(count)
            for label, count in labels.value_counts().items()
        },
        "target": target,
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision_weighted"],
        "recall": metrics["recall_weighted"],
        "f1": metrics["f1_weighted"],
        "top_k_accuracy": metrics.get("top_k_accuracy", {}),
        "confusion_matrix": "xgboost_confusion_matrix.csv",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_metadata = output_dir / "metadata.json.tmp"
    temporary_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_metadata.replace(output_dir / "metadata.json")
    LOG.info("Saved %s model and metadata to %s", dataset_name, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=(*IMAGE_DATASETS, "indian_liver_patient"),
        help="Train one registered dataset instead of all five.",
    )
    args = parser.parse_args()
    configure_logging()
    seed_everything()
    registry = load_registry()
    specs = {
        item["name"]: item
        for item in registry["datasets"]
        if item.get("name") in (*IMAGE_DATASETS, "indian_liver_patient")
    }
    expected = set((*IMAGE_DATASETS, "indian_liver_patient"))
    missing = expected.difference(specs)
    if missing:
        raise ValueError(f"Dataset registry is missing entries: {sorted(missing)}")
    selected = [args.dataset] if args.dataset else list((*IMAGE_DATASETS, "indian_liver_patient"))
    for dataset_name in selected:
        LOG.info("Starting new-dataset training: %s", dataset_name)
        if dataset_name == "indian_liver_patient":
            train_liver_dataset(specs[dataset_name])
        else:
            train_image_dataset(specs[dataset_name])
        LOG.info("Completed new-dataset training: %s", dataset_name)


if __name__ == "__main__":
    main()
