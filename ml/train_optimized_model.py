import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from xgboost import XGBClassifier

from sklearn.model_selection import train_test_split

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
)


RANDOM_SEED = 42


def load_source(training_dir, prefix, features):

    X = np.load(training_dir / f"{prefix}_X.npy")
    y = np.load(training_dir / f"{prefix}_y.npy")

    provenance = pd.read_csv(
        training_dir / f"{prefix}_provenance.csv"
    )

    if X.ndim != 2 or X.shape[1] != len(features):
        raise ValueError(f"Feature mismatch: {prefix}")

    if len(X) != len(y) or len(y) != len(provenance):
        raise ValueError(f"Record mismatch: {prefix}")

    if not np.isfinite(X).all():
        raise ValueError(f"Invalid feature values: {prefix}")

    if not np.isin(y, [0, 1]).all():
        raise ValueError(f"Invalid labels: {prefix}")

    expected = (
        provenance["Label"] != "Normal"
    ).astype("int8").to_numpy()

    if not np.array_equal(y, expected):
        raise ValueError(f"Label alignment mismatch: {prefix}")

    print(f"{prefix.upper()} records: {len(y):,}")

    return X, y, provenance


def calculate_metrics(y, probabilities, threshold):

    predictions = (
        probabilities >= threshold
    ).astype(np.int8)

    matrix = confusion_matrix(
        y, predictions, labels=[0, 1]
    )

    tn, fp, fn, tp = matrix.ravel()

    return {
        "accuracy": float(
            accuracy_score(y, predictions)
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(y, predictions)
        ),
        "precision": float(
            precision_score(
                y, predictions, zero_division=0
            )
        ),
        "recall": float(
            recall_score(
                y, predictions, zero_division=0
            )
        ),
        "f1_score": float(
            f1_score(
                y, predictions, zero_division=0
            )
        ),
        "roc_auc": float(
            roc_auc_score(y, probabilities)
        ),
        "average_precision": float(
            average_precision_score(y, probabilities)
        ),
        "false_positive_rate": float(
            fp / (fp + tn) if fp + tn else 0
        ),
        "false_negative_rate": float(
            fn / (fn + tp) if fn + tp else 0
        ),
        "confusion_matrix": matrix.tolist(),
    }


def print_metrics(name, metrics):

    print(f"\n{name}")
    print("=" * 65)

    for key, value in metrics.items():

        if key != "confusion_matrix":
            print(f"{key:<25}: {value:.6f}")

    print("\nConfusion matrix:")

    print(
        np.array(metrics["confusion_matrix"])
    )


def optimize_threshold(y, probabilities, provenance):

    results = []

    sources = provenance["Dataset"].to_numpy()

    for threshold in np.linspace(0.05, 0.95, 91):

        predictions = (
            probabilities >= threshold
        ).astype(np.int8)

        source_scores = []

        for source in np.unique(sources):

            mask = sources == source

            source_scores.append(
                balanced_accuracy_score(
                    y[mask],
                    predictions[mask],
                )
            )

        metrics = calculate_metrics(
            y, probabilities, threshold
        )

        results.append({
            "threshold": float(threshold),
            "mean_source_balanced_accuracy": float(
                np.mean(source_scores)
            ),
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
            "false_positive_rate":
                metrics["false_positive_rate"],
            "false_negative_rate":
                metrics["false_negative_rate"],
        })

    report = pd.DataFrame(results)

    report = report.sort_values(
        [
            "mean_source_balanced_accuracy",
            "f1_score",
            "false_positive_rate",
        ],
        ascending=[False, False, True],
    )

    threshold = float(
        report.iloc[0]["threshold"]
    )

    return threshold, report


