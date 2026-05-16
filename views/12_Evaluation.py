"""Dedicated evaluation and evidence page."""

from __future__ import annotations

import streamlit as st

from src.app_core import (
    load_scoring_bundle,
    render_restore_training_pipeline_ui,
    render_sidebar_metrics,
    render_sidebar_placeholder,
)
from src.evaluation_helpers import (
    baseline_metrics_table,
    bundle_has_labels,
    confusion_matrix_long_dataframe,
    contingency_matrix_dataframe,
    false_positive_negative_analysis,
    metrics_dataframe,
)
from src.iot_streamlit import classification_report_markdown, render_metrics_export_buttons
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page

st.set_page_config(
    page_title="Evaluation - IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
render_classic_page_header(
    title="Evaluation",
    tagline="Precision, recall, F1, PR-AUC, confusion-style views, baseline context, and FP/FN analysis for the current scoring run.",
    bullets=("Requires a loaded scoring bundle (project CSV or upload path on Detection).",),
)
st.caption("Open after a successful score - numbers always refer to **this session's** table, not a separate benchmark file.")

bundle, err = load_scoring_bundle()
if err is not None or bundle is None:
    st.error(err or "Scoring bundle unavailable.")
    render_restore_training_pipeline_ui()
    render_sidebar_placeholder("Evaluation unavailable", err)
    render_multipage_navigation_hint()
    st.stop()

render_sidebar_metrics(bundle)

metrics_tab, confusion_tab, errors_tab, baseline_tab, exports_tab = st.tabs(
    ("Metrics", "Confusion", "FP/FN", "Baseline", "Exports")
)

with metrics_tab:
    st.subheader("Autoencoder metrics")
    metrics_df = metrics_dataframe(bundle)
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
    if not bundle_has_labels(bundle):
        st.warning("Labels are unavailable in this run, so supervised metrics are shown as unavailable.")

with confusion_tab:
    st.subheader("Confusion matrix")
    st.dataframe(contingency_matrix_dataframe(bundle), use_container_width=True)
    if bundle_has_labels(bundle):
        cm_long = confusion_matrix_long_dataframe(bundle).copy()
        cm_long["cell"] = cm_long["actual"] + " | " + cm_long["predicted"]
        st.bar_chart(cm_long.set_index("cell")["count"])
    else:
        st.caption("Confusion chart requires labels.")

with errors_tab:
    st.subheader("False positive / false negative analysis")
    err_counts = false_positive_negative_analysis(bundle)
    c1, c2 = st.columns(2)
    c1.metric("False positives", "n/a" if err_counts["false_positives"] is None else f"{err_counts['false_positives']:,}")
    c2.metric("False negatives", "n/a" if err_counts["false_negatives"] is None else f"{err_counts['false_negatives']:,}")
    st.caption("Useful for discussing operational trade-offs at the current threshold.")

with baseline_tab:
    st.subheader("Baseline vs autoencoder")
    baseline_df, baseline_path = baseline_metrics_table()
    if baseline_df is None:
        st.caption("No parseable baseline metrics artefact found. Add `models/baseline_metrics.json` for side-by-side comparison.")
    else:
        auto_df = metrics_dataframe(bundle).rename(columns={"value": "autoencoder_value"})
        merged = auto_df.merge(baseline_df, how="left", on="metric")
        st.dataframe(merged, use_container_width=True, hide_index=True)
        st.caption(f"Baseline source: `{baseline_path}`")

with exports_tab:
    st.subheader("Evaluation exports")
    render_metrics_export_buttons(bundle, data_source_label="project_processed_csv", key_prefix="evaluation_page_metrics")
    st.download_button(
        "Download evaluation report (Markdown)",
        data=classification_report_markdown(bundle, data_source_label="project_processed_csv").encode("utf-8"),
        file_name="evaluation_report.md",
        mime="text/markdown",
    )

render_multipage_navigation_hint()
