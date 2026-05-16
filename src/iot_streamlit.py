"""
Shared Streamlit helpers: paths, cached scoring, and sidebar context.

**Layout:** ``render_app_chrome()`` injects global CSS from ``ui_theme``. Wizard
navigation uses ``WIZARD_STEP_PAGES`` from ``iot_constants`` + ``render_wizard_stepper()``.
``compute_scoring`` / ``score_dataframe`` call ``scoring_engine.build_scoring_bundle``;
session key **strings** live in ``src/iot_constants.py``; paths in ``src/iot_paths.py``.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from tensorflow import keras

from src.artifact_loaders import (
    list_keras_model_paths as list_keras_model_paths_disk,
    load_feature_column_meta,
    load_preprocessor_from_disk,
    read_processed_csv,
    read_threshold_mse,
)
from src.iot_constants import (
    DATA_SOURCE_CHOICES,
    LABEL_DATA_SOURCE_PROJECT,
    LABEL_DATA_SOURCE_UPLOAD,
    PROJECT_ROOT,
    SK_REPAIR_LAST_LOG,
    SK_REPAIR_ORIGINAL_DF,
    SK_REPAIR_WORKING_DF,
    SK_WIZARD_DATA_SOURCE,
    SK_WIZARD_MODEL_PATH,
    SK_WIZARD_SESSION_THRESHOLD,
    SK_WIZARD_UPLOAD_BYTES,
    SK_WIZARD_UPLOAD_NAME,
    WIZARD_STEP_PAGES,
)
from src.iot_paths import (
    DATA_PATH,
    FEATURE_COLUMNS_PATH,
    ID_COLUMNS,
    LABEL_COLUMNS,
    MODEL_PATH,
    PREPROCESSOR_PATH,
    THRESHOLD_PATH,
    coerce_hdf5_weights_path,
    default_disk_model_path,
)
from src.scoring_engine import (
    build_scoring_bundle,
    expected_feature_column_order,
    validate_dataframe_for_scoring,
)
from src.scoring_reports import (
    classification_report_markdown,
    metrics_filename_stub,
    metrics_report_csv_bytes,
    metrics_report_json_bytes,
    metrics_report_dict,
)
from src.scoring_types import (
    EVAL_METRIC_UNAVAILABLE,
    ScoringBundle,
    bundle_has_labels,
    confusion_matrix_long_dataframe,
    contingency_matrix_dataframe,
    evaluation_metrics_from_bundle,
    precision_recall_f1_from_counts,
    reconstruction_mse,
)
from src.table_io import missing_values_top_columns, parse_csv_bytes, try_read_processed_csv
from src.user_messages import friendly_scoring_error
from src.ui_theme import IOT_APP_STYLESHEET

# Small private constants keep repeated UI/session decisions in one place.
DEBUG_TRUE_VALUES = frozenset({"1", "true", "yes"})
KERAS_MODEL_SUFFIXES = frozenset({".keras", ".h5"})

# Shared copy for missing-artefact states (keep multipage instructions identical).
MARKDOWN_RESTORE_TRAINING_PIPELINE = (
    "**Restore the training pipeline**\n\n"
    "1. Run `src/preprocess.py` so `data/processed/ctu_iot_34_1.csv` exists.\n"
    "2. Run `train.py` so `models/` contains `autoencoder.h5` (weights), `preprocessor.pkl`, and `threshold.txt`.\n"
    "3. Reload the app in your browser.\n"
)

MARKDOWN_WHERE_EVALUATION_LIVES = (
    "**Evaluation evidence:** headline metrics (precision, recall, F1, **PR-AUC**), contingency counts, and metric "
    "interpretation are on the **Dashboard** (home). The **Detection results** page adds the ranked per-connection "
    "table, CSV export, and the same confusion-style counts for convenience."
)

# Clarifies artefact scope for examiners (batch vs live monitoring; where data comes from; what evaluation applies to).
MARKDOWN_ARTEFACT_BATCH_SCORING = (
    "**How this artefact relates to “monitoring”:** the model performs **batch scoring**, not live capture from a "
    "network interface. Each session loads a **table of Zeek-style connections** (see below for data sources), runs "
    "every row through the saved preprocessor and autoencoder, and stores reconstruction MSE and flags. "
    "**Reload** the app or change the processed CSV / model files on disk to refresh scores (cached from file mtimes)."
)

MARKDOWN_DATASET_SOURCES_FOR_SCORING = (
    "**Two ways to supply data for anomaly scoring:**\n\n"
    "1. **Project CSV** — `data/processed/ctu_iot_34_1.csv`, produced by `src/preprocess.py` (summarised on this page).\n"
    "2. **Upload** — on **Detection results**, choose *Upload — my own compatible CSV* and provide a UTF-8 file "
    "with the same feature columns the preprocessor was trained on. `label` / `detailed-label` are optional "
    "(needed for supervised-style evaluation metrics)."
)

MARKDOWN_EVALUATION_SCOPE = (
    "**Evaluation scope:** precision, recall, F1, **PR-AUC**, and the contingency table are computed on the "
    "**same connection rows scored in this app session** (project CSV or a successful upload). They measure agreement "
    "between **reconstruction-based flags** and Zeek **labels** on that table — **illustrative** for your report, not a "
    "substitute for a separately frozen hold-out benchmark unless you explicitly load that file here."
)

CAPTION_EVALUATION_SCOPE_SHORT = (
    "Numbers below describe **this session’s** scored rows only — useful for the report, not a frozen benchmark."
)

CAPTION_EVALUATION_ROWS_SCOPE = (
    "Metrics and the table below refer only to **connections scored in this session** (aligned with **Detection results**)."
)

# One-line defaults; long prose stays in MARKDOWN_* or expanders.
CAPTION_ARTEFACT_BATCH_SCORING = (
    "This app scores whole CSVs in your browser session — not live network capture. "
    "Reload the page or change files on disk to refresh cached scores."
)

CAPTION_WHERE_EVALUATION_LIVES = (
    "Headline metrics: **Overview** dashboard. Ranked rows and CSV exports: **Detection Results** under **Advanced Tools**."
)

CAPTION_DATASET_SOURCES_SHORT = (
    "Use the **project processed CSV** on disk, or an **uploaded** UTF-8 table with the same feature columns as training."
)

CAPTION_HOME_START_HERE = (
    "For a first run: **steps 1 → 5**, then return here for KPIs. Use **Advanced Tools** in the sidebar when you need depth."
)

CAPTION_SELECT_DATA_LEAD = (
    "Pick a data source, review **Preview** and **Checks**, then press **Continue to repair data**."
)

CAPTION_PREPARE_MODEL_LEAD = (
    "Confirm the saved **model file**, **MSE cut-off**, and **feature columns**, then open **Test model**."
)


def _is_truthy_flag(value: Any) -> bool:
    """Return ``True`` for the small set of values accepted by app debug flags."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip().lower() in DEBUG_TRUE_VALUES


