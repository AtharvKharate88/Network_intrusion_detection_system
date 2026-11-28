import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from xgboost import XGBClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from train_optimized_model import load_source


BASE = Path(
    r"D:\ASHISH\MINI Poject\Datasets\processed\training\robust_training"
)

BINARY_DIR = BASE / "optimized_model"
OUTPUT = BASE / "multiclass_models"

OUTPUT.mkdir(parents=True, exist_ok=True)

start = time.time()

metadata = json.loads(
    (BASE / "training_metadata.json").read_text()
)

features = metadata["features"]

assert len(features) == 36

print("\n===== LOADING DATASETS =====")

Xu, yu, pu = load_source(BASE, "unsw", features)
Xi, yi, pi = load_source(BASE, "iot", features)

X = np.concatenate([Xu, Xi]).astype(
    np.float32, copy=False
)

binary_y = np.concatenate([yu, yi])

provenance = pd.concat(
    [pu, pi], ignore_index=True
)

del Xu, Xi, yu, yi, pu, pi

attack_classes = sorted(
    set(provenance["Label"]) - {"Normal"}
)

classes = ["Normal"] + attack_classes

label_mapping = {
    label: i for i, label in enumerate(classes)
}

y = provenance["Label"].map(
    label_mapping
).to_numpy(dtype=np.int32)

assert len(classes) == 12
assert np.array_equal(y != 0, binary_y == 1)

print("Classes:", classes)
print("Records:", len(X))
print("Features:", len(features))

print("\n===== REUSING ORIGINAL DATA SPLITS =====")

with np.load(BINARY_DIR / "split_indices.npz") as splits:
    train_idx = splits["train"]
    val_idx = splits["validation"]
    test_idx = splits["test"]

all_indices = np.concatenate(
    [train_idx, val_idx, test_idx]
)

assert np.array_equal(
    np.sort(all_indices), np.arange(len(X))
)

print("Training:", len(train_idx))
print("Validation:", len(val_idx))
print("Testing:", len(test_idx))


def calculate_weights(indices):

    p = provenance.iloc[indices]

    groups = p["Dataset"] + "|" + p["Label"]

    counts = groups.value_counts()
    reference = float(counts.median())

    weights = groups.map(
        lambda g: np.clip(
            np.sqrt(reference / counts[g]),
            0.5,
            5.0
        )
    ).to_numpy(dtype=np.float32)

    return weights / weights.mean()


def train_model(name, tr, va, targets, num_classes):

    print(f"\n===== TRAINING {name} =====")

    model = XGBClassifier(
        objective="multi:softprob",
        num_class=num_classes,
        n_estimators=600,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=2.0,
        tree_method="hist",
        device="cpu",
        n_jobs=2,
        max_bin=256,
        eval_metric="mlogloss",
        early_stopping_rounds=30,
        random_state=42,
    )

    model.fit(
        X[tr],
        targets[tr],
        sample_weight=calculate_weights(tr),
        eval_set=[(X[va], targets[va])],
        verbose=25
    )

    print("Best iteration:", model.best_iteration)

    model.save_model(
        str(OUTPUT / f"{name}.json")
    )

    return model


# MODEL 1: Standalone multiclass classifier

standalone = train_model(
    "standalone_multiclass",
    train_idx,
    val_idx,
    y,
    len(classes)
)


# MODEL 2: Attack-only classifier

attack_train = train_idx[y[train_idx] != 0]
attack_val = val_idx[y[val_idx] != 0]

attack_model = train_model(
    "attack_type_classifier",
    attack_train,
    attack_val,
    y - 1,
    len(attack_classes)
)


# MODEL 3: Existing binary classifier

print("\n===== LOADING EXISTING BINARY MODEL =====")

binary_meta = json.loads(
    (BINARY_DIR / "hybrid_model_metadata.json").read_text()
)

assert binary_meta["features"] == features

threshold = binary_meta["decision_threshold"]

binary_model = XGBClassifier(n_jobs=2)

binary_model.load_model(
    str(BINARY_DIR / "nids_hybrid_xgboost.json")
)

assert binary_model.n_features_in_ == len(features)

print("Binary threshold:", threshold)


