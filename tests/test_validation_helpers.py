"""``validation_helpers`` — data quality summaries (no Streamlit / TF)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.validation_helpers import data_quality_summary, label_quality_summary, schema_overview


def test_data_quality_summary_counts() -> None:
    """Verify quality summary reports row and column counts."""
    df = pd.DataFrame({"a": [1, 2, np.nan], "b": [3, 4, 5]})
    q = data_quality_summary(df)
    assert q["rows"] == 3
    assert q["columns"] == 2
    assert q["columns_with_nulls"] >= 1


def test_label_quality_summary_without_label() -> None:
    """Verify label summary returns unavailable values when labels are absent."""
    df = pd.DataFrame({"x": [1, 2]})
    s = label_quality_summary(df)
    assert s["unique_labels"] is None


def test_label_quality_summary_with_benign() -> None:
    """Verify benign and non-benign label counts are normalized."""
    df = pd.DataFrame({"label": ["Benign", "benign", "Malicious"]})
    s = label_quality_summary(df)
    assert s["benign_rows"] == 2
    assert s["non_benign_rows"] == 1


def test_schema_overview_shape() -> None:
    """Verify schema overview contains one row per input column."""
    df = pd.DataFrame({"c": [1.0]})
    ov = schema_overview(df)
    assert "column" in ov.columns
    assert "dtype" in ov.columns
    assert len(ov) == 1