def _session_value(key: str, default: Any = None) -> Any:
    """Read Streamlit session state without failing in test or script contexts."""
    try:
        return st.session_state.get(key, default)
    except (RuntimeError, AttributeError):
        return default


def _normalise_project_path(raw_path: str | Path) -> Path:
    """Resolve a user/session path against the repository root when needed."""
    candidate = Path(str(raw_path))
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def _labels_from_dataframe(df: pd.DataFrame) -> pd.Series | None:
    """Return stripped Zeek labels when available, otherwise ``None``."""
    if "label" not in df.columns:
        return None
    return df["label"].astype(str).str.strip()


def _feature_columns_or_raise(preprocessor: Any) -> list[str]:
    """Resolve the trained feature order or raise the user-facing recovery text."""
    columns = expected_feature_column_order(preprocessor)
    if columns is None:
        raise ValueError(
            "Could not resolve the feature column list for the saved preprocessor. "
            "Re-run `train.py` to regenerate `preprocessor.pkl` and `feature_columns.pkl`."
        )
    return columns


def _build_bundle_for_dataframe(
    df: pd.DataFrame,
    *,
    preprocessor: Any,
    model: keras.Model,
    threshold: float,
    validation_fallback: str,
) -> ScoringBundle:
    """Validate and score one dataframe using already-loaded model artefacts."""
    ok, msg = validate_dataframe_for_scoring(df, preprocessor)
    if not ok:
        raise ValueError(msg or validation_fallback)

    return build_scoring_bundle(
        df.copy(),
        labels=_labels_from_dataframe(df),
        feature_cols=_feature_columns_or_raise(preprocessor),
        preprocessor=preprocessor,
        model=model,
        threshold=threshold,
    )


