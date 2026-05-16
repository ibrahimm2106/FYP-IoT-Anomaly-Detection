# Evaluation — reproducible protocol

Interactive Streamlit pages **explore** results; this file defines the **canonical offline evaluation** aligned with training.

## Primary script: `evaluate.py`

From the **project root**, after `src/preprocess.py` and `train.py` have succeeded:

```bash
python evaluate.py
```

**Inputs (expected paths):**

- `data/processed/ctu_iot_34_1.csv`
- `models/autoencoder.h5` (HDF5 weights; legacy `autoencoder.keras` from older runs is still accepted if present)
- `models/preprocessor.pkl`
- `models/threshold.txt`
- `models/feature_columns.pkl`

**Outputs (as implemented in `evaluate.py`):**

- `models/baseline_metrics.json` — Isolation Forest baseline metrics (used by Streamlit evaluation views when present).
- `models/test_evaluation.json` — Full test-set report (threshold sweep, breakdowns).
- `data/processed/test_scores.csv` — Per-row scored test set for inspection/export.

**Method summary** (see script header for detail):

1. Re-split processed CSV with the **same stratified seed** as `train.py` (70/15/15).
2. Score the **held-out test** portion with the saved AE + preprocessor + threshold logic.
3. Train **Isolation Forest** on benign training rows for baseline comparison.
4. Metrics: precision, recall, F1, PR-AUC, ROC-AUC where defined.
5. Threshold sweep on benign **validation** MSE percentiles (reporting, not silently changing production threshold file).

## In-app evaluation (exploratory)

- **Overview** — headline metrics for the **current** scoring bundle (project CSV or successful in-app pipeline).
- **Detection / Evaluation pages** — tables and charts on the **same scored frame** loaded in session.

These are **not** a substitute for `evaluate.py` when you need a **frozen** split and written evidence for the report.

## Automated checks

```bash
pytest
```

See `tests/` for unit coverage of validation, repair, metric helpers (including helpers re-exported from `iot_streamlit` that live in `scoring_types`), and session-key integrity. **CI** runs the same command on push (`.github/workflows/ci.yml`).

## Known limitations (for critical write-up)

- Metrics vs Zeek `label` are **dataset- and threshold-specific**; not a production IDS claim (`README.md`).
- **Batch** scoring only — not live interface capture (`README.md`).
- Uploads are **session-local** — see `docs/PRIVACY_AND_SCOPE.md`.
