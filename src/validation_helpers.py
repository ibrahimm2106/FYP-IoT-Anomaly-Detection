"""
Validation and data quality helpers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.table_io import missing_values_top_columns


def schema_overview(df: pd.DataFrame) -> pd.DataFrame:
    """Build a compact column/dtype overview.

    Args:
        df: Dataframe to inspect.

    Returns:
        Dataframe with ``column`` and ``dtype`` columns.
    """
    return (
        df.dtypes.astype(str)
        .rename("dtype")
        .reset_index()
        .rename(columns={"index": "column"})
    )


def data_quality_summary(df: pd.DataFrame) -> dict[str, int]:
    """Summarize core table quality counts.

    Args:
        df: Dataframe to audit.

    Returns:
        Dictionary containing row, column, duplicate, null, and invalid-number
        counts.
    """
    numeric_df = df.select_dtypes(include=["number"])
    invalid_numeric = int((~np.isfinite(numeric_df.to_numpy())).sum()) if numeric_df.shape[1] > 0 else 0
    return {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns_with_nulls": int(df.isna().any().sum()),
        "invalid_numeric_cells": invalid_numeric,
    }


def label_quality_summary(df: pd.DataFrame) -> dict[str, int | None]:
    """Summarize Zeek label availability and benign/non-benign counts.

    Args:
        df: Dataframe that may contain a ``label`` column.

    Returns:
        Dictionary with label counts, or ``None`` values when labels are absent.
    """
    if "label" not in df.columns:
        return {"unique_labels": None, "benign_rows": None, "non_benign_rows": None}
    label_norm = df["label"].astype(str).str.strip().str.casefold()
    return {
        "unique_labels": int(label_norm.nunique()),
        "benign_rows": int((label_norm == "benign").sum()),
        "non_benign_rows": int((label_norm != "benign").sum()),
    }


def missing_values_audit(df: pd.DataFrame, *, top_n: int = 25) -> pd.DataFrame | None:
    """Return the highest-null columns for review.

    Args:
        df: Dataframe to audit.
        top_n: Maximum number of columns to return.

    Returns:
        A dataframe of missing-value counts, or ``None`` when there are no
        missing cells.
    """
    return missing_values_top_columns(df, top_n=top_n)


__all__ = [
    "data_quality_summary",
    "label_quality_summary",
    "missing_values_audit",
    "schema_overview",
]