def render_restore_training_pipeline_ui() -> None:
    """User outcome line + numbered recovery steps behind an expander (keeps error states compact)."""
    st.caption(
        "Scoring cannot run until the processed CSV and model files exist — follow the steps below, then **refresh** the browser."
    )
    with st.expander("Step-by-step recovery", expanded=False):
        st.markdown(MARKDOWN_RESTORE_TRAINING_PIPELINE)


def app_debug_mode() -> bool:
    """Set `IOT_APP_DEBUG=1` or add `?debug=1` to the URL to show exception tracebacks in the UI."""
    if _is_truthy_flag(os.environ.get("IOT_APP_DEBUG", "")):
        return True
    try:
        return _is_truthy_flag(st.query_params.get("debug", ""))
    except Exception:
        return False


def safe_path_mtime(path: Path) -> float:
    """Cache-busting mtime without raising if the file is absent."""
    try:
        return float(path.stat().st_mtime) if path.is_file() else 0.0
    except OSError:
        return 0.0


def missing_label_columns_message(df: pd.DataFrame) -> str | None:
    """Return a concise UI error when the processed Zeek label columns are absent."""
    missing = [c for c in LABEL_COLUMNS if c not in df.columns]
    if not missing:
        return None
    need = ", ".join(f"`{c}`" for c in LABEL_COLUMNS)
    got = ", ".join(f"`{c}`" for c in df.columns[:40])
    more = "" if len(df.columns) <= 40 else f" … (+{len(df.columns) - 40} more)"
    return (
        f"Missing required column(s): {', '.join(f'`{m}`' for m in missing)}. "
        f"This pipeline expects both: {need} (Zeek `conn.log.labeled` export). "
        f"**Fix:** re-run `src/preprocess.py` on a labelled capture, or add/rename columns in the CSV. "
        f"Columns found (sample): {got}{more}"
    )


def list_keras_model_paths() -> list[Path]:
    """Keras/HDF5 weights under ``models/`` (delegates to ``artifact_loaders``)."""
    return list_keras_model_paths_disk()


def active_model_path() -> Path:
    """Resolved Keras file used for scoring (wizard override or default)."""
    raw = _session_value(SK_WIZARD_MODEL_PATH)
    if raw:
        candidate = _normalise_project_path(raw)
        if candidate.is_file() and candidate.suffix.lower() in KERAS_MODEL_SUFFIXES:
            return coerce_hdf5_weights_path(candidate).resolve()
    fallback = default_disk_model_path()
    return fallback.resolve() if fallback.is_file() else fallback


@st.cache_resource(show_spinner=False)
def _load_keras_model_cached(path_str: str) -> keras.Model:
    """Load the Keras model once per resolved path for the Streamlit session."""
    # compile=False avoids deserializing saved metrics (e.g. keras.metrics.mse) which
    # breaks across Keras 2 / TF 2.12 vs Keras 3 / newer TF. Inference only needs forward pass.
    return keras.models.load_model(Path(path_str), compile=False)


