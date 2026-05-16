"""
Plotly visualisation functions for IoT-23 anomaly detection analysis.

All functions return a ``plotly.graph_objects.Figure`` — rendering is left to the caller.
No Streamlit dependency.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.metrics import auc, precision_recall_curve, roc_curve


_PALETTE = {
    "benign": "#3b82f6",
    "malicious": "#ef4444",
    "autoencoder": "#6366f1",
    "baseline": "#f59e0b",
    "roc": "#10b981",
    "neutral": "#9ca3af",
    "threshold": "#f97316",
}


def mse_distribution_figure(
    scores: np.ndarray,
    labels: pd.Series | None,
    threshold: float,
    max_bins: int = 80,
) -> go.Figure:
    """
    Overlapping histogram of reconstruction MSE split by benign / malicious.

    When labels are unavailable all rows are shown as a single series.
    A vertical dashed line marks the saved threshold.
    """
    fig = go.Figure()

    if labels is not None and len(labels) == len(scores):
        benign_mask = labels.astype(str).str.strip().str.casefold() == "benign"
        fig.add_trace(
            go.Histogram(
                x=scores[benign_mask.to_numpy()],
                name="Benign",
                nbinsx=max_bins,
                opacity=0.65,
                marker_color=_PALETTE["benign"],
            )
        )
        fig.add_trace(
            go.Histogram(
                x=scores[~benign_mask.to_numpy()],
                name="Malicious",
                nbinsx=max_bins,
                opacity=0.65,
                marker_color=_PALETTE["malicious"],
            )
        )
    else:
        fig.add_trace(
            go.Histogram(
                x=scores,
                name="All rows",
                nbinsx=max_bins,
                opacity=0.75,
                marker_color=_PALETTE["autoencoder"],
            )
        )

    fig.add_vline(
        x=threshold,
        line_dash="dash",
        line_color=_PALETTE["threshold"],
        annotation_text=f"Threshold  {threshold:.5f}",
        annotation_position="top right",
        annotation_font_color=_PALETTE["threshold"],
    )
    fig.update_layout(
        barmode="overlay",
        title="Reconstruction MSE distribution — benign vs malicious",
        xaxis_title="Reconstruction MSE",
        yaxis_title="Connection count (log scale)",
        yaxis_type="log",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        template="plotly_white",
    )
    return fig


def pr_curve_figure(y_true: np.ndarray, scores: np.ndarray) -> go.Figure:
    """Interactive precision–recall curve with area shading and random baseline."""
    precision, recall, _ = precision_recall_curve(y_true, scores)
    pr_auc = float(auc(recall, precision))
    random_baseline = float(y_true.mean())

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=recall,
            y=precision,
            mode="lines",
            name=f"Autoencoder  PR-AUC = {pr_auc:.3f}",
            line=dict(color=_PALETTE["autoencoder"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(99,102,241,0.10)",
        )
    )
    fig.add_hline(
        y=random_baseline,
        line_dash="dot",
        line_color=_PALETTE["neutral"],
        annotation_text=f"Random baseline  ({random_baseline:.3f})",
        annotation_position="bottom right",
        annotation_font_color=_PALETTE["neutral"],
    )
    fig.update_layout(
        title="Precision–Recall curve",
        xaxis_title="Recall",
        yaxis_title="Precision",
        xaxis=dict(range=[0, 1]),
        yaxis=dict(range=[0, 1.05]),
        template="plotly_white",
    )
    return fig


def roc_curve_figure(y_true: np.ndarray, scores: np.ndarray) -> go.Figure:
    """Interactive ROC curve with area shading and random-classifier diagonal."""
    fpr, tpr, _ = roc_curve(y_true, scores)
    roc_auc = float(auc(fpr, tpr))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=fpr,
            y=tpr,
            mode="lines",
            name=f"Autoencoder  ROC-AUC = {roc_auc:.3f}",
            line=dict(color=_PALETTE["roc"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(16,185,129,0.10)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Random classifier  (AUC = 0.500)",
            line=dict(color=_PALETTE["neutral"], dash="dot", width=1.5),
        )
    )
    fig.update_layout(
        title="Receiver Operating Characteristic (ROC) curve",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        xaxis=dict(range=[0, 1]),
        yaxis=dict(range=[0, 1.05]),
        template="plotly_white",
    )
    return fig


def threshold_sweep_figure(sweep_df: pd.DataFrame) -> go.Figure:
    """
    Line chart of precision, recall and F1 across percentile threshold values.

    ``sweep_df`` must have columns: percentile, precision, recall, f1_score.
    """
    spec = {
        "precision": (_PALETTE["autoencoder"], "Precision"),
        "recall": (_PALETTE["roc"], "Recall"),
        "f1_score": (_PALETTE["baseline"], "F1-score"),
    }
    fig = go.Figure()
    for col, (color, label) in spec.items():
        fig.add_trace(
            go.Scatter(
                x=sweep_df["percentile"],
                y=sweep_df[col],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2),
                marker=dict(size=6),
            )
        )
    fig.update_layout(
        title="Precision / Recall / F1 across MSE threshold percentiles",
        xaxis_title="Benign-MSE percentile used as threshold",
        yaxis_title="Score",
        yaxis=dict(range=[0, 1.05]),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        template="plotly_white",
    )
    return fig


def per_attack_breakdown_figure(breakdown_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of detection rate per attack type (Zeek detailed-label)."""
    if breakdown_df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No attack-type breakdown available",
            template="plotly_white",
        )
        return fig

    sorted_df = breakdown_df.sort_values("detection_rate").reset_index(drop=True)
    colors = [
        f"rgba(239,68,68,{0.4 + 0.6 * r})" for r in sorted_df["detection_rate"]
    ]
    fig = go.Figure(
        go.Bar(
            x=sorted_df["detection_rate"],
            y=sorted_df["attack_type"],
            orientation="h",
            marker_color=colors,
            text=[f"n={n}  ({r:.0%})" for n, r in zip(sorted_df["count"], sorted_df["detection_rate"])],
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Detection rate: %{x:.2%}<br>"
                "Count: %{customdata[0]}<br>"
                "Avg MSE: %{customdata[1]:.5f}<extra></extra>"
            ),
            customdata=sorted_df[["count", "avg_mse"]].values,
        )
    )
    fig.update_layout(
        title="Detection rate by attack type (Zeek detailed-label)",
        xaxis_title="Detection rate",
        xaxis=dict(range=[0, 1.15], tickformat=".0%"),
        yaxis_title="",
        template="plotly_white",
        height=max(300, 60 + 40 * len(sorted_df)),
    )
    return fig


