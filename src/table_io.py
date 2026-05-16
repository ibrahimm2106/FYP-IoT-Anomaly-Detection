"""CSV table loading and quality helpers (pandas only; used by UI and validation)."""

from __future__ import annotations

import io

import pandas as pd

from src.iot_paths import DATA_PATH
from src.user_messages import friendly_scoring_error


def try_read_processed_csv() -> tuple[pd.DataFrame | None, str | None]:
    """Load the processed dataset without scoring — for partial UI when artefacts are incomplete."""
    if not DATA_PATH.is_file():
        return None, f"Processed CSV not found at `{DATA_PATH.as_posix()}`. Run `src/preprocess.py`."
    try:
        df = pd.read_csv(DATA_PATH, low_memory=False)
    except pd.errors.EmptyDataError:
        return None, "The CSV file is empty. Regenerate it with `src/preprocess.py`."
    except pd.errors.ParserError as exc:
        return None, f"CSV parse error: {exc}. Check the file is valid comma-separated text."
    except UnicodeDecodeError:
        return None, "The CSV could not be read as UTF-8. Re-export the processed file as UTF-8."
    except OSError as exc:
        return None, f"Could not read the dataset file ({type(exc).__name__}: {exc})."
    return df, None


def missing_values_top_columns(df: pd.DataFrame, top_n: int = 25) -> pd.DataFrame | None:
    """
    Compact audit of columns with nulls (for upload previews and data QA).

    Returns ``None`` when there are no missing values.
    """
    miss = df.isna().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    if miss.empty:
        return None
    out = miss.head(top_n).rename("missing_cells").reset_index().rename(columns={"index": "column"})
    out["missing_pct"] = (100.0 * out["missing_cells"] / max(len(df), 1)).round(2)
    return out


def parse_csv_bytes(raw: bytes) -> tuple[pd.DataFrame | None, str | None]:
    """Read a user-uploaded CSV from memory; return a friendly error string instead of raising."""
    if not raw:
        return None, "Empty file upload."
    try:
        df = pd.read_csv(io.BytesIO(raw), low_memory=False)
    except pd.errors.EmptyDataError:
        return None, "The CSV has no readable data rows (empty or header-only)."
    except pd.errors.ParserError as exc:
        return None, f"CSV parse error: {friendly_scoring_error(exc)}"
    except UnicodeDecodeError:
        return None, "The file could not be decoded as **UTF-8**. Save the CSV as UTF-8 and try again."
    except Exception as exc:  # noqa: BLE001
        return None, friendly_scoring_error(exc)
    if df.shape[1] == 0:
        return None, "The CSV has **no columns** after parsing (check the delimiter and header row)."
    return df, None


__all__ = ["missing_values_top_columns", "parse_csv_bytes", "try_read_processed_csv"]
