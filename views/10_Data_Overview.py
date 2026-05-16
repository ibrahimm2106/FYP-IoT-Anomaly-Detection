"""
Multipage Streamlit: dataset identity, quality summary, and preview (Data Overview).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_core import (
    CAPTION_DATASET_SOURCES_SHORT,
    CAPTION_WHERE_EVALUATION_LIVES,
    DATA_PATH,
    ID_COLUMNS,
    LABEL_COLUMNS,
    MARKDOWN_DATASET_SOURCES_FOR_SCORING,
    MARKDOWN_WHERE_EVALUATION_LIVES,
    app_debug_mode,
    load_feature_column_meta,
    load_scoring_bundle,
    missing_label_columns_message,
    render_sidebar_metrics,
    render_sidebar_placeholder,
    try_read_processed_csv,
)
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page
from src.validation_helpers import data_quality_summary, label_quality_summary, missing_values_audit, schema_overview

st.set_page_config(
    page_title="Data · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
render_classic_page_header(
    title="Data overview",
    tagline="Inspect the project processed CSV: provenance, scale, labels, dtypes, and missing values before scoring.",
    bullets=(
        "Headline evaluation KPIs live on **Overview** after a successful score.",
        "Use **Detection results** or wizard steps 1–5 to produce the scored table this page can summarise.",
    ),
)

# CTU-IoT-23 is the standard citation for this capture family; link is stable for reports.
IOT23_DATASET_URL = "https://www.stratosphereips.org/datasets-ctu-13"


def feature_table_for_preview(df: pd.DataFrame, max_cols: int = 40) -> pd.DataFrame:
    """Prefer modelling columns for the preview; fall back to full frame if very narrow."""
    drop_cols = [c for c in LABEL_COLUMNS if c in df.columns]
    preview = df.drop(columns=drop_cols, errors="ignore")
    preview = preview.drop(columns=[c for c in ID_COLUMNS if c in preview.columns], errors="ignore")
    if preview.shape[1] == 0:
        return df.head(20)
    if preview.shape[1] > max_cols:
        preview = pd.concat([preview.iloc[:, :max_cols], df[[c for c in LABEL_COLUMNS if c in df.columns]]], axis=1)
    return preview.head(20)


def missing_values_table(df: pd.DataFrame, top_n: int = 25) -> tuple[pd.DataFrame, int]:
    """Columns with at least one missing value, sorted by descending count (shared helper with Detection upload)."""
    total = int(len(df))
    out = missing_values_audit(df, top_n=top_n)
    if out is None:
        return pd.DataFrame(), total
    return out, total


with st.container():
    st.caption(CAPTION_WHERE_EVALUATION_LIVES)
    with st.expander("Where evaluation evidence lives (detail)", expanded=False):
        st.markdown(MARKDOWN_WHERE_EVALUATION_LIVES)
    st.subheader("Where scoring data comes from")
    st.caption(CAPTION_DATASET_SOURCES_SHORT)
    with st.expander("Project CSV vs upload (detail)", expanded=False):
        st.markdown(MARKDOWN_DATASET_SOURCES_FOR_SCORING)

st.divider()
bundle, err = load_scoring_bundle()
partial_df, partial_err = (None, None)
if err is not None or bundle is None:
    st.warning(err or "Full scoring is unavailable (missing files or a runtime error). You may still see a CSV-only summary below.")
    st.markdown(
        "**Typical fix:** run `src/preprocess.py`, then `train.py`, then refresh this page. "
        "If the file opens but columns are wrong, read the red error text."
    )
    partial_df, partial_err = try_read_processed_csv()
    if partial_err:
        st.error(partial_err)
    if app_debug_mode():
        st.caption("Debug mode is on — check the Dashboard error for any traceback.")
    render_sidebar_placeholder("Live scoring unavailable", err)
    if partial_df is None:
        render_multipage_navigation_hint()
        st.stop()

if bundle is not None:
    render_sidebar_metrics(bundle)
    df = bundle.df
else:
    df = partial_df  # type: ignore[assignment]
    st.subheader("CSV-only mode")
    st.caption(
        "The table below still reflects your file. **Model input width** and live sidebar counts need a successful `train.py` run."
    )
    col_msg = missing_label_columns_message(df)
    if col_msg:
        st.error(col_msg)

if len(df) == 0:
    st.warning("This CSV has **no data rows** — there is nothing to summarise. Regenerate it with `src/preprocess.py`.")
    render_multipage_navigation_hint()
    st.stop()

labels_for_charts: pd.Series | None = bundle.labels if bundle is not None else None
if labels_for_charts is None and "label" in df.columns:
    labels_for_charts = df["label"].astype(str).str.strip()
transformed_dim = bundle.transformed_dim if bundle is not None else None

dataset_filename = DATA_PATH.name if DATA_PATH else "processed CSV"
dataset_path_display = DATA_PATH.as_posix() if DATA_PATH.is_file() else str(DATA_PATH)

st.markdown("##### Loaded table")
st.caption("Shape, labels, and quality checks for the CSV currently in use.")
st.subheader("Dataset provenance")
st.caption("Reference metadata for reports and markers.")
st.markdown(
    f"| Field | Value |\n"
    f"|:------|:------|\n"
    f"| **Working name** | `{dataset_filename}` |\n"
    f"| **Collection / corpus** | **CTU-IoT-23** — labelled Zeek connection logs for IoT malware research |\n"
    f"| **Typical use here** | Scenario capture **34 · subscenario 1**, exported as `conn.log.labeled` |\n"
    f"| **On-disk path** | `{dataset_path_display}` |\n"
    f"| **Further reading** | [{IOT23_DATASET_URL}]({IOT23_DATASET_URL}) |\n"
)
st.caption(
    "Official CTU-IoT-23 bundle names can differ slightly; this table refers to the CSV produced by your "
    "`src/preprocess.py` run."
)

meta = load_feature_column_meta()
raw_field_count: int | None = None
if meta:
    nums = meta.get("numeric") or []
    cats = meta.get("categorical") or []
    if nums or cats:
        raw_field_count = len(nums) + len(cats)

if raw_field_count is None:
    try:
        feats = df.drop(columns=[c for c in LABEL_COLUMNS if c in df.columns], errors="ignore")
        feats = feats.drop(columns=[c for c in ID_COLUMNS if c in feats.columns], errors="ignore")
        raw_field_count = int(feats.shape[1])
    except (KeyError, ValueError):
        raw_field_count = None

st.divider()
st.subheader("Scale and feature shape")
st.caption("Raw CSV shape vs the width of the vector after preprocessing.")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", f"{len(df):,}", help="Connection records in the processed CSV.")
m2.metric("Columns", f"{df.shape[1]:,}", help="Includes Zeek fields plus label columns where present.")
if transformed_dim is not None and transformed_dim > 0:
    m3.metric("Model input width", f"{transformed_dim:,}", help="Vector length after scaling and one-hot encoding.")
else:
    m3.metric(
        "Model input width",
        "—",
        help="Shown after a successful scoring pass (trained model + preprocessor).",
    )
if raw_field_count is not None:
    m4.metric("Raw features (pre–one-hot)", f"{raw_field_count:,}", help="Columns passed to `ColumnTransformer` after dropping labels and IDs.")
else:
    m4.metric("Raw features (pre–one-hot)", "—", help="Could not infer; ensure `feature_columns.pkl` exists or inspect the CSV.")
st.caption(
    "**Model input width** is the vector length after scaling and one-hot encoding. **Raw features** are Zeek columns before expansion."
)

st.divider()
st.subheader("Preprocessing chain")
st.markdown(
    "`src/preprocess.py` reads **Zeek `conn.log.labeled`**, repairs merged tail fields where needed, and writes this "
    "CSV. `train.py` then **standardises** numeric columns, **one-hot encodes** categoricals, and **drops** "
    "high-cardinality identifiers (e.g. IPs, `uid`) before fitting. The preprocessor is **fit on benign training rows "
    "only**; large reconstruction MSE at inference suggests behaviour that was rare under that fit."
)

st.divider()
st.subheader("Label distribution (`label`)")
st.caption("How often each high-level Zeek label appears in this file.")
if labels_for_charts is not None and len(labels_for_charts) == len(df):
    vc = labels_for_charts.value_counts()
    chart_df = vc.rename_axis("label").reset_index(name="count")
    st.bar_chart(chart_df.set_index("label"))
    st.caption(
        "**Figure:** counts per Zeek `label`. For evaluation tables elsewhere, any value other than `Benign` "
        "(case-insensitive) is treated as malicious."
    )
else:
    st.warning("The `label` column is missing or length-mismatched; a bar chart cannot be drawn.")

st.divider()
st.subheader("Missing values audit")
missing_df, n_rows = missing_values_table(df)
if missing_df.empty:
    st.markdown("**Completeness:** no missing cells in the snapshot loaded by pandas.")
else:
    n_with_gaps = int(df.isna().any().sum())
    st.metric("Columns with nulls", f"{n_with_gaps:,}", help=f"Of {df.shape[1]:,} columns, count with ≥1 null (`isna()`).")
    st.dataframe(missing_df, use_container_width=True, hide_index=True)
    st.caption(
        f"Sorted by missing count (showing up to {len(missing_df)} columns). "
        f"Percentages are **row shares** (N = {n_rows:,}) for that column’s nulls."
    )

st.divider()
st.subheader("Validation checks")
st.caption("Quick QA diagnostics before you interpret model outputs.")
q1, q2, q3, q4 = st.columns(4)
qa = data_quality_summary(df)
lbl = label_quality_summary(df)
q1.metric("Duplicate rows", f"{qa['duplicate_rows']:,}", help="Exact duplicate full rows in the loaded dataframe.")
q2.metric("Unique `label` values", "—" if lbl["unique_labels"] is None else f"{int(lbl['unique_labels']):,}")
q3.metric("Benign rows", "—" if lbl["benign_rows"] is None else f"{int(lbl['benign_rows']):,}")
q4.metric("Non-benign rows", "—" if lbl["non_benign_rows"] is None else f"{int(lbl['non_benign_rows']):,}")

if qa["invalid_numeric_cells"] > 0 or df.select_dtypes(include=["number"]).shape[1] > 0:
    st.caption(
        f"Numeric stability check: **{qa['invalid_numeric_cells']:,}** non-finite values (`NaN`/`±inf`) across "
        f"**{df.select_dtypes(include=['number']).shape[1]}** numeric columns."
    )
else:
    st.caption("Numeric stability check skipped: no numeric columns detected by pandas.")

st.divider()
st.subheader("Top Zeek `detailed-label` values")
st.caption("Finer-grained Zeek subtype strings (when the column exists).")
if "detailed-label" in df.columns:
    detail = df["detailed-label"].astype(str).str.strip()
    top_detail = detail.value_counts().head(12)
    st.dataframe(
        top_detail.rename_axis("detailed-label").reset_index(name="count"),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("**Table:** twelve most frequent subtype strings from Zeek (qualitative context for the report).")
else:
    st.caption("Column `detailed-label` is absent; subtype frequencies are skipped.")

st.divider()
st.subheader("Sample records")
st.caption("A small slice of rows for a quick sanity check (wide tables may hide some ID columns in the preview).")
try:
    preview = feature_table_for_preview(df)
    st.dataframe(preview, use_container_width=True)
    st.caption(
        "**Table:** up to twenty rows; labels and common ID fields may be omitted when the feature grid is wide "
        f"(about forty feature columns plus labels). Source file: `{dataset_filename}`."
    )
except (KeyError, ValueError, TypeError) as exc:
    st.warning(f"Preview could not be built ({type(exc).__name__}); showing raw head instead.")
    st.dataframe(df.head(12), use_container_width=True)
    st.caption("Fallback: first twelve rows of the full frame.")

with st.expander("Column dtypes (reference table)", expanded=False):
    dtype_df = schema_overview(df)
    st.dataframe(dtype_df, use_container_width=True, hide_index=True)
    st.caption("**Table:** pandas dtypes on load; the model consumes scaled numeric and encoded categorical columns.")

if "uid" in df.columns:
    dup = int(df["uid"].duplicated().sum())
    st.caption(f"Duplicate `uid` values in this export: **{dup:,}** (informational; not used as a model feature).")

render_multipage_navigation_hint()
