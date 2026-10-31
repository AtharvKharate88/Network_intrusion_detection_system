from pathlib import Path
import pandas as pd

folder = Path("dataset/CIC-IDS2017/MachineLearningCVE")
columns = [
    "Flow Duration",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Flow IAT Mean",
    "Flow IAT Std",
    "Fwd IAT Total",
    "Fwd IAT Mean",
]

for file in sorted(folder.glob("*.csv")):
    try:
        df = pd.read_csv(file, usecols=lambda c: c.strip() in columns, nrows=1000, low_memory=False)
        df.columns = df.columns.str.strip()
        available = [c for c in columns if c in df.columns]
        if available:
            print(f"\n--- {file.name} ---")
            print(df[available].describe().to_string())
    except Exception as exc:
        print(f"\nCould not inspect {file.name}: {exc}")
