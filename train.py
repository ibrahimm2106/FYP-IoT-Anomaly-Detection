"""
Train a deep autoencoder on benign IoT-23 connections for reconstruction-based anomaly detection.

Preprocessing is fit on benign training data only. A validation reconstruction-error
threshold is saved for flagging unusual flows at inference time.

After training the autoencoder this script also:
  - Evaluates the held-out test set and saves per-row scores.
  - Trains an Isolation Forest baseline on the same benign training data.
  - Saves models/baseline_metrics.json for the Evaluation page comparison.
  - Runs a threshold sweep and saves models/threshold_sweep.json.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from tensorflow import keras

from src.iot_paths import LEGACY_MODEL_PATH, MODEL_PATH
from src.model import build_autoencoder

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "ctu_iot_34_1.csv"
MODELS_DIR = PROJECT_ROOT / "models"
PREPROCESSOR_PATH = MODELS_DIR / "preprocessor.pkl"
FEATURE_COLUMNS_PATH = MODELS_DIR / "feature_columns.pkl"
THRESHOLD_PATH = MODELS_DIR / "threshold.txt"

LABEL_COLUMNS = ("label", "detailed-label")

# Connection identifiers and IP literals (high cardinality, poor for generalisation).
ID_COLUMNS = ("uid", "id.orig_h", "id.resp_h")

# Zeek-style categorical fields; other object/string columns are treated as categorical too.
DEFAULT_CATEGORICAL = (
    "proto",
    "service",
    "conn_state",
    "local_orig",
    "local_resp",
    "history",
    "tunnel_parents",
)


def load_dataset(path: Path) -> pd.DataFrame:
    """Load the processed IoT connection table.

    Args:
        path: Path to the processed CSV.

    Returns:
        The processed Zeek-style connection table.

    Raises:
        FileNotFoundError: If the processed CSV has not been generated.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Cleaned dataset not found: {path}")
    return pd.read_csv(path, low_memory=False)


