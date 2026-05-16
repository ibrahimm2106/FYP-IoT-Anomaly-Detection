"""User-facing error strings (no Streamlit dependency)."""

from __future__ import annotations

import pandas as pd


def friendly_scoring_error(exc: BaseException) -> str:
    """Single-line style user message (no Python stack trace)."""
    msg = str(exc).strip()
    if isinstance(exc, ValueError) and "Missing required" in msg:
        return msg
    if isinstance(exc, ValueError) and "no data rows" in msg.lower():
        return msg
    if isinstance(exc, FileNotFoundError):
        return f"Expected file was not found: {msg}"
    if isinstance(exc, pd.errors.EmptyDataError):
        return "The CSV file is empty or has no parseable rows. Regenerate it with `src/preprocess.py`."
    if isinstance(exc, pd.errors.ParserError):
        return f"The CSV could not be parsed ({msg}). Check the file is valid comma-separated text."
    if isinstance(exc, UnicodeDecodeError):
        return "The CSV could not be decoded as UTF-8. Save the processed file as UTF-8 and try again."
    if isinstance(exc, (OSError, IOError)):
        return f"File or I/O problem ({type(exc).__name__}): {msg}"
    if isinstance(exc, KeyError):
        return f"Missing expected field after preprocessing ({type(exc).__name__}: {msg})."
    return f"{type(exc).__name__}: {msg}"


__all__ = ["friendly_scoring_error"]