def confusion_heatmap_figure(tp: int, fp: int, tn: int, fn: int) -> go.Figure:
    """Annotated 2×2 confusion-matrix heatmap."""
    z = [[tn, fp], [fn, tp]]
    annotations = [
        [f"TN<br>{tn:,}", f"FP<br>{fp:,}"],
        [f"FN<br>{fn:,}", f"TP<br>{tp:,}"],
    ]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=["Predicted normal", "Predicted anomaly"],
            y=["Actual benign", "Actual malicious"],
            text=annotations,
            texttemplate="%{text}",
            textfont=dict(size=14),
            colorscale="Blues",
            showscale=True,
            colorbar=dict(title="Count"),
        )
    )
    fig.update_layout(
        title="Confusion matrix heatmap",
        xaxis_title="Detector prediction",
        yaxis_title="Ground truth (Zeek label)",
        template="plotly_white",
    )
    return fig


def baseline_comparison_figure(
    autoencoder_metrics: dict,
    baseline_metrics: dict,
    model_names: tuple[str, str] = ("Autoencoder", "Isolation Forest"),
) -> go.Figure:
    """
    Grouped bar chart comparing autoencoder vs baseline across key metrics.

    Both dicts must have keys: precision, recall, f1_score, pr_auc, roc_auc.
    None values are rendered as 0 with a note in hover text.
    """
    metric_labels = {
        "precision": "Precision",
        "recall": "Recall",
        "f1_score": "F1-score",
        "pr_auc": "PR-AUC",
        "roc_auc": "ROC-AUC",
    }
    keys = list(metric_labels.keys())
    ae_vals = [autoencoder_metrics.get(k) or 0.0 for k in keys]
    bl_vals = [baseline_metrics.get(k) or 0.0 for k in keys]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name=model_names[0],
            x=list(metric_labels.values()),
            y=ae_vals,
            marker_color=_PALETTE["autoencoder"],
            text=[f"{v:.3f}" for v in ae_vals],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name=model_names[1],
            x=list(metric_labels.values()),
            y=bl_vals,
            marker_color=_PALETTE["baseline"],
            text=[f"{v:.3f}" for v in bl_vals],
            textposition="outside",
        )
    )
    fig.update_layout(
        barmode="group",
        title=f"{model_names[0]} vs {model_names[1]} — key metrics",
        yaxis=dict(range=[0, 1.15]),
        yaxis_title="Score",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        template="plotly_white",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Explainability figures
# ─────────────────────────────────────────────────────────────────────────────

def feature_reconstruction_error_figure(
    feature_names: list[str],
    reconstruction_errors: np.ndarray,
    row_mse: float,
    top_n: int = 25,
) -> go.Figure:
    """
    Horizontal bar chart of per-feature squared reconstruction error for one row.

    Shows which individual input dimensions the autoencoder failed to reconstruct,
    giving a direct, model-grounded explanation for why the row was flagged.
    """
    idx = np.argsort(reconstruction_errors)[::-1][:top_n]
    names = [feature_names[i] for i in idx]
    errs = reconstruction_errors[idx]
    max_err = errs.max() if errs.max() > 0 else 1.0
    colors = [f"rgba(239,68,68,{0.35 + 0.65 * e / max_err:.2f})" for e in errs]

    fig = go.Figure(
        go.Bar(
            x=errs,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{e:.5f}" for e in errs],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Reconstruction error: %{x:.6f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Per-feature reconstruction error (top {top_n})  —  row MSE: {row_mse:.5f}",
        xaxis_title="Squared reconstruction error",
        yaxis_title="",
        template="plotly_white",
        height=max(350, 35 * top_n + 80),
    )
    return fig


def shap_global_importance_figure(
    mean_abs_shap: dict[str, float],
    top_n: int = 20,
) -> go.Figure:
    """
    Horizontal bar chart of mean |SHAP value| aggregated by original feature.

    ``mean_abs_shap`` maps original feature name → mean absolute SHAP value
    (summed across one-hot groups and averaged across explained rows).
    """
    items = sorted(mean_abs_shap.items(), key=lambda x: x[1])[-top_n:]
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    max_v = max(vals) if vals else 1.0
    colors = [f"rgba(99,102,241,{0.35 + 0.65 * v / max_v:.2f})" for v in vals]

    fig = go.Figure(
        go.Bar(
            x=vals,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.5f}" for v in vals],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Mean |SHAP|: %{x:.6f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Global feature importance — mean |SHAP value|, top {top_n} original features",
        xaxis_title="Mean |SHAP value| (contribution to reconstruction MSE)",
        yaxis_title="",
        template="plotly_white",
        height=max(350, 35 * top_n + 80),
    )
    return fig


def shap_waterfall_figure(
    shap_by_feature: dict[str, float],
    base_value: float,
    actual_mse: float,
    top_n: int = 15,
) -> go.Figure:
    """
    Waterfall-style bar chart of SHAP contributions for one flagged connection.

    Red bars increase MSE above baseline; blue bars decrease it.
    ``shap_by_feature`` maps original feature name → SHAP value.
    """
    items = sorted(shap_by_feature.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    colors = [_PALETTE["malicious"] if v > 0 else _PALETTE["benign"] for v in vals]
    labels = [f"+{v:.5f}" if v > 0 else f"{v:.5f}" for v in vals]

    fig = go.Figure(
        go.Bar(
            x=vals,
            y=names,
            orientation="h",
            marker_color=colors,
            text=labels,
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>SHAP: %{x:.6f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color="#374151", line_width=1.5)
    fig.update_layout(
        title=(
            f"SHAP feature contributions (top {top_n})  —  "
            f"MSE: {actual_mse:.5f}   baseline: {base_value:.5f}"
        ),
        xaxis_title="SHAP value (red = increases anomaly score, blue = decreases)",
        yaxis_title="",
        template="plotly_white",
        height=max(350, 35 * top_n + 80),
    )
    return fig


def bootstrap_ci_figure(ci_results: dict[str, dict[str, Any]]) -> go.Figure:
    """
    Horizontal error-bar chart showing metric point estimates with 95 % bootstrap CIs.

    ``ci_results`` maps metric name → ``{"value": float, "lower": float, "upper": float}``.
    """
    metric_labels = {
        "precision": "Precision",
        "recall": "Recall",
        "f1_score": "F1-score",
        "pr_auc": "PR-AUC",
        "roc_auc": "ROC-AUC",
    }
    names, values, lowers, uppers, errors_minus, errors_plus = [], [], [], [], [], []
    for key, label in metric_labels.items():
        if key not in ci_results:
            continue
        d = ci_results[key]
        v = d.get("value") or 0.0
        lo = d.get("lower") or 0.0
        hi = d.get("upper") or 0.0
        names.append(label)
        values.append(v)
        lowers.append(lo)
        uppers.append(hi)
        errors_minus.append(max(0.0, v - lo))
        errors_plus.append(max(0.0, hi - v))

    fig = go.Figure(
        go.Scatter(
            x=values,
            y=names,
            mode="markers",
            marker=dict(color=_PALETTE["autoencoder"], size=12),
            error_x=dict(
                type="data",
                symmetric=False,
                array=errors_plus,
                arrayminus=errors_minus,
                color=_PALETTE["autoencoder"],
                thickness=2.5,
                width=8,
            ),
            text=[
                f"{v:.4f}  [{lo:.4f}, {hi:.4f}]"
                for v, lo, hi in zip(values, lowers, uppers)
            ],
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Metric point estimates with 95 % bootstrap confidence intervals",
        xaxis_title="Score",
        xaxis=dict(range=[0, 1.05]),
        yaxis_title="",
        template="plotly_white",
    )
    return fig


def live_mse_figure(
    indices: list[int],
    mse_values: list[float],
    flagged: list[bool],
    threshold: float,
    window: int = 300,
) -> go.Figure:
    """Rolling MSE chart for the live simulation page."""
    start = max(0, len(indices) - window)
    x = indices[start:]
    y = mse_values[start:]
    f = flagged[start:]

    benign_x = [xi for xi, fi in zip(x, f) if not fi]
    benign_y = [yi for yi, fi in zip(y, f) if not fi]
    alert_x = [xi for xi, fi in zip(x, f) if fi]
    alert_y = [yi for yi, fi in zip(y, f) if fi]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=benign_x, y=benign_y, mode="markers",
        name="Normal", marker=dict(color=_PALETTE["benign"], size=4, opacity=0.5),
    ))
    fig.add_trace(go.Scatter(
        x=alert_x, y=alert_y, mode="markers",
        name="Anomaly", marker=dict(color=_PALETTE["malicious"], size=7, symbol="x"),
    ))
    fig.add_hline(
        y=threshold, line_dash="dash", line_color=_PALETTE["threshold"],
        annotation_text="Threshold", annotation_position="top right",
    )
    fig.update_layout(
        title=f"Live reconstruction MSE  (last {window} connections)",
        xaxis_title="Connection index",
        yaxis_title="MSE",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        template="plotly_white",
        height=320,
        uirevision="live",
    )
    return fig