def load_model() -> keras.Model:
    """Return the active autoencoder, cached by selected model path."""
    return _load_keras_model_cached(str(active_model_path()))


@st.cache_resource
def load_preprocessor() -> object:
    """Return the fitted preprocessing pipeline saved by ``train.py``."""
    return load_preprocessor_from_disk()


def load_threshold() -> float:
    """Return the default reconstruction-MSE cut-off from ``models/threshold.txt``."""
    return read_threshold_mse()


def active_threshold() -> float:
    """MSE cut-off for flagging: session value from **Prepare model** when set, else ``threshold.txt``."""
    raw = _session_value(SK_WIZARD_SESSION_THRESHOLD)
    if raw is not None:
        try:
            threshold = float(raw)
            if np.isfinite(threshold) and threshold > 0:
                return threshold
        except (TypeError, ValueError):
            pass
    return load_threshold()


@st.cache_data(show_spinner=False)
def load_raw_dataframe(path_str: str) -> pd.DataFrame:
    """Load a processed CSV through the shared disk I/O wrapper."""
    return read_processed_csv(path_str)


def artifact_path_line(path: Path) -> str:
    """POSIX path plus a short existence hint for UI tables."""
    pos = path.as_posix()
    if path.is_file():
        return f"{pos} (found)"
    return f"{pos} (missing — run preprocessing and/or `train.py`)"


@st.cache_data(show_spinner=False)
def stratified_split_counts(_data_mtime: float) -> dict[str, int] | None:
    """
    Row counts for the stratified 70 / 15 / 15 split used in `train.py`
    (same `random_state` and `stratify=labels`).
    """
    try:
        from sklearn.model_selection import train_test_split
    except ImportError:
        return None
    if not DATA_PATH.is_file():
        return None
    try:
        df = load_raw_dataframe(str(DATA_PATH))
    except ValueError:
        return None
    missing = [c for c in LABEL_COLUMNS if c not in df.columns]
    if missing:
        return None
    labels = df["label"].astype(str).str.strip()
    features = df.drop(columns=list(LABEL_COLUMNS))
    features = features.drop(columns=[c for c in ID_COLUMNS if c in features.columns], errors="ignore")
    try:
        x_trainval, x_test, y_trainval, _y_test = train_test_split(
            features,
            labels,
            test_size=0.15,
            random_state=42,
            stratify=labels,
        )
        val_size = 0.15 / (1.0 - 0.15)
        x_train, x_val, _y_train, _y_val = train_test_split(
            x_trainval,
            y_trainval,
            test_size=val_size,
            random_state=42,
            stratify=y_trainval,
        )
    except ValueError:
        # e.g. too few rows per class for stratification
        return None
    return {
        "n_total": int(len(df)),
        "n_train": int(len(x_train)),
        "n_val": int(len(x_val)),
        "n_test": int(len(x_test)),
    }


def find_saved_baseline_reference() -> str | None:
    """Optional on-disk baseline for comparison (none shipped by default)."""
    for name in ("baseline_metrics.json", "baseline_metrics.yaml", "baseline_model.pkl"):
        candidate = PROJECT_ROOT / "models" / name
        if candidate.is_file():
            return candidate.as_posix()
    return None


def check_model_artefacts() -> str | None:
    """Model, preprocessor, and threshold only (upload scoring does not need on-disk processed CSV)."""
    mp = active_model_path()
    if not mp.is_file():
        return (
            f"Keras model not found: `{mp.as_posix()}`. "
            "Train the autoencoder with `train.py` after preprocessing, or pick another file on **Select model**."
        )
    if not PREPROCESSOR_PATH.is_file():
        return (
            f"Preprocessor not found: `{PREPROCESSOR_PATH.as_posix()}`. "
            "It is saved by `train.py` together with the model."
        )
    if not THRESHOLD_PATH.is_file():
        return (
            f"Threshold file not found: `{THRESHOLD_PATH.as_posix()}`. "
            "Run `train.py` to write the validation-derived MSE cut-off."
        )
    return None


