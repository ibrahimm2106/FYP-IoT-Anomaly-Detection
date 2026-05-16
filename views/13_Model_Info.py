"""
Multipage Streamlit: model, preprocessing, split, seed, threshold, limitations.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_core import (
    CAPTION_EVALUATION_SCOPE_SHORT,
    DATA_PATH,
    FEATURE_COLUMNS_PATH,
    MARKDOWN_EVALUATION_SCOPE,
    MODEL_PATH,
    PREPROCESSOR_PATH,
    THRESHOLD_PATH,
    artifact_path_line,
    check_environment,
    load_feature_column_meta,
    load_model,
    load_scoring_bundle,
    load_threshold,
    model_summary_text,
    reproducibility_summary_dict,
    reproducibility_summary_json_bytes,
    render_sidebar_metrics,
    render_sidebar_placeholder,
    stratified_split_counts,
    try_read_processed_csv,
)
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page

st.set_page_config(
    page_title="Model Information · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
render_classic_page_header(
    title="Model and training",
    tagline="Artefact paths, preprocessing notes, stratified split, threshold definition, optional Keras summary, and evaluation scope.",
    bullets=("Static details remain available even when live scoring fails — fix paths to refresh KPIs.",),
)
st.caption(CAPTION_EVALUATION_SCOPE_SHORT)
with st.expander("Evaluation scope (detail)", expanded=False):
    st.markdown(MARKDOWN_EVALUATION_SCOPE)

env_err = check_environment()
bundle, score_err = load_scoring_bundle()
if env_err:
    st.error(env_err)
    render_sidebar_placeholder("Artefacts missing", env_err)
elif score_err or bundle is None:
    st.warning(score_err or "Scoring did not complete. Static configuration details are still available.")
    render_sidebar_placeholder("Live scoring unavailable", score_err)
else:
    render_sidebar_metrics(bundle)

threshold = bundle.threshold if bundle is not None else None
if threshold is None:
    try:
        threshold = load_threshold()
    except (OSError, ValueError, TypeError):
        threshold = None

input_dim: int | None = None
if bundle is not None and bundle.transformed_dim > 0:
    input_dim = bundle.transformed_dim
elif MODEL_PATH.is_file():
    try:
        m = load_model()
        shp = m.input_shape
        if shp and shp[-1] is not None:
            input_dim = int(shp[-1])
    except (OSError, ValueError, RuntimeError):
        input_dim = None

st.subheader("Model configuration")
c1, c2, c3 = st.columns(3)
c1.metric("Architecture", "Dense autoencoder")
c2.metric("Input dimension", "—" if input_dim is None else f"{input_dim:,}")
c3.metric("Threshold (MSE)", "—" if threshold is None else f"{threshold:.6f}")

st.divider()
st.subheader("Preprocessing settings")
meta = load_feature_column_meta()
if meta:
    st.dataframe(
        pd.DataFrame(
            [
                {"setting": "Numeric feature count", "value": len(meta.get("numeric") or [])},
                {"setting": "Categorical feature count", "value": len(meta.get("categorical") or [])},
                {"setting": "Numeric scaler", "value": "StandardScaler"},
                {"setting": "Categorical encoder", "value": "OneHotEncoder(handle_unknown='ignore')"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption(f"`{FEATURE_COLUMNS_PATH.as_posix()}` not found. Re-run training to recover feature metadata.")

st.divider()
st.subheader("Split settings and seed")
split_info = None
if DATA_PATH.is_file():
    try:
        split_info = stratified_split_counts(DATA_PATH.stat().st_mtime)
    except (OSError, ValueError, KeyError, RuntimeError):
        split_info = None
if split_info:
    st.dataframe(
        pd.DataFrame(
            [
                {"split": "Train", "rows": split_info["n_train"]},
                {"split": "Validation", "rows": split_info["n_val"]},
                {"split": "Test", "rows": split_info["n_test"]},
                {"setting": "random_state", "rows": 42},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("Split counts unavailable; expected design is stratified 70/15/15 with random_state=42.")

st.divider()
st.subheader("Threshold method")
st.markdown(
    "Threshold method: **99th percentile** of benign validation reconstruction MSE, saved in `threshold.txt` and used "
    "for fixed-threshold anomaly flags."
)

st.divider()
st.subheader("Run configuration and artefact paths")
paths_df = pd.DataFrame(
    [
        {"artefact": "Model", "path": artifact_path_line(MODEL_PATH)},
        {"artefact": "Preprocessor", "path": artifact_path_line(PREPROCESSOR_PATH)},
        {"artefact": "Threshold", "path": artifact_path_line(THRESHOLD_PATH)},
        {"artefact": "Feature metadata", "path": artifact_path_line(FEATURE_COLUMNS_PATH)},
        {"artefact": "Processed data", "path": artifact_path_line(DATA_PATH)},
    ]
)
st.dataframe(paths_df, use_container_width=True, hide_index=True)
st.dataframe(
    pd.DataFrame([{"item": k, "value": v} for k, v in reproducibility_summary_dict().items()]),
    use_container_width=True,
    hide_index=True,
)
st.download_button(
    "Download run configuration (JSON)",
    data=reproducibility_summary_json_bytes(),
    file_name="run_configuration.json",
    mime="application/json",
)

with st.expander("Model summary (Keras text)", expanded=False):
    st.code(model_summary_text(), language=None)

with st.expander("Limitations", expanded=False):
    st.markdown(
        "- Unsupervised reconstruction error is not a probability.\n"
        "- Metrics are dataset and threshold dependent.\n"
        "- Batch scoring only; not live packet capture."
    )

render_multipage_navigation_hint()
