"""Lazy, validated loading and prediction for research-only model artifacts."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
LOG = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """A required trained model artifact is absent or malformed."""


class InvalidModelInputError(ValueError):
    """A request contains a feature unknown to the model's training schema."""


def _load_image_classifier(dataset: str) -> tuple[Any, list[str], Any]:
    folder = settings.root / "models" / dataset
    metadata_path = folder / "metadata.json"
    checkpoint_path = folder / "efficientnet_b0.pt"
    if not metadata_path.is_file() or not checkpoint_path.is_file():
        raise ModelUnavailableError(
            f"Trained image model artifacts are missing for {dataset}: {folder}"
        )
    try:
        import torch
        from torchvision.models import efficientnet_b0

        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        classes = metadata["classes"]
        if (
            metadata.get("architecture") != "efficientnet_b0"
            or not isinstance(classes, list)
            or not classes
        ):
            raise ValueError("Unexpected image model metadata.")
        model = efficientnet_b0(weights=None)
        model.classifier[1] = torch.nn.Linear(
            model.classifier[1].in_features, len(classes)
        )
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
    except (ImportError, OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError(
            f"Could not load the trained EfficientNet-B0 model for {dataset}."
        ) from exc
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return model, [str(label) for label in classes], device


class ImageModelPredictor:
    """Load one trained EfficientNet artifact and predict validated image bytes."""

    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        self.model, self.class_names, self.device = _load_image_classifier(dataset)

    def predict(
        self, image_bytes: bytes, top_k: int
    ) -> tuple[str, list[dict[str, Any]]]:
        try:
            import torch
        except ImportError as exc:
            raise ModelUnavailableError(
                "PyTorch is required for image inference."
            ) from exc
        if len(image_bytes) > 10 * 1024 * 1024:
            raise InvalidModelInputError("Image exceeds the 10 MiB upload limit.")
        try:
            with Image.open(BytesIO(image_bytes)) as probe:
                if probe.width < 1 or probe.height < 1:
                    raise InvalidModelInputError("Image dimensions must be positive.")
                if probe.width * probe.height > 40_000_000:
                    raise InvalidModelInputError("Image exceeds the 40-megapixel limit.")
                probe.verify()
            with Image.open(BytesIO(image_bytes)) as source:
                image = source.convert("RGB")
        except InvalidModelInputError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidModelInputError("The uploaded file is not a valid image.") from exc

        shortest_edge = min(image.size)
        longest_edge = max(image.size)
        if longest_edge / shortest_edge > 20:
            raise InvalidModelInputError("Image aspect ratio exceeds the supported limit.")
        scale = 256 / shortest_edge
        resized_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(resized_size, Image.Resampling.BICUBIC)
        left = (image.width - 224) // 2
        top = (image.height - 224) // 2
        image = image.crop((left, top, left + 224, top + 224))
        pixels = np.asarray(image, dtype=np.float32).copy() / 255.0
        tensor = torch.from_numpy(pixels).permute(2, 0, 1)
        mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32)[:, None, None]
        std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32)[:, None, None]
        tensor = ((tensor - mean) / std).unsqueeze(0)
        try:
            with torch.inference_mode():
                probabilities = (
                    torch.softmax(self.model(tensor.to(self.device)), dim=1)
                    .cpu()
                    .numpy()
                )
        except RuntimeError as exc:
            LOG.exception("Image inference failed for dataset %s.", self.dataset)
            raise ModelUnavailableError(
                f"Image inference failed for {self.dataset}."
            ) from exc
        return "EfficientNet-B0", _predictions(
            probabilities, self.class_names, top_k
        )


@lru_cache(maxsize=8)
def _image_predictor(dataset: str) -> ImageModelPredictor:
    return ImageModelPredictor(dataset)


def predict_image(
    dataset: str, image_bytes: bytes, top_k: int
) -> tuple[str, list[dict[str, Any]]]:
    return _image_predictor(dataset).predict(image_bytes, top_k)


def _normalize_feature_name(value: str) -> str:
    return "_".join(value.strip().casefold().replace("_", " ").split())


