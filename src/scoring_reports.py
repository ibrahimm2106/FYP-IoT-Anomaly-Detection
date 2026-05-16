"""Markdown / CSV / JSON report payloads derived from a ``ScoringBundle``."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.scoring_types import ScoringBundle, evaluation_metrics_from_bundle


def metrics_report_dict(bundle: ScoringBundle, *, data_source_description: str) -> dict[str, Any]:
    """Build the canonical metrics payload for CSV/JSON exports.

    Args:
        bundle: Scoring output for one app session.
        data_source_description: Human-readable data source label.

    Returns:
        Dictionary containing threshold, counts, and evaluation metrics.
    """
    ev = evaluation_metrics_from_bundle(bundle)
    return {
        "report_schema_version": 1,
        "data_source": data_source_description,
        "rows_scored": int(len(bundle.df)),
        "flagged_count": int(bundle.flagged.sum()),
        "true_malicious_label_count": ev["malicious_count"],
        "threshold_mse": float(bundle.threshold),
        "tp": ev["tp"],
        "fp": ev["fp"],
        "tn": ev["tn"],
        "fn": ev["fn"],
        "precision": ev["precision"],
        "recall": ev["recall"],
        "f1_score": ev["f1_score"],
        "pr_auc": ev["pr_auc"],
    }


def _metrics_value_for_csv(v: Any) -> Any:
    """Normalize optional metric values for CSV output.

    Args:
        v: Metric value that may be ``None`` or non-finite.

    Returns:
        Empty string for unavailable values; otherwise the original value.
    """
    if v is None:
        return ""
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return ""
    return v


def metrics_report_csv_bytes(bundle: ScoringBundle, data_source_description: str) -> bytes:
    """Serialize one metrics row as UTF-8 CSV bytes.

    Args:
        bundle: Scoring output for one app session.
        data_source_description: Human-readable data source label.

    Returns:
        CSV bytes for a single-row metrics report.
    """
    row = metrics_report_dict(bundle, data_source_description=data_source_description)
    flat = {k: _metrics_value_for_csv(v) for k, v in row.items()}
    return pd.DataFrame([flat]).to_csv(index=False).encode("utf-8")


def _metrics_row_json_safe(row: dict[str, Any]) -> dict[str, Any]:
    """Strip NaN/inf floats so ``json.dumps(..., allow_nan=False)`` never fails."""
    out: dict[str, Any] = {}
    for k, v in row.items():
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


def metrics_report_json_bytes(bundle: ScoringBundle, data_source_description: str) -> bytes:
    """Serialize one metrics row as strict JSON bytes.

    Args:
        bundle: Scoring output for one app session.
        data_source_description: Human-readable data source label.

    Returns:
        JSON bytes for a metrics report.
    """
    row = metrics_report_dict(bundle, data_source_description=data_source_description)
    safe = _metrics_row_json_safe(row)
    return json.dumps(safe, indent=2, allow_nan=False).encode("utf-8")


def metrics_filename_stub(label: str) -> str:
    """Create a filesystem-friendly metrics filename stub.

    Args:
        label: Source label to convert.

    Returns:
        Lowercase alphanumeric/underscore stub capped at 48 characters.
    """
    stub = re.sub(r"[^a-zA-Z0-9]+", "_", label).strip("_").lower()
    return stub[:48] if stub else "metrics"


def classification_report_markdown(bundle: ScoringBundle, *, data_source_label: str) -> str:
    """Simple reproducible markdown report for submission appendices."""
    ev = evaluation_metrics_from_bundle(bundle)
    precision = ev["precision"]
    recall = ev["recall"]
    f1 = ev["f1_score"]
    pr_auc = ev["pr_auc"]
    flagged = int(bundle.flagged.sum())
    malicious = ev["malicious_count"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _f(v: float | None) -> str:
        """Format optional metric values for markdown."""
        return "n/a" if v is None else f"{v:.4f}"

    lines = [
        "# IoT Autoencoder Detection Report",
        "",
        f"- Generated: {now}",
        f"- Data source: {data_source_label}",
        f"- Rows scored: {len(bundle.df)}",
        f"- Rows flagged: {flagged}",
        f"- Non-benign labels: {'n/a' if malicious is None else malicious}",
        f"- Threshold (MSE): {bundle.threshold:.6f}",
        "",
        "## Evaluation metrics",
        "",
        f"- Precision: {_f(precision)}",
        f"- Recall: {_f(recall)}",
        f"- F1-score: {_f(f1)}",
        f"- PR-AUC: {_f(pr_auc)}",
        "",
        "## Confusion counts",
        "",
        f"- TP: {'n/a' if ev['tp'] is None else ev['tp']}",
        f"- FP: {'n/a' if ev['fp'] is None else ev['fp']}",
        f"- TN: {'n/a' if ev['tn'] is None else ev['tn']}",
        f"- FN: {'n/a' if ev['fn'] is None else ev['fn']}",
        "",
        "## Notes",
        "",
        "- MSE is a reconstruction error score, not a calibrated probability.",
        "- Metrics are session-specific and depend on dataset and threshold.",
    ]
    return "\n".join(lines)


__all__ = [
    "classification_report_markdown",
    "metrics_filename_stub",
    "metrics_report_csv_bytes",
    "metrics_report_dict",
    "metrics_report_json_bytes",
]
