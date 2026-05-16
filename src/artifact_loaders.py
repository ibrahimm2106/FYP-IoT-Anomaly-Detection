"""
Disk-backed artefact I/O (pickle, CSV, threshold text) without Streamlit.

Streamlit-cached wrappers live in ``iot_streamlit`` for interactive performance.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd

from src.iot_paths import (
    DATA_PATH,
    FEATURE_COLUMNS_PATH,
    MODEL_PATH,
    PREPROCESSOR_PATH,
    THRESHOLD_PATH,
    coerce_hdf5_weights_path,
    default_disk_model_path,
)

MODEL_SUFFIXES = ("*.keras", "*.h5")


def load_feature_column_meta() -> dict | None:
    """Load feature metadata written by ``train.py``.

    Returns ``None`` when the file is absent or unreadable so callers can fall
    back to estimator metadata where possible.
    """
    if not FEATURE_COLUMNS_PATH.is_file():
        return None
    try:
        with FEATURE_COLUMNS_PATH.open("rb") as fh:
            return pickle.load(fh)
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError):
        return None


def read_threshold_mse() -> float:
    """Read the first numeric line from ``models/threshold.txt`` (raises ``ValueError`` on failure)."""
    try:
        lines = THRESHOLD_PATH.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            raise ValueError("empty file")
        return float(lines[0].strip())
    except (OSError, ValueError, IndexError) as exc:
        raise ValueError(
            f"Could not read a numeric threshold from `{THRESHOLD_PATH.as_posix()}`. "
            "Run `train.py` to write `models/threshold.txt`."
        ) from exc


def load_preprocessor_from_disk() -> object:
    """Unpickle the fitted preprocessing pipeline from ``models/preprocessor.pkl``."""
    with PREPROCESSOR_PATH.open("rb") as fh:
        return pickle.load(fh)


def read_processed_csv(path: Path | str) -> pd.DataFrame:
    """Read CSV from path; raises ``ValueError`` with examiner-facing text (no ``FileNotFoundError`` leak)."""
    p = Path(path)
    try:
        return pd.read_csv(p, low_memory=False)
    except FileNotFoundError:
        raise ValueError(f"Dataset file not found: `{p.as_posix()}`") from None
    except pd.errors.EmptyDataError as exc:
        raise ValueError("The CSV file is empty or has no parseable data rows.") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"Could not parse the CSV ({exc}).") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("The CSV is not valid UTF-8.") from exc
    except OSError as exc:
        raise ValueError(f"Could not read the dataset file ({type(exc).__name__}: {exc}).") from exc


def list_keras_model_paths() -> list[Path]:
    """Keras/HDF5 weights under ``models/`` (default disk model first when present, then others, deduped)."""
    seen: set[Path] = set()
    paths: list[Path] = []

    def add_if_model_file(path: Path) -> None:
        """Append a model path once, preserving display order."""
        resolved = path.resolve()
        if resolved.is_file() and resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)

    add_if_model_file(coerce_hdf5_weights_path(default_disk_model_path()))

    models_dir = MODEL_PATH.parent
    for suffix in MODEL_SUFFIXES:
        for path in sorted(models_dir.glob(suffix)):
            add_if_model_file(path)

    return paths


__all__ = [
    "load_feature_column_meta",
    "load_preprocessor_from_disk",
    "list_keras_model_paths",
    "read_processed_csv",
    "read_threshold_mse",
]
