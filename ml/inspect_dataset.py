import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent

METADATA_PATH = (
    ROOT / "backend" / "artifacts" / "nids_metadata.json"
)

LABEL_MAP = {
    0: "Normal",
    1: "Analysis",
    2: "Backdoor",
    3: "DoS",
    4: "Exploits",
    5: "Fuzzers",
    6: "Generic",
    7: "Reconnaissance",
    8: "Shellcode",
    9: "Worms",
}

# Candidate aliases requiring semantic validation
FEATURE_ALIASES = {
    "Total Fwd Packet": "Total Fwd Packets",
    "Total Bwd packets": "Total Backward Packets",
    "Total Length of Fwd Packet": "Total Length of Fwd Packets",
    "Total Length of Bwd Packet": "Total Length of Bwd Packets",
    "Packet Length Min": "Min Packet Length",
    "Packet Length Max": "Max Packet Length",
    "CWR Flag Count": "CWE Flag Count",
    "Fwd Segment Size Avg": "Avg Fwd Segment Size",
    "Bwd Segment Size Avg": "Avg Bwd Segment Size",
    "Fwd Bytes/Bulk Avg": "Fwd Avg Bytes/Bulk",
    "Fwd Packet/Bulk Avg": "Fwd Avg Packets/Bulk",
    "Fwd Bulk Rate Avg": "Fwd Avg Bulk Rate",
    "Bwd Bytes/Bulk Avg": "Bwd Avg Bytes/Bulk",
    "Bwd Packet/Bulk Avg": "Bwd Avg Packets/Bulk",
    "Bwd Bulk Rate Avg": "Bwd Avg Bulk Rate",
    "FWD Init Win Bytes": "Init_Win_bytes_forward",
    "Bwd Init Win Bytes": "Init_Win_bytes_backward",
    "Fwd Seg Size Min": "min_seg_size_forward",
}


def inspect_dataset(folder):
    data_path = folder / "Data.csv"
    label_path = folder / "Label.csv"

    print("\n" + "=" * 60)
    print("NIDS DATASET INSPECTION")
    print("=" * 60)

    for path in (data_path, label_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    with METADATA_PATH.open(encoding="utf-8") as file:
        model_features = json.load(file)["features"]

    columns = pd.read_csv(data_path, nrows=0).columns
    mapped_columns = [
        FEATURE_ALIASES.get(col, col) for col in columns
    ]

    print("\nFEATURE COMPATIBILITY")
    print("-" * 60)

    direct = [
        f for f in model_features if f in columns
    ]

    matched = [
        f for f in model_features if f in mapped_columns
    ]

    missing = [
        f for f in model_features if f not in mapped_columns
    ]

    extra = [
        f for f in mapped_columns if f not in model_features
    ]

    print("Dataset features:", len(columns))
    print("Existing model features:", len(model_features))
    print("Direct matches:", len(direct))
    print("Candidate matches after renaming:", len(matched))

    print("\nMissing model features:")
    for feature in missing:
        print(" -", feature)

    print("\nAdditional dataset features:")
    for feature in extra:
        print(" -", feature)

    print("\nDATA QUALITY")
    print("-" * 60)

    total_rows = 0
    missing_values = 0
    infinite_values = 0
    invalid_rows = 0

    missing_by_column = pd.Series(0, index=columns)
    infinite_by_column = pd.Series(0, index=columns)

    # Read in chunks to reduce RAM usage
    for chunk in pd.read_csv(data_path, chunksize=25000):
        total_rows += len(chunk)

        numeric = chunk.apply(pd.to_numeric, errors="coerce")

        missing_mask = numeric.isna()
        infinite_mask = np.isinf(numeric)

        missing_values += int(missing_mask.sum().sum())
        infinite_values += int(infinite_mask.sum().sum())

        missing_by_column += missing_mask.sum()
        infinite_by_column += infinite_mask.sum()

        invalid_rows += int(
            (missing_mask | infinite_mask).any(axis=1).sum()
        )

    print("Total data rows:", total_rows)
    print("Missing/non-numeric values:", missing_values)
    print("Infinite values:", infinite_values)
    print("Rows containing invalid values:", invalid_rows)

    print("\nColumns containing invalid values:")
    invalid_counts = missing_by_column + infinite_by_column

    for feature, count in invalid_counts.items():
        if count > 0:
            print(f" - {feature}: {count}")

    print("\nLABEL DISTRIBUTION")
    print("-" * 60)

    labels = pd.read_csv(label_path)["Label"]

    print("Total labels:", len(labels))
    print("Data and label counts match:", total_rows == len(labels))

    unknown = labels[~labels.isin(LABEL_MAP.keys())]

    print("Unknown or missing labels:", len(unknown))

    counts = labels.value_counts().sort_index()

    for label, count in counts.items():
        name = LABEL_MAP.get(label, "Unknown")
        percentage = count / len(labels) * 100

        print(
            f"{name:<18} "
            f"{count:>10,} "
            f"({percentage:6.2f}%)"
        )

    print("\n" + "=" * 60)
    print("INSPECTION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inspect NIDS dataset quality and compatibility."
    )

    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Directory containing Data.csv and Label.csv",
    )

    args = parser.parse_args()
    inspect_dataset(args.dataset_dir)
