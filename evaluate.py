"""
Standalone evaluation script for the IoT-23 autoencoder.

What it does
------------
1. Re-splits the processed CSV with the same seed as train.py (stratified 70/15/15).
2. Loads the saved model, preprocessor, and threshold.
3. Scores the held-out TEST SET (the 15% never seen during training or threshold calibration).
4. Trains an Isolation Forest baseline on the same benign training rows.
5. Computes a full metrics report: precision, recall, F1, PR-AUC, ROC-AUC.
6. Runs a threshold sweep (90th–99.9th percentile of benign validation MSE).
7. Breaks down detection rate by Zeek detailed-label (attack type).
8. Saves:
   - models/baseline_metrics.json  ← picked up automatically by the Streamlit Evaluation page
   - models/test_evaluation.json   ← full test-set report for submission appendix
   - data/processed/test_scores.csv ← per-row scored test set (importable into Detection Results)

Run from the project root:
    python evaluate.py

Prerequisites: run src/preprocess.py, then train.py before this script.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split

from src.iot_paths import (
    DATA_PATH,
    FEATURE_COLUMNS_PATH,
    PREPROCESSOR_PATH,
    THRESHOLD_PATH,
    coerce_hdf5_weights_path,
    default_disk_model_path,
)

PROJECT_ROOT = Path(__file__).resolve().parent

LABEL_COLUMNS = ("label", "detailed-label")
ID_COLUMNS = ("uid", "id.orig_h", "id.resp_h")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_artifacts() -> tuple[object, object, float, dict]:
    """Load the saved model, preprocessor, threshold, and feature metadata.

    Returns:
        Tuple of ``(model, preprocessor, threshold, feature_meta)``.
    """
    from tensorflow import keras

    mp = coerce_hdf5_weights_path(default_disk_model_path())
    model = keras.models.load_model(mp, compile=False)
    with PREPROCESSOR_PATH.open("rb") as fh:
        preprocessor = pickle.load(fh)
    threshold = float(THRESHOLD_PATH.read_text(encoding="utf-8").strip().splitlines()[0])
    with FEATURE_COLUMNS_PATH.open("rb") as fh:
        feature_meta = pickle.load(fh)
    return model, preprocessor, threshold, feature_meta


def _reconstruction_mse(x: np.ndarray, x_hat: np.ndarray) -> np.ndarray:
    """Return per-row reconstruction MSE for evaluation scoring.

    Args:
        x: Preprocessed input matrix.
        x_hat: Autoencoder reconstruction matrix.

    Returns:
        One MSE value for each row.
    """
    return np.mean(np.square(x - x_hat), axis=1)


def _is_benign(labels: pd.Series) -> np.ndarray:
    """Convert Zeek labels into a benign boolean mask.

    Args:
        labels: Label series from the processed dataset.

    Returns:
        Boolean NumPy array where benign rows are ``True``.
    """
    return (labels.astype(str).str.strip().str.casefold() == "benign").to_numpy()


def _binary_labels(labels: pd.Series) -> np.ndarray:
    """Convert Zeek labels into binary malicious labels.

    Args:
        labels: Label series from the processed dataset.

    Returns:
        ``1`` for non-benign rows and ``0`` for benign rows.
    """
    return (~_is_benign(labels)).astype(np.int32)


def _resplit(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Reproduce the exact train/validation/test split from ``train.py``.

    Args:
        df: Processed labelled connection table.

    Returns:
        Feature and label splits in train, validation, and test order.
    """
    labels = df["label"].astype(str).str.strip()
    features = df.drop(columns=list(LABEL_COLUMNS))
    features = features.drop(columns=[c for c in ID_COLUMNS if c in features.columns], errors="ignore")

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        features, labels, test_size=0.15, random_state=42, stratify=labels
    )
    val_size = 0.15 / (1.0 - 0.15)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=val_size, random_state=42, stratify=y_trainval
    )
    return X_train, X_val, X_test, y_train, y_val, y_test


