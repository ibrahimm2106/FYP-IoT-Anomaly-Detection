"""
Wizard step 5 — run the prepared model once and read results in plain language.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.app_core import (
    render_restore_training_pipeline_ui,
    SK_WIZARD_UPLOAD_BYTES,
    ScoringBundle,
    app_debug_mode,
    check_environment,
    check_model_artefacts,
    friendly_scoring_error,
    load_scoring_bundle,
    parse_csv_bytes,
    score_dataframe,
)
from src.evaluation_helpers import bundle_has_labels, contingency_matrix_dataframe, metrics_dataframe
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)

SK_TEST_BUNDLE = "iot_wizard_test_bundle"
SK_TEST_ERROR = "iot_wizard_test_error"

st.set_page_config(
    page_title="Test model · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=5)

render_wizard_step_header(
    step=5,
    title="Test model",
    tagline="Run the autoencoder once on **project** or **session** data, then read the plain-language summary.",
    bullets=(
        "Choose **session** or **project** data when both exist.",
        "Press **Run test** and wait for the spinner to finish.",
        "Read **What this run means** — then continue to **Export** or classic **Detection**.",
    ),
)
render_mini_example(
    "10,000 rows and threshold 0.02 → if 120 rows exceed 0.02 MSE, you see ~1.2% flagged (illustrative)."
)
st.caption("Choose **session** vs **project** if both exist, press **Run test**, then continue to **Export** or **Detection**.")

with st.popover("What “flagged” means"):
    st.markdown(
        "**Flagged** = reconstruction MSE **above** your cut-off vs benign training patterns — **not** proof of an attack. "
        "With Zeek **labels**, agreement tables are **illustrative** only (dataset- and threshold-specific)."
    )

model_err = check_model_artefacts()
if model_err:
    st.error(model_err)
    render_restore_training_pipeline_ui()
    st.page_link("views/04_Prepare_Model.py", label="← Back to Prepare model")
    render_multipage_navigation_hint()
    st.stop()

has_session_csv = bool(st.session_state.get(SK_WIZARD_UPLOAD_BYTES))
data_mode = "project"
if has_session_csv:
    pick = st.radio(
        "Which data should we use for this test?",
        (
            "session",
            "project",
        ),
        horizontal=True,
        format_func=lambda k: "Table from this session (select / repair)" if k == "session" else "Project CSV on disk",
        key="test_model_data_pick",
    )
    data_mode = str(pick)
else:
    st.info("No in-memory table found — this test will use the **project CSV** on disk.")

run = st.button("Run test", type="primary", help="Scores every row once. May take a little time on large files.")

if run:
    st.session_state.pop(SK_TEST_BUNDLE, None)
    st.session_state.pop(SK_TEST_ERROR, None)
    bundle: ScoringBundle | None = None
    err_msg: str | None = None
    try:
        with st.spinner("Scoring connections…"):
            if data_mode == "session" and has_session_csv:
                raw = st.session_state.get(SK_WIZARD_UPLOAD_BYTES)
                if not raw:
                    err_msg = "Session table is empty. Go back to **Select data** or **Repair data**."
                else:
                    df, perr = parse_csv_bytes(raw)
                    if df is None or perr:
                        err_msg = perr or "Could not read the session CSV."
                    else:
                        bundle = score_dataframe(df)
            else:
                env_err = check_environment()
                if env_err:
                    err_msg = env_err
                else:
                    bundle, disk_err = load_scoring_bundle()
                    err_msg = disk_err
    except Exception as exc:  # noqa: BLE001
        err_msg = friendly_scoring_error(exc)
        if app_debug_mode():
            import traceback

            err_msg += "\n\n```\n" + traceback.format_exc() + "\n```"

    if err_msg or bundle is None:
        st.session_state[SK_TEST_ERROR] = err_msg or "Scoring did not return a result."
        st.session_state.pop(SK_TEST_BUNDLE, None)
        st.error(st.session_state[SK_TEST_ERROR])
    else:
        st.session_state.pop(SK_TEST_ERROR, None)
        st.session_state[SK_TEST_BUNDLE] = bundle
        st.success("Test finished — see the summary below.")

bundle_out = st.session_state.get(SK_TEST_BUNDLE)
if isinstance(bundle_out, ScoringBundle):
    b = bundle_out
    n = len(b.df)
    flagged = int(b.flagged.sum())
    rate = 100.0 * flagged / max(n, 1)
    st.subheader("What this run means (plain language)")
    st.markdown(
        f"- We looked at **{n:,}** connection rows.\n"
        f"- **{flagged:,}** ({rate:.1f} %) scored **higher** than your MSE cut-off **{b.threshold:.6f}** — we treat those as **flagged** (look unusual).\n"
        f"- **{n - flagged:,}** rows stayed **below** the cut-off (not flagged)."
    )
    st.info(
        "A **higher** reconstruction error means the model had a harder time reconstructing that row from "
        "benign-style patterns — it does **not** mean a guaranteed attack.",
    )

    st.subheader("Quick numbers")
    m1, m2, m3 = st.columns(3)
    m1.metric("Flagged (unusual)", f"{flagged:,}", help="Count with MSE strictly above your threshold.")
    m2.metric("Not flagged", f"{n - flagged:,}", help="All other rows in this test.")
    m3.metric("MSE cut-off", f"{b.threshold:.6f}", help="Same value used for the anomaly flag.")

    if bundle_has_labels(b):
        st.subheader("Agreement with Zeek labels (if labels exist)")
        st.caption("Only available when your table has a **`label`** column. Malicious = any label other than Benign.")
        st.dataframe(contingency_matrix_dataframe(b), use_container_width=True, hide_index=True)
        st.dataframe(metrics_dataframe(b), use_container_width=True, hide_index=True)
    else:
        st.warning("No **`label`** column — we can still flag rows, but precision/recall style numbers are not available.")

    st.subheader("Score spread (sample)")
    err = np.asarray(b.errors, dtype=np.float64)
    cap = min(len(err), 12_000)
    sample = err[:cap]
    nb = min(28, max(8, int(np.sqrt(cap))))
    counts, edges = np.histogram(sample, bins=nb)
    mids = (edges[:-1] + edges[1:]) / 2.0
    chart_df = pd.DataFrame({"Typical error (bin)": mids.astype(float), "How many rows": counts.astype(int)})
    st.bar_chart(chart_df.set_index("Typical error (bin)"))
    st.caption(
        f"Histogram uses up to **{cap:,}** rows (higher errors toward the right). Your MSE cut-off for flagging is **{b.threshold:.6f}**."
    )

elif not run and st.session_state.get(SK_TEST_ERROR):
    st.error(st.session_state[SK_TEST_ERROR])
    st.caption("Adjust **Prepare model** or your data, then tap **Run test** again.")
elif not run and not isinstance(bundle_out, ScoringBundle):
    st.info("Tap **Run test** when you are ready. Large tables may take a short while.")

st.divider()
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.page_link("views/04_Prepare_Model.py", label="← Back to Prepare model")
with c2:
    st.page_link("views/06_Export.py", label="Continue to Export →")
with c3:
    st.page_link("views/12_Evaluation.py", label="Evaluation detail (advanced) →")
with c4:
    st.page_link("views/11_Detection_Results.py", label="Full scoring table (advanced) →")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1`.")

st.divider()
render_multipage_navigation_hint()
