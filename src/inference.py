"""
Standalone inference utilities: load saved artifacts and score Zeek connection data.

No Streamlit dependency — usable from scripts, notebooks, and the CLI.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow import keras

from src.iot_paths import (
    FEATURE_COLUMNS_PATH as _FEATURE_COLUMNS_PATH,
    PREPROCESSOR_PATH as _PREPROCESSOR_PATH,
    THRESHOLD_PATH as _THRESHOLD_PATH,
    coerce_hdf5_weights_path,
    default_disk_model_path,
)

_LABEL_COLUMNS = ("label", "detailed-label")
_ID_COLUMNS = ("uid", "id.orig_h", "id.resp_h")


def _default_path(path: Path | str | None, fallback: Path) -> Path:
    """Return a caller-supplied path as ``Path`` or the configured fallback."""
    return Path(path) if path is not None else fallback


def _read_first_float(path: Path) -> float:
    """Read the first non-empty line from a threshold file as ``float``."""
    raw_lines = path.read_text(encoding="utf-8").strip().splitlines()
    if not raw_lines:
        raise ValueError(f"Threshold file is empty: {path}")
    return float(raw_lines[0])


def _load_pickle(path: Path) -> object:
    """Load a pickle artifact from disk."""
    with path.open("rb") as handle:
        return pickle.load(handle)


def load_artifacts(
    model_path: Path | str | None = None,
    preprocessor_path: Path | str | None = None,
    threshold_path: Path | str | None = None,
    feature_columns_path: Path | str | None = None,
) -> tuple:
    """
    Load the saved model, preprocessor, threshold and feature metadata.

    All parameters are optional; omit them to use the default ``models/`` paths.

    Returns
    -------
    (model, preprocessor, threshold, feature_meta)
        where ``feature_meta`` is the dict ``{"numeric": [...], "categorical": [...]}``.
    """
    m_path = coerce_hdf5_weights_path(_default_path(model_path, default_disk_model_path()))
    p_path = _default_path(preprocessor_path, _PREPROCESSOR_PATH)
    t_path = _default_path(threshold_path, _THRESHOLD_PATH)
    fc_path = _default_path(feature_columns_path, _FEATURE_COLUMNS_PATH)

    model = keras.models.load_model(m_path, compile=False)
    preprocessor = _load_pickle(p_path)
    threshold = _read_first_float(t_path)
    feature_meta = _load_pickle(fc_path)

    return model, preprocessor, threshold, feature_meta


def _drop_non_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove label and connection-identifier columns before model inference."""
    drop = [c for c in list(_LABEL_COLUMNS) + list(_ID_COLUMNS) if c in df.columns]
    return df.drop(columns=drop, errors="ignore")


def reconstruction_mse(x: np.ndarray, x_hat: np.ndarray) -> np.ndarray:
    """Return per-row mean squared reconstruction error."""
    return np.mean(np.square(x - x_hat), axis=1)


def score_dataframe(
    df: pd.DataFrame,
    model: object,
    preprocessor: object,
    threshold: float,
    batch_size: int = 512,
) -> pd.DataFrame:
    """
    Score a DataFrame of Zeek connections and return it with two extra columns.

    Columns added
    -------------
    mse_score : float
        Per-row reconstruction MSE.
    flagged : bool
        True where MSE strictly exceeds the threshold.

    Label and ID columns (``label``, ``detailed-label``, ``uid``, ``id.orig_h``,
    ``id.resp_h``) are stripped before inference and **not** present in the output.
    The original DataFrame is not modified.
    """
    features = _drop_non_feature_columns(df)
    x = preprocessor.transform(features)
    x_hat = model.predict(x, batch_size=batch_size, verbose=0)
    mse = reconstruction_mse(x, x_hat)
    out = df.copy()
    out["mse_score"] = mse
    out["flagged"] = mse > threshold
    return out


def score_single_row(
    row: dict,
    model: object,
    preprocessor: object,
    threshold: float,
) -> dict:
    """
    Score one connection supplied as a plain dict of Zeek feature values.

    Returns
    -------
    {"mse_score": float, "flagged": bool}
    """
    df = pd.DataFrame([row])
    result = score_dataframe(df, model, preprocessor, threshold)
    return {
        "mse_score": float(result["mse_score"].iloc[0]),
        "flagged": bool(result["flagged"].iloc[0]),
    }


def score_csv_file(
    csv_path: Path | str,
    model: object,
    preprocessor: object,
    threshold: float,
    batch_size: int = 512,
) -> pd.DataFrame:
    """
    Load a CSV file of Zeek connections and return it scored.

    A convenience wrapper around :func:`score_dataframe` for CLI use.
    """
    df = pd.read_csv(Path(csv_path), low_memory=False)
    return score_dataframe(df, model, preprocessor, threshold, batch_size=batch_size)
