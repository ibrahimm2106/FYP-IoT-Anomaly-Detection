# Accessibility — UI notes

This artefact is a **Streamlit** multipage app. The following design choices support clearer use and basic inclusive access:

- **Contrast:** Light surfaces (`#f4f7fb`, `#ffffff`) with body text `#0f172a` and accent `#0f766e` are chosen for readable contrast on typical displays. See comments in `src/ui_theme.py`.
- **Keyboard:** Custom CSS adds **`:focus-visible`** outlines on main-area and sidebar links and buttons so keyboard users can see focus (see `src/ui_theme.py`).
- **Help text:** Metric widgets and several controls use Streamlit **`help=`** tooltips; wizard steps use short bullet lists and optional popovers instead of long blocks on the page.
- **Screen readers:** Prefer plain labels over emoji in popovers and alerts. Mini-examples use `role="note"` where rendered via `src/ui_helpers.py`.

**Limitations:** Streamlit controls the DOM; not every internal widget exposes the same ARIA labelling as a hand-built site. For a viva, mention **batch** (not live) scope and that uploads are **session-local** (`docs/PRIVACY_AND_SCOPE.md`).
