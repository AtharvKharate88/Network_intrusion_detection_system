import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


CHUNK_SIZE = 25000
RANDOM_SEED = 42
MAX_PER_CLASS = 100000

EXCLUDED_FEATURES = {
    "Avg Fwd Segment Size",
    "CWE Flag Count",
    "ECE Flag Count",
}


def prepare_training_data(processed_dir):

    metadata_path = processed_dir / "hybrid_metadata.json"
    dataset_path = processed_dir / "hybrid_dataset.csv"

    with metadata_path.open(encoding="utf-8") as file:
        metadata = json.load(file)

    features = [
        feature
        for feature in metadata["features"]
        if feature not in EXCLUDED_FEATURES
    ]

    print("\nTRAINING DATA PREPARATION")
    print("=" * 65)

    print("Original hybrid features:", len(metadata["features"]))
    print("Final selected features:", len(features))

    print("\nADDITIONAL EXCLUDED FEATURES")

    for feature in sorted(EXCLUDED_FEATURES):
        print(" -", feature)

    feature_types = {
        feature: "float32"
        for feature in features
    }

    # PHASE 1: Identify duplicate and conflicting records

    print("\nPHASE 1: DUPLICATE AND CONFLICT DETECTION")
    print("=" * 65)

    seen = {}
    conflicts = set()

    total_rows = 0
    duplicate_rows = 0

    for chunk in pd.read_csv(
        dataset_path,
        usecols=features + ["BinaryLabel"],
        dtype=feature_types,
        chunksize=CHUNK_SIZE,
    ):
        values = chunk[features].to_numpy()

        if not np.isfinite(values).all():
            raise ValueError("Non-finite feature values detected.")

        if not chunk["BinaryLabel"].isin([0, 1]).all():
            raise ValueError("Invalid binary labels detected.")

        hashes = pd.util.hash_pandas_object(
            chunk[features],
            index=False,
        ).to_numpy()

        labels = chunk["BinaryLabel"].to_numpy()

        for key, label in zip(hashes, labels):

            key = int(key)
            label = int(label)

            if key in seen:
                duplicate_rows += 1

                if seen[key] != label:
                    conflicts.add(key)

            else:
                seen[key] = label

        total_rows += len(chunk)

    print("Total records:", f"{total_rows:,}")
    print("Repeated feature records:", f"{duplicate_rows:,}")
    print("Unique feature signatures:", f"{len(seen):,}")
    print("Conflicting signatures:", f"{len(conflicts):,}")

    # PHASE 2: Remove duplicates and conflicting records

    print("\nPHASE 2: DATASET CLEANING")
    print("=" * 65)

    clean_path = processed_dir / "hybrid_cleaned.csv"
    temp_path = processed_dir / "hybrid_cleaned.tmp"

    first_chunk = True
    clean_rows = 0
    conflict_rows = 0
    removed_duplicates = 0

    required_columns = features + [
        "Label",
        "Dataset",
        "SourceFile",
        "BinaryLabel",
    ]

    try:

        for chunk in pd.read_csv(
            dataset_path,
            usecols=required_columns,
            dtype=feature_types,
            chunksize=CHUNK_SIZE,
        ):
            hashes = pd.util.hash_pandas_object(
                chunk[features],
                index=False,
            ).to_numpy()

            keep = []

            for key in hashes:

                key = int(key)

                if key in conflicts:
                    keep.append(False)
                    conflict_rows += 1

                elif key in seen:
                    keep.append(True)
                    del seen[key]

                else:
                    keep.append(False)
                    removed_duplicates += 1

            clean_chunk = chunk.loc[
                keep, required_columns
            ]

            if clean_chunk.empty:
                continue

            clean_chunk.to_csv(
                temp_path,
                mode="w" if first_chunk else "a",
                header=first_chunk,
                index=False,
            )

            first_chunk = False
            clean_rows += len(clean_chunk)

        if first_chunk:
            raise ValueError("No clean records remaining.")

        temp_path.replace(clean_path)

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    del seen
    del conflicts

    print("Duplicate records removed:", f"{removed_duplicates:,}")
    print("Conflicting records removed:", f"{conflict_rows:,}")
    print("Total records removed:", f"{total_rows - clean_rows:,}")
    print("Clean records remaining:", f"{clean_rows:,}")

    # PHASE 3: Memory-efficient source-specific sampling

    print("\nPHASE 3: TRAINING DATA SAMPLING")
    print("=" * 65)

    rng = np.random.default_rng(RANDOM_SEED)

    groups = {}

    for chunk in pd.read_csv(
        clean_path,
        dtype=feature_types,
        chunksize=CHUNK_SIZE,
    ):
        for (dataset, label), group in chunk.groupby(
            ["Dataset", "BinaryLabel"]
        ):
            key = (dataset, int(label))

            group = group.copy()
            group["_priority"] = rng.random(len(group))

            if key in groups:
                group = pd.concat(
                    [groups[key], group],
                    ignore_index=True,
                )

            groups[key] = group.nsmallest(
                MAX_PER_CLASS,
                "_priority",
            ).reset_index(drop=True)

    # PHASE 4: Save model-ready arrays

    print("\nPHASE 4: SAVING MODEL DATA")
    print("=" * 65)

    output_dir = processed_dir / "training"
    output_dir.mkdir(parents=True, exist_ok=True)

    source_names = {
        "CIC-UNSW-NB15-2024": "unsw",
        "CIC-IoT-DIAD-2024": "iot",
    }

    dataset_summary = {}

    for dataset, prefix in source_names.items():

        parts = [
            group
            for key, group in groups.items()
            if key[0] == dataset
        ]

        if not parts:
            raise ValueError(f"No records found for {dataset}")

        combined = pd.concat(
            parts,
            ignore_index=True,
        )

        combined = combined.sample(
            frac=1,
            random_state=RANDOM_SEED,
        ).reset_index(drop=True)

        X = combined[features].to_numpy(dtype=np.float32)
        y = combined["BinaryLabel"].to_numpy(dtype=np.int8)

        if len(np.unique(y)) != 2:
            raise ValueError(f"Missing binary class in {dataset}")

        np.save(output_dir / f"{prefix}_X.npy", X)
        np.save(output_dir / f"{prefix}_y.npy", y)

        combined[
            ["Label", "Dataset", "SourceFile"]
        ].to_csv(
            output_dir / f"{prefix}_provenance.csv",
            index=False,
        )

        normal_count = int((y == 0).sum())
        attack_count = int((y == 1).sum())

        dataset_summary[dataset] = {
            "records": len(y),
            "normal": normal_count,
            "attack": attack_count,
        }

        print(f"\nDataset: {dataset}")
        print("Total records:", f"{len(y):,}")
        print("Normal records:", f"{normal_count:,}")
        print("Attack records:", f"{attack_count:,}")
        print("Feature matrix shape:", X.shape)

        print("\nAttack category distribution:")
        print(combined["Label"].value_counts().to_string())

    # Save training configuration

    preparation_metadata = {
        "features": features,
        "feature_count": len(features),
        "additional_excluded_features": sorted(EXCLUDED_FEATURES),
        "original_rows": total_rows,
        "clean_rows": clean_rows,
        "duplicate_rows_removed": removed_duplicates,
        "conflict_rows_removed": conflict_rows,
        "max_records_per_binary_class_per_source": MAX_PER_CLASS,
        "random_seed": RANDOM_SEED,
        "binary_label_mapping": {
            "Normal": 0,
            "Attack": 1,
        },
        "training_source": "CIC-UNSW-NB15-2024",
        "evaluation_source": "CIC-IoT-DIAD-2024",
        "evaluation_strategy": "exploratory_cross_dataset",
        "dataset_summary": dataset_summary,
    }

    with (output_dir / "training_metadata.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(preparation_metadata, file, indent=4)

    print("\nFINAL SUMMARY")
    print("=" * 65)

    print("Original records:", f"{total_rows:,}")
    print("Clean records:", f"{clean_rows:,}")
    print("Final features:", len(features))
    print("Clean dataset:", clean_path)
    print("Training directory:", output_dir)

    print("\nTRAINING DATA PREPARATION COMPLETE")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    prepare_training_data(args.processed_dir)
