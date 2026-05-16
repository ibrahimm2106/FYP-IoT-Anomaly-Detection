"""
Reusable UI helpers for a consistent professional layout.

Wizard pages should call ``setup_wizard_page`` then ``render_wizard_step_header``
(and optionally ``render_mini_example``). **Classic** sidebar pages call ``setup_page``
then ``render_classic_page_header`` so the workflow strip does not fake a wizard step.
"""

from __future__ import annotations

import html

import streamlit as st

from src.iot_streamlit import (
    render_app_chrome,
    render_multipage_navigation_hint,
    render_wizard_stepper,
)

# Canonical names for examiner-facing copy (match README / stepper order).
WIZARD_STEP_NAMES: tuple[str, ...] = (
    "Select Data",
    "Repair Data",
    "Select Model",
    "Prepare Model",
    "Test Model",
    "Export",
    "Use Model",
)


def setup_page(*, workflow_step: int = 0, workflow_key: str = "", pipeline_stage: str = "") -> None:
    """Classic multipage tools: chrome + wizard links with **no misleading step highlight**."""
    del workflow_step, workflow_key, pipeline_stage
    render_app_chrome()
    render_wizard_stepper(current_step=0, classic_mode=True)


def setup_wizard_page(*, wizard_step: int) -> None:
    """Configure shared chrome for one numbered wizard page.

    Args:
        wizard_step: One-based wizard step to highlight in the workflow strip.
    """
    render_app_chrome()
    render_wizard_stepper(current_step=wizard_step, classic_mode=False)


def render_wizard_step_header(
    *,
    step: int,
    title: str,
    tagline: str,
    bullets: tuple[str, ...] | None = None,
) -> None:
    """
    Hero block for wizard steps (after ``setup_wizard_page``).

    ``step`` is 1–7. Keeps hierarchy: badge → title → tagline → optional short checklist
    (critical actions stay visible; use a popover for long prose).
    """
    if step < 1 or step > len(WIZARD_STEP_NAMES):
        raise ValueError(f"step must be 1–{len(WIZARD_STEP_NAMES)}, got {step}")
    name = WIZARD_STEP_NAMES[step - 1]
    badge = html.escape(f"Step {step} of 7 · {name}")
    t = html.escape(title)
    g = html.escape(tagline)
    st.markdown(
        f'<div class="iot-step-head"><span class="iot-step-badge">{badge}</span>'
        f'<h1 class="iot-step-title">{t}</h1><p class="iot-step-tagline">{g}</p></div>',
        unsafe_allow_html=True,
    )
    if bullets:
        items = "".join(f"<li>{html.escape(b)}</li>" for b in bullets)
        st.markdown(f'<ul class="iot-step-do">{items}</ul>', unsafe_allow_html=True)


def render_classic_page_header(
    *,
    title: str,
    tagline: str,
    bullets: tuple[str, ...] | None = None,
) -> None:
    """Hero for sidebar-driven classic pages (not a numbered wizard step)."""
    t = html.escape(title)
    g = html.escape(tagline)
    st.markdown(
        f'<div class="iot-step-head iot-classic-head"><span class="iot-step-badge">Advanced tool</span>'
        f'<h1 class="iot-step-title">{t}</h1><p class="iot-step-tagline">{g}</p></div>',
        unsafe_allow_html=True,
    )
    if bullets:
        items = "".join(f"<li>{html.escape(b)}</li>" for b in bullets)
        st.markdown(f'<ul class="iot-step-do">{items}</ul>', unsafe_allow_html=True)


def render_dashboard_header(*, title: str, tagline: str) -> None:
    """Overview page hero (step 0 — not part of the numbered wizard strip highlight)."""
    t = html.escape(title)
    g = html.escape(tagline)
    st.markdown(
        f'<div class="iot-step-head iot-home-head"><span class="iot-step-badge">Overview</span>'
        f'<h1 class="iot-step-title">{t}</h1><p class="iot-step-tagline">{g}</p></div>',
        unsafe_allow_html=True,
    )


def render_mini_example(text: str) -> None:
    """Short, always-visible example line (HTML-escaped)."""
    st.markdown(
        f'<div class="iot-mini-example" role="note"><strong>Example:</strong> {html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


__all__ = [
    "render_app_chrome",
    "render_classic_page_header",
    "render_multipage_navigation_hint",
    "render_mini_example",
    "render_dashboard_header",
    "render_wizard_step_header",
    "render_wizard_stepper",
    "setup_page",
    "setup_wizard_page",
    "WIZARD_STEP_NAMES",
]
