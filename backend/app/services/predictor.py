
import json
from pathlib import Path

import numpy as np
import xgboost as xgb


# Resolve artifacts relative to the backend directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = BACKEND_DIR / "artifacts"

MODEL_PATH = ARTIFACT_DIR / "nids_xgboost_reduced.json"
METADATA_PATH = ARTIFACT_DIR / "nids_metadata.json"

# Load once when the service is imported.
model = xgb.XGBClassifier()
model.load_model(str(MODEL_PATH))

with METADATA_PATH.open("r", encoding="utf-8") as file:
    metadata = json.load(file)

FEATURES = metadata["features"]
CLASS_NAMES = metadata["class_names"]

if model.get_booster().num_features() != len(FEATURES):
    raise RuntimeError(
        "Model feature count does not match metadata."
    )

if model.get_booster().num_features() != 73:
    raise RuntimeError(
        "Expected a model trained on 73 features."
    )


def predict_flow(features: dict) -> dict:
    """Predict an attack category from 73 named flow features."""

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
    }
