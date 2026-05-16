"""
Export helper functions for page-level reuse.
"""

from __future__ import annotations

import pandas as pd

from src.app_core import ScoringBundle
from src.iot_streamlit import classification_report_markdown, metrics_report_csv_bytes, metrics_report_json_bytes


def anomaly_export_dataframe(bundle: ScoringBundle, *, top_n: int, flagged_only: bool) -> pd.DataFrame:
    """Build a ranked anomaly export table.

    Args:
        bundle: Scoring output for one app session.
        top_n: Maximum number of rows to include.
        flagged_only: Whether to restrict output to flagged anomalies.

    Returns:
        Dataframe sorted by descending reconstruction MSE.
    """
    work = bundle.df.copy()
    work.insert(0, "record_index", range(len(work)))
    work["reconstruction_mse"] = bundle.errors
    work["anomaly_flag"] = bundle.flagged
    if flagged_only:
        work = work[work["anomaly_flag"]]
    work = work.sort_values("reconstruction_mse", ascending=False)
    return work.head(max(1, int(top_n)))


def metrics_exports(bundle: ScoringBundle, *, source_label: str) -> tuple[bytes, bytes]:
    """Create CSV and JSON metric export payloads.

    Args:
        bundle: Scoring output for one app session.
        source_label: Human-readable source label for filenames/reports.

    Returns:
        Tuple of ``(csv_bytes, json_bytes)``.
    """
    return (
        metrics_report_csv_bytes(bundle, source_label),
        metrics_report_json_bytes(bundle, source_label),
    )


def markdown_report_bytes(bundle: ScoringBundle, *, source_label: str) -> bytes:
    """Create a markdown report payload for download.

    Args:
        bundle: Scoring output for one app session.
        source_label: Human-readable source label.

    Returns:
        UTF-8 encoded markdown report bytes.
    """
    return classification_report_markdown(bundle, data_source_label=source_label).encode("utf-8")


__all__ = [
    "anomaly_export_dataframe",
    "markdown_report_bytes",
    "metrics_exports",
]