@lru_cache(maxsize=16)
def _load_joblib(path_string: str) -> dict[str, Any]:
    path = Path(path_string)
    if not path.is_file():
        raise ModelUnavailableError(f"Trained model artifact is missing: {path}")
    try:
        bundle = joblib.load(path)
    except (OSError, ValueError, EOFError) as exc:
        raise ModelUnavailableError(f"Could not load trained model artifact: {path}") from exc
    if not isinstance(bundle, dict) or "model" not in bundle or "class_names" not in bundle:
        raise ModelUnavailableError(f"Invalid model bundle format: {path}")
    return bundle


def _predictions(
    probabilities: np.ndarray,
    class_names: Sequence[str],
    top_k: int,
) -> list[dict[str, float | str]]:
    scores = np.asarray(probabilities, dtype=np.float64)
    if scores.ndim != 2 or scores.shape[0] != 1:
        raise ModelUnavailableError(f"Expected one-row probability matrix, got {scores.shape}.")
    names = list(class_names)
    if scores.shape[1] != len(names):
        raise ModelUnavailableError(
            f"Model emitted {scores.shape[1]} scores for {len(names)} classes."
        )
    if not np.isfinite(scores).all():
        raise ModelUnavailableError("Model emitted invalid non-finite probabilities.")
    indices = np.argsort(scores[0])[::-1][: min(top_k, len(names))]
    return [
        {"condition": names[int(index)], "probability": float(scores[0, index])}
        for index in indices
    ]


