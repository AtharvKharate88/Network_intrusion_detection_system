import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from feature_mapping import get_common_features

CHUNK_SIZE = 25000


def analyze_dataset(csv_path, features):
    print(f"\nAnalyzing: {csv_path.name}")

    total_rows = 0

    minimum = np.full(len(features), np.inf)
    maximum = np.full(len(features), -np.inf)

    sums = np.zeros(len(features))
    zero_counts = np.zeros(len(features), dtype=np.int64)

    for chunk in pd.read_csv(
        csv_path,
        usecols=features,
        chunksize=CHUNK_SIZE,
    ):
        values = chunk[features].to_numpy(
            dtype=np.float64
        )

        if not np.isfinite(values).all():
            raise ValueError(
                f"Invalid values found in {csv_path.name}"
            )

        total_rows += len(values)

        minimum = np.minimum(
            minimum,
            values.min(axis=0),
        )

        maximum = np.maximum(
            maximum,
            values.max(axis=0),
        )

        sums += values.sum(axis=0)
        zero_counts += (values == 0).sum(axis=0)

    if total_rows == 0:
        raise ValueError(f"Empty dataset: {csv_path}")

    result = pd.DataFrame({
        "Feature": features,
        "Minimum": minimum,
        "Maximum": maximum,
        "Mean": sums / total_rows,
        "ZeroPercent": zero_counts / total_rows * 100,
        "Constant": minimum == maximum,
    })

    print(f"Rows analyzed: {total_rows:,}")
    print("Features analyzed:", len(features))

    return result


def compare_features(unsw, iot):
    report = unsw.merge(
        iot,
        on="Feature",
        suffixes=("_UNSW", "_IoT"),
    )

    report["ZeroPercentDifference"] = (
        report["ZeroPercent_UNSW"]
        - report["ZeroPercent_IoT"]
    ).abs()

    report["MeanMagnitudeRatio"] = (
        np.maximum(
            report["Mean_UNSW"].abs(),
            report["Mean_IoT"].abs(),
        ) + 1e-9
    ) / (
        np.minimum(
            report["Mean_UNSW"].abs(),
            report["Mean_IoT"].abs(),
        ) + 1e-9
    )

    def assess_feature(row):
        if row["Constant_UNSW"] and row["Constant_IoT"]:
            if row["Minimum_UNSW"] == row["Minimum_IoT"]:
                return "Constant in both"

            return "Different dataset constants"

        if row["Constant_UNSW"] or row["Constant_IoT"]:
            return "Constant in one dataset"

        if row["ZeroPercentDifference"] >= 50:
            return "Large zero distribution difference"

        if row["MeanMagnitudeRatio"] >= 100:
            return "Large mean magnitude difference"

        if (
            row["ZeroPercent_UNSW"] >= 99
            and row["ZeroPercent_IoT"] >= 99
        ):
            return "Mostly zero in both"

        return "No obvious issue"

    report["Status"] = report.apply(
        assess_feature,
        axis=1,
    )

    return report


def main(processed_dir):
    features = get_common_features()

    unsw = analyze_dataset(
        processed_dir / "unsw_processed.csv",
        features,
    )

    iot = analyze_dataset(
        processed_dir / "iot_processed.csv",
        features,
    )

    report = compare_features(unsw, iot)

    output_path = processed_dir / "feature_quality_report.csv"

    report.to_csv(output_path, index=False)

    print("\nFEATURE QUALITY ANALYSIS")
    print("=" * 65)

    print("\nFEATURE STATUS SUMMARY")
    print("-" * 65)
    print(report["Status"].value_counts().to_string())

    flagged = report[
        report["Status"] != "No obvious issue"
    ]

    print("\nFEATURES REQUIRING REVIEW")
    print("-" * 65)

    for _, row in flagged.iterrows():
        print(f"\nFeature: {row['Feature']}")
        print(f"Status: {row['Status']}")
        print(
            f"UNSW zeros: {row['ZeroPercent_UNSW']:.2f}%"
        )
        print(
            f"IoT zeros: {row['ZeroPercent_IoT']:.2f}%"
        )
        print(
            f"UNSW mean: {row['Mean_UNSW']:.6g}"
        )
        print(
            f"IoT mean: {row['Mean_IoT']:.6g}"
        )

    print("\nSUMMARY")
    print("=" * 65)
    print("Total features:", len(report))
    print("Features requiring review:", len(flagged))
    print(
        "Features without obvious issues:",
        len(report) - len(flagged),
    )
    print("Report saved to:", output_path)
    print("\nFEATURE QUALITY ANALYSIS COMPLETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--processed-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    main(args.processed_dir)
