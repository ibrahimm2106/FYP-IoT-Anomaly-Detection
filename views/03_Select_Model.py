"""
Wizard step 3 — choose which saved Keras model file is used for anomaly scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from src.app_core import (
    LABEL_DATA_SOURCE_PROJECT,
    LABEL_DATA_SOURCE_UPLOAD,
    PROJECT_ROOT,
    SK_WIZARD_MODEL_PATH,
    SK_WIZARD_UPLOAD_BYTES,
    active_model_path,
    app_debug_mode,
    list_keras_model_paths,
    load_model,
)
from src.iot_paths import default_disk_model_path
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)

st.set_page_config(
    page_title="Select model · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=3)

render_wizard_step_header(
    step=3,
    title="Select model",
    tagline="Pick the **saved Keras** file (`.keras` / `.h5`) used for reconstruction scoring on each row.",
    bullets=(
        "Choose one **`.keras` / `.h5`** from the list (or train first).",
        "Optionally expand **Quick check** to verify the file loads.",
        "Continue to **Prepare model** to confirm threshold and features.",
    ),
)
render_mini_example(
    "Same as picking which saved calculator to use — baseline JSON files are for charts only, not row scoring."
)
st.caption("Preprocessor and threshold stay the **project defaults** on disk unless you retrain or replace files outside the app.")

with st.popover("Baseline JSON vs scoring model"):
    st.markdown(
        "**Autoencoder** weights score each row. **`baseline_metrics.json`** (if present) only feeds **Evaluation** / "
        "**Advanced** comparison charts — it does **not** replace the neural network for scoring."
    )

paths = list_keras_model_paths()
baseline_json = PROJECT_ROOT / "models" / "baseline_metrics.json"
test_eval_json = PROJECT_ROOT / "models" / "test_evaluation.json"

if paths and SK_WIZARD_MODEL_PATH not in st.session_state:
    st.session_state[SK_WIZARD_MODEL_PATH] = str(paths[0])

if not paths:
    st.warning("No `.keras` or `.h5` model file found yet. Run **`train.py`** once, then refresh this page.")
    st.page_link("views/13_Model_Info.py", label="Model info & training notes (advanced) →")
else:
    st.subheader("Model for scoring")
    labels: list[str] = []
    default_weights = default_disk_model_path()
    for p in paths:
        if default_weights.is_file() and p.resolve() == default_weights.resolve():
            labels.append(f"Main autoencoder — {p.name} (project default)")
        else:
            labels.append(f"Saved weights — {p.name}")

    cur = st.session_state.get(SK_WIZARD_MODEL_PATH)
    idx = 0
    if cur:
        try:
            curp = Path(str(cur)).resolve()
            for i, p in enumerate(paths):
                if p.resolve() == curp:
                    idx = i
                    break
        except OSError:
            idx = 0

    choice = st.radio(
        "Which file should the app load when you score connections?",
        list(range(len(paths))),
        index=idx,
        format_func=lambda i: labels[i],
        horizontal=False,
        key="wizard_model_choice_radio",
    )
    chosen = paths[int(choice)]
    st.session_state[SK_WIZARD_MODEL_PATH] = str(chosen.resolve())

    st.info(f"Using **{chosen.name}** for scoring.")

    with st.expander("Quick check — load this model now", expanded=False):
        try:
            m = load_model()
            st.write(f"Loaded OK · input width **{m.input_shape[-1]}** (after preprocessing).")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load this file: {exc}")

st.divider()
st.subheader("Other saved artefacts (not for row scoring)")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Baseline comparison (Isolation Forest)**")
    if baseline_json.is_file():
        mtime = datetime.fromtimestamp(baseline_json.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        st.caption(f"Found `baseline_metrics.json` · updated **{mtime}**")
        st.info(
            "Used on the **Evaluation** and **Advanced analysis** pages to compare numbers side‑by‑side. "
            "It does **not** replace the autoencoder for scoring.",
        )
    else:
        st.caption("Optional. Run **`train.py`** or **`evaluate.py`** to create it.")
with c2:
    st.markdown("**Test-set report JSON**")
    if test_eval_json.is_file():
        mtime = datetime.fromtimestamp(test_eval_json.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        st.caption(f"Found `test_evaluation.json` · updated **{mtime}**")
        st.info("Extra charts on **Advanced analysis** when present.")
    else:
        st.caption("Optional. Run **`evaluate.py`** to generate.")

st.divider()
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("Continue to prepare model →", type="primary"):
        st.switch_page("views/04_Prepare_Model.py")
with b2:
    if st.button("Continue to scoring →"):
        if st.session_state.get(SK_WIZARD_UPLOAD_BYTES):
            st.session_state["detection_src_radio"] = LABEL_DATA_SOURCE_UPLOAD
        else:
            st.session_state["detection_src_radio"] = LABEL_DATA_SOURCE_PROJECT
        st.switch_page("views/11_Detection_Results.py")
with b3:
    st.page_link("views/02_Repair_Data.py", label="← Back to Repair data")

st.caption(f"Active scoring model file: `{active_model_path().name}`")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1`.")

st.divider()
render_multipage_navigation_hint()
