"""Session keys and wizard routing are stable (single source: ``src/iot_constants``)."""

from __future__ import annotations

from pathlib import Path

from src.iot_constants import PROJECT_ROOT, WIZARD_STEP_PAGES


def test_project_root_contains_src() -> None:
    """Verify the computed project root points at this repository."""
    assert (PROJECT_ROOT / "src" / "iot_constants.py").is_file()


def test_wizard_step_pages_seven_scripts() -> None:
    """Verify the wizard exposes exactly seven existing view scripts."""
    assert len(WIZARD_STEP_PAGES) == 7
    for _label, script in WIZARD_STEP_PAGES:
        assert script is not None
        assert script.startswith("views/")
        assert (PROJECT_ROOT / script).is_file(), f"missing {script}"


def test_session_keys_are_unique_strings() -> None:
    """Verify all Streamlit session-state keys are unique non-empty strings."""
    import src.iot_constants as ic

    keys = [v for k, v in vars(ic).items() if k.startswith("SK_")]
    assert len(keys) == len(set(keys))
    assert all(isinstance(v, str) and v for v in keys)
