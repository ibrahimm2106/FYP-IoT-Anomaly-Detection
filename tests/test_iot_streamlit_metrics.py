"""Core metric helpers in ``iot_streamlit`` (imports TensorFlow — keep suite small)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.iot_streamlit import (
    ScoringBundle,
    bundle_has_labels,
    evaluation_metrics_from_bundle,
    friendly_scoring_error,
    precision_recall_f1_from_counts,
    reconstruction_mse,
)


def test_reconstruction_mse_shape() -> None:
    """Verify reconstruction MSE returns one score per row."""
    x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    x_hat = np.array([[0.0, 0.5], [0.5, 0.0]], dtype=np.float32)
    mse = reconstruction_mse(x, x_hat)
    assert mse.shape == (2,)
    assert mse[0] > 0


def test_precision_recall_f1_perfect() -> None:
    """Verify fixed-threshold metrics for a perfect confusion matrix."""
    p, r, f1 = precision_recall_f1_from_counts(tp=10, fp=0, tn=5, fn=0)
    assert p == 1.0
    assert r == 1.0
    assert f1 == 1.0


def test_precision_recall_f1_no_positive_predictions() -> None:
    """Verify precision/F1 are undefined with no positive predictions."""
    p, r, f1 = precision_recall_f1_from_counts(tp=0, fp=0, tn=10, fn=2)
    assert p is None
    assert r == 0.0
    assert f1 is None


def test_bundle_without_labels_has_no_supervised_metrics() -> None:
    """Verify unlabeled bundles suppress supervised metrics."""
    df = pd.DataFrame({"x": [1, 2]})
    b = ScoringBundle(
        df=df,
        errors=np.array([0.1, 0.2]),
        flagged=np.array([False, True]),
        threshold=0.15,
        labels=None,
        tp=None,
        fp=None,
        tn=None,
        fn=None,
        transformed_dim=1,
    )
    assert not bundle_has_labels(b)
    ev = evaluation_metrics_from_bundle(b)
    assert ev["precision"] is None
    assert ev["recall"] is None


def test_friendly_scoring_error_file_not_found() -> None:
    """Verify file-not-found errors become user-facing messages."""
    msg = friendly_scoring_error(FileNotFoundError("models/x"))
    assert "Expected file" in msg or "not found" in msg.lower()


def test_friendly_scoring_error_value_error_passthrough() -> None:
    """Verify validation errors keep their actionable message text."""
    msg = friendly_scoring_error(ValueError("Missing required column: z"))
    assert "Missing required" in msg