def _json_safe(d: dict) -> dict:
    """Strip NaN/inf floats so json.dumps never fails."""
    out: dict = {}
    for k, v in d.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (float, np.floating)):
            fv = float(v)
            out[k] = None if (np.isnan(fv) or np.isinf(fv)) else fv
        elif isinstance(v, (int, np.integer)):
            out[k] = int(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def main() -> int:
    """Run standalone held-out test evaluation.

    Returns:
        Process exit code. ``0`` means evaluation artefacts were written.
    """
    print("=== IoT-23 autoencoder — standalone evaluation ===\n")

    # ------------------------------------------------------------------
    # 0. Guard: check all required files exist
    # ------------------------------------------------------------------
    weights = coerce_hdf5_weights_path(default_disk_model_path())
    missing = [p for p in (weights, PREPROCESSOR_PATH, THRESHOLD_PATH, FEATURE_COLUMNS_PATH, DATA_PATH) if not p.is_file()]
    if missing:
        for p in missing:
            print(f"  Missing: {p}", file=sys.stderr)
        print("\nRun src/preprocess.py and train.py first.", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # 1. Load data and reproduce the split
    # ------------------------------------------------------------------
    print(f"Loading dataset: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH, low_memory=False)
    print(f"Total rows: {len(df):,}")

    X_train, X_val, X_test, y_train, y_val, y_test = _resplit(df)

    benign_train = _is_benign(y_train)
    benign_val = _is_benign(y_val)
    print(
        f"Split sizes — train: {len(X_train):,}  val: {len(X_val):,}  test: {len(X_test):,}"
    )
    print(
        f"Benign in train: {benign_train.sum():,}   Benign in val: {benign_val.sum():,}"
    )

    # ------------------------------------------------------------------
    # 2. Load saved artifacts
    # ------------------------------------------------------------------
    print("\nLoading model artifacts…")
    model, preprocessor, threshold, _feature_meta = _load_artifacts()
    print(f"Threshold (from training): {threshold:.6f}")

    # ------------------------------------------------------------------
    # 3. Transform splits
    # ------------------------------------------------------------------
    # Pipeline stage 2: Preprocessing uses the same fitted transformer saved by
    # training, preserving numeric scaling, one-hot categories, and feature order.
    print("Transforming test set…")
    X_train_ben = X_train.loc[benign_train]
    X_val_t = preprocessor.transform(X_val)
    X_test_t = preprocessor.transform(X_test)
    X_train_ben_t = preprocessor.transform(X_train_ben)

    # ------------------------------------------------------------------
    # 4. Score the TEST SET with the autoencoder
    # ------------------------------------------------------------------
    # Pipeline stages 3-5: the encoder/decoder reconstructs the transformed
    # vector, MSE measures reconstruction error, and the saved threshold turns
    # each score into a binary anomaly flag.
    print("Scoring test set with autoencoder…")
    test_pred = model.predict(X_test_t, batch_size=512, verbose=0)
    test_mse = _reconstruction_mse(X_test_t, test_pred)
    test_flagged = (test_mse > threshold).astype(np.int32)
    y_test_bin = _binary_labels(y_test)

    from src.metrics import classification_metrics, ranking_metrics, threshold_sweep, per_attack_type_metrics

    ae_cm = classification_metrics(y_test_bin, test_flagged)
    ae_rm = ranking_metrics(y_test_bin, test_mse)
    ae_full = {"split": "test", **ae_cm, **ae_rm}

    print("\n--- Autoencoder — test set ---")
    for k, v in ae_full.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    # ------------------------------------------------------------------
    # 5. Threshold sweep (benign validation MSE as reference)
    # ------------------------------------------------------------------
    print("\nRunning threshold sweep on validation benign errors…")
    val_pred = model.predict(X_val_t, batch_size=512, verbose=0)
    val_mse = _reconstruction_mse(X_val_t, val_pred)
    val_benign_mse = val_mse[benign_val]

    sweep_df = threshold_sweep(y_test_bin, test_mse, benign_scores=val_benign_mse)
    print(sweep_df[["percentile", "threshold", "precision", "recall", "f1_score"]].to_string(index=False))

    # ------------------------------------------------------------------
    # 6. Per-attack-type breakdown
    # ------------------------------------------------------------------
    if "detailed-label" in df.columns:
        print("\nPer-attack-type breakdown (test set)…")
        detailed_test = df.loc[y_test.index, "detailed-label"].reset_index(drop=True)
        y_test_reset = y_test.reset_index(drop=True)
        _ = y_test_reset  # used only for index alignment above
        breakdown_df = per_attack_type_metrics(detailed_test, test_flagged, test_mse)
        if not breakdown_df.empty:
            print(breakdown_df.to_string(index=False))
        else:
            print("  No attack types found in test set.")
    else:
        breakdown_df = pd.DataFrame()

    # ------------------------------------------------------------------
    # 7. Isolation Forest baseline (same benign training data)
    # ------------------------------------------------------------------
    print("\nTraining Isolation Forest baseline (benign training rows)…")
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=42, n_jobs=-1)
    iso.fit(X_train_ben_t)
    iso_raw = iso.decision_function(X_test_t)
    iso_scores = -iso_raw                      # higher = more anomalous (matches MSE convention)
    iso_labels = (iso.predict(X_test_t) == -1).astype(np.int32)

    bl_cm = classification_metrics(y_test_bin, iso_labels)
    bl_rm = ranking_metrics(y_test_bin, iso_scores)
    bl_full = {"split": "test_isolation_forest", **bl_cm, **bl_rm}

    print("\n--- Isolation Forest baseline — test set ---")
    for k, v in bl_full.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    # ------------------------------------------------------------------
    # 8. Save outputs
    # ------------------------------------------------------------------
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # baseline_metrics.json — consumed by Streamlit Evaluation page
    baseline_payload = {
        "model": "Isolation Forest",
        "n_estimators": 200,
        "precision": bl_cm["precision"],
        "recall": bl_cm["recall"],
        "f1_score": bl_cm["f1_score"],
        "pr_auc": bl_rm["pr_auc"],
        "roc_auc": bl_rm["roc_auc"],
    }
    baseline_path = MODELS_DIR / "baseline_metrics.json"
    baseline_path.write_text(
        json.dumps(_json_safe(baseline_payload), indent=2), encoding="utf-8"
    )
    print(f"\nSaved: {baseline_path}")

    # test_evaluation.json — full report for submission appendix
    test_eval_payload = {
        "autoencoder": _json_safe(ae_full),
        "isolation_forest": _json_safe(bl_full),
        "threshold_sweep": sweep_df.to_dict(orient="records"),
        "attack_breakdown": breakdown_df.to_dict(orient="records") if not breakdown_df.empty else [],
    }
    test_eval_path = MODELS_DIR / "test_evaluation.json"
    test_eval_path.write_text(
        json.dumps(test_eval_payload, indent=2), encoding="utf-8"
    )
    print(f"Saved: {test_eval_path}")

    # test_scores.csv — per-row scored test set
    scored_test = X_test.copy()
    scored_test["label"] = y_test.values
    if "detailed-label" in df.columns:
        scored_test["detailed-label"] = df.loc[y_test.index, "detailed-label"].values
    scored_test["mse_score"] = test_mse
    scored_test["flagged"] = test_flagged.astype(bool)
    test_scores_path = PROJECT_ROOT / "data" / "processed" / "test_scores.csv"
    scored_test.to_csv(test_scores_path, index=False)
    print(f"Saved: {test_scores_path}")

    # ------------------------------------------------------------------
    # 9. Summary
    # ------------------------------------------------------------------
    print("\n=== Evaluation summary ===")
    print(f"{'Metric':<18} {'Autoencoder':>14} {'Isolation Forest':>18}")
    print("-" * 52)
    for metric, label in [
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1_score", "F1-score"),
        ("pr_auc", "PR-AUC"),
        ("roc_auc", "ROC-AUC"),
    ]:
        ae_val = ae_full.get(metric)
        bl_val = bl_full.get(metric)
        ae_str = "n/a" if ae_val is None else f"{ae_val:.4f}"
        bl_str = "n/a" if bl_val is None else f"{bl_val:.4f}"
        print(f"{label:<18} {ae_str:>14} {bl_str:>18}")

    print(f"\nTest rows: {len(X_test):,}   Attack rows: {int(y_test_bin.sum()):,}")
    print(f"Fixed threshold (from training): {threshold:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
