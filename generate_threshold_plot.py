"""Generate a reconstruction-error threshold plot from saved score artefacts.

This utility is intentionally separate from the Streamlit app. It reads the
same repository paths documented in ``README.md``:

- ``data/processed/test_scores.csv`` for reconstruction MSE values.
- ``models/threshold.txt`` for the fixed anomaly cut-off.
- ``figure_5_4_threshold.png`` as the generated report figure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
SCORES_PATH = PROJECT_ROOT / "data" / "processed" / "test_scores.csv"
THRESHOLD_PATH = PROJECT_ROOT / "models" / "threshold.txt"
OUTPUT_PATH = PROJECT_ROOT / "figure_5_4_threshold.png"


def load_threshold(path: Path) -> float:
    """Read the saved reconstruction-MSE threshold.

    Args:
        path: Path to ``models/threshold.txt``.

    Returns:
        Threshold value as a float.

    Raises:
        ValueError: If the threshold file is empty or non-numeric.
    """
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        raise ValueError(f"Threshold file is empty: {path}")
    return float(lines[0])


def load_mse_scores(path: Path) -> pd.Series:
    """Load reconstruction MSE values from the evaluation score CSV.

    Args:
        path: Path to ``data/processed/test_scores.csv``.

    Returns:
        Numeric ``mse_score`` series.

    Raises:
        ValueError: If the CSV does not contain an ``mse_score`` column.
    """
    scores = pd.read_csv(path, low_memory=False)
    if "mse_score" not in scores.columns:
        raise ValueError(f"Expected column `mse_score` in {path}")
    return pd.to_numeric(scores["mse_score"], errors="coerce").dropna()


def save_threshold_plot(mse_scores: pd.Series, threshold: float, output_path: Path) -> None:
    """Create and save the reconstruction-error distribution figure.

    Args:
        mse_scores: Reconstruction MSE values to plot.
        threshold: Fixed anomaly threshold to draw as a vertical line.
        output_path: Destination PNG path.
    """
    plt.figure(figsize=(10, 5))
    plt.hist(
        mse_scores,
        bins=80,
        density=True,
        alpha=0.7,
        color="steelblue",
        label="Reconstruction MSE distribution",
    )
    plt.axvline(
        threshold,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Threshold = {threshold:.4f}",
    )
    plt.xlabel("Reconstruction Error (MSE)")
    plt.ylabel("Density")
    plt.title("Figure 5.4 - Reconstruction Error Distribution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def main() -> int:
    """Generate the threshold figure.

    Returns:
        Process exit code. ``0`` indicates the PNG was written.
    """
    try:
        threshold = load_threshold(THRESHOLD_PATH)
        mse_scores = load_mse_scores(SCORES_PATH)
        save_threshold_plot(mse_scores, threshold, OUTPUT_PATH)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
