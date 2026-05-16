# Architecture — IoT autoencoder Streamlit artefact

This note complements `README.md` for maintainers and examiners.

**Related:** [`DESIGN.md`](DESIGN.md) (decision log), [`EVALUATION.md`](EVALUATION.md) (reproducible eval + tests), [`PRIVACY_AND_SCOPE.md`](PRIVACY_AND_SCOPE.md), [`ACCESSIBILITY.md`](ACCESSIBILITY.md), [`MODULE_MAP.md`](MODULE_MAP.md), [`../diagrams/ARCHITECTURE_DIAGRAMS.md`](../diagrams/ARCHITECTURE_DIAGRAMS.md) (Mermaid).

## High-level flow

1. **Offline** — `src/preprocess.py` builds a processed CSV; `train.py` fits the preprocessor + Keras autoencoder and writes `models/` (weights, `preprocessor.pkl`, `threshold.txt`).
2. **Online (Streamlit)** — Pages call `src/app_core.py`, which delegates to `src/iot_streamlit.py` for Streamlit caches, environment checks, and orchestration. Core scoring runs through **`src/scoring_engine.py`** (`build_scoring_bundle`) with artefacts from **`src/artifact_loaders.py`** / **`src/iot_paths.py`** and types from **`src/scoring_types.py`**.

The **seven-step wizard** (`views/01_Select_Data.py` … `views/07_Use_Model.py`) keeps tabular data and threshold overrides in **session state**; advanced tools (`views/10_*.py`–`views/17_*.py`) reuse the same scoring helpers.

## Key modules

| Module | Role |
|--------|------|
| `app.py` | Streamlit entry: `st.navigation` (**app** · Main Workflow · Advanced Tools) and `nav.run()`. |
| `src/iot_streamlit.py` | Streamlit-only: caches, `compute_scoring` / `score_dataframe`, wizard chrome, sidebar metrics; delegates scoring to **`scoring_engine`**. |
| `src/scoring_types.py` | `ScoringBundle` and pure metric / matrix helpers (no Streamlit). |
| `src/scoring_engine.py` | Feature-column order, validation, `build_scoring_bundle` (preprocess + Keras + bundle). |
| `src/artifact_loaders.py` | Read threshold, preprocessor, processed CSV, list Keras files (no Streamlit). |
| `src/iot_paths.py` | Path constants for artefacts (used by loaders and UI). |
| `src/table_io.py` | CSV upload parsing and missing-value summaries. |
| `src/scoring_reports.py` | Metrics export rows (CSV/JSON) and markdown report text. |
| `src/iot_constants.py` | Wizard session keys and step metadata. |
| `src/app_core.py` | Re-exports the public API used by `views/*.py` so imports stay short. |
| `src/ui_theme.py` | Injected CSS string (`IOT_APP_STYLESHEET`) — single source for colours / cards. |
| `src/ui_helpers.py` | `setup_page` / `setup_wizard_page`, step headers, multipage hint. |
| `src/validation_helpers.py` | Schema and data-quality summaries (table I/O helpers from `table_io`). |
| `src/repair_helpers.py` | In-memory repair transforms for wizard step 2. |
| `src/evaluation_helpers.py` | Metrics and confusion-style tables from a bundle (`scoring_types`). |
| `src/export_helpers.py` | CSV / markdown export payloads. |

## Session keys (wizard)

Defined in **`src/iot_constants.py`** (imported by `iot_streamlit.py`; prefix `SK_` / `iot_`):

- `SK_WIZARD_DATA_SOURCE`, `SK_WIZARD_UPLOAD_BYTES`, `SK_WIZARD_UPLOAD_NAME` — select / repair / hand-off to detection.
- `SK_REPAIR_ORIGINAL_DF`, `SK_REPAIR_WORKING_DF`, `SK_REPAIR_LAST_LOG` — repair step working copy.
- `SK_WIZARD_MODEL_PATH` — optional override for `load_model()`.
- `SK_WIZARD_SESSION_THRESHOLD` — optional session MSE cut-off (does not edit `threshold.txt` on disk).

Test / export pages may read `iot_wizard_test_bundle` (see wizard Test page).

## Styling

Global rules live in `src/ui_theme.py` and are injected by `render_app_chrome()` on every page. Streamlit `[theme]` in `.streamlit/config.toml` should stay in sync with the accent colour for native widgets.
