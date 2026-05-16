"""Streamlit application entrypoint.

Run from the project root with:

``streamlit run app.py``

Navigation is intentionally owned by ``src.navigation``. The root file stays
small: configure the Streamlit shell, render the grouped button menu, then route
to the selected page function from ``st.session_state.current_page``.
"""

from __future__ import annotations

import streamlit as st

from src.navigation import render_current_page, render_navigation_menu


def main() -> None:
    """Render the application shell and the selected page."""
    st.set_page_config(
        page_title="IoT-23 anomaly detection",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    render_navigation_menu()
    render_current_page()


if __name__ == "__main__":
    main()