def check_processed_csv_available() -> str | None:
    """Processed dataset used for default scoring (`compute_scoring`)."""
    if not DATA_PATH.is_file():
        return (
            f"Processed dataset not found: `{DATA_PATH.as_posix()}`. "
            "Build it from the raw Zeek log using `src/preprocess.py`."
        )
    return None


def check_environment() -> str | None:
    """Return a user-facing error string, or None when default bundle scoring is possible."""
    return check_model_artefacts() or check_processed_csv_available()


def scoring_cache_signature() -> tuple[float, float, float, float, float]:
    """File mtimes + session threshold so cached scores refresh when artefacts or cut-off change."""
    try:
        session_threshold = float(_session_value(SK_WIZARD_SESSION_THRESHOLD, float("nan")))
    except (TypeError, ValueError):
        session_threshold = float("nan")
    if not np.isfinite(session_threshold):
        session_threshold = float("nan")

    return (
        safe_path_mtime(DATA_PATH),
        safe_path_mtime(active_model_path()),
        safe_path_mtime(PREPROCESSOR_PATH),
        safe_path_mtime(THRESHOLD_PATH),
        session_threshold,
    )


def render_evaluation_summary_panel(bundle: ScoringBundle) -> None:
    """
    Testing / evaluation block: classification metrics, PR-AUC, confusion counts, and a short interpretation.

    Uses only fields derived from the current scoring run (`ScoringBundle`).
    """
    try:
        _render_evaluation_summary_panel_impl(bundle)
    except Exception as exc:
        st.warning(
            f"The evaluation block could not be drawn ({friendly_scoring_error(exc)}). "
            "The rest of the dashboard is unchanged."
        )
        if app_debug_mode():
            st.code(traceback.format_exc(), language="text")


