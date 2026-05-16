"""
Wizard step 4 — confirm model, threshold, and inputs before scoring (session-only changes where noted).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_core import (
    CAPTION_PREPARE_MODEL_LEAD,
    SK_WIZARD_SESSION_THRESHOLD,
    render_restore_training_pipeline_ui,
    active_model_path,
    active_threshold,
    app_debug_mode,
    check_model_artefacts,
    load_preprocessor,
    load_threshold,
)
from src.iot_streamlit import THRESHOLD_PATH, expected_feature_column_order
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)

st.set_page_config(
    page_title="Prepare model · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=4)

render_wizard_step_header(
    step=4,
    title="Prepare model",
    tagline="Confirm the saved **model file**, **MSE cut-off**, and **feature columns** before **Test model**.",
    bullets=(
        "Read the **Status** metrics (model, preprocessor, threshold, features).",
        "Keep **saved training threshold** or try a **custom** cut-off for this session only.",
        "Open **Input features** if you need to verify column names.",
    ),
)
st.caption(CAPTION_PREPARE_MODEL_LEAD)
render_mini_example(
    "Higher MSE cut-off → fewer rows flagged; lower → more flags. Session slider does not edit `threshold.txt` on disk."
)

with st.popover("Session threshold vs file on disk"):
    st.markdown(
        "**Custom** slider values apply while this browser session lasts. Reloading the app or choosing **Use saved** "
        "returns to `models/threshold.txt`. To change the file permanently, retrain or edit outside Streamlit.\n\n"
        "**Retraining:** new weights and thresholds come from **`train.py`** on your machine — not inside this browser."
    )

model_err = check_model_artefacts()
saved_th: float | None = None
if not model_err:
    try:
        saved_th = load_threshold()
    except ValueError as exc:
        st.error(str(exc))
        render_restore_training_pipeline_ui()
        render_multipage_navigation_hint()
        st.stop()
else:
    st.warning(model_err)
    render_restore_training_pipeline_ui()

st.subheader("Status")
s1, s2, s3, s4 = st.columns(4)
mp = active_model_path()
s1.metric(
    "Neural network",
    "Ready" if mp.is_file() else "Missing",
    help="The `.keras` / `.h5` file chosen on **Select model** (or the project default).",
)
s2.metric(
    "Preprocessor",
    "Ready" if not model_err else "—",
    help="Scaling and encoding saved with training (`preprocessor.pkl`).",
)
try:
    _th_show = f"{active_threshold():.6f}"
except Exception:
    _th_show = "—"
s3.metric(
    "Threshold in use",
    _th_show,
    help="MSE above this value marks a row as flagged. Session value overrides the text file when set.",
)
s4.metric(
    "Input features",
    "From training" if not model_err else "—",
    help="Column list is fixed by the saved preprocessor — change it only by retraining.",
)

st.divider()
st.subheader("Saved weights")
st.caption("Pick a different file on **Select model** if you have more than one trained export.")
st.page_link("views/03_Select_Model.py", label="Change model file →")
st.write(f"**Active file:** `{mp.name}`")

st.divider()
st.subheader("Anomaly threshold (MSE)")
if saved_th is not None:
    th_mode = st.radio(
        "How should we pick the cut-off?",
        ("training", "custom"),
        horizontal=True,
        format_func=lambda k: "Use saved training value" if k == "training" else "Try a custom value (this session only)",
        key="prepare_threshold_mode",
    )
    if th_mode == "training":
        st.session_state.pop(SK_WIZARD_SESSION_THRESHOLD, None)
        st.success(f"Using training threshold **{saved_th:.6f}** from `{THRESHOLD_PATH.name}`.")
    else:
        lo = max(float(saved_th) * 0.2, 1e-12)
        hi = max(float(saved_th) * 5.0, lo * 1.0001)
        cur = float(st.session_state.get(SK_WIZARD_SESSION_THRESHOLD, saved_th))
        cur = min(max(cur, lo), hi)
        new_v = st.slider(
            "MSE cut-off for flagging rows",
            min_value=float(lo),
            max_value=float(hi),
            value=float(cur),
            format="%.6f",
            help="Higher → fewer flags. Does not edit `threshold.txt` on disk.",
            key="prepare_threshold_slider",
        )
        st.session_state[SK_WIZARD_SESSION_THRESHOLD] = float(new_v)
        st.info(f"Custom cut-off **{new_v:.6f}** will be used when you score.")
else:
    st.info("Fix missing model files above to load the training threshold, or run **`train.py`** first.")

st.divider()
with st.expander("Input features (read-only)", expanded=False):
    st.caption("These columns are fed into the preprocessor after dropping labels and IDs. To change them, retrain with **`train.py`**.")
    if not model_err:
        try:
            pre = load_preprocessor()
            cols = expected_feature_column_order(pre)
            if cols:
                st.dataframe(
                    pd.DataFrame({"Feature column": cols}),
                    use_container_width=True,
                    hide_index=True,
                    height=min(400, 35 * (len(cols) + 1)),
                )
            else:
                st.warning("Could not read the feature list from the preprocessor metadata.")
        except Exception as exc:  # noqa: BLE001
            st.warning(str(exc))
    else:
        st.caption("Load a preprocessor to see the feature list.")

st.divider()
with st.expander("Train or refresh weights (on your computer)", expanded=False):
    st.markdown(
        "- **`python src/preprocess.py`** — build the processed CSV.\n"
        "- **`python train.py`** — fit the preprocessor + autoencoder and write `models/` (including `threshold.txt`).\n"
        "Then **reload** this app to pick up new files."
    )

st.divider()
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("Continue to test model →", type="primary"):
        st.switch_page("views/05_Test_Model.py")
with b2:
    if st.button("Open scoring table →"):
        st.switch_page("views/11_Detection_Results.py")
with b3:
    st.page_link("views/03_Select_Model.py", label="← Back to Select model")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1`.")

st.divider()
render_multipage_navigation_hint()
