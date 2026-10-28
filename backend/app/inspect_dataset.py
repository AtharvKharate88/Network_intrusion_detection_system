from pathlib import Path

import pandas as pd

DATASET_DIR = (
    Path(__file__).resolve().parents[2]
    / "dataset"
    / "CIC-IDS2017"
    / "MachineLearningCVE"
)

csv_files = sorted(DATASET_DIR.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError(f"No CSV files found in {DATASET_DIR}")

print(f"Dataset folder: {DATASET_DIR}")
print(f"CSV files found: {len(csv_files)}")

for file in csv_files:
    print(f"\n{'=' * 70}")
    print(f"FILE: {file.name}")

    df = pd.read_csv(file, nrows=5, low_memory=False)

    # Remove accidental spaces from column names for display only.
    df.columns = df.columns.str.strip()

    print(f"Columns: {len(df.columns)}")
    print("First 10 columns:", df.columns[:10].tolist())
    print("Last column:", repr(df.columns[-1]))

    print("\nSample rows:")
    print(df.head(2).to_string(index=False))