# Design — evidence-based solution

This document maps **requirements → design decisions → implementation** so examiners can trace the artefact beyond UI polish.

## Problem constraints

| ID | Constraint | Source |
|----|------------|--------|
| R1 | Tabular Zeek-style **connection** records (not raw packets). | Dataset / brief |
| R2 | **Unsupervised** anomaly signal (no attack labels required at train time). | Literature / scope |
| R3 | **Reproducible** batch scoring in a standard environment (Python + pinned deps). | Module rubric |
| R4 | Optional **supervised-style** metrics when `label` exists (illustrative only). | Ethical framing (`README.md`) |
| R5 | **No server-side persistence** of user uploads; session-scoped processing. | Privacy (`docs/PRIVACY_AND_SCOPE.md`) |

## Decision log

| Decision | Alternatives considered | Rationale | Where |
|----------|-------------------------|-----------|-------|
| Dense **autoencoder** + reconstruction **MSE** | One-class SVM, Isolation Forest only, LSTM-AE | Classic AE on benign-only is standard, interpretable, fits tabular Zeek features; IF retained as **optional baseline** artefact (`evaluate.py`, `models/baseline_metrics.json`). | `train.py`, `src/model.py`, `evaluate.py` |
| **Fixed threshold** from benign **validation** MSE | Percentile on test set, manual only | Matches common practice; avoids test leakage for threshold calibration narrative in training script. | `train.py` → `models/threshold.txt` |
| **sklearn** preprocessor persisted (`joblib`/`pickle`) | All in-Keras preprocessing | Clear separation: preprocessing versioned with training run; scoring reloads same pipeline. | `models/preprocessor.pkl` |
| **Streamlit** multipage + **7-step wizard** | Single-page only, Dash | Rapid iteration, examiner-friendly walkthrough; advanced tools (`10_`–`17_`) grouped in the sidebar. | `app.py` (`st.navigation`), `views/01_*.py`–`07_*.py`, `src/ui_helpers.py` |
| Session **repair** in memory | Write repaired CSV to disk by default | Safer default for lab machines; user exports explicitly from wizard. | `views/02_Repair_Data.py`, `src/repair_helpers.py` |
| **Facade** `app_core` re-exporting `iot_streamlit` | Pages import `iot_streamlit` directly | Shorter page imports; single entry for tools. | `src/app_core.py` |

## Component ↔ requirement traceability

| Component | Satisfies |
|-----------|-----------|
| `src/preprocess.py` | R1 — flatten labelled conn export to CSV. |
| `train.py` | R2, R3 — benign-only AE + saved artefacts. |
| `src/iot_streamlit.py` + `src/scoring_engine.py` — `compute_scoring` / `score_dataframe` / `build_scoring_bundle` | R3, R4 — deterministic scoring + metrics when labels exist. |
| `src/validation_helpers.py` + `src/table_io.py` | R1, R3 — schema checks and upload/processed table helpers. |
| `src/repair_helpers.py` | R5 — optional cleaning without persisting uploads. |
| `evaluate.py` | R3, R4 — held-out test evaluation + baseline JSON for comparison. |

## Session keys (wizard)

Canonical string keys live in **`src/iot_constants.py`** to avoid drift. See `docs/ARCHITECTURE.md` for meanings.

## Scoring module split (done)

Heavy scoring logic is split so **`iot_streamlit`** stays Streamlit- and cache-oriented: **`scoring_types`** (bundle + metrics), **`scoring_engine`** (validate + transform + infer), **`artifact_loaders`** / **`iot_paths`** (disk), **`table_io`** (CSV / null audit), **`scoring_reports`** (export payloads), **`user_messages`** (errors). **`app_core`** still exposes the same symbols via **`iot_streamlit`** re-exports where view scripts depended on them. See **`docs/MODULE_MAP.md`**.
