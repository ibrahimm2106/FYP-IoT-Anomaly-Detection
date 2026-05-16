"""
Multipage Streamlit: explainability — why was this connection flagged?

Two complementary lenses
------------------------
1. Per-feature reconstruction error (always instant):
   For any flagged row, shows which input dimensions the autoencoder
   reconstructed poorly — the direct, model-grounded explanation.

2. SHAP feature attribution (button-triggered, ~30 s):
   Uses SHAP GradientExplainer on an MSE-output wrapper of the autoencoder.
   SHAP values are aggregated from the 569-dim transformed space back to the
   ~13 original Zeek features for clean interpretation.
   Global importance (mean |SHAP| across top flagged rows) + per-row waterfall.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.app_core import (
    render_restore_training_pipeline_ui,
    load_model,
    load_scoring_bundle,
    render_sidebar_metrics,
    render_sidebar_placeholder,
)
from src.plots import (
    feature_reconstruction_error_figure,
    shap_global_importance_figure,
    shap_waterfall_figure,
)
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page

st.set_page_config(
    page_title="Explainability · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREPROCESSOR_PATH = PROJECT_ROOT / "models" / "preprocessor.pkl"

render_classic_page_header(
    title="Explainability",
    tagline="Per-feature reconstruction error for instant, model-grounded explanations; optional SHAP attribution (~30 s) when configured.",
    bullets=("Requires flagged rows in the current scoring run.",),
)

# ─────────────────────────────────────────────────────────────────────────────
# Load bundle
# ─────────────────────────────────────────────────────────────────────────────
bundle, err = load_scoring_bundle()
if err or bundle is None:
    st.error(err or "Scoring bundle unavailable.")
    render_restore_training_pipeline_ui()
    render_sidebar_placeholder("Explainability unavailable", err)
    render_multipage_navigation_hint()
    st.stop()

render_sidebar_metrics(bundle)

has_labels = bundle.labels is not None and len(bundle.labels) == len(bundle.df)
flagged_mask = bundle.flagged
n_flagged = int(flagged_mask.sum())

if n_flagged == 0:
    st.warning("No flagged connections in this scoring run — nothing to explain.")
    render_multipage_navigation_hint()
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: load preprocessor (cached within session)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _load_preprocessor() -> object:
    """Load the fitted preprocessor for explainability views."""
    with PREPROCESSOR_PATH.open("rb") as fh:
        return pickle.load(fh)


def _get_feature_names(preprocessor: object) -> list[str]:
    """Cleaned feature names: strip transformer prefix, make readable."""
    raw = preprocessor.get_feature_names_out()
    cleaned = []
    for name in raw:
        parts = name.split("__", 1)
        cleaned.append(parts[1] if len(parts) == 2 else name)
    return cleaned


def _build_group_mapping(preprocessor: object) -> dict[str, list[int]]:
    """Map each original feature → list of its transformed feature indices."""
    mapping: dict[str, list[int]] = {}
    idx = 0
    for t_name, t_obj, features in preprocessor.transformers_:
        if t_name == "remainder":
            continue
        if t_name == "num":
            for feat in features:
                mapping[feat] = [idx]
                idx += 1
        elif t_name == "cat":
            for i, feat in enumerate(features):
                n_cats = len(t_obj.categories_[i])
                mapping[feat] = list(range(idx, idx + n_cats))
                idx += n_cats
    return mapping


def _transform_bundle_features(df: pd.DataFrame, preprocessor: object) -> np.ndarray:
    """Drop non-feature columns and transform with the saved preprocessor."""
    drop = [c for c in ("label", "detailed-label", "uid", "id.orig_h", "id.resp_h") if c in df.columns]
    return preprocessor.transform(df.drop(columns=drop, errors="ignore"))


# ─────────────────────────────────────────────────────────────────────────────
# Prepare data for analysis
# ─────────────────────────────────────────────────────────────────────────────
preprocessor = _load_preprocessor()
model = load_model()

feature_names = _get_feature_names(preprocessor)
group_mapping = _build_group_mapping(preprocessor)

# Transform all rows once (cached in session state)
if "X_transformed" not in st.session_state:
    with st.spinner("Transforming features…"):
        st.session_state["X_transformed"] = _transform_bundle_features(bundle.df, preprocessor)

X_all: np.ndarray = st.session_state["X_transformed"]

# Flagged rows sorted by MSE descending
flagged_indices = np.where(flagged_mask)[0]
flagged_sorted = flagged_indices[np.argsort(bundle.errors[flagged_indices])[::-1]]

# ─────────────────────────────────────────────────────────────────────────────
# Section 1 · Per-feature reconstruction error
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("1 · Per-feature reconstruction error")
st.markdown(
    "Select any flagged connection below. "
    "The chart shows which input features the autoencoder **failed to reconstruct**, "
    "measured as the squared error per feature. "
    "Features with high values are the primary drivers of the anomaly flag — "
    "they look unusual relative to the benign traffic the model was trained on."
)

top_n_rows = min(200, n_flagged)
row_options = {
    f"#{i + 1}  MSE={bundle.errors[idx]:.5f}"
    + (f"  [{bundle.labels.iloc[idx]}]" if has_labels else "")
    + (f"  [{bundle.df['detailed-label'].iloc[idx]}]" if "detailed-label" in bundle.df.columns else "")
    : int(idx)
    for i, idx in enumerate(flagged_sorted[:top_n_rows])
}

col_sel, col_top = st.columns([3, 1])
selected_label = col_sel.selectbox(
    f"Select a flagged connection (showing top {top_n_rows} by MSE)",
    options=list(row_options.keys()),
    key="explain_row_select",
)
top_k = col_top.slider("Features shown", min_value=10, max_value=40, value=20, step=5)

selected_idx = row_options[selected_label]
X_row = X_all[[selected_idx]]
X_hat = model.predict(X_row, verbose=0, batch_size=1)
feat_errors = np.square(X_row - X_hat)[0]

st.plotly_chart(
    feature_reconstruction_error_figure(feature_names, feat_errors, bundle.errors[selected_idx], top_n=top_k),
    use_container_width=True,
)

# Show key feature values for this row
with st.expander("Raw feature values for this connection", expanded=False):
    row_data = bundle.df.iloc[selected_idx]
    st.dataframe(
        pd.DataFrame({"feature": row_data.index, "value": row_data.values}),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 2 · SHAP feature attribution
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("2 · SHAP feature attribution")
st.markdown(
    "SHAP (SHapley Additive exPlanations) decomposes the anomaly score of each flagged "
    "connection into individual feature contributions using game-theoretic attribution. "
    "**Red** = feature pushes MSE up (increases anomaly score). "
    "**Blue** = feature pushes MSE down. "
    "Values are aggregated from the 569-dimensional preprocessed space back to the "
    f"{len(group_mapping)} original Zeek features for interpretability."
)

n_explain = st.slider("Rows to explain (top N by MSE)", min_value=5, max_value=30, value=10)
n_background = st.slider("Background sample size (benign rows)", min_value=20, max_value=100, value=50)

compute_btn = st.button("Compute SHAP values", type="primary")

if "shap_values" not in st.session_state:
    st.session_state["shap_values"] = None
    st.session_state["shap_base"] = None
    st.session_state["shap_explained_idx"] = None

if compute_btn:
    try:
        import shap
        import tensorflow as tf
        from tensorflow import keras

        # Background: sample benign rows from the current scoring session
        if has_labels:
            benign_mask = (bundle.labels.str.casefold() == "benign").to_numpy()
            X_benign = X_all[benign_mask]
        else:
            # fallback: lowest-MSE rows approximate benign
            low_err_idx = np.argsort(bundle.errors)[:500]
            X_benign = X_all[low_err_idx]

        n_bg = min(n_background, len(X_benign))
        bg_idx = np.random.default_rng(42).integers(0, len(X_benign), size=n_bg)
        background = X_benign[bg_idx].astype(np.float32)

        # Rows to explain
        explain_idx = flagged_sorted[:n_explain]
        X_explain = X_all[explain_idx].astype(np.float32)

        # Build MSE wrapper model so SHAP sees a scalar anomaly score
        inp = keras.Input(shape=(X_all.shape[1],), name="shap_input")
        rec = model(inp)
        mse_out = keras.layers.Lambda(
            lambda pair: tf.reduce_mean(tf.square(pair[0] - pair[1]), axis=1, keepdims=True),
            name="mse_output",
        )([inp, rec])
        mse_model = keras.Model(inputs=inp, outputs=mse_out, name="mse_wrapper")

        with st.spinner(f"Computing SHAP for {n_explain} connections (background={n_bg})…"):
            explainer = shap.GradientExplainer(mse_model, background)
            raw_shap = explainer.shap_values(X_explain)

        if isinstance(raw_shap, list):
            raw_shap = raw_shap[0]
        # raw_shap shape: (n_explain, n_features, 1) or (n_explain, n_features)
        if raw_shap.ndim == 3:
            raw_shap = raw_shap[:, :, 0]

        # Aggregate to original features
        agg_shap = np.zeros((n_explain, len(group_mapping)))
        orig_feature_names = list(group_mapping.keys())
        for fi, (feat, indices) in enumerate(group_mapping.items()):
            valid_idx = [i for i in indices if i < raw_shap.shape[1]]
            if valid_idx:
                agg_shap[:, fi] = raw_shap[:, valid_idx].sum(axis=1)

        st.session_state["shap_values"] = agg_shap
        st.session_state["shap_base"] = float(mse_model.predict(background, verbose=0).mean())
        st.session_state["shap_explained_idx"] = explain_idx
        st.session_state["shap_feature_names"] = orig_feature_names
        st.success(f"SHAP computed for {n_explain} connections.")

    except Exception as exc:
        st.error(f"SHAP computation failed: {exc}. Per-feature reconstruction error (Section 1) is always available.")

if st.session_state["shap_values"] is not None:
    shap_vals: np.ndarray = st.session_state["shap_values"]
    base_val: float = st.session_state["shap_base"]
    explained_idx: np.ndarray = st.session_state["shap_explained_idx"]
    orig_names: list[str] = st.session_state["shap_feature_names"]

    # Global importance
    mean_abs: dict[str, float] = {
        orig_names[fi]: float(np.mean(np.abs(shap_vals[:, fi])))
        for fi in range(len(orig_names))
    }
    st.plotly_chart(shap_global_importance_figure(mean_abs, top_n=len(orig_names)), use_container_width=True)
    st.caption(
        "Global importance = mean |SHAP value| across the explained rows. "
        "Features near the top systematically drive the anomaly score above baseline."
    )

    # Per-row waterfall
    st.markdown("#### Individual connection SHAP breakdown")
    shap_row_options = {
        f"#{i + 1}  MSE={bundle.errors[idx]:.5f}"
        + (f"  [{bundle.labels.iloc[idx]}]" if has_labels else "")
        : i
        for i, idx in enumerate(explained_idx)
    }
    chosen = st.selectbox("Select a connection", list(shap_row_options.keys()), key="shap_row")
    ri = shap_row_options[chosen]
    row_shap = {orig_names[fi]: float(shap_vals[ri, fi]) for fi in range(len(orig_names))}

    st.plotly_chart(
        shap_waterfall_figure(row_shap, base_val, bundle.errors[explained_idx[ri]], top_n=len(orig_names)),
        use_container_width=True,
    )

    with st.expander("SHAP values table — all explained rows", expanded=False):
        shap_df = pd.DataFrame(shap_vals, columns=orig_names)
        shap_df.insert(0, "mse_score", [bundle.errors[i] for i in explained_idx])
        if has_labels:
            shap_df.insert(0, "label", [bundle.labels.iloc[i] for i in explained_idx])
        st.dataframe(shap_df.style.format(precision=5), use_container_width=True, hide_index=True)

    st.download_button(
        "Download SHAP values (CSV)",
        data=shap_df.to_csv(index=False).encode("utf-8"),
        file_name="shap_values.csv",
        mime="text/csv",
    )
else:
    st.info("Click **Compute SHAP values** to run attribution analysis.")

render_multipage_navigation_hint()
