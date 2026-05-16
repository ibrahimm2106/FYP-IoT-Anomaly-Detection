"""``repair_helpers`` — in-memory repair transforms (no Streamlit / TF)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.repair_helpers import (
    duplicate_row_count,
    optional_columns_to_drop,
    repair_dataframe,
    total_missing_cells,
)


def test_total_missing_cells() -> None:
    """Verify missing-cell counting across all columns."""
    df = pd.DataFrame({"a": [1.0, np.nan], "b": [np.nan, 2.0]})
    assert total_missing_cells(df) == 2


def test_duplicate_row_count() -> None:
    """Verify duplicate-row counting excludes the first occurrence."""
    df = pd.DataFrame({"x": [1, 1, 2]})
    assert duplicate_row_count(df) == 1


def test_optional_columns_to_drop_respects_required() -> None:
    """Verify required model features are protected from optional dropping."""
    df = pd.DataFrame({"f1": [1], "f2": [2], "label": ["Benign"]})
    req = ["f1"]
    drop_opts = optional_columns_to_drop(df, req)
    assert "f1" not in drop_opts
    assert "f2" in drop_opts


def test_repair_median_fill_no_duplicates() -> None:
    """Verify median imputation fills numeric gaps without dropping rows."""
    df = pd.DataFrame({"feat": [1.0, np.nan, 3.0], "label": ["Benign", "Benign", "Benign"]})
    out, log = repair_dataframe(
        df,
        required=["feat"],
        missing_numeric="median",
        missing_categorical="none",
        drop_duplicates=False,
        extra_columns_to_drop=[],
        add_invalid_flag=False,
        remove_invalid_rows=False,
        clip_numeric_percentiles=False,
    )
    assert out["feat"].isna().sum() == 0
    assert log["numeric_missing_filled"] > 0
