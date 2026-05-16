"""
Multipage Streamlit: centralized export and reporting page.
"""

from __future__ import annotations

import streamlit as st

from src.app_core import (
    render_restore_training_pipeline_ui,
    load_scoring_bundle,
    render_metrics_export_buttons,
    render_sidebar_metrics,
    render_sidebar_placeholder,
    reproducibility_summary_json_bytes,
)
from src.evaluation_helpers import confusion_matrix_long_dataframe, contingency_matrix_dataframe
from src.export_helpers import anomaly_export_dataframe, markdown_report_bytes
from src.ui_helpers import (
    render_classic_page_header,
    render_multipage_navigation_hint,
    setup_page,
)

st.set_page_config(
    page_title="Export tools · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
render_classic_page_header(
    title="Export tools",
    tagline="Extra downloads in one workspace: anomaly slices, metrics, markdown reports, confusion tables, reproducibility JSON.",
    bullets=(
        "Advanced optional page — same scoring engine as the wizard; open after a successful scoring run.",
    ),
)

bundle, err = load_scoring_bundle()
if err is not None or bundle is None:
    st.error(err or "Scoring bundle unavailable.")
    render_restore_training_pipeline_ui()
    render_sidebar_placeholder("Export unavailable", err)
    render_multipage_navigation_hint()
    st.stop()

render_sidebar_metrics(bundle)

st.subheader("Anomaly table export")
top_n = st.number_input("Rows to include (highest MSE first)", min_value=1, max_value=max(1, len(bundle.df)), value=min(200, len(bundle.df)))
only_flagged = st.checkbox("Export flagged rows only", value=True)

table = anomaly_export_dataframe(bundle, top_n=int(top_n), flagged_only=only_flagged)
if not table.empty:
    st.dataframe(table.head(20), use_container_width=True, hide_index=True)
    st.caption("Preview of the export table (first 20 rows).")
    st.download_button(
        "Download anomaly export (CSV)",
        data=table.to_csv(index=False).encode("utf-8"),
        file_name="anomaly_export.csv",
        mime="text/csv",
    )
else:
    st.info("No rows match current export filters.")

st.divider()
st.subheader("Metrics and narrative exports")
render_metrics_export_buttons(
    bundle,
    data_source_label="project_processed_csv",
    key_prefix="export_page_metrics",
)
st.download_button(
    "Download markdown report",
    data=markdown_report_bytes(bundle, source_label="project_processed_csv"),
    file_name="run_report.md",
    mime="text/markdown",
)

st.divider()
st.subheader("Confusion / matrix export")
cm = contingency_matrix_dataframe(bundle)
cm_long = confusion_matrix_long_dataframe(bundle)
st.dataframe(cm, use_container_width=True)
st.download_button(
    "Download confusion counts (CSV)",
    data=cm_long.to_csv(index=False).encode("utf-8"),
    file_name="confusion_counts.csv",
    mime="text/csv",
    help="If labels are unavailable, values may be n/a.",
)

st.divider()
st.subheader("Reproducibility export")
st.download_button(
    "Download reproducibility snapshot (JSON)",
    data=reproducibility_summary_json_bytes(),
    file_name="reproducibility_snapshot.json",
    mime="application/json",
)

render_multipage_navigation_hint()