def _render_evaluation_summary_panel_impl(bundle: ScoringBundle) -> None:
    """Render the evaluation panel after outer error handling has succeeded.

    Args:
        bundle: Scoring output for one app session.
    """
    na = EVAL_METRIC_UNAVAILABLE

    n_rows = len(bundle.df)
    n_flagged = int(bundle.flagged.sum())
    ev = evaluation_metrics_from_bundle(bundle)
    n_malicious = ev["malicious_count"]
    precision = ev["precision"]
    recall = ev["recall"]
    f1 = ev["f1_score"]
    pr_auc = ev["pr_auc"]

    st.subheader("Evaluation — flags vs Zeek labels")
    st.caption(CAPTION_EVALUATION_ROWS_SCOPE)
    with st.expander("How these metrics are defined", expanded=False):
        if bundle_has_labels(bundle):
            st.markdown(
                f"- **Ground truth:** Zeek `label` — any value other than **Benign** (case-insensitive) counts as malicious.\n"
                f"- **Prediction (flag):** reconstruction MSE **>** **{bundle.threshold:.6f}**.\n"
                "- **PR-AUC:** ranks rows by the same per-row MSE (`sklearn.metrics.average_precision_score`); "
                "it is **not** tied only to that single threshold."
            )
        else:
            st.markdown(
                f"This run has **no `label` column**, so precision / recall / F1 / PR-AUC are unavailable. "
                f"Scoring and flags still use **MSE > {bundle.threshold:.6f}**."
            )

    st.markdown("##### Dataset scale")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric(
        "Rows scored",
        f"{n_rows:,}",
        help="Number of rows evaluated in this scoring run (project CSV or a compatible upload).",
    )
    s2.metric("Rows flagged", f"{n_flagged:,}", help="Count with MSE strictly above the saved threshold.")
    s3.metric(
        "Non-benign labels",
        f"{int(n_malicious):,}" if n_malicious is not None else "n/a",
        help="Rows whose `label` is not benign (case-insensitive), when labels are available.",
    )
    s4.metric("Input width", f"{bundle.transformed_dim:,}", help="Length of the vector passed to the autoencoder.")

    st.markdown("##### At fixed threshold")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Precision",
        f"{precision:.4f}" if precision is not None else na,
        help="TP / (TP + FP): fraction of flagged rows that carry a non-benign label.",
    )
    m2.metric(
        "Recall",
        f"{recall:.4f}" if recall is not None else na,
        help="TP / (TP + FN): fraction of malicious-labelled rows that are flagged at the saved threshold.",
    )
    m3.metric(
        "F1-score",
        f"{f1:.4f}" if f1 is not None else na,
        help="Harmonic mean of precision and recall when both are defined.",
    )
    m4.metric(
        "PR-AUC",
        f"{pr_auc:.4f}" if pr_auc is not None else na,
        help="Area under the precision–recall curve for ranking by MSE (across thresholds, not only the saved cut-off).",
    )

    st.divider()
    st.subheader("Contingency table")
    st.dataframe(contingency_matrix_dataframe(bundle), use_container_width=True)
    if bundle_has_labels(bundle):
        st.caption("Each cell is a **connection count** for this scored table.")
        with st.expander("How to read this table", expanded=False):
            st.markdown(
                "Counts show agreement between Zeek **labels** and the **fixed-threshold** detector on **this session’s** "
                "rows only — **illustrative** for your report, not a substitute for a held-out test protocol."
            )
    else:
        st.caption("Labels are missing — confusion-style cells show as **n/a**.")

    st.divider()
    with st.expander("What these numbers mean (plain language)", expanded=False):
        st.markdown(
            "- **Precision:** among rows you **flag**, how many truly carry a non-benign label (fewer false alarms).\n"
            "- **Recall:** among malicious-labelled rows, how many you **catch** at this threshold.\n"
            "- **F1:** balances precision and recall when both exist.\n"
            "- **PR-AUC:** how well MSE **orders** malicious ahead of benign across cut-offs — useful if you tune the threshold later.\n"
            "- **Scope:** all figures are **dataset- and threshold-specific**; do not assume they transfer to other networks without new evaluation."
        )
    st.divider()
    render_metrics_export_buttons(
        bundle,
        data_source_label="project_processed_csv",
        key_prefix="dash_eval_metrics",
    )


def score_dataframe(df: pd.DataFrame) -> ScoringBundle:
    """
    Run reconstruction scoring on an arbitrary compatible dataframe (not cached).

    Raises `ValueError` with an examiner-facing message when validation or transform fails.
    """
    preprocessor = load_preprocessor()
    return _build_bundle_for_dataframe(
        df,
        preprocessor=preprocessor,
        model=load_model(),
        threshold=active_threshold(),
        validation_fallback="Validation failed for uploaded CSV.",
    )


def render_metrics_export_buttons(
    bundle: ScoringBundle,
    *,
    data_source_label: str,
    key_prefix: str,
) -> None:
    """Two download buttons: single-row metrics as CSV and JSON."""
    stub = metrics_filename_stub(data_source_label)
    st.subheader("Export evaluation summary")
    st.caption(
        "One row per file: precision, recall, F1, PR-AUC (when defined), TP/FP/TN/FN, rows scored, flagged count, "
        "malicious label count, and the MSE threshold — all for **this** scoring run."
    )
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            label="Metrics as CSV",
            data=metrics_report_csv_bytes(bundle, data_source_label),
            file_name=f"anomaly_metrics_{stub}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            help="Spreadsheet-friendly single row; empty cells mean “not defined for this run”.",
        )
    with c2:
        st.download_button(
            label="Metrics as JSON",
            data=metrics_report_json_bytes(bundle, data_source_label),
            file_name=f"anomaly_metrics_{stub}.json",
            mime="application/json",
            key=f"{key_prefix}_json",
            help="Same numbers as the CSV, in JSON for scripts or notebooks.",
        )


