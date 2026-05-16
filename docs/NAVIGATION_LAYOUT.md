# Streamlit navigation layout

The app now uses a single Streamlit entrypoint and a session-state router instead of `st.navigation`.

```text
app.py
  -> render grouped button menu
  -> render page selected by st.session_state.current_page

src/navigation.py
  -> ROUTES: canonical route metadata grouped by functional category
  -> PAGES: page name to render function mapping
  -> render_navigation_menu(): button grid grouped by category
  -> render_current_page(): conditional route execution
  -> compatibility shim for legacy st.page_link / st.switch_page calls

views/
  -> existing page scripts remain the rendering surface for each workflow module
  -> high-traffic pages use tabs and compact metric grids to reduce stacked content
```

Functional navigation groups:

| Group | Pages |
|-------|-------|
| Command Center | Overview |
| Data Ingestion | Select Data, Repair Data, Data Overview |
| Model Lifecycle | Select Model, Prepare Model, Test Model, Use Model |
| Model Evaluation | Detection Results, Evaluation, Advanced Analysis, Explainability |
| System Metrics | Model Information, Live Simulation |
| Reports and Export | Export, Export Tools |

Routing state is stored in `st.session_state.current_page`. Workflow buttons that still reference `views/*.py` are translated by `src/navigation.py` so the older page scripts can continue to work while the app runs through the new router.
