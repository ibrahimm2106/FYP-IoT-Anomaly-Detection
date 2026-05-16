"""
Wizard step 2 — optional in-memory repairs before scoring (missing values, duplicates, columns, flags).
"""

from __future__ import annotations

import streamlit as st

from src.app_core import (
    LABEL_DATA_SOURCE_UPLOAD,
    SK_REPAIR_LAST_LOG,
    SK_REPAIR_ORIGINAL_DF,
    SK_REPAIR_WORKING_DF,
    SK_WIZARD_DATA_SOURCE,
    SK_WIZARD_UPLOAD_BYTES,
    SK_WIZARD_UPLOAD_NAME,
    app_debug_mode,
    check_model_artefacts,
    load_preprocessor,
    parse_csv_bytes,
    try_read_processed_csv,
)
from src.repair_helpers import (
    duplicate_row_count,
    optional_columns_to_drop,
    repair_dataframe,
    required_feature_names,
    summarize_log,
    total_missing_cells,
)
from src.ui_helpers import (
    render_mini_example,
    render_multipage_navigation_hint,
    render_wizard_step_header,
    setup_wizard_page,
)

st.set_page_config(
    page_title="Repair data · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_wizard_page(wizard_step=2)

render_wizard_step_header(
    step=2,
    title="Repair data",
    tagline="Clean the table **in memory** only; nothing is written to `data/processed/` from this screen.",
    bullets=(
        "Confirm **Data summary** (rows, missing cells, duplicates).",
        "Choose options (impute, dedupe, drop columns), then **Apply**.",
        "Continue to **Select model** when the preview looks right.",
    ),
)
render_mini_example(
    "Blanks in a numeric column → median fill replaces each gap with that column’s middle value."
)
st.caption("Review the summary, optionally **Apply** repairs, then continue to **Select model** when the preview looks right.")

with st.popover("How repairs interact with scoring"):
    st.markdown(
        "Repairs change the **working DataFrame** in session only. **Scaling** and encoding still come from the saved "
        "**`preprocessor.pkl`** when you score. If you skip repairs, the original copy from step 1 is used."
    )


def _load_source_into_session() -> tuple[bool, str | None]:
    """Load the selected wizard data source into repair session state.

    Returns:
        Tuple of ``(success, error_message)``. ``error_message`` is ``None``
        when loading succeeds.
    """
    if SK_REPAIR_ORIGINAL_DF in st.session_state and SK_REPAIR_WORKING_DF in st.session_state:
        return True, None
    src = st.session_state.get(SK_WIZARD_DATA_SOURCE)
    if src == "sample":
        df, err = try_read_processed_csv()
        if err or df is None:
            return False, err or "Could not load the project CSV."
        st.session_state[SK_REPAIR_ORIGINAL_DF] = df
        st.session_state[SK_REPAIR_WORKING_DF] = df.copy()
        return True, None
    if src == "upload":
        raw = st.session_state.get(SK_WIZARD_UPLOAD_BYTES)
        if not raw:
            return False, "No uploaded file in session. Go back to **Select data**."
        df, err = parse_csv_bytes(raw)
        if err or df is None:
            return False, err or "Could not parse the upload."
        st.session_state[SK_REPAIR_ORIGINAL_DF] = df
        st.session_state[SK_REPAIR_WORKING_DF] = df.copy()
        return True, None
    raw = st.session_state.get(SK_WIZARD_UPLOAD_BYTES)
    if raw:
        df, err = parse_csv_bytes(raw)
        if df is not None and not err:
            st.session_state[SK_WIZARD_DATA_SOURCE] = "upload"
            st.session_state[SK_REPAIR_ORIGINAL_DF] = df
            st.session_state[SK_REPAIR_WORKING_DF] = df.copy()
            return True, None
    df, err = try_read_processed_csv()
    if df is not None and not err:
        st.session_state[SK_WIZARD_DATA_SOURCE] = "sample"
        st.session_state[SK_REPAIR_ORIGINAL_DF] = df
        st.session_state[SK_REPAIR_WORKING_DF] = df.copy()
        return True, None
    return False, "Open **Select data** first and continue with sample or upload."


ok_load, load_err = _load_source_into_session()
if not ok_load:
    st.error(load_err or "Nothing to repair.")
    st.page_link("views/01_Select_Data.py", label="← Back to Select data")
    render_multipage_navigation_hint()
    st.stop()

orig = st.session_state[SK_REPAIR_ORIGINAL_DF]
work = st.session_state[SK_REPAIR_WORKING_DF]

model_err = check_model_artefacts()
preprocessor = None
req: list[str] | None = None
if not model_err:
    preprocessor = load_preprocessor()
    req = required_feature_names(preprocessor)

miss_before = total_missing_cells(orig)
dup_before = duplicate_row_count(orig)
opt_drop = optional_columns_to_drop(orig, req)

st.subheader("Data summary")
m1, m2, m3 = st.columns(3)
m1.metric("Rows", f"{len(orig):,}", help="Current working copy matches original until you apply repairs.")
m2.metric("Missing cells", f"{miss_before:,}", help="Total NaN across all columns.")
m3.metric("Duplicate rows", f"{dup_before:,}", help="Fully identical rows (all columns).")

st.divider()
st.subheader("Repair options")
st.caption("Only options that match your data are highlighted; others stay available with a short note.")

c_miss, c_dup = st.columns(2)
with c_miss:
    miss_opts = ("none", "median", "mean", "zero", "drop_rows")
    miss_labels = {
        "none": "Do nothing",
        "median": "Fill numeric: median",
        "mean": "Fill numeric: mean",
        "zero": "Fill numeric: 0",
        "drop_rows": "Drop rows with any missing (model columns)",
    }
    missing_numeric = st.selectbox(
        "Missing values — numbers",
        miss_opts,
        format_func=lambda k: miss_labels[k],
        index=0,
        help="Applies to numeric **model** columns when the preprocessor list is known; otherwise all numeric columns.",
        key="repair_missing_numeric",
    )
    if miss_before == 0:
        st.caption("No missing cells — this mainly affects new gaps if you clip or drop duplicates first.")

with c_dup:
    drop_dupes = st.toggle(
        "Remove duplicate rows",
        value=False,
        disabled=dup_before == 0,
        help="Keeps the first copy of each identical row.",
        key="repair_drop_dupes",
    )
    if dup_before == 0:
        st.caption("No duplicate rows found.")

c_cat, c_clip = st.columns(2)
with c_cat:
    cat_miss = st.selectbox(
        "Missing values — text / categories",
        ("none", "placeholder"),
        format_func=lambda k: "Do nothing" if k == "none" else 'Fill with "(missing)"',
        help="Applies to non-numeric model columns (when known).",
        key="repair_missing_cat",
    )

with c_clip:
    clip_on = st.toggle(
        "Clip extreme numbers (1st–99th % per column)",
        value=False,
        help="Caps very large/small values. Your saved preprocessor still applies its own scaling at score time.",
        key="repair_clip",
    )

extra_drop: list[str] = []
if opt_drop:
    extra_drop = st.multiselect(
        "Extra columns to remove (optional)",
        options=opt_drop,
        default=[],
        help="Cannot remove columns the model needs or label columns.",
        key="repair_extra_cols",
    )
else:
    st.caption("No extra columns to drop (all columns look required for the model or are labels).")

c_flag, c_remove = st.columns(2)
with c_flag:
    add_invalid = st.toggle(
        'Flag bad rows (add column "_iot_invalid_row")',
        value=False,
        help="Marks rows with NaN or ±∞ in numeric model columns after the steps above.",
        key="repair_flag_invalid",
    )
with c_remove:
    remove_invalid = st.toggle(
        "Remove flagged rows",
        value=False,
        disabled=not add_invalid,
        help="Requires flagging. Drops rows where the flag is true.",
        key="repair_remove_invalid",
    )

st.divider()
pv1, pv2 = st.columns(2)
with pv1:
    if st.button("Preview changes", help="Does not save — shows what your choices would do from the original table."):
        preview_df, preview_log = repair_dataframe(
            orig,
            required=req,
            missing_numeric=missing_numeric,
            missing_categorical=cat_miss,
            drop_duplicates=drop_dupes,
            extra_columns_to_drop=list(extra_drop),
            add_invalid_flag=add_invalid,
            remove_invalid_rows=remove_invalid,
            clip_numeric_percentiles=clip_on,
        )
        st.session_state["_repair_preview_df"] = preview_df
        st.session_state["_repair_preview_log"] = preview_log

with pv2:
    if st.button("Reset table", help="Discard repairs and reload from the original copy."):
        st.session_state[SK_REPAIR_WORKING_DF] = orig.copy()
        st.session_state.pop(SK_REPAIR_LAST_LOG, None)
        st.session_state.pop("_repair_preview_df", None)
        st.session_state.pop("_repair_preview_log", None)
        st.rerun()

if "_repair_preview_df" in st.session_state and "_repair_preview_log" in st.session_state:
    with st.expander("Preview result (not applied yet)", expanded=True):
        pdf = st.session_state["_repair_preview_df"]
        plg = st.session_state["_repair_preview_log"]
        st.markdown(summarize_log(plg))
        st.dataframe(pdf.head(6), use_container_width=True, hide_index=True)

if st.button("Apply repairs", type="primary"):
    new_df, log = repair_dataframe(
        orig,
        required=req,
        missing_numeric=missing_numeric,
        missing_categorical=cat_miss,
        drop_duplicates=drop_dupes,
        extra_columns_to_drop=list(extra_drop),
        add_invalid_flag=add_invalid,
        remove_invalid_rows=remove_invalid,
        clip_numeric_percentiles=clip_on,
    )
    st.session_state[SK_REPAIR_WORKING_DF] = new_df
    st.session_state[SK_REPAIR_LAST_LOG] = log
    st.session_state.pop("_repair_preview_df", None)
    st.session_state.pop("_repair_preview_log", None)
    st.success(summarize_log(log))
    st.rerun()

if SK_REPAIR_LAST_LOG in st.session_state:
    st.info("Last apply: " + summarize_log(st.session_state[SK_REPAIR_LAST_LOG]))

st.divider()
st.subheader("Current table (first rows)")
st.dataframe(work.head(8), use_container_width=True, hide_index=True)

st.divider()
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("Continue to select model →", type="primary"):
        out = st.session_state[SK_REPAIR_WORKING_DF]
        name = st.session_state.get(SK_WIZARD_UPLOAD_NAME) or "repaired_data.csv"
        if st.session_state.get(SK_WIZARD_DATA_SOURCE) == "sample":
            name = "project_sample.csv"
        st.session_state[SK_WIZARD_UPLOAD_BYTES] = out.to_csv(index=False).encode("utf-8")
        st.session_state[SK_WIZARD_UPLOAD_NAME] = name
        st.session_state["detection_src_radio"] = LABEL_DATA_SOURCE_UPLOAD
        st.switch_page("views/03_Select_Model.py")
with b2:
    st.page_link("views/01_Select_Data.py", label="← Change data source")
with b3:
    st.page_link("views/11_Detection_Results.py", label="Skip to detection table (advanced) →")

if app_debug_mode():
    st.caption("Debug: `IOT_APP_DEBUG=1` or `?debug=1`.")

st.divider()
render_multipage_navigation_hint()