@st.cache_data(show_spinner="Loading dataset and computing reconstruction errors…")
def compute_scoring(_cache_key: tuple[float, float, float, float, float]) -> ScoringBundle:
    """Load and score the default project CSV.

    The argument is intentionally unused by the body: Streamlit includes it in
    the cache key so score results refresh when the data/model/threshold files
    or session threshold change.
    """
    df = load_raw_dataframe(str(DATA_PATH))
    return _build_bundle_for_dataframe(
        df,
        preprocessor=load_preprocessor(),
        model=load_model(),
        threshold=active_threshold(),
        validation_fallback="Validation failed for the project processed CSV.",
    )


def load_scoring_bundle() -> tuple[ScoringBundle | None, str | None]:
    """Return the cached default scoring bundle plus a user-facing error, if any."""
    err = check_environment()
    if err:
        return None, err
    try:
        bundle = compute_scoring(scoring_cache_signature())
    except Exception as exc:  # noqa: BLE001 — surface any TF/sklearn/pandas failure as a user message
        msg = friendly_scoring_error(exc)
        if app_debug_mode():
            msg += (
                "\n\n**Debug traceback** (disable by unsetting `IOT_APP_DEBUG` and removing `?debug=1` from the URL):\n```\n"
                f"{traceback.format_exc()}\n```"
            )
        return None, msg
    return bundle, None


def render_sidebar_metrics(bundle: ScoringBundle) -> None:
    """Render compact session-level scoring facts in the Streamlit sidebar."""
    st.sidebar.markdown("##### Session summary")
    st.sidebar.caption("Counts and threshold for the scoring run loaded in this browser session.")
    st.sidebar.metric(
        "MSE threshold",
        f"{bundle.threshold:.6f}",
        help="Rows with reconstruction MSE above this value are flagged (from `models/threshold.txt`).",
    )
    st.sidebar.metric("Rows scored", f"{len(bundle.df):,}", help="Connections evaluated in this run.")
    st.sidebar.metric("Rows flagged", f"{int(bundle.flagged.sum()):,}", help="Count with MSE strictly above the threshold.")


