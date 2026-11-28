import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from feature_mapping import (
    get_common_features,
    harmonize_features,
    resolve_columns,
)

LABEL_MAP = {
    "Benign": "Normal",
    "BruteForce": "BruteForce",
    "Recon": "Reconnaissance",
    "Web-Based": "WebAttack",
}

CHUNK_SIZE = 25000


def preprocess_iot(dataset_dir, output_path):
    features = get_common_features()
    statistics = []
    files = []

    for folder, label in LABEL_MAP.items():
        category_dir = dataset_dir / folder

        csv_files = sorted(category_dir.glob("*.csv"))

        if not csv_files:
            raise FileNotFoundError(
                f"No CSV files found in {category_dir}"
            )

        for csv_path in csv_files:
            files.append((csv_path, label))

    # Check feature compatibility before writing output.
    for csv_path, label in files:
        columns = pd.read_csv(csv_path, nrows=0).columns
        resolve_columns(columns, features)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = output_path.with_suffix(".tmp")

    total_rows = 0
    total_saved = 0
    first_chunk = True

    print("\nIoT DATASET PREPROCESSING")
    print("=" * 60)

    try:
        for csv_path, label in files:
            print(f"\nProcessing: {csv_path.name}")
            print(f"Label: {label}")

            file_rows = 0
            file_saved = 0

            for chunk in pd.read_csv(
                csv_path,
                chunksize=CHUNK_SIZE,
                low_memory=False,
            ):
                file_rows += len(chunk)

                mapping = resolve_columns(
                    chunk.columns,
                    features,
                )

                selected = chunk[
                    list(mapping.values())
                ].copy()

                selected = selected.apply(
                    pd.to_numeric,
                    errors="coerce",
                )

                selected = selected.replace(
                    [np.inf, -np.inf],
                    np.nan,
                ).dropna()

                if selected.empty:
                    continue

                mapped = harmonize_features(
                    selected,
                    features,
                    time_unit="microseconds",
                )

                mapped["Label"] = label
                mapped["Dataset"] = "CIC-IoT-DIAD-2024"
                mapped["SourceFile"] = (
                    csv_path.relative_to(dataset_dir).as_posix()
                )

                mapped.to_csv(
                    temp_path,
                    mode="w" if first_chunk else "a",
                    header=first_chunk,
                    index=False,
                )

                first_chunk = False
                file_saved += len(mapped)

            total_rows += file_rows
            total_saved += file_saved

            statistics.append({
                "Label": label,
                "Input": file_rows,
                "Saved": file_saved,
                "Removed": file_rows - file_saved,
            })

            print("Input rows:", file_rows)
            print("Saved rows:", file_saved)
            print("Removed rows:", file_rows - file_saved)

        if first_chunk:
            raise ValueError("No valid records were produced.")

        temp_path.replace(output_path)

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    summary = pd.DataFrame(statistics)

    print("\nCLASS DISTRIBUTION")
    print("=" * 60)
    print(
        summary.groupby("Label")[
            ["Input", "Saved", "Removed"]
        ].sum().to_string()
    )

    print("\nPREPROCESSING SUMMARY")
    print("=" * 60)
    print("Files processed:", len(files))
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

    preprocess_iot(args.dataset_dir, args.output)
