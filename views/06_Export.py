"""
Wizard step 6 — download model artefacts, session tables, and scoring outputs in one place.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.app_core import (
    FEATURE_COLUMNS_PATH,
    render_restore_training_pipeline_ui,
    PREPROCESSOR_PATH,
    ScoringBundle,
    THRESHOLD_PATH,
    active_model_path,
    app_debug_mode,
    load_scoring_bundle,
    render_metrics_export_buttons,
    reproducibility_summary_json_bytes,
    SK_WIZARD_UPLOAD_BYTES,
    SK_WIZARD_UPLOAD_NAME,
)
from src.evaluation_helpers import confusion_matrix_long_dataframe
from src.export_helpers import anomaly_export_dataframe, markdown_report_bytes
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)

SK_TEST_BUNDLE = "iot_wizard_test_bundle"


def _toast_download() -> None:
    """Show a best-effort browser download toast."""
    try:
        st.toast("Download started — check your browser’s downloads folder.")
    except Exception:
        pass


st.set_page_config(
    page_title="Export · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=6)

render_wizard_step_header(
    step=6,
    title="Export",
    tagline="Download **trained artefacts**, **session CSV**, and **scoring outputs** for your report or another machine.",
    bullets=(
        "Bundles use the **last wizard test** when present, else **project scoring**.",
        "Use each **Download** button — your browser saves a copy; nothing is deleted here.",
        "Continue to **Use model** for the simplest upload-only check, or use **Export Tools** under Advanced Tools for extra formats.",
    ),
)
render_mini_example(
    "Download `autoencoder.h5` + `preprocessor.pkl` + `threshold.txt` together so a marker can reproduce your run."
)
st.caption("Each group below states which **scoring run** the bytes come from — use the popover if you are unsure.")

with st.popover("Which scoring run is packaged"):
    st.markdown(
        "If you just ran **Test model**, exports prefer that **in-memory** bundle. Otherwise the app falls back to the "
        "same **project CSV** scoring used on the home dashboard — see captions under each download group."
    )

# --- Resolve scoring bundle: last wizard test, else project scoring ---
bundle: ScoringBundle | None = None
bundle_source = "none"
raw_test = st.session_state.get(SK_TEST_BUNDLE)
if isinstance(raw_test, ScoringBundle):
    bundle = raw_test
    bundle_source = "wizard_test_run"
else:
    b2, err2 = load_scoring_bundle()
    if b2 is not None and not err2:
        bundle = b2
        bundle_source = "project_scoring"

if bundle is None:
    st.warning(
        "No scoring results are available yet. Run **Test model** or open **Detection results** once the project CSV scores successfully.",
    )
    render_restore_training_pipeline_ui()

st.divider()
st.subheader("1 · Model files (trained)")
st.caption("These are the same files under `models/` that the app loads. Your browser downloads a **copy**; nothing is deleted here.")

mp = active_model_path()
if mp.is_file():
    st.download_button(
        label=f"Download neural network ({mp.suffix}) — `{mp.name}`",
        data=mp.read_bytes(),
        file_name=mp.name,
        mime="application/octet-stream",
        key="export_dl_model_keras",
        on_click=_toast_download,
        help="Keras saved model used for reconstruction scoring.",
    )
else:
    st.caption("No model file found at the active path — use **Select model** or run **`train.py`**.")

if PREPROCESSOR_PATH.is_file():
    st.download_button(
        label="Download preprocessor (`.pkl`) — `preprocessor.pkl`",
        data=PREPROCESSOR_PATH.read_bytes(),
        file_name="preprocessor.pkl",
        mime="application/octet-stream",
        key="export_dl_preprocessor",
        on_click=_toast_download,
        help="Column scaling and encoding from training.",
    )
else:
    st.caption("`preprocessor.pkl` not found.")

if THRESHOLD_PATH.is_file():
    st.download_button(
        label="Download threshold (`.txt`) — `threshold.txt`",
        data=THRESHOLD_PATH.read_bytes(),
        file_name="threshold.txt",
        mime="text/plain",
        key="export_dl_threshold",
        on_click=_toast_download,
        help="MSE cut-off saved from validation (session override does not change this file).",
    )
else:
    st.caption("`threshold.txt` not found.")

if FEATURE_COLUMNS_PATH.is_file():
    st.download_button(
        label="Download feature list (`.pkl`) — `feature_columns.pkl`",
        data=FEATURE_COLUMNS_PATH.read_bytes(),
        file_name="feature_columns.pkl",
        mime="application/octet-stream",
        key="export_dl_feature_cols",
        on_click=_toast_download,
        help="Numeric and categorical field names used with the preprocessor.",
    )

st.divider()
st.subheader("2 · Your session table (repaired / uploaded)")
raw_sess = st.session_state.get(SK_WIZARD_UPLOAD_BYTES)
if raw_sess:
    fname = st.session_state.get(SK_WIZARD_UPLOAD_NAME) or "session_table.csv"
    if not str(fname).lower().endswith(".csv"):
        fname = f"{Path(fname).stem}.csv"
    st.download_button(
        label=f"Download session CSV — `{fname}`",
        data=raw_sess if isinstance(raw_sess, (bytes, bytearray)) else bytes(raw_sess),
        file_name=str(fname),
        mime="text/csv",
        key="export_dl_session_csv",
        on_click=_toast_download,
        help="The in-memory table from Select / Repair / scoring hand-off (UTF-8 CSV).",
    )
    st.success("Session table is ready to download.")
else:
    st.info("No session CSV in memory — go through **Select data** (and **Repair data** if you use it) first.")

st.divider()
st.subheader("3 · Results & anomaly outputs")
if bundle is not None:
    if bundle_source == "wizard_test_run":
        st.caption("These downloads use your **last Test model** run (wizard).")
    else:
        st.caption("These downloads use the **project CSV** scoring pass (same as the home dashboard when it loads).")
    src_lbl = "wizard_test_run" if bundle_source == "wizard_test_run" else "project_processed_csv"
    top_n = st.number_input(
        "Rows in anomaly CSV (highest error first)",
        min_value=1,
        max_value=max(1, len(bundle.df)),
        value=min(200, len(bundle.df)),
        key="export_wizard_top_n",
    )
    only_flagged = st.checkbox("Only rows flagged as unusual", value=True, key="export_wizard_flagged_only")

    table = anomaly_export_dataframe(bundle, top_n=int(top_n), flagged_only=only_flagged)
    if not table.empty:
        st.dataframe(table.head(12), use_container_width=True, hide_index=True)
        st.caption("Preview (first 12 rows).")
        st.download_button(
            label="Download anomaly table (`.csv`) — scores & flags",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name="anomaly_results_export.csv",
            mime="text/csv",
            key="export_dl_anomaly_csv",
            on_click=_toast_download,
        )
        st.success("Anomaly export is ready.")
    else:
        st.info("No rows match the current filters.")

    st.markdown("**Metrics** (single-row summaries)")
    render_metrics_export_buttons(bundle, data_source_label=src_lbl, key_prefix="wizard_export_metrics")

    st.download_button(
        label="Download report (`.md`) — short narrative",
        data=markdown_report_bytes(bundle, source_label=src_lbl),
        file_name="run_report.md",
        mime="text/markdown",
        key="export_dl_md_report",
        on_click=_toast_download,
    )

    cm_long = confusion_matrix_long_dataframe(bundle)
    st.download_button(
        label="Download confusion-style counts (`.csv`)",
        data=cm_long.to_csv(index=False).encode("utf-8"),
        file_name="confusion_counts.csv",
        mime="text/csv",
        key="export_dl_confusion",
        on_click=_toast_download,
        help="Uses labels when present; otherwise cells may show n/a.",
    )

    st.download_button(
        label="Download reproducibility snapshot (`.json`)",
        data=reproducibility_summary_json_bytes(),
        file_name="reproducibility_snapshot.json",
        mime="application/json",
        key="export_dl_repro_json",
        on_click=_toast_download,
    )
else:
    st.caption("Run a successful test or scoring pass to unlock anomaly CSV and metrics here.")

st.divider()
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.page_link("views/05_Test_Model.py", label="← Back to Test model")
with c2:
    st.page_link("views/07_Use_Model.py", label="Simple use (upload) →")
with c3:
    st.page_link("views/17_Export_tools.py", label="More export formats (advanced) →")
with c4:
    st.page_link("views/11_Detection_Results.py", label="Detection table (advanced) →")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1`.")

st.divider()
render_multipage_navigation_hint()
