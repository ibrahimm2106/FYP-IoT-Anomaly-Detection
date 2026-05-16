"""
Multipage Streamlit: reconstruction scores, thresholding, ranked examples, CSV upload/export.
"""

from __future__ import annotations

import hashlib
import traceback

import numpy as np
import pandas as pd
import streamlit as st

from src.app_core import (
    DATA_SOURCE_CHOICES,
    LABEL_DATA_SOURCE_PROJECT,
    LABEL_DATA_SOURCE_UPLOAD,
    render_restore_training_pipeline_ui,
    ScoringBundle,
    SK_WIZARD_UPLOAD_BYTES,
    SK_WIZARD_UPLOAD_NAME,
    app_debug_mode,
    check_model_artefacts,
    classification_report_markdown,
    friendly_scoring_error,
    load_preprocessor,
    load_scoring_bundle,
    parse_csv_bytes,
    render_metrics_export_buttons,
    render_sidebar_metrics,
    render_sidebar_placeholder,
    score_dataframe,
    validate_dataframe_for_scoring,
)
from src.evaluation_helpers import bundle_has_labels, contingency_matrix_dataframe, evaluation_metrics_from_bundle
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page
from src.validation_helpers import missing_values_audit

st.set_page_config(
    page_title="Results · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
render_classic_page_header(
    title="Detection results",
    tagline="Score the project CSV or a validated upload; browse ranked rows, flags, metrics exports, and optional charts.",
    bullets=(
        "Prefer **Select data** (wizard step 1) first for preview and schema checks.",
        "Batch scoring only — not live packet capture.",
    ),
)
st.caption(
    "**Flow:** pick data source → adjust filters → download. **Metrics** CSV/JSON describe the **full** scored run; "
    "the anomaly CSV follows your table filters."
)

# Session keys for upload scoring (keep names stable for bookmarked sessions).
SK_UPLOAD_BUNDLE = "detection_upload_bundle"
SK_UPLOAD_FILENAME = "detection_upload_filename"
SK_UPLOAD_DIGEST = "_det_upload_sha256"
SK_UPLOAD_SCORE_ERROR = "detection_upload_score_error"
SK_DATA_SOURCE_PREV = "_detection_data_source_prev"


def _source_is_project(selection: str) -> bool:
    """Return whether the selected source is the project CSV."""
    return selection == LABEL_DATA_SOURCE_PROJECT


def _results_export_stub(selection: str) -> str:
    """Return the filename stem for result exports."""
    return "project_results" if _source_is_project(selection) else "upload_results"


def _clear_upload_session_keys() -> None:
    """Clear upload-specific scoring state when switching back to project data."""
    for key in (
        SK_UPLOAD_BUNDLE,
        SK_UPLOAD_FILENAME,
        SK_UPLOAD_DIGEST,
        SK_UPLOAD_SCORE_ERROR,
        SK_WIZARD_UPLOAD_BYTES,
        SK_WIZARD_UPLOAD_NAME,
    ):
        st.session_state.pop(key, None)


def _render_label_agreement_expander(*, bundle: ScoringBundle, threshold: float) -> None:
    """Render the compact labels-versus-flags evaluation expander."""
    with st.expander("Labels vs flags — quick evaluation", expanded=False):
        st.markdown(
            "**Reconstruction MSE** measures how well the model reconstructs each row after benign-only training "
            "(higher = poorer fit). It is **not** a calibrated attack probability. A row is **flagged** when "
            f"**MSE > {threshold:.6f}** (from `models/threshold.txt`)."
        )
        st.subheader("Contingency table")
        if bundle_has_labels(bundle):
            st.caption(
                "**Malicious** = any `label` other than `Benign` (case-insensitive). Each cell is a **connection count** "
                "for this scoring run (same layout as the Dashboard)."
            )
        else:
            st.caption("No label column detected for this run; confusion-style evaluation values are unavailable.")
        st.dataframe(contingency_matrix_dataframe(bundle), use_container_width=True)
        ev = evaluation_metrics_from_bundle(bundle)
        precision, recall, f1, pr_auc = ev["precision"], ev["recall"], ev["f1_score"], ev["pr_auc"]
        m1, m2, m3, m4 = st.columns(4)
        na = "—"
        m1.metric(
            "Precision",
            f"{precision:.4f}" if precision is not None else na,
            help="TP / (TP + FP): fraction of flagged rows with a non-benign label.",
        )
        m2.metric(
            "Recall",
            f"{recall:.4f}" if recall is not None else na,
            help="TP / (TP + FN): fraction of malicious-labelled rows flagged at this threshold.",
        )
        m3.metric(
            "F1-score",
            f"{f1:.4f}" if f1 is not None else na,
            help="Harmonic mean of precision and recall when both are defined.",
        )
        m4.metric(
            "PR-AUC",
            f"{pr_auc:.4f}" if pr_auc is not None else na,
            help="Average precision for ranking by MSE (`sklearn.metrics.average_precision_score`); not tied to this threshold alone.",
        )


# Zeek / IoT-23 exports: prefer these for human-readable row identity in demos.
IDENTIFIER_COLUMNS = ("ts", "uid", "id.orig_h", "id.resp_h")
LABEL_DISPLAY_COLUMNS = ("label", "detailed-label")

EXPORT_COLUMN_RENAMES: dict[str, str] = {
    "record_index": "csv_row_index",
    "ts": "timestamp",
    "uid": "connection_uid",
    "id.orig_h": "origin_host_ip",
    "id.orig_p": "origin_port",
    "id.resp_h": "response_host_ip",
    "id.resp_p": "response_port",
    "label": "true_label",
    "detailed-label": "true_label_detail",
    "reconstruction_mse": "anomaly_score_reconstruction_mse",
    "anomaly_flag": "anomaly_flag",
}


def _pick_columns(df: pd.DataFrame, candidates: tuple[str, ...]) -> list[str]:
    """Return candidate columns that exist in a dataframe."""
    return [c for c in candidates if c in df.columns]


def build_results_view(
    df: pd.DataFrame,
    errors: np.ndarray,
    flagged: np.ndarray,
    *,
    only_flagged: bool,
    top_n: int,
) -> pd.DataFrame:
    """Return a display/export frame: sorted by reconstruction MSE descending, capped at top_n."""
    n = len(df)
    if n == 0:
        return pd.DataFrame()
    idx = np.arange(n, dtype=np.int64)
    mse = np.asarray(errors, dtype=np.float64)
    fl = np.asarray(flagged, dtype=bool)

    if only_flagged:
        idx = idx[fl[idx]]

    if idx.size == 0:
        return pd.DataFrame()

    order = np.argsort(mse[idx])[::-1]
    cap = max(0, min(int(top_n), len(idx)))
    idx = idx[order[:cap]]

    out = df.iloc[idx].copy()
    out.insert(0, "record_index", idx.astype(np.int64))
    out["reconstruction_mse"] = mse[idx]
    out["anomaly_flag"] = fl[idx]
    return out


def reorder_columns_for_display(frame: pd.DataFrame) -> pd.DataFrame:
    """Put identifiers first, then labels, then scores and flag."""
    if frame.empty:
        return frame
    front = ["record_index"]
    front += [c for c in IDENTIFIER_COLUMNS if c in frame.columns]
    front += [c for c in LABEL_DISPLAY_COLUMNS if c in frame.columns]
    tail = ["reconstruction_mse", "anomaly_flag"]
    middle = [c for c in frame.columns if c not in front + tail]
    ordered = [c for c in front + middle + tail if c in frame.columns]
    return frame.loc[:, ordered]


def _export_column_header(original: str) -> str:
    """Map internal result columns to reader-friendly export headers."""
    if original in EXPORT_COLUMN_RENAMES:
        return EXPORT_COLUMN_RENAMES[original]
    return original.replace(".", "_").replace("-", "_")


def ordered_columns_for_export(columns: list[str]) -> list[str]:
    """Row index and IDs first, true labels, remaining Zeek features (sorted), then score and flag last."""
    colset = set(columns)
    lead = ("record_index", "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p")
    front = [c for c in lead if c in colset]
    labs = [c for c in LABEL_DISPLAY_COLUMNS if c in colset]
    tail = [c for c in ("reconstruction_mse", "anomaly_flag") if c in colset]
    used = set(front) | set(labs) | set(tail)
    middle = sorted(c for c in columns if c not in used)
    return front + labs + middle + tail


def build_clean_export_dataframe(filtered: pd.DataFrame) -> pd.DataFrame:
    """
    Readable CSV: same rows as the filtered table, renamed columns, Yes/No flag.

    Does not alter `filtered` or any scoring arrays.
    """
    if filtered.empty:
        return filtered.copy()
    out = filtered.copy()
    out["anomaly_flag"] = out["anomaly_flag"].map({True: "Yes", False: "No"})
    cols = ordered_columns_for_export(list(out.columns))
    out = out.loc[:, cols]
    out.columns = [_export_column_header(c) for c in cols]
    return out


def results_table_column_config() -> dict:
    """Streamlit column_config for anomaly results tables (keys must match dataframe columns)."""
    return {
        "record_index": st.column_config.NumberColumn(
            "Row #",
            help="Zero-based row index in the scored table (same order as the project CSV or your upload).",
        ),
        "reconstruction_mse": st.column_config.NumberColumn(
            "Reconstruction MSE",
            format="%.6f",
            help="Mean squared error between input and reconstruction; higher = less like benign training traffic.",
        ),
        "anomaly_flag": st.column_config.CheckboxColumn(
            "Flagged",
            help="Checked when MSE is strictly above the saved validation threshold.",
        ),
    }


model_err = check_model_artefacts()
if model_err:
    st.error(model_err)
    render_restore_training_pipeline_ui()
    render_sidebar_placeholder("Model files missing", model_err)
    if app_debug_mode():
        st.warning("Debug mode is on — check the Dashboard for any traceback.")
    render_multipage_navigation_hint()
    st.stop()

st.markdown("##### Data source")
st.caption("Project file on disk, or a one-off UTF-8 upload scored with the same saved model and threshold.")
data_source = st.radio(
    "Which file should we score?",
    DATA_SOURCE_CHOICES,
    horizontal=True,
    key="detection_src_radio",
    help="Project CSV uses `data/processed/ctu_iot_34_1.csv`. Upload requires the same columns the model was trained on. "
    "Use **Select data** (step 1) to pick a file with preview and checks.",
)

prev_source = st.session_state.get(SK_DATA_SOURCE_PREV)
if prev_source is not None and prev_source != data_source and _source_is_project(data_source):
    _clear_upload_session_keys()
st.session_state[SK_DATA_SOURCE_PREV] = data_source
st.divider()

bundle: ScoringBundle | None = None
metrics_source_label = "project_processed_csv"

if _source_is_project(data_source):
    bundle, disk_err = load_scoring_bundle()
    if disk_err or bundle is None:
        st.error(disk_err or "Scoring the project CSV did not complete.")
        render_restore_training_pipeline_ui()
        st.info(
            "**Tip:** if the project CSV is missing but `models/` is complete, switch to **Upload — my own compatible CSV** "
            "and score a Zeek-style table that matches the trained schema."
        )
        render_sidebar_placeholder("Project CSV not scored", disk_err)
        render_multipage_navigation_hint()
        st.stop()
else:
    st.subheader("Upload path — check file, then score")
    st.caption(
        "**UTF-8 CSV** required. The file must include **every feature column** "
        "the saved preprocessor expects (same layout as this project’s processed Zeek export). "
        "**`label`** and **`detailed-label`** are optional but recommended for evaluation. "
        "Everything runs **in memory** — nothing is written under `data/` or `models/`."
    )
    wizard_bytes = st.session_state.get(SK_WIZARD_UPLOAD_BYTES)
    wizard_name = st.session_state.get(SK_WIZARD_UPLOAD_NAME)
    if wizard_bytes is not None:
        c_w1, c_w2 = st.columns((4, 1))
        with c_w1:
            st.success(
                f"Using file from **Select data**: `{wizard_name or 'upload.csv'}`. "
                "Replace it below or clear to choose again.",
            )
        with c_w2:
            if st.button("Clear wizard file", key="detection_clear_wizard_upload"):
                st.session_state.pop(SK_WIZARD_UPLOAD_BYTES, None)
                st.session_state.pop(SK_WIZARD_UPLOAD_NAME, None)
                st.rerun()

    uploaded = st.file_uploader(
        "CSV file",
        type=["csv"],
        accept_multiple_files=False,
        key="detection_csv_upload",
        help="Drag and drop or browse. Only `.csv` files are accepted.",
    )
    if uploaded is not None:
        st.session_state.pop(SK_WIZARD_UPLOAD_BYTES, None)
        st.session_state.pop(SK_WIZARD_UPLOAD_NAME, None)
        wizard_bytes = None

    if uploaded is None and wizard_bytes is None:
        st.info(
            "Choose a CSV above, or go to **Select data** (step 1) for preview and checks first.",
        )
        render_sidebar_placeholder("Waiting for a file", "Pick a CSV, then click Run scoring.")
        render_multipage_navigation_hint()
        st.stop()

    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        upload_name = uploaded.name or "upload.csv"
    else:
        raw_bytes = wizard_bytes
        upload_name = str(wizard_name or "upload.csv")
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if st.session_state.get(SK_UPLOAD_DIGEST) != digest:
        st.session_state.pop(SK_UPLOAD_BUNDLE, None)
        st.session_state.pop(SK_UPLOAD_FILENAME, None)
        st.session_state.pop(SK_UPLOAD_SCORE_ERROR, None)
    st.session_state[SK_UPLOAD_DIGEST] = digest

    df_upload, parse_err = parse_csv_bytes(raw_bytes)
    if df_upload is None or parse_err:
        st.error(parse_err or "Could not read the uploaded file.")
        render_sidebar_placeholder("Could not read CSV", parse_err)
        render_multipage_navigation_hint()
        st.stop()

    st.markdown(f"**Selected file:** `{upload_name}`")
    c_rows, c_cols, c_size = st.columns(3)
    c_rows.metric("Rows", f"{len(df_upload):,}")
    c_cols.metric("Columns", f"{df_upload.shape[1]:,}")
    c_size.metric(
        "File size",
        f"{len(raw_bytes) / 1024:.1f} KiB" if len(raw_bytes) >= 1024 else f"{len(raw_bytes)} bytes",
    )

    st.subheader("Preview (first 8 rows)")
    st.dataframe(df_upload.head(8), use_container_width=True, hide_index=True)

    st.subheader("Missing values — top columns")
    miss_df = missing_values_audit(df_upload, top_n=25)
    if miss_df is None:
        st.caption("No missing cells detected with `pandas.isna()` on the loaded frame.")
    else:
        st.dataframe(miss_df, use_container_width=True, hide_index=True)
        st.caption("Up to 25 columns with the most nulls; **missing_pct** is the percentage of rows where that column is null.")

    preprocessor = load_preprocessor()
    schema_ok, schema_msg = validate_dataframe_for_scoring(df_upload, preprocessor)
    if not schema_ok:
        st.warning(schema_msg or "This file does not match the model’s expected schema.")
        st.error(
            "**This file cannot be scored yet.** Fix the issues in the yellow box, or align your CSV with this project’s "
            "`src/preprocess.py` output."
        )
        render_sidebar_placeholder("Schema check failed", schema_msg)
        render_multipage_navigation_hint()
        st.stop()

    st.success("Schema check passed — feature columns match what this preprocessor expects.")
    if "label" not in df_upload.columns:
        st.info("`label` not found: scoring/export works, but precision/recall/F1/PR-AUC and confusion counts are unavailable.")
    last_score_err = st.session_state.get(SK_UPLOAD_SCORE_ERROR)
    if last_score_err:
        st.error(f"**Last scoring attempt failed:** {last_score_err}")

    run_scoring = st.button("Run scoring on this file", type="primary", help="Uses the same model, preprocessor, and threshold as the project pipeline.")
    if run_scoring:
        st.session_state.pop(SK_UPLOAD_SCORE_ERROR, None)
        try:
            scored_bundle = score_dataframe(df_upload)
            st.session_state[SK_UPLOAD_BUNDLE] = scored_bundle
            st.session_state[SK_UPLOAD_FILENAME] = upload_name
            st.rerun()
        except ValueError as exc:
            st.session_state[SK_UPLOAD_SCORE_ERROR] = str(exc)
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            msg = friendly_scoring_error(exc)
            st.session_state[SK_UPLOAD_SCORE_ERROR] = msg
            st.error(msg)
            if app_debug_mode():
                st.code(traceback.format_exc(), language="text")
        render_multipage_navigation_hint()
        st.stop()

    bundle = st.session_state.get(SK_UPLOAD_BUNDLE)
    metrics_source_label = f"upload:{st.session_state.get(SK_UPLOAD_FILENAME, upload_name)}"
    if bundle is None:
        st.info("Click **Run scoring on this file** to compute MSE, flags, and evaluation metrics for every row.")
        render_sidebar_placeholder("Not scored yet", "Run scoring after the schema check passes.")
        render_multipage_navigation_hint()
        st.stop()

if bundle is None:
    st.error("Something went wrong: no scoring results are loaded. Please reload the page.")
    render_multipage_navigation_hint()
    st.stop()

threshold = bundle.threshold

render_sidebar_metrics(bundle)
if not _source_is_project(data_source):
    st.sidebar.caption(f"**Scored from upload:** `{st.session_state.get(SK_UPLOAD_FILENAME, '—')}`")

errors = bundle.errors
flagged = bundle.flagged
n_rows = len(bundle.df)
n_flagged = int(flagged.sum())
ev = evaluation_metrics_from_bundle(bundle)
n_malicious = ev["malicious_count"]

with st.container(border=True):
    st.markdown("##### Start here")
    st.markdown(
        "- **1.** Confirm the **data source** above (project CSV or upload).\n"
        "- **2.** Use **filters** and the table to inspect high-MSE rows; adjust the row cap if the table is slow.\n"
        "- **3.** Download **anomaly CSV** (filtered table) and/or **metrics CSV/JSON** (full run) when ready."
    )

st.markdown("##### At a glance — this scoring run")
h1, h2, h3, h4, h5 = st.columns(5)
h1.metric("Rows scored", f"{n_rows:,}", help="Total connections in this scoring run.")
h2.metric("Rows flagged", f"{n_flagged:,}", help="Count with MSE strictly above the saved threshold.")
h3.metric(
    "Non-benign labels",
    "n/a" if n_malicious is None else f"{int(n_malicious):,}",
    help="Requires `label`; values other than benign are counted as malicious.",
)
h4.metric("MSE threshold", f"{threshold:.6f}", help="Cut-off from `models/threshold.txt` (benign validation percentile).")
h5.metric("Input width", f"{bundle.transformed_dim:,}", help="Length of the preprocessed feature vector.")

st.divider()
st.subheader("Scored connections — main table")
st.caption(
    "After filters, rows are sorted by **descending MSE**. **Row #** is zero-based in the scored table. "
    "The anomaly CSV download matches exactly what you see here."
)

max_top = min(10_000, max(1, n_rows))
default_top = min(40, max_top)

st.markdown("##### Table filters")
fc1, fc2, fc3 = st.columns((2, 2, 2))
with fc1:
    only_flagged = st.checkbox(
        "Show flagged rows only",
        value=False,
        help="If checked, only rows with MSE strictly above the saved threshold are kept before sorting and capping.",
    )
with fc2:
    top_n = st.number_input(
        "Row cap (highest MSE first)",
        min_value=1,
        max_value=max_top,
        value=default_top,
        step=1,
        help="After optional “flagged only”, keep at most this many rows, highest MSE first (large tables stay responsive).",
    )
with fc3:
    id_hint = ", ".join(_pick_columns(bundle.df, IDENTIFIER_COLUMNS)) or "none in this table"
    st.caption(f"**IDs included in CSV export (when present):** {id_hint}.")

extra_filter_cols = st.columns((2, 2))
with extra_filter_cols[0]:
    label_options = ["All labels"]
    if "label" in bundle.df.columns:
        labels_unique = sorted(bundle.df["label"].astype(str).str.strip().unique().tolist())
        label_options += labels_unique
    selected_label = st.selectbox(
        "Filter by Zeek `label`",
        label_options,
        index=0,
        help="Optional semantic filter before sorting by MSE.",
    )
with extra_filter_cols[1]:
    e_min = float(np.min(errors)) if len(errors) else 0.0
    e_max = float(np.max(errors)) if len(errors) else 0.0
    mse_range = st.slider(
        "MSE range filter",
        min_value=e_min,
        max_value=e_max if e_max > e_min else e_min + 1e-9,
        value=(e_min, e_max if e_max > e_min else e_min + 1e-9),
        help="Keep rows whose reconstruction MSE is within this interval.",
    )

display_df = build_results_view(
    bundle.df,
    errors,
    flagged,
    only_flagged=only_flagged,
    top_n=int(top_n),
)
display_df = reorder_columns_for_display(display_df)
if selected_label != "All labels" and "label" in display_df.columns and not display_df.empty:
    display_df = display_df[display_df["label"].astype(str).str.strip() == selected_label]
if not display_df.empty:
    display_df = display_df[
        (display_df["reconstruction_mse"] >= mse_range[0]) & (display_df["reconstruction_mse"] <= mse_range[1])
    ]

st.divider()
with st.expander("Record drilldown (optional)", expanded=False):
    st.caption("Inspect every field for one row from the filtered table.")
    if display_df.empty:
        st.caption("No rows available for drilldown with current filters.")
    else:
        drill_idx = st.number_input(
            "Select row index from filtered table",
            min_value=0,
            max_value=max(0, len(display_df) - 1),
            value=0,
            step=1,
            help="Shows all fields for one selected record in the current filtered table.",
        )
        row = display_df.iloc[int(drill_idx)]
        st.dataframe(
            pd.DataFrame({"field": row.index.astype(str), "value": row.values}),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader("Downloads")
st.caption(
    "**Anomaly results CSV** — friendly column names and Yes/No flags for the **rows in the table above** (filters apply). "
    "**Metrics CSV / JSON** — one summary for the **entire** scored dataset (ignores the row cap)."
)

if display_df.empty:
    st.warning(
        "No rows match the current filters — for example, **Show flagged rows only** may hide everything if nothing is flagged. "
        "Adjust filters to bring rows back into the table."
    )
    st.info("You can still download **metrics** — they always describe the **full** scored dataset.")
else:
    cfg = results_table_column_config()
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={k: v for k, v in cfg.items() if k in display_df.columns},
    )

    export_csv_df = build_clean_export_dataframe(display_df)
    csv_bytes = export_csv_df.to_csv(index=False).encode("utf-8")
    stub = _results_export_stub(data_source)
    st.download_button(
        label="Download anomaly table (CSV)",
        data=csv_bytes,
        file_name=f"{stub}_filtered.csv",
        mime="text/csv",
        help="UTF-8 CSV of the rows currently shown in the table (same filters and column renames).",
        key="detection_export_results_csv",
    )
    st.caption(f"**Rows in this export:** {len(display_df):,} · **Columns:** {len(export_csv_df.columns)}")

render_metrics_export_buttons(
    bundle,
    data_source_label=metrics_source_label,
    key_prefix="detection_metrics_export",
)

_render_label_agreement_expander(bundle=bundle, threshold=threshold)

with st.expander("Top anomalies and threshold context (optional)", expanded=False):
    st.caption("Quick analyst context around the current decision threshold.")
    t1, t2, t3 = st.columns(3)
    above_margin = float(np.mean(errors > (threshold * 1.10))) if len(errors) else 0.0
    near_band = float(np.mean((errors >= threshold * 0.95) & (errors <= threshold * 1.05))) if len(errors) else 0.0
    t1.metric("Rows > threshold", f"{int((errors > threshold).sum()):,}")
    t2.metric("Rows > 110% threshold", f"{above_margin * 100:.2f}%")
    t3.metric("Rows in +/-5% band", f"{near_band * 100:.2f}%")
    top_k = min(10, len(bundle.df))
    if top_k > 0:
        top_rows = build_results_view(bundle.df, errors, flagged, only_flagged=False, top_n=top_k)
        top_rows = reorder_columns_for_display(top_rows)
        st.dataframe(top_rows, use_container_width=True, hide_index=True)
        st.caption("Top rows by reconstruction MSE, independent of interactive filters.")

with st.expander("Reporting export — Markdown appendix (optional)", expanded=False):
    st.caption("Download a concise markdown report suitable for appendices or viva evidence.")
    report_md = classification_report_markdown(bundle, data_source_label=metrics_source_label)
    st.download_button(
        label="Download run report (Markdown)",
        data=report_md.encode("utf-8"),
        file_name=f"detection_report_{_results_export_stub(data_source)}.md",
        mime="text/markdown",
        help="Narrative summary with threshold, metrics, and confusion counts for this run.",
    )

st.divider()
with st.expander("Optional charts — MSE distribution", expanded=False):
    if len(errors) == 0:
        st.warning("No scores were produced (empty input).")
    else:
        q = np.quantile(errors, [0.0, 0.5, 0.9, 0.99, 1.0])
        summary = pd.DataFrame(
            {
                "Statistic": ["Minimum", "Median", "90th %ile", "99th %ile", "Maximum"],
                "Reconstruction MSE": [float(q[0]), float(q[1]), float(q[2]), float(q[3]), float(q[4])],
            }
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.caption(f"Quantiles over all scored rows. Threshold: **{threshold:.6f}**.")
        counts, edges = np.histogram(errors, bins=40)
        hist_df = pd.DataFrame({"Bin start (MSE)": edges[:-1], "Connection count": counts}).set_index("Bin start (MSE)")
        st.bar_chart(hist_df)
        st.caption("Equal-width bins on this scoring run.")

render_multipage_navigation_hint()
