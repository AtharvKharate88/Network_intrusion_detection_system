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
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)


RANDOM_SEED = 42


def evaluate_model(model, X, y, name):

    predictions = model.predict(X)
    probabilities = model.predict_proba(X)[:, 1]

    matrix = confusion_matrix(
        y, predictions, labels=[0, 1]
    )

    tn, fp, fn, tp = matrix.ravel()

    metrics = {
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(
            precision_score(y, predictions, zero_division=0)
        ),
        "recall": float(
            recall_score(y, predictions, zero_division=0)
        ),
        "f1_score": float(
            f1_score(y, predictions, zero_division=0)
        ),
        "roc_auc": float(roc_auc_score(y, probabilities)),
        "false_positive_rate": float(
            fp / (fp + tn) if fp + tn else 0
        ),
        "confusion_matrix": matrix.tolist(),
    }

    print(f"\n{name}")
    print("=" * 65)

    for key, value in metrics.items():
        if key != "confusion_matrix":
            print(f"{key:<25}: {value:.6f}")

    print("\nConfusion matrix:")
    print(matrix)

    print("\nClassification report:")

    print(
        classification_report(
            y,
            predictions,
            labels=[0, 1],
            target_names=["Normal", "Attack"],
            zero_division=0,
        )
    )

    return metrics, predictions


def train_binary_model(training_dir):

    start_time = time.time()

    with (training_dir / "training_metadata.json").open(
        encoding="utf-8"
    ) as file:
        metadata = json.load(file)

    features = metadata["features"]

    print("\nBINARY NIDS MODEL TRAINING")
    print("=" * 65)

    print("\nLoading UNSW training data...")

    X = np.load(training_dir / "unsw_X.npy")
    y = np.load(training_dir / "unsw_y.npy")

    if X.shape[1] != len(features):
        raise ValueError("Training feature count mismatch.")

    if len(X) != len(y):
        raise ValueError("Training record count mismatch.")

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    del X, y

    print("Training records:", f"{len(y_train):,}")
    print("Validation records:", f"{len(y_val):,}")
    print("Selected features:", len(features))

    model = XGBClassifier(
        objective="binary:logistic",
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        device="cpu",
        n_jobs=2,
        max_bin=256,
        eval_metric="logloss",
        early_stopping_rounds=20,
        random_state=RANDOM_SEED,
    )

    print("\nTRAINING XGBOOST MODEL")
    print("=" * 65)

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=10,
    )

    print("\nTraining completed.")
    print("Best iteration:", model.best_iteration)

    validation_metrics, _ = evaluate_model(
        model,
        X_val,
        y_val,
        "UNSW VALIDATION RESULTS",
    )

    del X_train, X_val, y_train, y_val

    print("\nLoading IoT cross-dataset evaluation data...")

    X_test = np.load(training_dir / "iot_X.npy")
    y_test = np.load(training_dir / "iot_y.npy")

    if X_test.shape[1] != len(features):
        raise ValueError("Evaluation feature count mismatch.")

    if len(X_test) != len(y_test):
        raise ValueError("Evaluation record count mismatch.")

    test_metrics, predictions = evaluate_model(
        model,
        X_test,
        y_test,
        "IOT CROSS-DATASET EVALUATION",
    )

    provenance = pd.read_csv(
        training_dir / "iot_provenance.csv"
    )

    if len(provenance) != len(y_test):
        raise ValueError("Provenance record count mismatch.")

    provenance["Actual"] = y_test
    provenance["Predicted"] = predictions
    provenance["Correct"] = predictions == y_test

    category_results = (
        provenance.groupby("Label")
        .agg(
            Records=("Correct", "size"),
            Correct=("Correct", "sum"),
            DetectionRate=("Correct", "mean"),
        )
        .reset_index()
    )

    print("\nIOT CATEGORY-WISE RESULTS")
    print("=" * 65)
    print(category_results.to_string(index=False))

    importance = pd.DataFrame({
        "Feature": features,
        "Importance": model.feature_importances_,
    }).sort_values(
        "Importance",
        ascending=False,
    )

    print("\nTOP 15 IMPORTANT FEATURES")
    print("=" * 65)
    print(importance.head(15).to_string(index=False))

    output_dir = training_dir / "binary_model"
    output_dir.mkdir(parents=True, exist_ok=True)

    model.save_model(
        str(output_dir / "nids_binary_xgboost.json")
    )

    importance.to_csv(
        output_dir / "feature_importance.csv",
        index=False,
    )

    category_results.to_csv(
        output_dir / "category_evaluation.csv",
        index=False,
    )

    elapsed = time.time() - start_time

    results = {
        "model": "XGBoost",
        "task": "binary_intrusion_detection",
        "features": features,
        "feature_count": len(features),
        "label_mapping": {
            "Normal": 0,
            "Attack": 1,
        },
        "training_source": "CIC-UNSW-NB15-2024",
        "evaluation_source": "CIC-IoT-DIAD-2024",
        "evaluation_strategy": "exploratory_cross_dataset",
        "best_iteration": int(model.best_iteration),
        "validation_metrics": validation_metrics,
        "cross_dataset_metrics": test_metrics,
        "execution_time_seconds": elapsed,
        "status": "experimental",
    }

    with (output_dir / "binary_model_metadata.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(results, file, indent=4)

    print("\nFINAL TRAINING SUMMARY")
    print("=" * 65)
    print("Features:", len(features))
    print("Validation accuracy:",
          f"{validation_metrics['accuracy']:.2%}")
    print("Cross-dataset accuracy:",
          f"{test_metrics['accuracy']:.2%}")
    print("Cross-dataset F1:",
          f"{test_metrics['f1_score']:.6f}")
    print("Execution time:",
          f"{elapsed / 60:.2f} minutes")
    print("Model saved to:", output_dir)
    print("\nBINARY MODEL TRAINING COMPLETE")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--training-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    train_binary_model(args.training_dir)
