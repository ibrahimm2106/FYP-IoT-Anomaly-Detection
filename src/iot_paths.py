"""
Filesystem paths and column role constants for the IoT scoring pipeline.

Separated from ``iot_streamlit`` so scoring logic and tests can import layout
without pulling Streamlit or TensorFlow.
"""

from __future__ import annotations

from pathlib import Path

from src.iot_constants import PROJECT_ROOT

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "ctu_iot_34_1.csv"
# TF 2.12's default `model.save("*.keras")` writes HDF5, but Keras 3+ treats `*.keras` as a zip
# and errors with "accessible .keras zip file". Use `.h5` so every version loads HDF5 correctly.
MODEL_PATH = PROJECT_ROOT / "models" / "autoencoder.h5"
LEGACY_MODEL_PATH = PROJECT_ROOT / "models" / "autoencoder.keras"
PREPROCESSOR_PATH = PROJECT_ROOT / "models" / "preprocessor.pkl"
THRESHOLD_PATH = PROJECT_ROOT / "models" / "threshold.txt"
FEATURE_COLUMNS_PATH = PROJECT_ROOT / "models" / "feature_columns.pkl"

LABEL_COLUMNS = ("label", "detailed-label")
ID_COLUMNS = ("uid", "id.orig_h", "id.resp_h")


def default_disk_model_path() -> Path:
    """Prefer `autoencoder.h5`; fall back to legacy `autoencoder.keras` if only that exists."""
    if MODEL_PATH.is_file():
        return MODEL_PATH
    if LEGACY_MODEL_PATH.is_file():
        return LEGACY_MODEL_PATH
    return MODEL_PATH


def coerce_hdf5_weights_path(cand: Path) -> Path:
    """
    TF 2.12 often writes HDF5 bytes to a ``*.keras`` path; Keras 3+ then fails to open it.

    When the file is HDF5 and a sibling ``*.h5`` exists (e.g. after retraining), prefer the ``.h5`` path.
    """
    if not cand.is_file() or cand.suffix.lower() != ".keras":
        return cand
    try:
        head = cand.open("rb").read(4)
    except OSError:
        return cand
    if not head.startswith(b"\x89HDF"):
        return cand
    alt = cand.with_suffix(".h5")
    if alt.is_file():
        return alt
    return cand


__all__ = [
    "DATA_PATH",
    "FEATURE_COLUMNS_PATH",
    "ID_COLUMNS",
    "LABEL_COLUMNS",
    "LEGACY_MODEL_PATH",
    "MODEL_PATH",
    "PREPROCESSOR_PATH",
    "PROJECT_ROOT",
    "THRESHOLD_PATH",
    "coerce_hdf5_weights_path",
    "default_disk_model_path",
]
