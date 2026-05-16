"""
In-memory table repairs for the wizard (before scoring).

Does not replace train-time preprocessing: the saved preprocessor still scales/encodes at score time.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.iot_streamlit import LABEL_COLUMNS


def total_missing_cells(df: pd.DataFrame) -> int:
    """Count all missing cells in a dataframe.

    Args:
        df: Dataframe to inspect.

    Returns:
        Total number of null cells.
    """
    return int(df.isna().sum().sum())


def duplicate_row_count(df: pd.DataFrame) -> int:
    """Count fully duplicated rows.

    Args:
        df: Dataframe to inspect.

    Returns:
        Number of duplicate rows after the first occurrence.
    """
    return int(df.duplicated().sum())


def required_feature_names(preprocessor: Any) -> list[str] | None:
    """Resolve the model-required feature names from the fitted preprocessor.

    Args:
        preprocessor: Fitted preprocessing pipeline.

    Returns:
        Ordered feature names, or ``None`` when they cannot be resolved.
    """
    from src.scoring_engine import expected_feature_column_order

    return expected_feature_column_order(preprocessor)


def optional_columns_to_drop(df: pd.DataFrame, required: list[str] | None) -> list[str]:
    """Columns safe to offer for removal (not required model inputs, keep labels)."""
    keep = set(LABEL_COLUMNS)
    if required:
        keep |= set(required)
    return sorted([c for c in df.columns if c not in keep])


def numeric_feature_subset(df: pd.DataFrame, required: list[str] | None) -> list[str]:
    """Return numeric columns that are relevant to repair operations.

    Args:
        df: Candidate repair dataframe.
        required: Optional model-required feature list.

    Returns:
        Numeric columns, restricted to required features when available.
    """
    if not required:
        return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return [c for c in required if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def non_numeric_feature_subset(df: pd.DataFrame, required: list[str] | None) -> list[str]:
    """Return non-numeric columns that are relevant to repair operations.

    Args:
        df: Candidate repair dataframe.
        required: Optional model-required feature list.

    Returns:
        Non-numeric columns, restricted to required features when available.
    """
    cols = list(required) if required else [c for c in df.columns if c not in LABEL_COLUMNS]
    return [c for c in cols if c in df.columns and not pd.api.types.is_numeric_dtype(df[c])]


def repair_dataframe(
    df: pd.DataFrame,
    *,
    required: list[str] | None,
    missing_numeric: str,
    missing_categorical: str,
    drop_duplicates: bool,
    extra_columns_to_drop: list[str],
    add_invalid_flag: bool,
    remove_invalid_rows: bool,
    clip_numeric_percentiles: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply selected repairs. Returns (new_df, log).

    missing_numeric: none | median | mean | zero | drop_rows
    missing_categorical: none | placeholder
    """
    log: dict[str, Any] = {
        "missing_cells_before": total_missing_cells(df),
        "rows_before": len(df),
        "dupes_removed": 0,
        "rows_dropped_missing": 0,
        "numeric_missing_filled": 0,
        "categorical_missing_filled": 0,
        "inf_replaced": 0,
        "cols_dropped": [],
        "invalid_flagged": 0,
        "invalid_rows_removed": 0,
        "clip_updates": 0,
    }
    work = df.copy()
    flag_col = "_iot_invalid_row"
    if not add_invalid_flag and flag_col in work.columns:
        work = work.drop(columns=[flag_col])

    # 1) Drop user-selected extra columns
    protected = set(LABEL_COLUMNS)
    if required:
        protected |= set(required)
    for col in extra_columns_to_drop:
        if col in work.columns and col not in protected:
            work = work.drop(columns=[col])
            log["cols_dropped"].append(col)

    # 2) Replace inf with NaN in numeric columns (subset: required numerics or all numeric)
    num_cols = numeric_feature_subset(work, required)
    for c in num_cols:
        if c not in work.columns:
            continue
        s = work[c]
        if not pd.api.types.is_numeric_dtype(s):
            continue
        arr = np.asarray(s, dtype=np.float64)
        inf_mask = np.isinf(arr)
        n_inf = int(inf_mask.sum())
        if n_inf:
            log["inf_replaced"] += n_inf
            arr = arr.copy()
            arr[inf_mask] = np.nan
            work[c] = arr

    # 3) Duplicates
    if drop_duplicates:
        before = len(work)
        work = work.drop_duplicates(keep="first").reset_index(drop=True)
        log["dupes_removed"] = before - len(work)

    # 4) Missing values — subset: required columns present in work
    subset_cols: list[str] = []
    if required:
        subset_cols = [c for c in required if c in work.columns]
    else:
        subset_cols = [c for c in work.columns if c not in LABEL_COLUMNS]

    if missing_numeric == "drop_rows" and subset_cols:
        before = len(work)
        work = work.dropna(subset=subset_cols, how="any").reset_index(drop=True)
        log["rows_dropped_missing"] = before - len(work)
    else:
        for c in num_cols:
            if c not in work.columns:
                continue
            na = work[c].isna()
            if not na.any():
                continue
            if missing_numeric == "none":
                pass
            elif missing_numeric == "median":
                fill = work[c].median()
                n = int(na.sum())
                work.loc[na, c] = fill
                log["numeric_missing_filled"] += n
            elif missing_numeric == "mean":
                fill = work[c].mean()
                n = int(na.sum())
                work.loc[na, c] = fill
                log["numeric_missing_filled"] += n
            elif missing_numeric == "zero":
                n = int(na.sum())
                work.loc[na, c] = 0.0
                log["numeric_missing_filled"] += n

        cat_cols = non_numeric_feature_subset(work, required)
        if missing_categorical == "placeholder":
            for c in cat_cols:
                if c not in work.columns:
                    continue
                na = work[c].isna()
                if na.any():
                    n = int(na.sum())
                    col = work[c].astype("object")
                    col = col.where(~na, "(missing)")
                    work[c] = col
                    log["categorical_missing_filled"] += n

    # 5) Flag invalid (NaN/Inf in required numeric columns after imputation)
    if add_invalid_flag:
        bad = np.zeros(len(work), dtype=bool)
        for c in num_cols:
            if c not in work.columns:
                continue
            s = pd.to_numeric(work[c], errors="coerce")
            bad |= s.isna().to_numpy() | np.isinf(np.asarray(s, dtype=np.float64))
        work[flag_col] = bad
        log["invalid_flagged"] = int(bad.sum())

    if remove_invalid_rows and flag_col in work.columns:
        before = len(work)
        work = work.loc[~work[flag_col]].drop(columns=[flag_col]).reset_index(drop=True)
        log["invalid_rows_removed"] = before - len(work)

    # 6) Winsorize numeric feature columns (optional; preprocessor still applies its own scaler later)
    if clip_numeric_percentiles and num_cols:
        for c in num_cols:
            if c not in work.columns or not pd.api.types.is_numeric_dtype(work[c]):
                continue
            s = work[c].astype(np.float64)
            lo, hi = s.quantile(0.01), s.quantile(0.99)
            if pd.isna(lo) or pd.isna(hi) or lo >= hi:
                continue
            before_vals = s.copy()
            clipped = s.clip(lower=float(lo), upper=float(hi))
            updates = int((before_vals != clipped).sum())
            if updates:
                log["clip_updates"] += updates
                work[c] = clipped

    log["missing_cells_after"] = total_missing_cells(work)
    log["rows_after"] = len(work)
    return work, log