def hierarchical_predict(values):

    probabilities = binary_model.predict_proba(
        values
    )[:, 1]

    attack_mask = probabilities >= threshold

    predictions = np.zeros(
        len(values), dtype=np.int32
    )

    if attack_mask.any():

        predictions[attack_mask] = (
            attack_model.predict(
                values[attack_mask]
            ).astype(np.int32) + 1
        )

    return predictions


def evaluate(name, indices, predictions, partition):

    actual = y[indices]

    binary_actual = actual != 0
    binary_predicted = predictions != 0

    normal_mask = ~binary_actual
    attack_mask = binary_actual

    metrics = {
        "accuracy": float(
            accuracy_score(actual, predictions)
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(actual, predictions)
        ),
        "macro_f1": float(
            f1_score(
                actual, predictions,
                average="macro",
                zero_division=0
            )
        ),
        "weighted_f1": float(
            f1_score(
                actual, predictions,
                average="weighted",
                zero_division=0
            )
        ),
        "attack_detection_recall": float(
            binary_predicted[attack_mask].mean()
        ),
        "normal_false_positive_rate": float(
            binary_predicted[normal_mask].mean()
        ),
        "attack_type_accuracy": float(
            (actual[attack_mask] ==
             predictions[attack_mask]).mean()
        )
    }

    print(f"\n===== {name}: {partition} =====")

    for key, value in metrics.items():
        print(f"{key:<30}: {value:.6f}")

    report = classification_report(
        actual,
        predictions,
        labels=list(range(len(classes))),
        target_names=classes,
        zero_division=0,
        output_dict=True
    )

    pd.DataFrame(report).T.to_csv(
        OUTPUT / f"{name}_{partition}_report.csv"
    )

    if partition == "test":

        print(classification_report(
            actual,
            predictions,
            labels=list(range(len(classes))),
            target_names=classes,
            zero_division=0
        ))

        matrix = confusion_matrix(
            actual,
            predictions,
            labels=list(range(len(classes)))
        )

        pd.DataFrame(
            matrix,
            index=classes,
            columns=classes
        ).to_csv(
            OUTPUT / f"{name}_confusion_matrix.csv"
        )

        details = provenance.iloc[indices].copy()

        details["Actual"] = np.array(classes)[actual]
        details["Predicted"] = np.array(classes)[predictions]

        details["Correct"] = actual == predictions

        source_report = details.groupby(
            ["Dataset", "Label"]
        )["Correct"].agg(["count", "sum", "mean"])

        source_report.to_csv(
            OUTPUT / f"{name}_source_results.csv"
        )

        details.to_csv(
            OUTPUT / f"{name}_test_predictions.csv",
            index=False
        )

    return metrics


results = []

for partition, indices in [
    ("validation", val_idx),
    ("test", test_idx)
]:

    values = X[indices]

    predictions = {
        "standalone": standalone.predict(values),
        "hierarchical": hierarchical_predict(values)
    }

    for name, pred in predictions.items():

        metrics = evaluate(
            name, indices, pred, partition
        )

        results.append({
            "architecture": name,
            "partition": partition,
            **metrics
        })


comparison = pd.DataFrame(results)

comparison.to_csv(
    OUTPUT / "architecture_comparison.csv",
    index=False
)

print("\n===== FINAL ARCHITECTURE COMPARISON =====")

print(comparison.to_string(index=False))

# Save all configuration needed for deployment.

config = {
    "features": features,
    "feature_count": len(features),
    "classes": classes,
    "label_mapping": label_mapping,
    "attack_classes": attack_classes,
    "binary_threshold": threshold,
    "standalone_model": "standalone_multiclass.json",
    "attack_type_model": "attack_type_classifier.json",
    "evaluation_strategy": "reused_stratified_row_holdout",
    "independent_capture_test": False,
    "status": "experimental",
    "results": results
}

(OUTPUT / "multiclass_metadata.json").write_text(
    json.dumps(config, indent=4),
    encoding="utf-8"
)

print("\nModels and reports saved to:", OUTPUT)

print(
    "Execution time:",
    round((time.time() - start) / 60, 2),
    "minutes"
)

print("\n[SUCCESS] Architecture comparison completed")
