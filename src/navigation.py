"""Button-driven routing for the Streamlit application.

This module replaces Streamlit's sidebar ``st.navigation`` API with an explicit
session-state router. Pages remain in ``views/`` so existing page ownership stays
clear, while the application shell gets a scalable grouped button menu.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import hashlib
import runpy

import streamlit as st

from src.iot_constants import PROJECT_ROOT
from src.iot_streamlit import render_app_chrome

CURRENT_PAGE_KEY = "current_page"


@dataclass(frozen=True)
class PageRoute:
    """One routable page in the application shell."""

    name: str
    category: str
    script_path: str
    summary: str


ROUTES: tuple[PageRoute, ...] = (
    PageRoute(
        "Overview",
        "Command Center",
        "views/Home.py",
        "KPIs, scoring status, and guided workflow entry.",
    ),
    PageRoute("Select Data", "Data Ingestion", "views/01_Select_Data.py", "Choose project CSV or upload."),
    PageRoute("Repair Data", "Data Ingestion", "views/02_Repair_Data.py", "Clean the working table in memory."),
    PageRoute("Data Overview", "Data Ingestion", "views/10_Data_Overview.py", "Inspect provenance, labels, and quality."),
    PageRoute("Select Model", "Model Lifecycle", "views/03_Select_Model.py", "Pick the saved Keras artefact."),
    PageRoute("Prepare Model", "Model Lifecycle", "views/04_Prepare_Model.py", "Confirm threshold and feature shape."),
    PageRoute("Test Model", "Model Lifecycle", "views/05_Test_Model.py", "Smoke-test scoring before export."),
    PageRoute("Use Model", "Model Lifecycle", "views/07_Use_Model.py", "Score a compatible table directly."),
    PageRoute("Detection Results", "Model Evaluation", "views/11_Detection_Results.py", "Ranked rows, filters, exports."),
    PageRoute("Evaluation", "Model Evaluation", "views/12_Evaluation.py", "Metrics, confusion counts, FP/FN analysis."),
    PageRoute("Advanced Analysis", "Model Evaluation", "views/14_Advanced_Analysis.py", "Curves, sweeps, baseline, test JSON."),
    PageRoute("Explainability", "Model Evaluation", "views/15_Explainability.py", "Feature-level reconstruction context."),
    PageRoute("Model Information", "System Metrics", "views/13_Model_Info.py", "Training notes and artefact details."),
    PageRoute("Live Simulation", "System Metrics", "views/16_Live_Simulation.py", "Playback-style scoring simulation."),
    PageRoute("Export", "Reports and Export", "views/06_Export.py", "Wizard export step."),
    PageRoute("Export Tools", "Reports and Export", "views/17_Export_tools.py", "Advanced export formats."),
)

ROUTES_BY_NAME: "OrderedDict[str, PageRoute]" = OrderedDict((route.name, route) for route in ROUTES)
ROUTE_NAME_BY_SCRIPT = {route.script_path.replace("\\", "/").lower(): route.name for route in ROUTES}


def _script_renderer(script_path: str) -> Callable[[], None]:
    """Return a page rendering function backed by a ``views/*.py`` script."""

    def render() -> None:
        _run_view_script(script_path)

    render.__name__ = f"render_{Path(script_path).stem.lower()}"
    render.__doc__ = f"Render {script_path} through the session-state router."
    return render


PAGES: "OrderedDict[str, Callable[[], None]]" = OrderedDict(
    (route.name, _script_renderer(route.script_path)) for route in ROUTES
)


def _default_page() -> str:
    """Return the initial page for a new Streamlit session."""
    return "Overview"


def _normalise_script_ref(page: str | Path) -> str:
    """Convert Streamlit page references into repository-relative path keys."""
    raw = str(page).replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    path = Path(raw)
    if path.is_absolute():
        try:
            raw = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            raw = path.as_posix()
    return raw.lower()


def resolve_page_name(page: str | Path) -> str | None:
    """Resolve a route name or legacy ``views/*.py`` reference to a page name."""
    if isinstance(page, str) and page in ROUTES_BY_NAME:
        return page
    return ROUTE_NAME_BY_SCRIPT.get(_normalise_script_ref(page))


def navigate_to(page_name: str) -> None:
    """Set the current route and trigger a Streamlit rerun."""
    st.session_state.current_page = page_name
    st.rerun()


def _ensure_current_page() -> str:
    """Initialize and validate ``st.session_state.current_page``."""
    current = st.session_state.get(CURRENT_PAGE_KEY)
    if current not in PAGES:
        current = _default_page()
        st.session_state.current_page = current
    return str(current)


def _button_key(prefix: str, page_name: str, label: str) -> str:
    """Build a stable key for generated navigation buttons."""
    digest = hashlib.sha1(f"{prefix}:{page_name}:{label}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _grouped_routes() -> "OrderedDict[str, list[PageRoute]]":
    """Return routes grouped in the same order as ``ROUTES``."""
    grouped: "OrderedDict[str, list[PageRoute]]" = OrderedDict()
    for route in ROUTES:
        grouped.setdefault(route.category, []).append(route)
    return grouped


def render_navigation_menu() -> None:
    """Render the grouped button menu that controls ``current_page``."""
    render_app_chrome()
    current = _ensure_current_page()
    expanded = current == _default_page()

    with st.expander(f"Application menu - current page: {current}", expanded=expanded):
        st.caption("Grouped page buttons keep the app scalable as workflow, evaluation, and system tools grow.")
        for category, routes in _grouped_routes().items():
            st.markdown(f"**{category}**")
            columns = st.columns(min(3, len(routes)))
            for index, route in enumerate(routes):
                with columns[index % len(columns)]:
                    selected = route.name == current
                    label = route.name if not selected else f"{route.name} - open"
                    if st.button(
                        label,
                        key=_button_key("nav", route.name, route.category),
                        type="primary" if selected else "secondary",
                        use_container_width=True,
                        help=route.summary,
                        disabled=selected,
                    ):
                        navigate_to(route.name)


def render_current_page() -> None:
    """Render the page selected in ``st.session_state.current_page``."""
    current = _ensure_current_page()
    render_page = PAGES[current]
    render_page()


@contextmanager
def _patched_streamlit_page_api() -> Iterator[None]:
    """Adapt legacy page scripts to the custom router during execution.

    Existing views still contain ``st.page_link`` and ``st.switch_page`` calls
    that used to target Streamlit's multipage registry. While a view is running,
    those calls are translated into router button actions.
    """

    original_set_page_config = st.set_page_config
    original_switch_page = st.switch_page
    original_page_link = st.page_link

    def _set_page_config_noop(*_args: object, **_kwargs: object) -> None:
        return None

    def _switch_page(page: str | Path) -> None:
        page_name = resolve_page_name(page)
        if page_name is None:
            st.error(f"Unknown page target: {page}")
            st.stop()
        navigate_to(page_name)

    def _page_link(
        page: str | Path,
        *,
        label: str | None = None,
        icon: str | None = None,
        help: str | None = None,
        disabled: bool = False,
        use_container_width: bool = True,
        **_kwargs: object,
    ) -> bool:
        page_name = resolve_page_name(page)
        if page_name is None:
            st.caption(label or str(page))
            return False
        route = ROUTES_BY_NAME[page_name]
        text = label or route.name
        if icon:
            text = f"{icon} {text}"
        if st.button(
            text,
            key=_button_key("page_link", page_name, text),
            help=help or route.summary,
            disabled=disabled or page_name == st.session_state.get(CURRENT_PAGE_KEY),
            use_container_width=use_container_width,
        ):
            navigate_to(page_name)
            return True
        return False

    st.set_page_config = _set_page_config_noop
    st.switch_page = _switch_page
    st.page_link = _page_link
    try:
        yield
    finally:
        st.set_page_config = original_set_page_config
        st.switch_page = original_switch_page
        st.page_link = original_page_link


def _run_view_script(script_path: str) -> None:
    """Execute a view script and call ``main()`` when the script exposes one."""
    path = PROJECT_ROOT / script_path
    if not path.is_file():
        st.error(f"Missing page script: {script_path}")
        return

    with _patched_streamlit_page_api():
        namespace = runpy.run_path(str(path))
        main = namespace.get("main")
        if callable(main):
            main()


__all__ = [
    "CURRENT_PAGE_KEY",
    "PAGES",
    "ROUTES",
    "PageRoute",
    "navigate_to",
    "render_current_page",
    "render_navigation_menu",
    "resolve_page_name",
]
