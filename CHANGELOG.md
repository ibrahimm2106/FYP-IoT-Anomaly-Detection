# Changelog

All notable changes to this repository are documented here (artefact evolution for examiners).

## [Unreleased]

### Changed

- **Navigation / IA** — Page scripts live in **`views/`** (no flat auto `pages/` list). Root **`app.py`** uses **`st.navigation`** with sections **`app`** (Overview / `Home.py`), **Main Workflow** (sidebar titles **`1. Select Data`** … **`7. Use Model`**), and **Advanced Tools** (including **Model Information** for `13_Model_Info.py`). Wizard step 6 remains **Export** (`06_Export.py`); extra formats hub **`17_Export_tools.py`**. `WIZARD_STEP_PAGES`, `page_link` / `switch_page` use `views/...` paths. **No** scoring or model logic changed. Requires **Streamlit ≥ 1.36** (`st.navigation` / `st.Page`).

### Added

Ten maintainer-facing improvements (constants, scoring split, quality gates, documentation):

1. **`src/iot_constants.py`** — central wizard session keys and `WIZARD_STEP_PAGES` (consumed by `iot_streamlit`).
2. **`src/iot_paths.py`** — canonical `Path`s for data, models, preprocessor, threshold, feature-column pickle.
3. **`src/user_messages.py`** — examiner-facing scoring / I/O error strings.
4. **`src/scoring_types.py`** — `ScoringBundle`, reconstruction MSE, contingency/confusion DataFrames, metric helpers, `finalize_scoring_bundle`.
5. **`src/artifact_loaders.py`** — disk-backed artefact reads (CSV, pickles, threshold, Keras file listing) without Streamlit.
6. **`src/scoring_engine.py`** — feature-column order, upload/processed validation, `build_scoring_bundle` (transform + infer + bundle).
7. **`src/table_io.py`** — CSV bytes parsing, optional processed read, missing-value column summaries.
8. **`src/scoring_reports.py`** — single-row metrics CSV/JSON, markdown classification report, export filename stub.
9. **`tests/`** + **`pytest.ini`** — automated tests for validation, repair, metric helpers, and constants; **`.github/workflows/ci.yml`** runs `pytest`; **`requirements.txt`** includes `pytest`.
10. **Documentation pack** — **`docs/DESIGN.md`**, **`docs/EVALUATION.md`**, **`docs/PRIVACY_AND_SCOPE.md`**, **`docs/MODULE_MAP.md`**, **`docs/diagrams/ARCHITECTURE_DIAGRAMS.md`** (plus **`docs/ARCHITECTURE.md`** and this changelog).

### Changed

- **`src/iot_streamlit.py`** — wizard/session constants from `iot_constants`; paths from `iot_paths`; scoring via **`scoring_engine.build_scoring_bundle`** (shared with uploads and project CSV); metrics export via **`scoring_reports`**; duplicate logic removed in favour of the modules above.
- **`src/validation_helpers.py`** — imports `missing_values_top_columns` from **`table_io`**.
- **`src/evaluation_helpers.py`** — bundle/metric/matrix helpers from **`scoring_types`**; baseline path helper from `iot_streamlit`.
- **`src/repair_helpers.py`** — lazy `expected_feature_column_order` import from **`scoring_engine`**.
- **`README.md`**, **`docs/ARCHITECTURE.md`**, **`docs/MODULE_MAP.md`**, **`docs/DESIGN.md`**, **`docs/EVALUATION.md`**, **`docs/diagrams/ARCHITECTURE_DIAGRAMS.md`**, **`src/app_core.py` module docstring** — updated to describe the layout above.
- **UI / usability** — wizard strip uses **two rows** (4+3) with wrapping CSS; **classic pages** no longer show a misleading “current wizard step”; **`render_classic_page_header`** on classic pages; **Detection** progressive disclosure; **emoji-free** popovers/alerts where practical; **`docs/ACCESSIBILITY.md`** and focus-visible styling in **`ui_theme.py`**.
- **Help flow** — short **captions** + **expanders** for long copy (`MARKDOWN_ARTEFACT_BATCH_SCORING`, evaluation definitions, dataset sources, evaluation scope); **`render_restore_training_pipeline_ui()`** (lead caption + “Step-by-step recovery” expander) replaces raw restore markdown on failure paths; wizard steps gain one-line **next-action** captions where helpful.
