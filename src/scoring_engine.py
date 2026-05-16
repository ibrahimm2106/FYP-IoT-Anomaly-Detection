"""
Pre-validation and reconstruction scoring (TensorFlow inference).

Callers supply a loaded ``preprocessor`` and ``model``; session threshold and
caching remain in ``iot_streamlit``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.artifact_loaders import load_feature_column_meta
from src.iot_paths import ID_COLUMNS, LABEL_COLUMNS
from src.scoring_types import ScoringBundle, finalize_scoring_bundle, reconstruction_mse
from src.user_messages import friendly_scoring_error


def _feature_meta_columns() -> list[str] | None:
    """Return feature order from ``feature_columns.pkl`` when estimator metadata is absent."""
    meta = load_feature_column_meta()
    if not meta:
        return None

    numeric = meta.get("numeric") or []
    categorical = meta.get("categorical") or []
    columns = [str(column) for column in [*numeric, *categorical]]
    return columns or None


def expected_feature_column_order(preprocessor: Any) -> list[str] | None:
    """Column names and order required by the fitted ``ColumnTransformer`` (matches training)."""
    feature_names = getattr(preprocessor, "feature_names_in_", None)
    if feature_names is not None and len(feature_names) > 0:
        return [str(column) for column in feature_names]
    return _feature_meta_columns()


def validate_dataframe_for_scoring(df: pd.DataFrame, preprocessor: Any) -> tuple[bool, str | None]:
    """
    Check labels and feature schema before ``preprocessor.transform``.

    The upload must include the same feature columns the preprocessor was fit on.
    """
    if len(df) == 0:
        return False, "The dataset has **no rows** after parsing."
    if df.columns.duplicated().any():
        dupes = [str(c) for c in df.columns[df.columns.duplicated()].unique()][:15]
        shown = ", ".join(f"`{c}`" for c in dupes)
        return False, f"Duplicate column names are not supported (examples: {shown})."
    cols = expected_feature_column_order(preprocessor)
    if not cols:
        return (
            False,
            "Could not determine the **feature column list** for this model. "
            "Re-run `train.py` so `preprocessor.pkl` and `feature_columns.pkl` are written together, then try again.",
        )
    missing = [c for c in cols if c not in df.columns]
    if missing:
        head = ", ".join(f"`{c}`" for c in missing[:20])
        tail = f" … (+{len(missing) - 20} more)" if len(missing) > 20 else ""
        return (
            False,
            f"Missing **{len(missing)}** column(s) required for inference: {head}{tail}. "
            "Use the same schema as this project’s processed Zeek CSV for feature columns.",
        )
    return True, None


def _inference_frame(work_df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Select trained feature columns and drop identifier columns before transform."""
    features = work_df.loc[:, feature_cols].copy()
    return features.drop(columns=[c for c in ID_COLUMNS if c in features.columns], errors="ignore")


def build_scoring_bundle(
    work_df: pd.DataFrame,
    *,
    labels: pd.Series | None,
    feature_cols: list[str],
    preprocessor: Any,
    model: Any,
    threshold: float,
) -> ScoringBundle:
    """
    Transform ``feature_cols`` from ``work_df``, run autoencoder, return a ``ScoringBundle``.

    Raises ``ValueError`` with a friendly message on preprocessing/inference failure.
    """
    try:
        transformed = preprocessor.transform(_inference_frame(work_df, feature_cols))
        reconstructed = model.predict(transformed, batch_size=512, verbose=0)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Preprocessing or inference failed ({friendly_scoring_error(exc)}). "
            "Check that numeric columns are parseable numbers and categoricals match Zeek-style strings."
        ) from exc

    errors = reconstruction_mse(transformed, reconstructed)
    flagged = errors > threshold
    return finalize_scoring_bundle(
        work_df,
        labels,
        errors,
        flagged,
        threshold,
        int(transformed.shape[1]),
    )


__all__ = [
    "build_scoring_bundle",
    "expected_feature_column_order",
    "validate_dataframe_for_scoring",
]
