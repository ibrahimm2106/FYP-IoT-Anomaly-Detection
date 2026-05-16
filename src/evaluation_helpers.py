"""
Evaluation helpers for metrics, matrix views, and error analysis.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.iot_streamlit import find_saved_baseline_reference
from src.scoring_types import (
    ScoringBundle,
    bundle_has_labels,
    confusion_matrix_long_dataframe,
    contingency_matrix_dataframe,
    evaluation_metrics_from_bundle,
)


def metrics_dataframe(bundle: ScoringBundle) -> pd.DataFrame:
    """Return headline evaluation metrics as a two-column table.

    Args:
        bundle: Scoring output for one app session.

    Returns:
        Dataframe with metric names and values.
    """
    ev = evaluation_metrics_from_bundle(bundle)
    return pd.DataFrame(
        [
            {"metric": "Precision", "value": ev["precision"]},
            {"metric": "Recall", "value": ev["recall"]},
            {"metric": "F1-score", "value": ev["f1_score"]},
            {"metric": "PR-AUC", "value": ev["pr_auc"]},
        ]
    )


def false_positive_negative_analysis(bundle: ScoringBundle) -> dict[str, int | None]:
    """Extract false-positive and false-negative counts.

    Args:
        bundle: Scoring output for one app session.

    Returns:
        Dictionary with counts, or ``None`` values when labels are unavailable.
    """
    ev = evaluation_metrics_from_bundle(bundle)
    if not bundle_has_labels(bundle):
        return {"false_positives": None, "false_negatives": None}
    return {"false_positives": int(ev["fp"] or 0), "false_negatives": int(ev["fn"] or 0)}


def baseline_metrics_table() -> tuple[pd.DataFrame | None, str | None]:
    """Load optional baseline metrics for comparison views.

    Returns:
        Tuple of ``(metrics_dataframe, source_path)``. The dataframe is
        ``None`` when no JSON baseline is available.
    """
    baseline_path = find_saved_baseline_reference()
    if baseline_path is None:
        return None, None
    p = Path(baseline_path)
    if p.suffix.lower() != ".json":
        return None, baseline_path
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None, baseline_path
    if not isinstance(raw, dict):
        return None, baseline_path
    keys = ("precision", "recall", "f1_score", "pr_auc", "accuracy")
    rows = [{"metric": k, "baseline_value": raw.get(k)} for k in keys if k in raw]
    if not rows:
        return None, baseline_path
    return pd.DataFrame(rows), baseline_path


__all__ = [
    "baseline_metrics_table",
    "bundle_has_labels",
    "confusion_matrix_long_dataframe",
    "contingency_matrix_dataframe",
    "evaluation_metrics_from_bundle",
    "false_positive_negative_analysis",
    "metrics_dataframe",
]
