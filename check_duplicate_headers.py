from pathlib import Path
import pandas as pd

folder = Path("dataset/CIC-IDS2017/MachineLearningCVE")

for file in sorted(folder.glob("*.csv")):
    header = pd.read_csv(file, nrows=0, low_memory=False).columns.tolist()
    matches = [
        (i, name)
        for i, name in enumerate(header)
        if "Fwd Header Length" in name
    ]
    if matches:
        print(f"\n{file.name}")
        for i, name in matches:
            print(f"Column {i}: {name!r}")