def split_features_and_labels(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Separate model features from Zeek label columns.

    Args:
        df: Processed connection table containing ``label`` and
            ``detailed-label``.

    Returns:
        Feature columns, coarse labels, and detailed labels.

    Raises:
        ValueError: If either expected label column is absent.
    """
    missing = [c for c in LABEL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Expected label columns {LABEL_COLUMNS}; missing {missing}.")
    labels = df["label"].astype(str).str.strip()
    detailed = df["detailed-label"].astype(str).str.strip()
    features = df.drop(columns=list(LABEL_COLUMNS))
    return features, labels, detailed


def drop_identifier_columns(features: pd.DataFrame) -> pd.DataFrame:
    """Remove connection identifiers that should not drive generalisation.

    Args:
        features: Candidate feature table after labels have been removed.

    Returns:
        The feature table with high-cardinality identifier columns dropped.
    """
    present = [c for c in ID_COLUMNS if c in features.columns]
    if present:
        print(f"Dropping identifier / IP columns: {present}")
    return features.drop(columns=present, errors="ignore")


def detect_column_types(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Classify columns as numeric (scaled) or categorical (one-hot encoded)."""
    categorical = [
        c
        for c in features.columns
        if c in DEFAULT_CATEGORICAL
        or pd.api.types.is_object_dtype(features[c])
        or pd.api.types.is_string_dtype(features[c])
    ]
    numeric = [c for c in features.columns if c not in categorical]
    return numeric, categorical


def _one_hot_encoder() -> OneHotEncoder:
    """Build a version-compatible dense one-hot encoder.

    Returns:
        A ``OneHotEncoder`` that ignores unknown categories.
    """
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    """Create the preprocessing transformer used before the autoencoder.

    Args:
        numeric: Numeric feature columns that will be standardized.
        categorical: Text/category feature columns that will be one-hot encoded.

    Returns:
        A ``ColumnTransformer`` with numeric and categorical branches.

    Raises:
        ValueError: If no usable feature columns remain.
    """
    steps: list[tuple[str, object, list[str]]] = []
    if numeric:
        steps.append(("num", StandardScaler(), numeric))
    if categorical:
        steps.append(("cat", _one_hot_encoder(), categorical))
    if not steps:
        raise ValueError("No usable feature columns after dropping labels and identifiers.")
    return ColumnTransformer(steps)


def reconstruction_mse(x: np.ndarray, x_hat: np.ndarray) -> np.ndarray:
    """Calculate one reconstruction-error score per transformed row.

    Args:
        x: Preprocessed input matrix.
        x_hat: Autoencoder reconstruction of ``x``.

    Returns:
        A one-dimensional array of mean squared errors.
    """
    return np.mean(np.square(x - x_hat), axis=1)


def is_benign(labels: pd.Series) -> pd.Series:
    """Identify benign rows using the normalized Zeek ``label`` value.

    Args:
        labels: Zeek label series.

    Returns:
        Boolean mask with ``True`` for benign rows.
    """
    return labels.str.casefold() == "benign"


def save_artifacts(
    model: keras.Model,
    preprocessor: ColumnTransformer,
    numeric_cols: list[str],
    categorical_cols: list[str],
    threshold: float,
) -> None:
    """Persist the trained model and all inference dependencies.

    Args:
        model: Trained Keras autoencoder.
        preprocessor: Fitted preprocessing pipeline.
        numeric_cols: Numeric columns used during fitting.
        categorical_cols: Categorical columns used during fitting.
        threshold: Validation-derived reconstruction-MSE threshold.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    # Explicit HDF5 avoids TF 2.12 writing HDF5 bytes to a ``*.keras`` path (rejected by Keras 3+).
    # include_optimizer=False shrinks the file and avoids extra deserialization on load.
    model.save(MODEL_PATH, save_format="h5", include_optimizer=False)
    if LEGACY_MODEL_PATH.is_file():
        try:
            LEGACY_MODEL_PATH.unlink()
        except OSError:
            pass
    with PREPROCESSOR_PATH.open("wb") as fh:
        pickle.dump(preprocessor, fh, protocol=pickle.HIGHEST_PROTOCOL)
    feature_meta = {"numeric": numeric_cols, "categorical": categorical_cols}
    with FEATURE_COLUMNS_PATH.open("wb") as fh:
        pickle.dump(feature_meta, fh, protocol=pickle.HIGHEST_PROTOCOL)
    THRESHOLD_PATH.write_text(f"{threshold:.10g}\n", encoding="utf-8")


def _json_safe(d: dict) -> dict:
    """Convert NumPy scalars and non-finite floats into JSON-safe values.

    Args:
        d: Metrics dictionary that may contain NumPy scalar values.

    Returns:
        A dictionary suitable for strict JSON serialization.
    """
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


def run_post_training_evaluation(
    model: keras.Model,
    preprocessor: ColumnTransformer,
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_val: pd.Series,
    y_test: pd.Series,
    threshold: float,
) -> None:
    """Score the test set, train an Isolation Forest baseline, and save artefacts.

    Args:
        model: Trained Keras autoencoder.
        preprocessor: Fitted preprocessing pipeline.
        X_train: Training feature split.
        X_val: Validation feature split.
        X_test: Held-out test feature split.
        y_train: Training labels.
        y_val: Validation labels.
        y_test: Held-out test labels.
        threshold: Fixed anomaly threshold selected from benign validation MSE.
    """
    from src.metrics import classification_metrics, ranking_metrics, threshold_sweep

    print("\n--- Post-training evaluation ---")

    benign_train = is_benign(y_train)
    benign_val = is_benign(y_val)

    X_train_ben = X_train.loc[benign_train]
    X_val_t = preprocessor.transform(X_val)
    X_test_t = preprocessor.transform(X_test)
    X_train_ben_t = preprocessor.transform(X_train_ben)

    # Test set — autoencoder scores
    print("Scoring test set with autoencoder…")
    test_pred = model.predict(X_test_t, batch_size=512, verbose=0)
    test_mse = reconstruction_mse(X_test_t, test_pred)
    test_flagged = (test_mse > threshold).astype(np.int32)
    y_test_bin = (y_test.str.casefold() != "benign").astype(np.int32).to_numpy()

    ae_cm = classification_metrics(y_test_bin, test_flagged)
    ae_rm = ranking_metrics(y_test_bin, test_mse)
    print(
        f"  Test precision: {ae_cm['precision']:.4f}  recall: {ae_cm['recall']:.4f}"
        f"  F1: {ae_cm['f1_score']:.4f}  PR-AUC: {ae_rm['pr_auc'] or 'n/a'}"
        f"  ROC-AUC: {ae_rm['roc_auc'] or 'n/a'}"
    )

    # Threshold sweep on validation benign errors
    print("Running threshold sweep…")
    val_pred = model.predict(X_val_t, batch_size=512, verbose=0)
    val_mse = reconstruction_mse(X_val_t, val_pred)
    val_benign_mse = val_mse[benign_val.to_numpy()]
    sweep_df = threshold_sweep(y_test_bin, test_mse, benign_scores=val_benign_mse)
    sweep_path = MODELS_DIR / "threshold_sweep.json"
    sweep_path.write_text(
        json.dumps(sweep_df.to_dict(orient="records"), indent=2), encoding="utf-8"
    )
    print(f"  Saved: {sweep_path}")

    # Isolation Forest baseline
    print("Training Isolation Forest baseline…")
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=42, n_jobs=-1)
    iso.fit(X_train_ben_t)
    iso_scores = -iso.decision_function(X_test_t)
    iso_labels = (iso.predict(X_test_t) == -1).astype(np.int32)
    bl_cm = classification_metrics(y_test_bin, iso_labels)
    bl_rm = ranking_metrics(y_test_bin, iso_scores)
    print(
        f"  IF precision: {bl_cm['precision']:.4f}  recall: {bl_cm['recall']:.4f}"
        f"  F1: {bl_cm['f1_score']:.4f}  PR-AUC: {bl_rm['pr_auc'] or 'n/a'}"
        f"  ROC-AUC: {bl_rm['roc_auc'] or 'n/a'}"
    )

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
    print(f"  Saved: {baseline_path}")

    # Save per-row test scores for the dashboard upload
    scored_test = X_test.copy()
    scored_test["label"] = y_test.values
    scored_test["mse_score"] = test_mse
    scored_test["flagged"] = test_flagged.astype(bool)
    test_scores_path = PROJECT_ROOT / "data" / "processed" / "test_scores.csv"
    scored_test.to_csv(test_scores_path, index=False)
    print(f"  Saved: {test_scores_path}")


def main() -> int:
    """Run the complete training pipeline.

    Returns:
        Process exit code. ``0`` indicates all core artefacts were written.
    """
    print("=== IoT deep autoencoder — training ===\n")

    try:
        print(f"Loading dataset: {DATA_PATH}")
        df = load_dataset(DATA_PATH)
        features, labels, _detailed = split_features_and_labels(df)
        features = drop_identifier_columns(features)

        numeric_cols, categorical_cols = detect_column_types(features)
        if not numeric_cols and not categorical_cols:
            raise ValueError("No feature columns left to model.")

        print(f"Total rows: {len(df)}")
        print(f"Numeric columns ({len(numeric_cols)}): {numeric_cols}")
        print(f"Categorical columns ({len(categorical_cols)}): {categorical_cols}")

        # Stratified 70% / 15% / 15% train / validation / test on attack label
        X_trainval, X_test, y_trainval, _y_test = train_test_split(
            features,
            labels,
            test_size=0.15,
            random_state=42,
            stratify=labels,
        )
        val_size = 0.15 / (1.0 - 0.15)
        X_train, X_val, y_train, y_val = train_test_split(
            X_trainval,
            y_trainval,
            test_size=val_size,
            random_state=42,
            stratify=y_trainval,
        )

        benign_train = is_benign(y_train)
        benign_val = is_benign(y_val)
        n_benign_tr = int(benign_train.sum())
        n_benign_val = int(benign_val.sum())
        if n_benign_tr == 0:
            raise ValueError("No benign rows in the training split.")
        if n_benign_val == 0:
            raise ValueError("No benign rows in the validation split.")

        X_train_benign = X_train.loc[benign_train]

        # Pipeline stage 1: Data Ingestion has loaded the processed Zeek CSV.
        # Labels drive stratification and benign-only training selection, but
        # labels are never passed into the autoencoder feature matrix.
        print("\nFitting preprocessor on benign training rows only...")
        preprocessor = build_preprocessor(numeric_cols, categorical_cols)
        preprocessor.fit(X_train_benign)

        # Pipeline stage 2: Preprocessing standardizes numeric telemetry and
        # one-hot encodes categorical Zeek fields. The fitted transformer is
        # saved so Streamlit inference uses the exact same feature order.
        print("Transforming splits...")
        X_train_benign_t = preprocessor.transform(X_train_benign)
        X_val_t = preprocessor.transform(X_val)
        X_val_benign_t = preprocessor.transform(X_val.loc[benign_val])

        input_dim = X_train_benign_t.shape[1]
        print(f"Transformed feature dimension: {input_dim}")

        # Pipeline stage 3: Autoencoder Encoder/Decoder Layers compress each
        # benign connection into a latent representation and reconstruct the
        # original vector. Targets equal inputs because this is self-supervised.
        print("\nBuilding and compiling autoencoder...")
        model = build_autoencoder(input_dim)

        early_stop = keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=5,
            restore_best_weights=True,
        )

        print("\nTraining on benign traffic (targets = inputs)...\n")
        history = model.fit(
            X_train_benign_t,
            X_train_benign_t,
            epochs=100,
            batch_size=256,
            shuffle=True,
            validation_data=(X_val_benign_t, X_val_benign_t),
            callbacks=[early_stop],
            verbose=1,
        )

        # Pipeline stage 4: Reconstruction Error Calculation compares the
        # decoder output with the input vector using per-row mean squared error.
        print("\nComputing validation reconstruction error (MSE per row)...")
        val_pred = model.predict(X_val_t, batch_size=512, verbose=0)
        val_errors = reconstruction_mse(X_val_t, val_pred)

        # Pipeline stage 5: Anomaly Thresholding uses only benign validation
        # errors. Any future row above this persisted percentile is flagged.
        benign_val_errors = val_errors[benign_val.to_numpy()]
        threshold = float(np.percentile(benign_val_errors, 99.0))

        # === Figure 5.3: validation reconstruction error distribution ===
        import matplotlib.pyplot as plt

        mu = float(np.mean(benign_val_errors))
        sigma = float(np.std(benign_val_errors))
        T = threshold  # already 99th percentile; keep your existing definition

        print(f"\nBenign val mean MSE: {mu:.6f}")
        print(f"Benign val std MSE:  {sigma:.6f}")
        print(f"Using threshold T (99th percentile): {T:.6f}")

        plt.figure(figsize=(10, 5))
        plt.hist(benign_val_errors, bins=80, density=True, alpha=0.7,
                 color="steelblue", label="Benign validation MSE")
        plt.axvline(T, color="red", linestyle="--", linewidth=2,
                    label="Threshold T = " + str(round(T, 4)))
        plt.xlabel("Reconstruction Error (MSE)")
        plt.ylabel("Density")
        plt.title("Figure 5.4 - Reconstruction Error Distribution (Benign Validation Set)")
        plt.legend()
        plt.tight_layout()
        plt.savefig("figure_5_4_threshold.png", dpi=300, bbox_inches="tight")
        plt.close()

        print("Saving model, preprocessing, feature column names, and threshold...")
        save_artifacts(model, preprocessor, numeric_cols, categorical_cols, threshold)

        try:
            run_post_training_evaluation(
                model, preprocessor,
                X_train, X_val, X_test,
                y_train, y_val, _y_test,
                threshold,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"\nWarning: post-training evaluation failed ({exc}). Core artefacts are still saved.", file=sys.stderr)

        print("\n--- Summary ---")
        print(f"Train / validation / test sizes: {len(X_train)} / {len(X_val)} / {len(X_test)}")
        print(f"Benign rows used for training: {n_benign_tr}")
        print(f"Benign rows in validation (for threshold stats): {n_benign_val}")
        print(f"Epochs completed: {len(history.history['loss'])}")
        print(f"Final train MSE: {float(history.history['loss'][-1]):.6f}")
        print(f"Final val MSE (benign-only val monitor): {float(history.history['val_loss'][-1]):.6f}")
        print(
            f"Val benign reconstruction MSE — min / median / max: "
            f"{benign_val_errors.min():.6f} / {float(np.median(benign_val_errors)):.6f} / {benign_val_errors.max():.6f}"
        )
        print(f"Saved anomaly threshold (99th percentile, benign val): {threshold:.6f}")
        print(f"\nOutputs:\n  {MODEL_PATH}\n  {PREPROCESSOR_PATH}\n  {FEATURE_COLUMNS_PATH}\n  {THRESHOLD_PATH}")

    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: I/O failure: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