@lru_cache(maxsize=1)
def _symptoms_config() -> tuple[str, Path]:
    folder = settings.root / "models" / "symptoms"
    metadata_path = folder / "model_metadata.json"
    if not metadata_path.is_file():
        raise ModelUnavailableError(f"Symptom model metadata is missing: {metadata_path}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        selected = str(metadata["selected_model"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ModelUnavailableError("Symptom model metadata is invalid or has no selected_model.") from exc
    return selected, folder


@lru_cache(maxsize=1)
def _load_biobert() -> tuple[Any, Any, list[str], list[str], Any]:
    selected, folder = _symptoms_config()
    checkpoint = folder / "biobert"
    metadata_path = checkpoint / "features_and_classes.json"
    if selected != "biobert" or not metadata_path.is_file():
        raise ModelUnavailableError("The selected BioBERT checkpoint is missing.")
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint, local_files_only=True
        )
    except (ImportError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError("Could not load the locally trained BioBERT model.") from exc
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return tokenizer, model, metadata["feature_names"], metadata["class_names"], device


def predict_symptoms(symptoms: Sequence[str], top_k: int) -> tuple[str, list[dict[str, Any]]]:
    selected, folder = _symptoms_config()
    normalized_symptoms = {_normalize_feature_name(item) for item in symptoms}
    if not normalized_symptoms:
        raise InvalidModelInputError("Provide at least one symptom.")
    if selected == "biobert":
        tokenizer, model, features, class_names, device = _load_biobert()
        unknown = normalized_symptoms.difference(features)
        if unknown:
            raise InvalidModelInputError(
                f"Unknown symptoms for the trained model: {sorted(unknown)[:10]}"
            )
        text = "reported symptoms: " + " ".join(
            feature.replace("_", " ") for feature in features if feature in normalized_symptoms
        )
        encoded = tokenizer(
            text, return_tensors="pt", truncation=True, max_length=128
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        import torch

        with torch.inference_mode():
            logits = model(**encoded).logits
            scores = torch.softmax(logits, dim=1).cpu().numpy()
        return "BioBERT", _predictions(scores, class_names, top_k)

    if selected not in {"lightgbm", "xgboost"}:
        raise ModelUnavailableError(f"Unsupported selected symptom model: {selected!r}")
    bundle = _load_joblib(str(folder / f"{selected}.joblib"))
    features = list(bundle["feature_names"])
    unknown = normalized_symptoms.difference(features)
    if unknown:
        raise InvalidModelInputError(
            f"Unknown symptoms for the trained model: {sorted(unknown)[:10]}"
        )
    vector = sparse.csr_matrix(
        [
            [
                1.0 if feature in normalized_symptoms else 0.0
                for feature in features
            ]
        ],
        dtype=np.float32,
    )
    probabilities = bundle["model"].predict_proba(vector)
    return str(bundle.get("model_name", selected)), _predictions(
        probabilities, bundle["class_names"], top_k
    )


@lru_cache(maxsize=1)
def _load_ddxplus() -> tuple[Any, dict[str, Any], Any]:
    folder = settings.root / "models" / "ddxplus"
    metadata_path = folder / "metadata.json"
    weights_path = folder / "model_state.pt"
    if not metadata_path.is_file() or not weights_path.is_file():
        raise ModelUnavailableError("DDXPlus model artifacts are not trained yet.")
    try:
        import torch

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        architecture = metadata["architecture"]
        if architecture != [512, 256, 128, 49]:
            raise ValueError(f"Unexpected DDXPlus architecture: {architecture}")
        model = torch.nn.Sequential(
            torch.nn.Linear(512, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.2),
            torch.nn.Linear(256, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.2),
            torch.nn.Linear(128, 49),
        )
        state = torch.load(weights_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
    except (ImportError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError("Could not load the DDXPlus model checkpoint.") from exc
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return model, metadata, device


def predict_ddxplus(
    age: float, sex: str, evidences: Sequence[str], top_k: int
) -> tuple[str, list[dict[str, Any]]]:
    model, metadata, device = _load_ddxplus()
    known = metadata["known_evidence"]
    feature_vocab = metadata["feature_vocab"]
    vector = np.zeros(512, dtype=np.float32)
    vector[0] = float(age) / 120.0
    vector[1] = 1.0 if sex == "M" else 0.0
    for token in set(evidences):
        base_code = token.split("_@_", 1)[0]
        allowed_values = known.get(base_code)
        if allowed_values is None or token not in allowed_values:
            raise InvalidModelInputError(f"Invalid DDXPlus evidence code/value: {token!r}")
        indices = feature_vocab.get(token)
        if indices is not None:
            for index in indices:
                vector[int(index)] = 1.0
    try:
        import torch

        with torch.inference_mode():
            logits = model(torch.from_numpy(vector).unsqueeze(0).to(device))
            probabilities = torch.softmax(logits, dim=1).cpu().numpy()
    except ImportError as exc:
        raise ModelUnavailableError("PyTorch is required for DDXPlus inference.") from exc
    return "DDXPlus PyTorch", _predictions(
        probabilities, metadata["class_names"], top_k
    )


def predict_tabular(
    disease: str, features: dict[str, Any], top_k: int
) -> tuple[str, list[dict[str, Any]]]:
    bundle_paths = {
        "diabetes": settings.root / "models" / "diabetes" / "model.joblib",
        "heart": settings.root / "models" / "heart" / "xgboost.joblib",
        "kidney": settings.root / "models" / "kidney" / "xgboost.joblib",
        "indian_liver_patient": (
            settings.root / "models" / "indian_liver_patient" / "xgboost.joblib"
        ),
    }
    if disease not in bundle_paths:
        raise ValueError(f"Unsupported tabular model: {disease}")
    bundle = _load_joblib(str(bundle_paths[disease]))
    feature_names = list(bundle["feature_names"])
    unexpected = set(features).difference(feature_names)
    if unexpected:
        raise InvalidModelInputError(
            f"Unsupported {disease} input features: {sorted(unexpected)}"
        )
    model = bundle["model"]
    numeric_features: set[str] = set()
    if hasattr(model, "named_steps"):
        preprocessor = model.named_steps.get("preprocessor")
        if preprocessor is not None:
            for transformer_name, _, columns in preprocessor.transformers_:
                if transformer_name == "numeric":
                    numeric_features.update(str(column) for column in columns)
    row = {
        feature: (
            np.nan
            if features.get(feature) is None
            else features.get(feature)
        )
        for feature in feature_names
    }
    for feature in numeric_features:
        row[feature] = pd.to_numeric(pd.Series([row[feature]]), errors="coerce").iloc[0]
    frame = pd.DataFrame([row], columns=feature_names)
    probabilities = model.predict_proba(frame)
    model_name = bundle.get("metadata", {}).get("model_name", "XGBoost")
    return f"{disease}:{model_name}", _predictions(
        probabilities, bundle["class_names"], top_k
    )