def summarize_log(log: dict[str, Any]) -> str:
    """Render a compact human-readable summary of a repair log.

    Args:
        log: Dictionary returned by ``repair_dataframe``.

    Returns:
        Markdown string summarizing the repair effects.
    """
    parts = [
        f"Rows: **{log['rows_before']:,}** → **{log['rows_after']:,}**",
        f"Missing cells: **{log['missing_cells_before']:,}** → **{log['missing_cells_after']:,}**",
    ]
    if log.get("dupes_removed", 0):
        parts.append(f"Duplicate rows removed: **{log['dupes_removed']:,}**")
    if log.get("rows_dropped_missing", 0):
        parts.append(f"Rows dropped (missing): **{log['rows_dropped_missing']:,}**")
    if log.get("numeric_missing_filled", 0):
        parts.append(f"Numeric missing cells filled: **{log['numeric_missing_filled']:,}**")
    if log.get("categorical_missing_filled", 0):
        parts.append(f"Text/category missing filled: **{log['categorical_missing_filled']:,}**")
    if log.get("inf_replaced", 0):
        parts.append(f"∞ / invalid numbers → NaN (then imputed): **{log['inf_replaced']:,}** cell(s)")
    if log.get("cols_dropped"):
        parts.append(f"Columns dropped: **{len(log['cols_dropped'])}**")
    if log.get("invalid_flagged", 0):
        parts.append(f"Invalid rows flagged: **{log['invalid_flagged']:,}**")
    if log.get("invalid_rows_removed", 0):
        parts.append(f"Invalid rows removed: **{log['invalid_rows_removed']:,}**")
    if log.get("clip_updates", 0):
        parts.append(f"Numeric values clipped (1–99%): **{log['clip_updates']:,}** cell(s)")
    return " · ".join(parts)


__all__ = [
    "duplicate_row_count",
    "non_numeric_feature_subset",
    "numeric_feature_subset",
    "optional_columns_to_drop",
    "repair_dataframe",
    "required_feature_names",
    "summarize_log",
    "total_missing_cells",
]
