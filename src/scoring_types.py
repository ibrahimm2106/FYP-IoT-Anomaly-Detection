"""
Core scoring types and pure metric helpers (no Streamlit / TensorFlow).

``ScoringBundle`` is the shared contract between the scoring engine and UI layers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ScoringBundle:
    """Everything UI pages need after one forward pass over the scored CSV."""

    df: pd.DataFrame
    errors: np.ndarray
    flagged: np.ndarray
    threshold: float
    labels: pd.Series | None
    tp: int | None
    fp: int | None
    tn: int | None
    fn: int | None
    transformed_dim: int


EVAL_METRIC_UNAVAILABLE = "— (not defined for this run)"


def reconstruction_mse(x: np.ndarray, x_hat: np.ndarray) -> np.ndarray:
    """Return per-row mean squared reconstruction error."""
    return np.mean(np.square(x - x_hat), axis=1)


def malicious_label_boolean_mask(labels: pd.Series) -> pd.Series:
    """True where Zeek `label` is treated as malicious (anything other than benign, case-insensitive)."""
    s = labels.astype(str).str.strip()
    return s.str.casefold() != "benign"


def precision_recall_f1_from_counts(tp: int, fp: int, tn: int, fn: int) -> tuple[float | None, float | None, float | None]:
    """Point estimates from a 2×2 confusion matrix at a fixed threshold (matches ``compute_scoring`` definitions)."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1: float | None = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2.0 * precision * recall / (precision + recall)
    return precision, recall, f1


def bundle_has_labels(bundle: ScoringBundle) -> bool:
    """True when the bundle carries one aligned label for every scored row."""
    return bundle.labels is not None and len(bundle.labels) == len(bundle.df)


def pr_auc_from_scores(labels: pd.Series, scores: np.ndarray) -> float | None:
    """
    PR-AUC (average precision) for malicious=positive using reconstruction MSE as the ranking score.

    Uses sklearn on the **already computed** per-row scores and labels only (no invented values).
    """
    try:
        from sklearn.metrics import average_precision_score
    except ImportError:
        return None
    if len(labels) != len(scores):
        return None
    y_true = (labels.astype(str).str.strip().str.casefold() != "benign").astype(np.int32).to_numpy()
    y_score = np.asarray(scores, dtype=np.float64)
    pos = int(y_true.sum())
    neg = int(len(y_true) - pos)
    if pos == 0 or neg == 0:
        return None
    try:
        ap = average_precision_score(y_true, y_score)
    except ValueError:
        return None
    if ap is None or (isinstance(ap, float) and (np.isnan(ap) or np.isinf(ap))):
        return None
    return float(ap)


def evaluation_metrics_from_bundle(bundle: ScoringBundle) -> dict[str, float | int | None]:
    """Compute supervised-style evaluation metrics for one scoring bundle."""
    if not bundle_has_labels(bundle):
        return {
            "precision": None,
            "recall": None,
            "f1_score": None,
            "pr_auc": None,
            "tp": None,
            "fp": None,
            "tn": None,
            "fn": None,
            "malicious_count": None,
        }
    labels = bundle.labels
    assert labels is not None
    tp = int(bundle.tp or 0)
    fp = int(bundle.fp or 0)
    tn = int(bundle.tn or 0)
    fn = int(bundle.fn or 0)
    precision, recall, f1 = precision_recall_f1_from_counts(tp, fp, tn, fn)
    pr_auc = pr_auc_from_scores(labels, bundle.errors)
    malicious = int(malicious_label_boolean_mask(labels).sum())
    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "pr_auc": pr_auc,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "malicious_count": malicious,
    }


def contingency_matrix_dataframe(bundle: ScoringBundle) -> pd.DataFrame:
    """Zeek label (benign vs malicious) × detector flag; same cell semantics as ``compute_scoring``."""
    if not bundle_has_labels(bundle):
        return pd.DataFrame(
            {
                "Detector prediction": ["Flagged (anomaly)", "Not flagged (normal)"],
                "Malicious (`label`)": ["n/a", "n/a"],
                "Benign (`label`)": ["n/a", "n/a"],
            }
        ).set_index("Detector prediction")
    tp, fp, tn, fn = int(bundle.tp or 0), int(bundle.fp or 0), int(bundle.tn or 0), int(bundle.fn or 0)
    return pd.DataFrame(
        {
            "Detector prediction": ["Flagged (anomaly)", "Not flagged (normal)"],
            "Malicious (`label`)": [tp, fn],
            "Benign (`label`)": [fp, tn],
        }
    ).set_index("Detector prediction")


def confusion_matrix_long_dataframe(bundle: ScoringBundle) -> pd.DataFrame:
    """Long-format confusion matrix for charts and report exports."""
    if not bundle_has_labels(bundle):
        return pd.DataFrame(
            [
                {"actual": "Malicious", "predicted": "Flagged", "count": np.nan},
                {"actual": "Malicious", "predicted": "Not flagged", "count": np.nan},
                {"actual": "Benign", "predicted": "Flagged", "count": np.nan},
                {"actual": "Benign", "predicted": "Not flagged", "count": np.nan},
            ]
        )
    return pd.DataFrame(
        [
            {"actual": "Malicious", "predicted": "Flagged", "count": int(bundle.tp or 0)},
            {"actual": "Malicious", "predicted": "Not flagged", "count": int(bundle.fn or 0)},
            {"actual": "Benign", "predicted": "Flagged", "count": int(bundle.fp or 0)},
            {"actual": "Benign", "predicted": "Not flagged", "count": int(bundle.tn or 0)},
        ]
    )


def finalize_scoring_bundle(
    df: pd.DataFrame,
    labels: pd.Series | None,
    errors: np.ndarray,
    flagged: np.ndarray,
    threshold: float,
    transformed_dim: int,
) -> ScoringBundle:
    """Attach TP/FP/TN/FN when labels align with ``df``."""
    tp: int | None = None
    fp: int | None = None
    tn: int | None = None
    fn: int | None = None
    if labels is not None and len(labels) == len(df):
        benign = labels.str.casefold() == "benign"
        malicious = ~benign
        tp = int((flagged & malicious).sum())
        fp = int((flagged & benign).sum())
        tn = int((~flagged & benign).sum())
        fn = int((~flagged & malicious).sum())
    return ScoringBundle(
        df=df,
        errors=errors,
        flagged=flagged,
        threshold=threshold,
        labels=labels,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        transformed_dim=transformed_dim,
    )


__all__ = [
    "EVAL_METRIC_UNAVAILABLE",
    "ScoringBundle",
    "bundle_has_labels",
    "confusion_matrix_long_dataframe",
    "contingency_matrix_dataframe",
    "evaluation_metrics_from_bundle",
    "finalize_scoring_bundle",
    "malicious_label_boolean_mask",
    "precision_recall_f1_from_counts",
    "pr_auc_from_scores",
    "reconstruction_mse",
]
