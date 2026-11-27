import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.flow_adapter import (
    FEATURE_MAP,
    HEADER_ALIASES,
    TIME_FEATURES,
)

METADATA_PATH = (
    ROOT / "backend" / "artifacts" / "nids_metadata.json"
)

# Exclude unavailable and potentially redundant features.
EXCLUDED_FEATURES = {
    "Destination Port",
    "Fwd Header Length.1",
}


def get_common_features():
    """Return candidate common features in model order."""

    with METADATA_PATH.open(encoding="utf-8") as file:
        metadata = json.load(file)

    return [
        feature
        for feature in metadata["features"]
        if feature not in EXCLUDED_FEATURES
    ]


def resolve_columns(columns, expected_features):
    """Resolve source columns using the existing flow adapter."""

    available = set(columns)
    mapping = {}
    missing = []

    for feature in expected_features:
        candidates = (
            FEATURE_MAP.get(feature, feature),
            feature,
            *HEADER_ALIASES.get(feature, ()),
        )

        source = next(
            (name for name in candidates if name in available),
            None,
        )

        if source is None:
            missing.append(feature)
        else:
            mapping[feature] = source

    if missing:
        raise ValueError(
            "Missing required features: "
            + ", ".join(missing)
        )

    if len(set(mapping.values())) != len(mapping):
        raise ValueError(
            "Multiple features resolve to the same source column."
        )

    return mapping


def harmonize_features(
    dataframe,
    expected_features=None,
    *,
    time_unit,
):
    """Standardize feature names, order, types and time units."""

    if time_unit not in {"seconds", "microseconds"}:
        raise ValueError(
            "time_unit must be seconds or microseconds"
        )

    if expected_features is None:
        expected_features = get_common_features()

    if not dataframe.columns.is_unique:
        raise ValueError("Duplicate source column names detected.")

    mapping = resolve_columns(
        dataframe.columns,
        expected_features,
    )

    result = pd.DataFrame(index=dataframe.index)

    for feature, source in mapping.items():
        values = pd.to_numeric(
            dataframe[source],
            errors="raise",
        ).astype("float64")

        if feature in TIME_FEATURES and time_unit == "seconds":
            values = values * 1_000_000

        if not np.isfinite(values.to_numpy()).all():
            raise ValueError(
                f"Invalid numeric values in {feature}"
            )

        result[feature] = values

    return result[expected_features]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test NIDS feature harmonization."
    )

    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--time-unit",
        choices=["seconds", "microseconds"],
        required=True,
    )

    args = parser.parse_args()

    sample = pd.read_csv(args.csv, nrows=1000)

    features = get_common_features()

    mapped = harmonize_features(
        sample,
        features,
        time_unit=args.time_unit,
    )

    print("FEATURE HARMONIZATION")
    print("-" * 50)
    print("Input rows:", len(sample))
    print("Input columns:", len(sample.columns))
    print("Expected features:", len(features))
    print("Mapped features:", len(mapped.columns))
    print("Output shape:", mapped.shape)
    print("Time unit: microseconds")
    print("All required features mapped successfully.")
