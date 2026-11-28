import argparse
from itertools import zip_longest
from pathlib import Path

import numpy as np
import pandas as pd

from feature_mapping import (
    get_common_features,
    harmonize_features,
    resolve_columns,
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

CHUNK_SIZE = 25000


def preprocess_unsw(dataset_dir, output_path):
    data_path = dataset_dir / "Data.csv"
    label_path = dataset_dir / "Label.csv"

    features = get_common_features()

    columns = pd.read_csv(data_path, nrows=0).columns
    mapping = resolve_columns(columns, features)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = output_path.with_suffix(".tmp")

    total_rows = 0
    total_saved = 0
    first_chunk = True
    class_counts = {}

    print("\nUNSW DATASET PREPROCESSING")
    print("=" * 60)

    data_reader = pd.read_csv(
        data_path,
        chunksize=CHUNK_SIZE,
        low_memory=False,
    )

    label_reader = pd.read_csv(
        label_path,
        chunksize=CHUNK_SIZE,
    )

    try:
        for data, labels in zip_longest(
            data_reader,
            label_reader,
        ):
            if data is None or labels is None:
                raise ValueError(
                    "Data and label counts do not match."
                )

            if len(data) != len(labels):
                raise ValueError(
                    "Data and label chunk sizes differ."
                )

            data = data.reset_index(drop=True)
            labels = labels.reset_index(drop=True)

            total_rows += len(data)

            attack_labels = labels["Label"].map(LABEL_MAP)

            if attack_labels.isna().any():
                raise ValueError("Unknown attack labels found.")

            selected = data[
                list(mapping.values())
            ].copy()

            selected = selected.apply(
                pd.to_numeric,
                errors="coerce",
            )

            valid_mask = np.isfinite(
                selected.to_numpy()
            ).all(axis=1)

            selected = selected.loc[valid_mask]

            if selected.empty:
                continue

            mapped = harmonize_features(
                selected,
                features,
                time_unit="microseconds",
            )

            mapped["Label"] = attack_labels.loc[valid_mask]
            mapped["Dataset"] = "CIC-UNSW-NB15-2024"
            mapped["SourceFile"] = "Data.csv"

            mapped.to_csv(
                temp_path,
                mode="w" if first_chunk else "a",
                header=first_chunk,
                index=False,
            )

            first_chunk = False
            total_saved += len(mapped)

            for label, count in (
                mapped["Label"].value_counts().items()
            ):
                class_counts[label] = (
                    class_counts.get(label, 0)
                    + int(count)
                )

            print(
                f"Processed: {total_rows:,} | "
                f"Saved: {total_saved:,}"
            )

        if first_chunk:
            raise ValueError("No valid records produced.")

        temp_path.replace(output_path)

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    print("\nCLASS DISTRIBUTION")
    print("=" * 60)

    for label, count in sorted(class_counts.items()):
        print(f"{label:<20} {count:>10,}")

    print("\nPREPROCESSING SUMMARY")
    print("=" * 60)
    print("Total input rows:", total_rows)
    print("Total saved rows:", total_saved)
    print("Total removed rows:", total_rows - total_saved)
    print("Model features:", len(features))
    print("Output:", output_path)
    print("\nPREPROCESSING COMPLETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    preprocess_unsw(args.dataset_dir, args.output)
