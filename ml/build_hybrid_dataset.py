import argparse
import json
from pathlib import Path

import pandas as pd

from feature_mapping import get_common_features

CHUNK_SIZE = 25000

CONSTANT_FEATURES = {
    "Bwd PSH Flags",
    "Fwd URG Flags",
    "Bwd URG Flags",
    "URG Flag Count",
    "Fwd Avg Bytes/Bulk",
    "Fwd Avg Packets/Bulk",
    "Fwd Avg Bulk Rate",
}

METADATA_COLUMNS = [
    "Label",
    "Dataset",
    "SourceFile",
]


def get_selected_features():
    return [
        feature
        for feature in get_common_features()
        if feature not in CONSTANT_FEATURES
    ]


def build_hybrid_dataset(processed_dir):
    features = get_selected_features()

    input_files = [
        processed_dir / "unsw_processed.csv",
        processed_dir / "iot_processed.csv",
    ]

    output_path = processed_dir / "hybrid_dataset.csv"
    temp_path = processed_dir / "hybrid_dataset.tmp"
    metadata_path = processed_dir / "hybrid_metadata.json"

    required_columns = features + METADATA_COLUMNS

    total_rows = 0
    class_counts = {}
    dataset_counts = {}
    binary_counts = {"Normal": 0, "Attack": 0}
    first_chunk = True

    print("\nHYBRID DATASET CREATION")
    print("=" * 60)

    print("Original features:", len(get_common_features()))
    print("Excluded features:", len(CONSTANT_FEATURES))
    print("Selected features:", len(features))

    print("\nREMOVED FEATURES")
    for feature in sorted(CONSTANT_FEATURES):
        print(" -", feature)

    try:
        for csv_path in input_files:
            print(f"\nProcessing: {csv_path.name}")

            file_rows = 0

            for chunk in pd.read_csv(
                csv_path,
                usecols=required_columns,
                chunksize=CHUNK_SIZE,
                dtype={
                    feature: "float32"
                    for feature in features
                },
            ):
                chunk = chunk[required_columns].copy()

                if chunk[METADATA_COLUMNS].isna().any().any():
                    raise ValueError("Missing label or source metadata.")

                # Binary classification:
                # 0 = Normal, 1 = Attack
                chunk["BinaryLabel"] = (
                    chunk["Label"] != "Normal"
                ).astype("int8")

                chunk.to_csv(
                    temp_path,
                    mode="w" if first_chunk else "a",
                    header=first_chunk,
                    index=False,
                )

                first_chunk = False

                file_rows += len(chunk)
                total_rows += len(chunk)

                for label, count in (
                    chunk["Label"].value_counts().items()
                ):
                    class_counts[label] = (
                        class_counts.get(label, 0)
                        + int(count)
                    )

                for dataset, count in (
                    chunk["Dataset"].value_counts().items()
                ):
                    dataset_counts[dataset] = (
                        dataset_counts.get(dataset, 0)
                        + int(count)
                    )

                binary_counts["Normal"] += int(
                    (chunk["BinaryLabel"] == 0).sum()
                )

                binary_counts["Attack"] += int(
                    (chunk["BinaryLabel"] == 1).sum()
                )

            print(f"Rows added: {file_rows:,}")

        if first_chunk:
            raise ValueError("No records were produced.")

        temp_path.replace(output_path)

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    metadata = {
        "features": features,
        "feature_count": len(features),
        "excluded_features": sorted(CONSTANT_FEATURES),
        "total_rows": total_rows,
        "class_counts": class_counts,
        "dataset_counts": dataset_counts,
        "binary_counts": binary_counts,
        "binary_label_mapping": {
            "Normal": 0,
            "Attack": 1,
        },
        "status": "experimental",
    }

    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4)

    print("\nDATASET DISTRIBUTION")
    print("=" * 60)

    for dataset, count in dataset_counts.items():
        print(f"{dataset:<25} {count:>12,}")

    print("\nMULTICLASS DISTRIBUTION")
    print("=" * 60)

    for label, count in sorted(class_counts.items()):
        print(f"{label:<20} {count:>12,}")

    print("\nBINARY CLASS DISTRIBUTION")
    print("=" * 60)

    for label, count in binary_counts.items():
        percentage = count / total_rows * 100
        print(f"{label:<10} {count:>12,} ({percentage:.2f}%)")

    print("\nHYBRID DATASET SUMMARY")
    print("=" * 60)
    print("Total records:", f"{total_rows:,}")
    print("Selected features:", len(features))
    print("Traffic classes:", len(class_counts))
    print("Dataset saved to:", output_path)
    print("Metadata saved to:", metadata_path)
    print("\nHYBRID DATASET CREATION COMPLETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    build_hybrid_dataset(args.processed_dir)