def train_hybrid_model(training_dir):

    start_time = time.time()

    print("\nHYBRID NIDS MODEL TRAINING")
    print("=" * 65)

    with (
        training_dir / "training_metadata.json"
    ).open(encoding="utf-8") as file:

        metadata = json.load(file)

    features = metadata["features"]

    # PHASE 1: Load both datasets

    print("\nPHASE 1: LOADING DATASETS")

    X_unsw, y_unsw, p_unsw = load_source(
        training_dir, "unsw", features
    )

    X_iot, y_iot, p_iot = load_source(
        training_dir, "iot", features
    )

    X = np.concatenate(
        [X_unsw, X_iot], axis=0
    )

    y = np.concatenate(
        [y_unsw, y_iot]
    )

    provenance = pd.concat(
        [p_unsw, p_iot],
        ignore_index=True,
    )

    del X_unsw, X_iot
    del y_unsw, y_iot
    del p_unsw, p_iot

    print("Combined records:", f"{len(y):,}")
    print("Features:", len(features))

    # PHASE 2: Source and category-aware splitting

    print("\nPHASE 2: DATASET SPLITTING")

    strata = (
        provenance["Dataset"]
        + "|"
        + provenance["Label"]
    )

    if strata.value_counts().min() < 10:
        raise ValueError(
            "Insufficient records in a source/category "
            "group for reliable stratification."
        )

    indices = np.arange(len(y))

    train_idx, remaining_idx = train_test_split(
        indices,
        test_size=0.30,
        random_state=RANDOM_SEED,
        stratify=strata,
    )

    val_idx, test_idx = train_test_split(
        remaining_idx,
        test_size=0.50,
        random_state=RANDOM_SEED,
        stratify=strata.iloc[remaining_idx],
    )

    assert not np.intersect1d(
        train_idx, val_idx
    ).size

    assert not np.intersect1d(
        train_idx, test_idx
    ).size

    assert not np.intersect1d(
        val_idx, test_idx
    ).size

    X_train = X[train_idx]
    y_train = y[train_idx]

    X_val = X[val_idx]
    y_val = y[val_idx]

    X_test = X[test_idx]
    y_test = y[test_idx]

    p_train = provenance.iloc[
        train_idx
    ].reset_index(drop=True)

    p_val = provenance.iloc[
        val_idx
    ].reset_index(drop=True)

    p_test = provenance.iloc[
        test_idx
    ].reset_index(drop=True)

    del X, y

    print("Training records:", f"{len(y_train):,}")
    print("Validation records:", f"{len(y_val):,}")
    print("Testing records:", f"{len(y_test):,}")

    # PHASE 3: Moderate category weighting

    print("\nPHASE 3: CATEGORY WEIGHTING")

    train_groups = (
        p_train["Dataset"]
        + "|"
        + p_train["Label"]
    )

    counts = train_groups.value_counts()

    reference = float(counts.median())

    weights = train_groups.map(
        lambda group: np.clip(
            np.sqrt(reference / counts[group]),
            0.5,
            5.0,
        )
    ).to_numpy(dtype=np.float32)

    weights /= weights.mean()

    print("Minimum weight:", float(weights.min()))
    print("Maximum weight:", float(weights.max()))

    # PHASE 4: Train XGBoost

    print("\nPHASE 4: XGBOOST TRAINING")
    print("=" * 65)

    model = XGBClassifier(
        objective="binary:logistic",
        n_estimators=1500,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=2.0,
        tree_method="hist",
        device="cpu",
        n_jobs=2,
        max_bin=256,
        eval_metric="logloss",
        early_stopping_rounds=50,
        random_state=RANDOM_SEED,
    )

    model.fit(
        X_train,
        y_train,
        sample_weight=weights,
        eval_set=[(X_val, y_val)],
        verbose=20,
    )

    print("\nBest iteration:", model.best_iteration)

    # PHASE 5: Validation threshold selection

    print("\nPHASE 5: THRESHOLD OPTIMIZATION")

    val_probabilities = model.predict_proba(
        X_val
    )[:, 1]

    threshold, threshold_report = optimize_threshold(
        y_val,
        val_probabilities,
        p_val,
    )

    print("Selected threshold:", threshold)

    validation_metrics = calculate_metrics(
        y_val,
        val_probabilities,
        threshold,
    )

    print_metrics(
        "VALIDATION RESULTS",
        validation_metrics,
    )

    # PHASE 6: Held-out row evaluation

    print("\nPHASE 6: MODEL EVALUATION")

    test_probabilities = model.predict_proba(
        X_test
    )[:, 1]

    test_predictions = (
        test_probabilities >= threshold
    ).astype(np.int8)

    default_metrics = calculate_metrics(
        y_test,
        test_probabilities,
        0.5,
    )

    test_metrics = calculate_metrics(
        y_test,
        test_probabilities,
        threshold,
    )

    print_metrics(
        "HELD-OUT RESULTS: DEFAULT THRESHOLD",
        default_metrics,
    )

    print_metrics(
        "HELD-OUT RESULTS: OPTIMIZED THRESHOLD",
        test_metrics,
    )

    print("\nCLASSIFICATION REPORT")

    print(
        classification_report(
            y_test,
            test_predictions,
            labels=[0, 1],
            target_names=["Normal", "Attack"],
            zero_division=0,
        )
    )

    # PHASE 7: Source-specific evaluation

    source_results = {}

    for source in p_test["Dataset"].unique():

        mask = (
            p_test["Dataset"] == source
        ).to_numpy()

        metrics = calculate_metrics(
            y_test[mask],
            test_probabilities[mask],
            threshold,
        )

        source_results[source] = metrics

        print_metrics(
            f"SOURCE RESULTS: {source}",
            metrics,
        )

    # PHASE 8: Category-specific evaluation

    p_test["Actual"] = y_test
    p_test["Predicted"] = test_predictions

    p_test["Correct"] = (
        y_test == test_predictions
    )

    category_results = (
        p_test.groupby(["Dataset", "Label"])
        .agg(
            Records=("Correct", "size"),
            Correct=("Correct", "sum"),
            DetectionRate=("Correct", "mean"),
        )
        .reset_index()
    )

    print("\nCATEGORY-WISE RESULTS")
    print("=" * 65)

    print(
        category_results.to_string(index=False)
    )

    # PHASE 9: Save model and reports

    output_dir = training_dir / "optimized_model"

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    model.save_model(
        str(output_dir / "nids_hybrid_xgboost.json")
    )

    importance = pd.DataFrame({
        "Feature": features,
        "Importance": model.feature_importances_,
    }).sort_values(
        "Importance",
        ascending=False,
    )

    importance.to_csv(
        output_dir / "feature_importance.csv",
        index=False,
    )

    category_results.to_csv(
        output_dir / "category_evaluation.csv",
        index=False,
    )

    threshold_report.to_csv(
        output_dir / "threshold_analysis.csv",
        index=False,
    )

    p_test.to_csv(
        output_dir / "test_predictions.csv",
        index=False,
    )

    np.savez(
        output_dir / "split_indices.npz",
        train=train_idx,
        validation=val_idx,
        test=test_idx,
    )

    elapsed = time.time() - start_time

    results = {
        "model": "XGBoost",
        "task": "binary_intrusion_detection",
        "features": features,
        "feature_count": len(features),
        "decision_threshold": threshold,
        "label_mapping": {
            "Normal": 0,
            "Attack": 1,
        },
        "training_records": len(y_train),
        "validation_records": len(y_val),
        "testing_records": len(y_test),
        "random_seed": RANDOM_SEED,
        "best_iteration": int(model.best_iteration),
        "model_parameters": model.get_params(),
        "validation_metrics": validation_metrics,
        "default_threshold_metrics": default_metrics,
        "test_metrics": test_metrics,
        "source_metrics": source_results,
        "evaluation_strategy":
            "source_category_stratified_row_holdout",
        "independent_capture_test": False,
        "execution_time_seconds": elapsed,
        "status": "experimental",
    }

    with (
        output_dir / "hybrid_model_metadata.json"
    ).open("w", encoding="utf-8") as file:

        json.dump(results, file, indent=4)

    print("\nFINAL HYBRID MODEL SUMMARY")
    print("=" * 65)

    print("Features:", len(features))

    print(
        "Validation accuracy:",
        f"{validation_metrics['accuracy']:.2%}"
    )

    print(
        "Held-out accuracy:",
        f"{test_metrics['accuracy']:.2%}"
    )

    print(
        "Balanced accuracy:",
        f"{test_metrics['balanced_accuracy']:.2%}"
    )

    print(
        "Precision:",
        f"{test_metrics['precision']:.2%}"
    )

    print(
        "Attack recall:",
        f"{test_metrics['recall']:.2%}"
    )

    print(
        "F1-score:",
        f"{test_metrics['f1_score']:.6f}"
    )

    print(
        "False positive rate:",
        f"{test_metrics['false_positive_rate']:.2%}"
    )

    print(
        "False negative rate:",
        f"{test_metrics['false_negative_rate']:.2%}"
    )

    print("Decision threshold:", threshold)

    print(
        "Execution time:",
        f"{elapsed / 60:.2f} minutes"
    )

    print("Model saved to:", output_dir)

    print("\nHYBRID MODEL TRAINING COMPLETE")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--training-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    train_hybrid_model(args.training_dir)
