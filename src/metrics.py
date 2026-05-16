"""
Standalone metrics for reconstruction-based anomaly detection.

No Streamlit dependency — safe to import from scripts, notebooks, and evaluate.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def binary_labels(labels: pd.Series) -> np.ndarray:
    """Convert Zeek label series to 1 (malicious) / 0 (benign) integer array."""
    return (
        labels.astype(str).str.strip().str.casefold() != "benign"
    ).astype(np.int32).to_numpy()


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int]:
    """Precision, recall, F1, TP, FP, TN, FN at a fixed threshold."""
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def ranking_metrics(y_true: np.ndarray, scores: np.ndarray) -> dict[str, float | None]:
    """
    PR-AUC (average precision) and ROC-AUC from continuous anomaly scores.

    Returns None for each metric when only one class is present.
    """
    pos = int(y_true.sum())
    neg = int(len(y_true) - pos)
    if pos == 0 or neg == 0:
        return {"pr_auc": None, "roc_auc": None}
    return {
        "pr_auc": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
    }


def threshold_sweep(
    y_true: np.ndarray,
    scores: np.ndarray,
    benign_scores: np.ndarray | None = None,
    percentiles: list[float] | None = None,
) -> pd.DataFrame:
    """
    Evaluate precision, recall and F1 at multiple MSE percentile thresholds.

    Parameters
    ----------
    y_true:
        Binary labels — 1 = malicious, 0 = benign.
    scores:
        Per-row reconstruction MSE for the full evaluation set.
    benign_scores:
        MSE of known-benign rows used to derive percentile cut-offs.
        Falls back to ``scores[y_true == 0]`` when None.
    percentiles:
        Percentiles of the benign MSE distribution to sweep (default 90–99.9).
    """
    if percentiles is None:
        percentiles = [90.0, 95.0, 97.0, 98.0, 99.0, 99.5, 99.9]
    ref = benign_scores if benign_scores is not None else scores[y_true == 0]
    rows = []
    for p in percentiles:
        thresh = float(np.percentile(ref, p))
        y_pred = (scores > thresh).astype(np.int32)
        m = classification_metrics(y_true, y_pred)
        rows.append({"percentile": p, "threshold": thresh, **m})
    return pd.DataFrame(rows)


def per_attack_type_metrics(
    labels_detailed: pd.Series,
    y_pred: np.ndarray,
    scores: np.ndarray,
) -> pd.DataFrame:
    """
    Detection rate and average MSE broken down by Zeek detailed-label.

    Benign rows are excluded. Each unique attack label becomes one row.
    """
    clean = labels_detailed.astype(str).str.strip()
    attack_mask = clean.str.casefold() != "benign"
    attack_types = clean[attack_mask].unique()

    rows = []
    for atype in sorted(attack_types):
        mask = (clean == atype).to_numpy()
        n = int(mask.sum())
        if n == 0:
            continue
        detected = int(y_pred[mask].sum())
        rows.append(
            {
                "attack_type": atype,
                "count": n,
                "detected": detected,
                "detection_rate": round(detected / n, 4),
                "avg_mse": round(float(scores[mask].mean()), 6),
                "median_mse": round(float(np.median(scores[mask])), 6),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["attack_type", "count", "detected", "detection_rate", "avg_mse", "median_mse"]
        )
    return (
        pd.DataFrame(rows)
        .sort_values("detection_rate", ascending=False)
        .reset_index(drop=True)
    )


def full_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    scores: np.ndarray,
    split_name: str = "test",
) -> dict:
    """Combine classification and ranking metrics into one flat dict."""
    cm = classification_metrics(y_true, y_pred)
    rm = ranking_metrics(y_true, scores)
    return {"split": split_name, **cm, **rm}


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    scores: np.ndarray,
    metric: str,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    random_state: int = 42,
) -> tuple[float, float]:
    """
    Bootstrap ``ci``-level confidence interval for one metric.

    Parameters
    ----------
    y_true:  binary ground truth (1 = malicious, 0 = benign)
    y_pred:  binary predictions at the fixed threshold
    scores:  continuous anomaly scores (reconstruction MSE)
    metric:  one of ``precision``, ``recall``, ``f1_score``, ``pr_auc``, ``roc_auc``
    n_bootstrap: number of bootstrap resamples (default 1000)
    ci:      confidence level (default 0.95 → 95 % CI)

    Returns
    -------
    (lower, upper)  — the CI endpoints
    """
    rng = np.random.default_rng(random_state)
    n = len(y_true)
    values: list[float] = []

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        yt, yp, sc = y_true[idx], y_pred[idx], scores[idx]

        if metric in ("precision", "recall", "f1_score"):
            val = classification_metrics(yt, yp)[metric]
        elif metric in ("pr_auc", "roc_auc"):
            rm = ranking_metrics(yt, sc)
            val = rm.get(metric) or 0.0
        else:
            raise ValueError(f"Unknown metric '{metric}'.")
        values.append(val)

    alpha = (1.0 - ci) / 2.0
    lower = float(np.percentile(values, 100.0 * alpha))
    upper = float(np.percentile(values, 100.0 * (1.0 - alpha)))
    return lower, upper


def bootstrap_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    scores: np.ndarray,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    random_state: int = 42,
) -> dict[str, dict[str, float]]:
    """
    Bootstrap CIs for all five key metrics.

    Returns a dict mapping metric name → ``{"value": float, "lower": float, "upper": float}``.
    """
    metrics_list = ["precision", "recall", "f1_score", "pr_auc", "roc_auc"]
    point = {**classification_metrics(y_true, y_pred), **ranking_metrics(y_true, scores)}
    result: dict[str, dict] = {}
    for m in metrics_list:
        lower, upper = bootstrap_ci(
            y_true, y_pred, scores, m,
            n_bootstrap=n_bootstrap, ci=ci, random_state=random_state,
        )
        result[m] = {"value": point.get(m), "lower": lower, "upper": upper}
    return result
