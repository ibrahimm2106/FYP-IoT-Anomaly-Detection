"""Overview dashboard: headline KPIs and entry context for the workflow."""

from __future__ import annotations

import streamlit as st

from src.app_core import (
    CAPTION_ARTEFACT_BATCH_SCORING,
    MARKDOWN_ARTEFACT_BATCH_SCORING,
    app_debug_mode,
    load_scoring_bundle,
    render_evaluation_summary_panel,
    render_restore_training_pipeline_ui,
    render_sidebar_metrics,
    render_sidebar_placeholder,
)
from src.evaluation_helpers import evaluation_metrics_from_bundle
from src.ui_helpers import (
    render_dashboard_header,
    render_mini_example,
    render_multipage_navigation_hint,
    setup_wizard_page,
)


def _render_unavailable_state(err: str | None) -> None:
    """Render the dashboard when model or data artefacts are missing."""
    status_tab, guide_tab = st.tabs(("Status", "Scoring guide"))
    with status_tab:
        st.error(err or "Could not load scoring results - fix artefacts or paths, then refresh.")
        render_restore_training_pipeline_ui()
        if app_debug_mode():
            st.warning(
                "Developer debug is enabled (`IOT_APP_DEBUG=1` or `?debug=1`). Extended error text may include a traceback."
            )
        else:
            st.caption(
                "For a full traceback only when debugging, set `IOT_APP_DEBUG=1` or append `?debug=1` to the URL."
            )
    with guide_tab:
        st.caption(CAPTION_ARTEFACT_BATCH_SCORING)
        st.markdown(MARKDOWN_ARTEFACT_BATCH_SCORING)
    render_sidebar_placeholder("Live scoring unavailable", err)


def _render_metric_grid(bundle) -> None:
    """Render a compact two-row KPI grid for the current scoring bundle."""
    ev = evaluation_metrics_from_bundle(bundle)
    with st.container(border=True):
        st.subheader("Session KPIs")
        top = st.columns(3)
        top[0].metric("Rows scored", f"{len(bundle.df):,}")
        top[1].metric("Rows flagged", f"{int(bundle.flagged.sum()):,}")
        top[2].metric("Threshold (MSE)", f"{bundle.threshold:.6f}")

        bottom = st.columns(3)
        bottom[0].metric("Precision", "n/a" if ev["precision"] is None else f"{float(ev['precision']):.4f}")
        bottom[1].metric("Recall", "n/a" if ev["recall"] is None else f"{float(ev['recall']):.4f}")
        bottom[2].metric("PR-AUC", "n/a" if ev["pr_auc"] is None else f"{float(ev['pr_auc']):.4f}")
        st.caption("Label-dependent metrics appear as n/a when `label` is unavailable.")


def _render_scoring_guide() -> None:
    """Render the compact scoring explanation in collapsible sections."""
    st.caption(CAPTION_ARTEFACT_BATCH_SCORING)
    with st.expander("Batch scoring, data sources, and cache behaviour", expanded=True):
        st.markdown(MARKDOWN_ARTEFACT_BATCH_SCORING)
    with st.expander("Quick guide - how scoring works", expanded=False):
        st.markdown(
            "1. **Input:** each row becomes a numeric vector (scaled numbers + one-hot categories); noisy IDs are dropped.\n"
            "2. **Training:** the autoencoder learns to reconstruct **benign** traffic only (**MSE**).\n"
            "3. **Score:** higher reconstruction **MSE** means a poorer fit to benign patterns.\n"
            "4. **Flag:** `threshold.txt` turns MSE into a **binary** unusual / normal decision.\n"
            "5. **Evaluation:** flags vs **`label`** when available (illustrative, not a production IDS claim)."
        )


def main() -> None:
    """Render the overview dashboard page."""
    st.set_page_config(
        page_title="Overview - IoT-23 anomaly detection",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    setup_wizard_page(wizard_step=0)

    st.caption("For a first run: steps 1-5, then return here for KPIs. Use the grouped menu for deeper tools.")
    render_dashboard_header(
        title="IoT anomaly detection artefact",
        tagline="Use the application menu for grouped navigation; use the seven-step strip for the primary guided path.",
    )

    bundle, err = load_scoring_bundle()
    if err is not None or bundle is None:
        _render_unavailable_state(err)
    else:
        render_sidebar_metrics(bundle)
        snapshot_tab, evaluation_tab, guide_tab = st.tabs(("Snapshot", "Evaluation", "Scoring guide"))
        with snapshot_tab:
            st.caption(
                "Scores Zeek-style tables with a benign-trained **autoencoder**; **reconstruction MSE** above a saved "
                "**threshold** flags unusual rows. **Labels** unlock precision/recall-style metrics when present."
            )
            render_mini_example(
                "After steps 1-5, return here to read rows scored / flagged and precision-recall at a glance."
            )
            _render_metric_grid(bundle)
        with evaluation_tab:
            render_evaluation_summary_panel(bundle)
        with guide_tab:
            _render_scoring_guide()

    st.divider()
    with st.popover("Presenter tip"):
        st.caption("Mention **batch** scoring vs **live** capture when you describe scope.")
    render_multipage_navigation_hint()


if __name__ == "__main__":
    main()
