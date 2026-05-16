"""
Preprocess IoT-23 Zeek conn.log.labeled captures for downstream modelling.

Reads tab-separated Zeek logs with a #fields header directive, drops metadata
comment lines, and writes a flat CSV for analysis and autoencoder experiments.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

# IoT-23 Zeek exports sometimes merge the last three columns into one TSV cell,
# using two-or-more spaces inside that cell as the separator (see #fields line).
_MERGED_TAIL_SPLIT = re.compile(r"\s{2,}")

# Paths relative to project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_LOG_PATH = PROJECT_ROOT / "data" / "raw" / "ctu_iot_34_1_zeek_conn.log.labeled"
PROCESSED_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "ctu_iot_34_1.csv"


def expand_merged_trailing_fields(tab_tokens: list[str]) -> list[str]:
    """
    Split a merged trailing cell (tunnel_parents / label / detailed-label) when needed.

    Returns a new token list; leaves rows unchanged when the last cell is already a
    single logical field or does not match the triple tail pattern.
    """
    if len(tab_tokens) < 2:
        return tab_tokens
    tail_segments = _MERGED_TAIL_SPLIT.split(tab_tokens[-1].strip())
    if len(tail_segments) != 3:
        return tab_tokens
    return tab_tokens[:-1] + tail_segments


def extract_column_names(fields_line: str) -> list[str]:
    """
    Parse a Zeek #fields directive into column names.

    The first tab-separated token must be '#fields'; remaining tokens are names.
    """
    parts = fields_line.rstrip("\r\n").split("\t")
    if not parts or parts[0].strip() != "#fields":
        raise ValueError("Expected a line starting with '#fields' as the directive.")
    names = [p.strip() for p in parts[1:] if p.strip() != ""]
    names = expand_merged_trailing_fields(names)
    if not names:
        raise ValueError("No column names found after '#fields' directive.")
    return names


def read_zeek_labeled_conn_log(path: Path) -> tuple[list[str], list[str]]:
    """
    Scan a Zeek conn.log.labeled file for #fields and collect non-comment data rows.

    Returns (column_names, list of raw data lines including newlines).
    """
    column_names: list[str] | None = None
    data_lines: list[str] = []

    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        for line in handle:
            if line.startswith("#fields"):
                column_names = extract_column_names(line)
                continue
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            if column_names is None:
                raise ValueError(
                    "Encountered data rows before a '#fields' line; file may be malformed."
                )
            data_lines.append(line)

    if column_names is None:
        raise ValueError("No '#fields' line found; cannot determine column headers.")

    return column_names, data_lines


def parse_data_line(line: str, expected_columns: int) -> list[str]:
    """Tab-split one Zeek row and align trailing merged label columns."""
    parts = line.rstrip("\r\n").split("\t")
    parts = expand_merged_trailing_fields(parts)
    if len(parts) != expected_columns:
        raise ValueError(
            f"Row has {len(parts)} fields after parsing, expected {expected_columns}."
        )
    return parts


def lines_to_dataframe(column_names: list[str], data_lines: list[str]) -> pd.DataFrame:
    """Parse tab-separated data rows into a DataFrame aligned with column_names."""
    if not data_lines:
        return pd.DataFrame(columns=column_names)

    expected = len(column_names)
    rows: list[list[str]] = []
    for lineno, raw in enumerate(data_lines, start=1):
        try:
            rows.append(parse_data_line(raw, expected))
        except ValueError as exc:
            raise ValueError(f"Bad data row at line offset {lineno}: {exc}") from exc

    return pd.DataFrame(rows, columns=column_names)


def validate_label_columns(df: pd.DataFrame) -> None:
    """Ensure expected supervision columns survived parsing."""
    required = {"label", "detailed-label"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"Expected columns {sorted(required)}; missing: {missing}. "
            f"Found columns: {list(df.columns)}"
        )


def save_processed(df: pd.DataFrame, out_path: Path) -> None:
    """Write the cleaned processed CSV, creating parent folders if required.

    Args:
        df: Parsed Zeek connection dataframe.
        out_path: Destination CSV path.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def main() -> int:
    """Load raw Zeek log, print summary, and write cleaned CSV."""
    try:
        columns, data_lines = read_zeek_labeled_conn_log(RAW_LOG_PATH)
        df = lines_to_dataframe(columns, data_lines)
        validate_label_columns(df)

        print(f"Loaded: {RAW_LOG_PATH}")
        print(f"Shape (rows, columns): {df.shape}")
        print("Columns:")
        for name in df.columns:
            print(f"  - {name}")

        save_processed(df, PROCESSED_CSV_PATH)
        print(f"Saved cleaned dataset to: {PROCESSED_CSV_PATH}")
    except FileNotFoundError:
        print(
            f"Error: raw file not found at '{RAW_LOG_PATH}'. "
            "Place the Zeek conn.log.labeled file there and retry.",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Error: invalid or unexpected log format: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: could not read or write files: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