def _legacy_multipage_navigation_hint() -> None:
    """Brand strip + brief IA note (sidebar sections come from ``st.navigation`` in ``app.py``)."""
    st.sidebar.markdown(
        '<div class="iot-sidebar-brand">'
        '<p class="iot-sidebar-brand-title">IoT-23 artefact</p>'
        '<p class="iot-sidebar-brand-sub">Final-year project · Zeek connection logs · Autoencoder scoring</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    st.sidebar.markdown("**How navigation works**")
    st.sidebar.caption(
        "**Main Workflow** — steps 1–7 (same guided strip under the header on each wizard page). **Overview** lives under **app**. "
        "**Advanced Tools** — optional deep dives; same scoring engine. "
        "The strip never marks an advanced page as a numbered wizard step."
    )


def render_sidebar_placeholder(title: str = "Live scoring unavailable", detail: str | None = None) -> None:
    """Sidebar when no `ScoringBundle` (missing artefacts or scoring error)."""
    st.sidebar.warning(title)
    if detail:
        st.sidebar.caption(detail[:900])


def render_app_chrome() -> None:
    """Inject global CSS (colour system, cards, sidebar, wizard rail)."""
    st.markdown(IOT_APP_STYLESHEET, unsafe_allow_html=True)


def render_wizard_stepper(*, current_step: int, classic_mode: bool = False) -> None:
    """
    Seven-step strip inside a bordered container (two rows: 4 + 3 for readability).

    ``current_step == 0`` with ``classic_mode=False``: home — all steps linked, none highlighted.
    ``classic_mode=True``: advanced Tool page — never highlights a wizard step.
    ``current_step`` 1–7 with ``classic_mode=False``: wizard page — that step shows "You are here".
    """
    with st.container(border=True):
        if classic_mode:
            st.caption(
                "**Advanced tool** — you are not on a numbered wizard step. Use the links below to open the "
                "**guided workflow** (steps 1–7); none is highlighted as your current position."
            )
        st.markdown('<p class="iot-workflow-label">Guided workflow · 7 steps (primary path)</p>', unsafe_allow_html=True)

        def _render_one_step(idx: int, short_label: str, page_script: str | None) -> None:
            """Render one workflow step link or active marker."""
            rel = page_script
            path_ok = rel is not None and (PROJECT_ROOT / rel).is_file()
            is_here = (not classic_mode) and current_step != 0 and idx == current_step
            esc = html.escape(short_label)
            if path_ok and rel is not None:
                if is_here:
                    st.markdown(
                        f'<div><span class="iot-wizard-pill-active">{idx}. {esc}</span></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div class="iot-wizard-here">You are here</div>', unsafe_allow_html=True)
                else:
                    st.page_link(rel, label=f"{idx}. {short_label}", help=f"Open step {idx}: {short_label}")
            else:
                if is_here:
                    st.markdown(f"**:green[{idx}.]** {short_label}")
                elif (not classic_mode) and current_step != 0 and idx < current_step:
                    st.markdown(f"**:blue[{idx}.]** {short_label}")
                else:
                    st.markdown(f"**:gray[{idx}.]** {short_label}")

        row_a = st.columns(4)
        for idx, col in enumerate(row_a, start=1):
            short_label, page_script = WIZARD_STEP_PAGES[idx - 1]
            with col:
                _render_one_step(idx, short_label, page_script)
        row_b = st.columns(3)
        for j, col in enumerate(row_b):
            idx = 5 + j
            short_label, page_script = WIZARD_STEP_PAGES[idx - 1]
            with col:
                _render_one_step(idx, short_label, page_script)

        foot = (
            "More depth lives in the **Model Evaluation**, **System Metrics**, and **Reports and Export** menu groups."
            if not classic_mode
            else "Return to **Overview** or **step 1 - Select Data** to follow the guided path from the start."
        )
        st.markdown(f'<p class="iot-wizard-foot">{html.escape(foot)}</p>', unsafe_allow_html=True)


def render_multipage_navigation_hint() -> None:
    """Brand strip + brief IA note for the custom button router."""
    st.sidebar.markdown(
        '<div class="iot-sidebar-brand">'
        '<p class="iot-sidebar-brand-title">IoT-23 artefact</p>'
        '<p class="iot-sidebar-brand-sub">Final-year project - Zeek connection logs - Autoencoder scoring</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    st.sidebar.markdown("**How navigation works**")
    st.sidebar.caption(
        "Use the **Application menu** at the top of the page for grouped buttons. "
        "The guided strip opens steps 1-7 only; evaluation, exports, and system tools live in their own groups."
    )


def reproducibility_summary_dict() -> dict[str, Any]:
    """Machine-readable summary of paths and training assumptions shown in exports."""
    return {
        "project_root": PROJECT_ROOT.as_posix(),
        "data_path": DATA_PATH.as_posix(),
        "model_path": MODEL_PATH.as_posix(),
        "preprocessor_path": PREPROCESSOR_PATH.as_posix(),
        "feature_columns_path": FEATURE_COLUMNS_PATH.as_posix(),
        "threshold_path": THRESHOLD_PATH.as_posix(),
        "training_split_strategy": "stratified 70/15/15",
        "training_random_state": 42,
        "threshold_definition": "99th percentile of benign validation reconstruction MSE",
    }


def reproducibility_summary_json_bytes() -> bytes:
    """Serialize reproducibility metadata for Streamlit download buttons."""
    return json.dumps(reproducibility_summary_dict(), indent=2, allow_nan=False).encode("utf-8")


def model_summary_text() -> str:
    """Return ``model.summary()`` as plain text for display and export."""
    try:
        model = load_model()
        buf = io.StringIO()
        model.summary(print_fn=lambda line: buf.write(line + "\n"))
        return buf.getvalue()
    except Exception as exc:
        return f"[Model summary unavailable: {friendly_scoring_error(exc)}]"
