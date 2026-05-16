"""
Multipage Streamlit: advanced analysis — visualisations, test-set evaluation, and baseline comparison.

Panels
------
0. Bootstrap confidence intervals (95 % CIs on all key metrics)
1. MSE score distribution (benign vs malicious, with threshold line)
2. Precision–Recall curve (with PR-AUC)
3. ROC curve (with ROC-AUC)
4. Threshold sensitivity sweep (precision / recall / F1 across percentiles)
5. Confusion matrix heatmap
6. Per-attack-type detection breakdown (Zeek detailed-label)
7. Autoencoder vs Isolation Forest baseline comparison
8. Test-set evaluation report (from models/test_evaluation.json if available)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.app_core import (
    render_restore_training_pipeline_ui,
    load_scoring_bundle,
    render_sidebar_metrics,
    render_sidebar_placeholder,
)
from src.metrics import (
    binary_labels,
    bootstrap_all_metrics,
    classification_metrics,
    per_attack_type_metrics,
    ranking_metrics,
    threshold_sweep,
)
from src.plots import (
    baseline_comparison_figure,
    bootstrap_ci_figure,
    confusion_heatmap_figure,
    mse_distribution_figure,
    per_attack_breakdown_figure,
    pr_curve_figure,
    roc_curve_figure,
    threshold_sweep_figure,
)
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page

st.set_page_config(
    page_title="Advanced Analysis · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
_BASELINE_PATH = MODELS_DIR / "baseline_metrics.json"
_TEST_EVAL_PATH = MODELS_DIR / "test_evaluation.json"
_SWEEP_PATH = MODELS_DIR / "threshold_sweep.json"

render_classic_page_header(
    title="Advanced analysis",
    tagline="MSE distribution, PR and ROC curves, threshold sensitivity, per-attack breakdown, baseline comparison, and test-set panels when artefacts exist.",
    bullets=(
        "Charts use the same scoring bundle as the Dashboard.",
        "Run `python evaluate.py` to populate test-set JSON and baseline files under `models/`.",
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# Load scoring bundle
# ─────────────────────────────────────────────────────────────────────────────
bundle, err = load_scoring_bundle()
if err or bundle is None:
    st.error(err or "Scoring bundle unavailable.")
    render_restore_training_pipeline_ui()
    render_sidebar_placeholder("Advanced analysis unavailable", err)
    render_multipage_navigation_hint()
    st.stop()

render_sidebar_metrics(bundle)

has_labels = bundle.labels is not None and len(bundle.labels) == len(bundle.df)
scores = bundle.errors
flagged = bundle.flagged

if has_labels:
    labels = bundle.labels
    assert labels is not None
    y_true = binary_labels(labels)
    y_pred = flagged.astype(np.int32)
else:
    labels = None
    y_true = None
    y_pred = None

# ─────────────────────────────────────────────────────────────────────────────
# 0. Bootstrap confidence intervals
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("0 · Bootstrap confidence intervals (95 %)")
st.caption(
    "Point estimates alone don't tell you how stable a metric is. "
    "Bootstrap resampling (1 000 iterations) quantifies the uncertainty in each metric "
    "for the rows scored in this session — a hallmark of rigorous ML evaluation."
)

if y_true is not None and y_pred is not None and int(y_true.sum()) > 0:
    run_bootstrap = st.button("Compute bootstrap CIs (1 000 iterations, ~10 s)", type="primary")
    if "bootstrap_ci_results" not in st.session_state:
        st.session_state["bootstrap_ci_results"] = None

    if run_bootstrap:
        with st.spinner("Bootstrapping…"):
            ci_results = bootstrap_all_metrics(y_true, y_pred, scores, n_bootstrap=1000)
        st.session_state["bootstrap_ci_results"] = ci_results

    if st.session_state.get("bootstrap_ci_results"):
        ci_results = st.session_state["bootstrap_ci_results"]
        st.plotly_chart(bootstrap_ci_figure(ci_results), use_container_width=True)

        ci_table = []
        for m, label in [("precision", "Precision"), ("recall", "Recall"),
                         ("f1_score", "F1-score"), ("pr_auc", "PR-AUC"), ("roc_auc", "ROC-AUC")]:
            d = ci_results.get(m, {})
            v = d.get("value")
            lo, hi = d.get("lower"), d.get("upper")
            ci_table.append({
                "Metric": label,
                "Estimate": "n/a" if v is None else f"{v:.4f}",
                "95 % CI lower": "n/a" if lo is None else f"{lo:.4f}",
                "95 % CI upper": "n/a" if hi is None else f"{hi:.4f}",
                "Width": "n/a" if (hi is None or lo is None) else f"{hi - lo:.4f}",
            })
        st.dataframe(pd.DataFrame(ci_table), use_container_width=True, hide_index=True)
        st.caption(
            "Narrow CI width → stable metric. Wide width → metric is sensitive to which "
            "connections happen to be in the scored set (common with highly imbalanced data)."
        )
        st.download_button(
            "Download CI table (CSV)",
            data=pd.DataFrame(ci_table).to_csv(index=False).encode("utf-8"),
            file_name="bootstrap_confidence_intervals.csv",
            mime="text/csv",
        )
    else:
        st.info("Click the button above to run bootstrap CI estimation.")
else:
    st.info("Bootstrap CIs require labelled data with both benign and malicious rows.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 1. MSE score distribution
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("1 · Reconstruction MSE distribution")
st.caption(
    "Benign connections (blue) should cluster at low MSE; malicious connections (red) "
    "produce higher reconstruction error because the autoencoder was never trained on them. "
    "The dashed line is the saved threshold — rows to its right are flagged as anomalies."
)
st.plotly_chart(
    mse_distribution_figure(scores, labels, bundle.threshold),
    use_container_width=True,
)

if not has_labels:
    st.info(
        "Labels (`label` column) are not available in this scoring run. "
        "The distribution is shown as a single series.",
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 2 & 3. PR curve and ROC curve (side by side)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("2 & 3 · Precision–Recall and ROC curves")
st.caption(
    "Both curves use the **per-row MSE as a continuous ranking score** — "
    "they are not tied to the fixed threshold. "
    "PR-AUC is the primary metric for imbalanced datasets; "
    "ROC-AUC provides a complementary view of separability."
)

if y_true is not None and int(y_true.sum()) > 0 and int((1 - y_true).sum()) > 0:
    col_pr, col_roc = st.columns(2)
    with col_pr:
        st.plotly_chart(pr_curve_figure(y_true, scores), use_container_width=True)
    with col_roc:
        st.plotly_chart(roc_curve_figure(y_true, scores), use_container_width=True)

    rm = ranking_metrics(y_true, scores)
    m1, m2 = st.columns(2)
    m1.metric(
        "PR-AUC",
        f"{rm['pr_auc']:.4f}" if rm["pr_auc"] else "n/a",
        help="Average precision — area under the PR curve. "
             "Higher is better; random baseline equals class prevalence.",
    )
    m2.metric(
        "ROC-AUC",
        f"{rm['roc_auc']:.4f}" if rm["roc_auc"] else "n/a",
        help="Area under the ROC curve. "
             "0.5 = random classifier, 1.0 = perfect separation.",
    )
else:
    st.warning(
        "PR / ROC curves require both malicious and benign labels in the scoring run. "
        "Labels are unavailable or only one class is present.",
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 4. Threshold sensitivity sweep
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("4 · Threshold sensitivity sweep")
st.caption(
    "Moving the detection threshold changes the precision–recall trade-off. "
    "The chart below sweeps the threshold from the 90th to 99.9th percentile of "
    "**benign reconstruction errors** in this scoring run and shows how "
    "precision, recall and F1 respond. "
    "The saved threshold (99th percentile, benign validation set) is one point on this curve."
)

if y_true is not None and int(y_true.sum()) > 0:
    # Use benign rows in the current scoring run as the reference distribution
    benign_mask = (y_true == 0)
    benign_scores = scores[benign_mask]
    sweep_df = threshold_sweep(y_true, scores, benign_scores=benign_scores)
    st.plotly_chart(threshold_sweep_figure(sweep_df), use_container_width=True)

    with st.expander("Threshold sweep — full table", expanded=False):
        display_cols = ["percentile", "threshold", "precision", "recall", "f1_score", "tp", "fp", "fn", "tn"]
        st.dataframe(
            sweep_df[display_cols].style.format(
                {"threshold": "{:.6f}", "precision": "{:.4f}", "recall": "{:.4f}", "f1_score": "{:.4f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    # Also load the pre-saved sweep from evaluate.py if it exists (test-set version)
    if _SWEEP_PATH.is_file():
        try:
            saved_sweep = pd.DataFrame(json.loads(_SWEEP_PATH.read_text(encoding="utf-8")))
            with st.expander("Test-set threshold sweep (from evaluate.py)", expanded=False):
                st.caption(
                    "This sweep was computed on the held-out **test set** by `evaluate.py`, "
                    "using benign validation errors as the percentile reference — "
                    "a stricter, leak-free evaluation."
                )
                st.dataframe(
                    saved_sweep[display_cols].style.format(
                        {"threshold": "{:.6f}", "precision": "{:.4f}", "recall": "{:.4f}", "f1_score": "{:.4f}"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        except (ValueError, KeyError, json.JSONDecodeError):
            pass
else:
    st.info("Threshold sweep requires labelled data.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 5. Confusion matrix heatmap
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("5 · Confusion matrix heatmap")
st.caption(
    "Visual representation of TP / FP / TN / FN at the **fixed saved threshold**. "
    "Large FN count means the model misses attacks; "
    "large FP count means benign traffic is over-flagged."
)

if (
    has_labels
    and bundle.tp is not None
    and bundle.fp is not None
    and bundle.tn is not None
    and bundle.fn is not None
):
    st.plotly_chart(
        confusion_heatmap_figure(bundle.tp, bundle.fp, bundle.tn, bundle.fn),
        use_container_width=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TP", f"{bundle.tp:,}", help="Correctly flagged malicious connections")
    c2.metric("FP", f"{bundle.fp:,}", help="Benign connections incorrectly flagged")
    c3.metric("FN", f"{bundle.fn:,}", help="Malicious connections missed at this threshold")
    c4.metric("TN", f"{bundle.tn:,}", help="Correctly passed benign connections")
else:
    st.info("Confusion matrix requires labelled data.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 6. Per-attack-type breakdown
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("6 · Detection rate by attack type")
st.caption(
    "Each bar shows the fraction of connections of that attack type (Zeek `detailed-label`) "
    "that were flagged at the fixed threshold. "
    "Low detection rates highlight attack families the model struggles with — "
    "a useful talking point for model limitations."
)

if has_labels and "detailed-label" in bundle.df.columns:
    detailed = bundle.df["detailed-label"]
    breakdown_df = per_attack_type_metrics(detailed, flagged.astype(np.int32), scores)
    if not breakdown_df.empty:
        st.plotly_chart(per_attack_breakdown_figure(breakdown_df), use_container_width=True)
        with st.expander("Attack breakdown — full table", expanded=False):
            st.dataframe(
                breakdown_df.style.format(
                    {"detection_rate": "{:.2%}", "avg_mse": "{:.5f}", "median_mse": "{:.5f}"}
                ),
                use_container_width=True,
                hide_index=True,
            )
        st.download_button(
            "Download attack breakdown (CSV)",
            data=breakdown_df.to_csv(index=False).encode("utf-8"),
            file_name="attack_type_breakdown.csv",
            mime="text/csv",
        )
    else:
        st.info("No attack types found in the current scoring run.")
else:
    st.info(
        "Per-attack breakdown requires both the `label` and `detailed-label` columns.",
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 7. Baseline comparison
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("7 · Autoencoder vs Isolation Forest baseline")
st.caption(
    "Run `python evaluate.py` once to generate `models/baseline_metrics.json`. "
    "The Isolation Forest is trained on the same benign training rows as the autoencoder "
    "and evaluated on the held-out test set — a fair apples-to-apples comparison."
)

if _BASELINE_PATH.is_file():
    try:
        baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        baseline = None

    if baseline and y_true is not None:
        rm = ranking_metrics(y_true, scores)
        autoencoder_metrics = {
            "precision": bundle.tp / (bundle.tp + bundle.fp) if (bundle.tp and bundle.fp is not None and (bundle.tp + bundle.fp) > 0) else None,
            "recall": bundle.tp / (bundle.tp + bundle.fn) if (bundle.tp and bundle.fn is not None and (bundle.tp + bundle.fn) > 0) else None,
            "f1_score": None,
            "pr_auc": rm.get("pr_auc"),
            "roc_auc": rm.get("roc_auc"),
        }
        if autoencoder_metrics["precision"] and autoencoder_metrics["recall"]:
            p = autoencoder_metrics["precision"]
            r = autoencoder_metrics["recall"]
            autoencoder_metrics["f1_score"] = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

        st.plotly_chart(
            baseline_comparison_figure(autoencoder_metrics, baseline),
            use_container_width=True,
        )

        col_ae, col_if = st.columns(2)
        with col_ae:
            st.markdown("**Autoencoder (current session)**")
            for k, label in [("precision", "Precision"), ("recall", "Recall"), ("f1_score", "F1"), ("pr_auc", "PR-AUC"), ("roc_auc", "ROC-AUC")]:
                v = autoencoder_metrics.get(k)
                st.metric(label, "n/a" if v is None else f"{v:.4f}")
        with col_if:
            st.markdown("**Isolation Forest (test set)**")
            for k, label in [("precision", "Precision"), ("recall", "Recall"), ("f1_score", "F1"), ("pr_auc", "PR-AUC"), ("roc_auc", "ROC-AUC")]:
                v = baseline.get(k)
                st.metric(label, "n/a" if v is None else f"{v:.4f}")
    elif baseline:
        st.info("Baseline metrics loaded. Labels required to compute autoencoder metrics for comparison.")
        st.json(baseline)
    else:
        st.warning("Could not parse `models/baseline_metrics.json`. Run `python evaluate.py` again.")
else:
    st.info(
        "No baseline found. Run `python evaluate.py` to train an Isolation Forest baseline "
        "and generate `models/baseline_metrics.json`.",
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# 8. Test-set evaluation report
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("8 · Test-set evaluation report")
st.caption(
    "The held-out test set (15% of the dataset) was **never used during training or threshold calibration**. "
    "Metrics here are the gold-standard evaluation numbers for your report. "
    "Generated by `python evaluate.py`."
)

if _TEST_EVAL_PATH.is_file():
    try:
        test_eval = json.loads(_TEST_EVAL_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        test_eval = None

    if test_eval:
        ae_report = test_eval.get("autoencoder", {})
        if_report = test_eval.get("isolation_forest", {})

        metrics_rows = []
        for k, label in [
            ("precision", "Precision"),
            ("recall", "Recall"),
            ("f1_score", "F1-score"),
            ("pr_auc", "PR-AUC"),
            ("roc_auc", "ROC-AUC"),
        ]:
            metrics_rows.append(
                {
                    "Metric": label,
                    "Autoencoder (test set)": ae_report.get(k),
                    "Isolation Forest (test set)": if_report.get(k),
                }
            )

        report_df = pd.DataFrame(metrics_rows)
        st.dataframe(
            report_df.style.format(
                {
                    "Autoencoder (test set)": lambda v: "n/a" if v is None else f"{v:.4f}",
                    "Isolation Forest (test set)": lambda v: "n/a" if v is None else f"{v:.4f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        confusion_cols = ["tp", "fp", "tn", "fn"]
        if all(k in ae_report for k in confusion_cols):
            st.markdown("**Confusion counts (autoencoder, test set)**")
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("TP", f"{ae_report['tp']:,}")
            cc2.metric("FP", f"{ae_report['fp']:,}")
            cc3.metric("TN", f"{ae_report['tn']:,}")
            cc4.metric("FN", f"{ae_report['fn']:,}")

        st.download_button(
            "Download test evaluation (JSON)",
            data=_TEST_EVAL_PATH.read_bytes(),
            file_name="test_evaluation.json",
            mime="application/json",
        )

        with st.expander("Full test evaluation JSON", expanded=False):
            st.json(test_eval)
    else:
        st.warning("Could not parse `models/test_evaluation.json`. Re-run `python evaluate.py`.")
else:
    st.info(
        "Run `python evaluate.py` to generate `models/test_evaluation.json` "
        "with full held-out test-set metrics.",
    )

render_multipage_navigation_hint()
