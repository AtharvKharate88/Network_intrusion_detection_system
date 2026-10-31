from pathlib import Path
import pandas as pd
import numpy as np

folder = Path("dataset/CIC-IDS2017/MachineLearningCVE")

for file in sorted(folder.glob("*.csv")):
    df = pd.read_csv(file, nrows=1000, low_memory=False)
    col1 = df[" Fwd Header Length"]
    col2 = df[" Fwd Header Length.1"]

    equal = np.isclose(
        pd.to_numeric(col1, errors="coerce"),
        pd.to_numeric(col2, errors="coerce"),
        equal_nan=True,
    )

    print(f"{file.name}: {equal.sum()}/{len(equal)} rows equal")
    if not equal.all():
        print(df.loc[~equal, [" Fwd Header Length", " Fwd Header Length.1"]].head(3))
