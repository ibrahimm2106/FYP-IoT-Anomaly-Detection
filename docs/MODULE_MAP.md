# Module map (maintainer view)

| Path | Responsibility |
|------|----------------|
| `app.py` | `st.navigation` (**app** · Main Workflow · Advanced Tools) + `nav.run()`; scripts under `views/`. |
| `src/iot_constants.py` | `PROJECT_ROOT`, wizard **session keys**, `WIZARD_STEP_PAGES`, detection radio label strings. |
| `src/iot_paths.py` | Path objects for data, models, preprocessor, threshold, feature-column pickle (`iot_constants` for `PROJECT_ROOT`). |
| `src/user_messages.py` | Examiner-facing error text (`friendly_scoring_error`, etc.). |
| `src/scoring_types.py` | **`ScoringBundle`**, reconstruction MSE, contingency/confusion helpers, `finalize_scoring_bundle`, PR/F1 helpers. |
| `src/artifact_loaders.py` | Disk I/O: threshold text, preprocessor pickle, processed CSV, Keras paths, feature-column meta (no Streamlit). |
| `src/scoring_engine.py` | `expected_feature_column_order`, `validate_dataframe_for_scoring`, **`build_scoring_bundle`** (transform + predict + finalize). |
| `src/table_io.py` | `parse_csv_bytes`, `try_read_processed_csv`, `missing_values_top_columns`. |
| `src/scoring_reports.py` | Metrics row dict/CSV/JSON bytes, `classification_report_markdown`, `metrics_filename_stub`. |
| `src/iot_streamlit.py` | Streamlit caches, `compute_scoring` / `score_dataframe` (delegates to **`scoring_engine`**), wizard chrome, markdown constants, sidebar metrics; re-exports some scoring symbols for **`app_core`**. |
| `src/app_core.py` | Re-exports for `views/*.py` — stable import surface. |
| `src/ui_helpers.py` | `setup_wizard_page`, `setup_page` (classic chrome), `render_wizard_step_header`, `render_classic_page_header`, multipage sidebar hint. |
| `src/ui_theme.py` | Injected global CSS. |
| `src/validation_helpers.py` | Schema overview, data quality summaries (uses `missing_values_top_columns` from **`table_io`**). |
| `src/repair_helpers.py` | In-memory repair transforms + summaries. |
| `src/evaluation_helpers.py` | Metrics tables, FP/FN helpers, baseline JSON table (uses **`scoring_types`** + `iot_streamlit` for baseline path helper). |
| `src/export_helpers.py` | Export payloads (metrics/report helpers via **`iot_streamlit`** re-exports from **`scoring_reports`**). |
| `src/preprocess.py` | Raw labelled conn → processed CSV. |
| `src/model.py` | Keras autoencoder definition. |
| `train.py` | Fit preprocessor + model; write `models/`. |
| `evaluate.py` | Held-out evaluation + baseline + JSON reports. |
| `tests/` | `pytest` suite (see `docs/EVALUATION.md`). |

**Hot path for scoring:** `views/*` → `app_core` → `iot_streamlit` → **`scoring_engine.build_scoring_bundle`** (with `artifact_loaders` / `iot_paths` / `scoring_types`).
