"""
Central definitions for wizard session-state keys and step routing.

Keeping string keys in one module avoids typos across ``views/`` and
``src/iot_streamlit.py`` and gives tests a lightweight import surface
(without loading the full scoring stack) where possible.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Detection page radio labels (exact strings — equality checks + wizard hand-off).
LABEL_DATA_SOURCE_PROJECT = "Project CSV — `data/processed/ctu_iot_34_1.csv`"
LABEL_DATA_SOURCE_UPLOAD = "Upload — my own compatible CSV"
DATA_SOURCE_CHOICES = (LABEL_DATA_SOURCE_PROJECT, LABEL_DATA_SOURCE_UPLOAD)

# Wizard → Detection hand-off (same bytes shape as a normal upload).
SK_WIZARD_UPLOAD_BYTES = "iot_wizard_upload_bytes"
SK_WIZARD_UPLOAD_NAME = "iot_wizard_upload_filename"
SK_WIZARD_DATA_SOURCE = "iot_wizard_data_source"  # "sample" | "upload"

# Wizard step 2 — in-memory repaired table (DataFrame) + last repair log dict.
SK_REPAIR_ORIGINAL_DF = "iot_repair_original_df"
SK_REPAIR_WORKING_DF = "iot_repair_working_df"
SK_REPAIR_LAST_LOG = "iot_repair_last_log"

# Wizard step 3 — optional override for which Keras file ``load_model()`` loads.
SK_WIZARD_MODEL_PATH = "iot_wizard_model_path"

# Wizard step 4 — optional session MSE threshold (unset → ``models/threshold.txt``).
SK_WIZARD_SESSION_THRESHOLD = "iot_wizard_session_threshold"

# Seven-step workflow (paths relative to project root — targets ``views/*.py`` wired from ``app.py`` ``st.navigation``).
WIZARD_STEP_PAGES: tuple[tuple[str, str | None], ...] = (
    ("Select Data", "views/01_Select_Data.py"),
    ("Repair Data", "views/02_Repair_Data.py"),
    ("Select Model", "views/03_Select_Model.py"),
    ("Prepare Model", "views/04_Prepare_Model.py"),
    ("Test Model", "views/05_Test_Model.py"),
    ("Export", "views/06_Export.py"),
    ("Use Model", "views/07_Use_Model.py"),
)

__all__ = [
    "DATA_SOURCE_CHOICES",
    "LABEL_DATA_SOURCE_PROJECT",
    "LABEL_DATA_SOURCE_UPLOAD",
    "PROJECT_ROOT",
    "SK_REPAIR_LAST_LOG",
    "SK_REPAIR_ORIGINAL_DF",
    "SK_REPAIR_WORKING_DF",
    "SK_WIZARD_DATA_SOURCE",
    "SK_WIZARD_MODEL_PATH",
    "SK_WIZARD_SESSION_THRESHOLD",
    "SK_WIZARD_UPLOAD_BYTES",
    "SK_WIZARD_UPLOAD_NAME",
    "WIZARD_STEP_PAGES",
]
