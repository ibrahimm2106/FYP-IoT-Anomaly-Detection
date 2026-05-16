"""
Wizard step 7 — simplest screen: upload a CSV and hear in plain words if anything looks unusual.
"""

from __future__ import annotations

import hashlib

import numpy as np
import streamlit as st

from src.app_core import (
    render_restore_training_pipeline_ui,
    ScoringBundle,
    app_debug_mode,
    check_model_artefacts,
    friendly_scoring_error,
    parse_csv_bytes,
    score_dataframe,
)
from src.evaluation_helpers import bundle_has_labels, evaluation_metrics_from_bundle
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)

SK_USE_DIGEST = "iot_simple_use_digest"
SK_USE_BUNDLE = "iot_simple_use_bundle"


st.set_page_config(
    page_title="Use model · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=7)

render_wizard_step_header(
    step=7,
    title="Use model",
    tagline="Minimal path: upload a compatible CSV and get an **everyday-language** summary — no training controls on this page.",
    bullets=(
        "Upload **UTF-8 CSV** matching the model’s expected columns.",
        "Press **Check for unusual activity** and read the summary.",
        "Open **More detail** only if you want MSE / threshold context.",
    ),
)
render_mini_example(
    "A small `sample_conn.csv` with the same columns as training → instant benign-vs-unusual wording after you click check."
)
st.caption("Upload a UTF-8 CSV, then press **Check for unusual activity** — nothing is stored on the server.")

with st.popover("Same engine as the full wizard"):
    st.markdown(
        "This step calls the same **`score_dataframe`** path as earlier steps; nothing is stored on the server — "
        "results live in your **browser session** until you close the tab."
    )

model_err = check_model_artefacts()
if model_err:
    st.error(model_err)
    render_restore_training_pipeline_ui()
    st.page_link("views/04_Prepare_Model.py", label="← What to fix first")
    render_multipage_navigation_hint()
    st.stop()

uploaded = st.file_uploader(
    "Choose a CSV file (UTF-8)",
    type=["csv"],
    accept_multiple_files=False,
    help="Same kind of connection table the model was trained on (Zeek-style columns).",
    key="simple_use_csv",
)

if uploaded is None:
    st.info("Pick a **CSV** above, then press the button. Nothing is saved on the server — it runs in your browser session.")
    st.session_state.pop(SK_USE_BUNDLE, None)
    st.session_state.pop(SK_USE_DIGEST, None)
else:
    raw = uploaded.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    if st.session_state.get(SK_USE_DIGEST) != digest:
        st.session_state.pop(SK_USE_BUNDLE, None)
    st.session_state[SK_USE_DIGEST] = digest

    if st.button("Check for unusual activity", type="primary"):
        st.session_state.pop(SK_USE_BUNDLE, None)
        df, perr = parse_csv_bytes(raw)
        if df is None or perr:
            st.error(perr or "We could not read this file. Try saving it as UTF-8 CSV.")
        else:
            try:
                with st.spinner("Looking through your rows…"):
                    bundle = score_dataframe(df)
                st.session_state[SK_USE_BUNDLE] = bundle
                st.success("Check complete — read the summary below.")
            except Exception as exc:  # noqa: BLE001
                msg = friendly_scoring_error(exc)
                st.error(msg)
                if app_debug_mode():
                    import traceback

                    st.code(traceback.format_exc(), language="text")

    b = st.session_state.get(SK_USE_BUNDLE)
    if isinstance(b, ScoringBundle) and st.session_state.get(SK_USE_DIGEST) == digest:
        n = len(b.df)
        flagged = int(b.flagged.sum())
        pct = 100.0 * flagged / max(n, 1)
        st.subheader("Plain-language result")
        if flagged == 0:
            st.markdown(
                f"We reviewed **{n:,}** rows. **None** stood out as unusual with the current sensitivity — "
                "everything stayed within the “normal” range the model expects."
            )
        elif flagged == n:
            st.markdown(
                f"We reviewed **{n:,}** rows. **All** of them looked **unusual** compared with typical training traffic. "
                "That often means the file format or traffic mix is very different from what the model saw before — worth a second look."
            )
        else:
            st.markdown(
                f"We reviewed **{n:,}** rows. **{flagged:,}** (**{pct:.1f} %**) looked **unusual** — "
                "they crossed the line the model uses for “not like normal benign traffic.” The rest looked ordinary under this check."
            )

        with st.expander("A bit more detail (optional)", expanded=False):
            st.write(
                f"The model compares each row to patterns it learned from **benign** connections. "
                f"It uses a numeric **reconstruction score**; when that score is **above {b.threshold:.6f}**, "
                f"we treat the row as **flagged** (unusual-looking). This is **not** the same as proof of an attack."
            )
            if bundle_has_labels(b):
                ev = evaluation_metrics_from_bundle(b)
                st.caption(
                    "Your file had **labels**, so we can loosely compare flags to those labels (illustrative only)."
                )
                pr = ev.get("precision")
                rc = ev.get("recall")
                if pr is not None and rc is not None:
                    st.write(
                        f"- When we said “unusual,” **{float(pr) * 100:.1f} %** of those were also marked non-benign in your labels (precision).\n"
                        f"- We caught **{float(rc) * 100:.1f} %** of the non-benign-labelled rows this way (recall)."
                    )
            else:
                st.caption("No **`label`** column — we only report unusual-looking rows, not agreement with truth labels.")

        if flagged > 0:
            fl = np.asarray(b.flagged, dtype=bool)
            idx = np.flatnonzero(fl)[:5]
            show = b.df.iloc[idx].copy()
            show.insert(0, "unusual_score", np.asarray(b.errors, dtype=np.float64)[idx])
            st.caption("First few unusual rows (technical preview):")
            st.dataframe(show, use_container_width=True, hide_index=True)

st.divider()
st.page_link("views/06_Export.py", label="← Back to Export")
st.page_link("views/01_Select_Data.py", label="Full guided workflow from the start →")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1`.")

st.divider()
render_multipage_navigation_hint()
