from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

DATASET_DIR = (
    Path(__file__).resolve().parents[2]
    / "dataset"
    / "CIC-IDS2017"
    / "MachineLearningCVE"
)

label_counts = Counter()
missing_counts = Counter()
infinite_counts = Counter()
reference_columns = None
total_rows = 0

csv_files = sorted(DATASET_DIR.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError(f"No CSV files found in {DATASET_DIR}")

for file in csv_files:
    print(f"\nChecking: {file.name}")

    for chunk in pd.read_csv(file, chunksize=100_000, low_memory=False):
        chunk.columns = chunk.columns.str.strip()

        # Ensure all files have the same columns in the same order.
        columns = list(chunk.columns)

        if reference_columns is None:
            reference_columns = columns
        elif columns != reference_columns:
            raise ValueError(
                f"Column mismatch detected in {file.name}"
            )

        if "Label" not in chunk.columns:
            raise ValueError(f"Label column missing in {file.name}")

        # Count labels, ignoring accidental spaces around label text.
        labels = chunk["Label"].astype("string").str.strip()
        label_counts.update(labels.dropna().tolist())

        total_rows += len(chunk)

        # Check missing values.
        missing = chunk.isna().sum()
        for column, count in missing.items():
            missing_counts[column] += int(count)

        # Check infinite values in numeric columns.
        numeric = chunk.select_dtypes(include="number")
        if not numeric.empty:
            inf = np.isinf(numeric).sum()
            for column, count in inf.items():
                infinite_counts[column] += int(count)

print("\n" + "=" * 60)
print("DATASET QUALITY REPORT")
print("=" * 60)

print(f"Files checked: {len(csv_files)}")
print(f"Total rows: {total_rows:,}")
print(f"Feature columns (excluding Label): {len(reference_columns) - 1}")

print("\nAttack label counts:")
for label, count in label_counts.most_common():
    print(f"{label}: {count:,}")

print("\nColumns with missing values:")
found_missing = False
for column, count in missing_counts.most_common():
    if count > 0:
        print(f"{column}: {count:,}")
        found_missing = True
if not found_missing:
    print("None")

print("\nColumns with infinite values:")
found_infinite = False
for column, count in infinite_counts.most_common():
    if count > 0:
        print(f"{column}: {count:,}")
        found_infinite = True
if not found_infinite:
    print("None")

print("\nColumn consistency: PASS")