
import json
from typing import Any
from pathlib import Path

import numpy as np
import xgboost as xgb


# Resolve artifacts relative to the backend directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = BACKEND_DIR / "artifacts"

MODEL_PATH = ARTIFACT_DIR / "nids_multiclass_v2.json"
METADATA_PATH = ARTIFACT_DIR / "nids_metadata_v2.json"

# Load once when the service is imported.
model = xgb.XGBClassifier(n_jobs=2)
model.load_model(str(MODEL_PATH))

with METADATA_PATH.open("r", encoding="utf-8") as file:
    metadata = json.load(file)

FEATURES = metadata["features"]
CLASS_NAMES = metadata["class_names"]
REMOVED_FEATURES = metadata.get("removed_features", [])

if model.get_booster().num_features() != len(FEATURES):
    raise RuntimeError(
        "Model feature count does not match metadata."
    )

if len(FEATURES) != metadata["feature_count"]:
    raise RuntimeError("Invalid metadata feature count.")

if model.n_classes_ != len(CLASS_NAMES):
    raise RuntimeError("Model class count does not match metadata.")

if len(set(FEATURES)) != len(FEATURES):
    raise RuntimeError("Duplicate model features.")

if len(set(CLASS_NAMES)) != len(CLASS_NAMES):
    raise RuntimeError("Duplicate class names.")

if "Normal" not in CLASS_NAMES:
    raise RuntimeError("Normal class is missing.")


def predict_flow(features: dict[str, Any]) -> dict[str, Any]:
    """Predict an attack category from named flow features."""

    missing = [name for name in FEATURES if name not in features]
    if missing:
        raise ValueError(
            f"Missing {len(missing)} model features. "
            f"First missing features: {missing[:5]}"
        )

    try:
        values = np.asarray(
            [features[name] for name in FEATURES],
            dtype=np.float32,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "All model features must be numeric."
        ) from exc

    if not np.isfinite(values).all():
        raise ValueError(
            "Features must contain only finite numeric values."
        )

    probabilities = model.predict_proba(values.reshape(1, -1))[0]
    predicted_index = int(np.argmax(probabilities))
    predicted_class = CLASS_NAMES[predicted_index]
    confidence = float(probabilities[predicted_index])

    return {
        "predicted_class": predicted_class,
        "confidence": confidence,
        "alert": predicted_class != "Normal",
        "model_status": "loaded",
        "probabilities": {
            CLASS_NAMES[index]: float(probability)
            for index, probability in enumerate(probabilities)
        },
    }


def model_info() -> dict[str, Any]:
    """Return the immutable model contract used by the API and dashboard."""

    return {
        "model_type": metadata["model_type"],
        "model_version": metadata["model_version"],
        "architecture": metadata["architecture"],
        "class_count": len(CLASS_NAMES),
        "time_unit": metadata["time_unit"],
        "feature_count": len(FEATURES),
        "features": FEATURES,
        "class_names": CLASS_NAMES,
        "removed_features": REMOVED_FEATURES,
        "dataset": metadata.get("dataset"),
        "training_rows": metadata.get("training_rows"),
        "testing_rows": metadata.get("testing_rows"),
    }
