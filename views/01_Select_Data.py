"""
Wizard step 1 — choose sample (project) CSV or upload; preview and validate before scoring.
"""

from __future__ import annotations

import streamlit as st

from src.app_core import (
    CAPTION_SELECT_DATA_LEAD,
    DATA_PATH,
    SK_REPAIR_LAST_LOG,
    SK_REPAIR_ORIGINAL_DF,
    SK_REPAIR_WORKING_DF,
    SK_WIZARD_DATA_SOURCE,
    SK_WIZARD_UPLOAD_BYTES,
    SK_WIZARD_UPLOAD_NAME,
    app_debug_mode,
    check_model_artefacts,
    load_preprocessor,
    missing_label_columns_message,
    parse_csv_bytes,
    try_read_processed_csv,
    validate_dataframe_for_scoring,
)
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)
from src.validation_helpers import data_quality_summary, missing_values_audit

st.set_page_config(
    page_title="Select data · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=1)

render_wizard_step_header(
    step=1,
    title="Select data",
    tagline="Pick the connection table you will use for the rest of the wizard (sample project CSV or your upload).",
    bullets=(
        "Choose **Sample** or **Upload** (UTF-8 CSV).",
        "Use **Preview** and **Checks** before leaving this step.",
        "Press **Continue to repair data** when that button is enabled (follow any warnings shown).",
    ),
)
render_mini_example(
    "One row ≈ one Zeek `conn` record: `ts`, `proto`, `id.orig_h`, `id.resp_h`, … Optional `label` enables precision/recall later."
)
st.caption(CAPTION_SELECT_DATA_LEAD)

with st.popover("Valid columns and Zeek shape"):
    st.markdown(
        "Each **row** is one Zeek-style **connection**. A typical row includes **`ts`**, **`uid`**, **`proto`**, "
        "**`service`**, **`id.orig_h`**, **`id.resp_h`**, ports, bytes, duration, and (if present) **`label`** / "
        "**`detailed-label`**. Your CSV must match the columns the saved model was trained on."
    )

mode = st.radio(
    "Data source",
    ("Sample (project CSV)", "Upload my CSV"),
    horizontal=True,
    help="Sample uses the processed file on disk. Upload keeps the file in memory only.",
)

validation_box = st.container()
preview_box = st.container()

if mode == "Sample (project CSV)":
    df, err = try_read_processed_csv()
    with preview_box:
        st.subheader("Preview")
        if err or df is None:
            st.error(err or "Could not load the project CSV.")
            st.info("Run `src/preprocess.py` from the project root, then refresh this page.")
        else:
            st.dataframe(df.head(8), use_container_width=True, hide_index=True)
            q = data_quality_summary(df)
            st.caption(f"Rows: **{q['rows']:,}** · Columns: **{q['columns']}** · Path: `{DATA_PATH.name}`")

    with validation_box:
        st.subheader("Checks")
        if err or df is None:
            pass
        else:
            lbl = missing_label_columns_message(df)
            if lbl:
                st.warning(lbl)
            model_err = check_model_artefacts()
            if model_err:
                st.info("Train the model to run a full schema check against the preprocessor.")
                st.caption(model_err[:400] + ("…" if len(model_err) > 400 else ""))
            else:
                preprocessor = load_preprocessor()
                ok, schema_msg = validate_dataframe_for_scoring(df, preprocessor)
                if ok:
                    st.success("Schema matches the saved preprocessor.")
                else:
                    st.warning(schema_msg or "Schema check failed.")

    if err or df is None:
        st.caption("Fix the error in **Preview** or **Checks** above — **Continue** enables when the project CSV loads.")
    go = st.button("Continue to repair data →", type="primary", disabled=bool(err or df is None))
    if go and df is not None:
        for k in (SK_WIZARD_UPLOAD_BYTES, SK_WIZARD_UPLOAD_NAME, SK_REPAIR_ORIGINAL_DF, SK_REPAIR_WORKING_DF, SK_REPAIR_LAST_LOG):
            st.session_state.pop(k, None)
        st.session_state[SK_WIZARD_DATA_SOURCE] = "sample"
        st.switch_page("views/02_Repair_Data.py")

else:
    up = st.file_uploader("CSV (UTF-8)", type=["csv"], accept_multiple_files=False, key="select_data_upload")
    raw: bytes | None = None
    upload_name = ""
    parsed = None
    perr: str | None = None
    if up is not None:
        raw = up.getvalue()
        upload_name = up.name or "upload.csv"
        parsed, perr = parse_csv_bytes(raw)

    with preview_box:
        st.subheader("Preview")
        if up is None:
            st.info("Choose a CSV file above.")
        elif parsed is None or perr:
            st.error(perr or "Could not parse this file.")
        else:
            st.dataframe(parsed.head(8), use_container_width=True, hide_index=True)
            q = data_quality_summary(parsed)
            st.caption(f"Rows: **{q['rows']:,}** · Columns: **{q['columns']}** · File: `{upload_name}`")
            miss = missing_values_audit(parsed, top_n=10)
            if miss is not None:
                with st.expander("Missing values (top columns)", expanded=False):
                    st.dataframe(miss, use_container_width=True, hide_index=True)

    schema_ok = False
    model_err_msg: str | None = None
    with validation_box:
        st.subheader("Checks")
        if up is None:
            pass
        elif parsed is None or perr:
            st.error(perr or "Parse error.")
        else:
            if "label" not in parsed.columns:
                st.info("Optional: add a **`label`** column for precision/recall metrics later.")
            model_err_msg = check_model_artefacts()
            if model_err_msg:
                st.info("Train the model to validate columns against the preprocessor.")
                st.caption(model_err_msg[:400] + ("…" if len(model_err_msg) > 400 else ""))
                schema_ok = True
            else:
                preprocessor = load_preprocessor()
                schema_ok, schema_msg = validate_dataframe_for_scoring(parsed, preprocessor)
                if schema_ok:
                    st.success("Schema matches the saved preprocessor.")
                else:
                    st.warning(schema_msg or "Schema check failed.")
                    st.error("Fix the issues above before continuing, or use **Repair data** when it is available.")

        if not (
            raw is not None
            and parsed is not None
            and not perr
            and (bool(model_err_msg) or schema_ok)
        ):
            st.caption(
                "Upload a UTF-8 CSV, fix any parse or schema messages, then **Continue** enables "
                "(or train the model if only artefacts are missing — you can still continue when the schema matches)."
            )
        can_upload_continue = (
            raw is not None
            and parsed is not None
            and not perr
            and (bool(model_err_msg) or schema_ok)
        )
        go_u = st.button("Continue to repair data →", type="primary", disabled=not can_upload_continue)
        if go_u and raw is not None and parsed is not None and not perr:
            if not model_err_msg and not schema_ok:
                st.stop()
            for k in (SK_REPAIR_ORIGINAL_DF, SK_REPAIR_WORKING_DF, SK_REPAIR_LAST_LOG):
                st.session_state.pop(k, None)
            st.session_state[SK_WIZARD_UPLOAD_BYTES] = raw
            st.session_state[SK_WIZARD_UPLOAD_NAME] = upload_name
            st.session_state[SK_WIZARD_DATA_SOURCE] = "upload"
            st.switch_page("views/02_Repair_Data.py")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1` in the URL.")

st.divider()
render_multipage_navigation_hint()
