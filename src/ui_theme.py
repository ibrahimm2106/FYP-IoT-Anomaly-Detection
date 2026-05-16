"""
Global Streamlit styling: colour tokens, typography, and layout polish.

Injected once per page via ``render_app_chrome()`` in ``iot_streamlit``. Colours are
chosen for **WCAG 2.1 AA** contrast on light surfaces (body text #0f172a on #ffffff
and #f4f7fb exceeds 4.5:1; accent #0f766e on white for UI chrome exceeds 4.5:1 for
large UI text; avoid using accent for long body copy).
"""

from __future__ import annotations

# Single stylesheet fragment (injected with st.markdown(..., unsafe_allow_html=True)).
IOT_APP_STYLESHEET = """
<style>
:root {
  --iot-bg: #f4f7fb;
  --iot-surface: #ffffff;
  --iot-text: #0f172a;
  --iot-muted: #475569;
  --iot-border: #cbd5e1;
  --iot-accent: #0f766e;
  --iot-accent-strong: #115e59;
  --iot-accent-soft: #ecfdf5;
  --iot-accent-border: #5eead4;
  --iot-warn-bg: #fffbeb;
  --iot-warn-border: #fcd34d;
  --iot-radius: 12px;
  --iot-radius-sm: 8px;
  --iot-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), 0 2px 8px rgba(15, 23, 42, 0.04);
  --iot-font: "Source Sans 3", "Segoe UI", system-ui, -apple-system, sans-serif;
}

/* App shell */
[data-testid="stAppViewContainer"] {
  background: var(--iot-bg) !important;
}
.main .block-container {
  padding-top: 1.35rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1100px !important;
  font-family: var(--iot-font);
}

/* Typography hierarchy */
.main h1, .main h2, .main h3 {
  color: var(--iot-text) !important;
  font-weight: 650 !important;
  letter-spacing: -0.02em !important;
}
.main h1 { font-size: 1.75rem !important; margin-top: 0.25rem !important; }
.main h2 { font-size: 1.2rem !important; margin-top: 1.25rem !important; }
.main h3 { font-size: 1.05rem !important; }
.main .stMarkdown p, .main .stCaption {
  color: var(--iot-muted);
  line-height: 1.55;
}

/* Metrics as cards */
div[data-testid="stMetric"] {
  background: var(--iot-surface) !important;
  border: 1px solid var(--iot-border) !important;
  border-radius: var(--iot-radius-sm) !important;
  padding: 0.65rem 0.85rem !important;
  box-shadow: var(--iot-shadow) !important;
}
div[data-testid="stMetric"] label {
  color: var(--iot-muted) !important;
  font-size: 0.78rem !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--iot-text) !important;
}

/* Primary actions */
button[kind="primary"], [data-testid="baseButton-primary"] {
  background-color: var(--iot-accent) !important;
  border-color: var(--iot-accent-strong) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  border-radius: var(--iot-radius-sm) !important;
}
button[kind="primary"]:hover {
  background-color: var(--iot-accent-strong) !important;
}

/* Dividers */
hr {
  margin: 1.5rem 0 !important;
  border-color: var(--iot-border) !important;
}

/* Expanders */
.streamlit-expanderHeader {
  font-weight: 600 !important;
  color: var(--iot-text) !important;
}

/* Sidebar — light panel with accent rail */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #eef2f7 0%, #e8edf4 100%) !important;
  border-right: 1px solid var(--iot-border) !important;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown li,
[data-testid="stSidebar"] [data-testid="stCaption"] {
  color: var(--iot-muted) !important;
}
[data-testid="stSidebar"] [data-testid="stHeader"] {
  background: transparent !important;
}

.iot-sidebar-brand {
  border-left: 4px solid var(--iot-accent);
  padding: 0.5rem 0 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  background: var(--iot-surface);
  border-radius: 0 var(--iot-radius-sm) var(--iot-radius-sm) 0;
  box-shadow: var(--iot-shadow);
}
.iot-sidebar-brand-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--iot-text) !important;
}
.iot-sidebar-brand-sub {
  margin: 0.2rem 0 0 0;
  font-size: 0.78rem;
  color: var(--iot-muted) !important;
  line-height: 1.35;
}

/* Wizard step rail */
.iot-workflow-rail {
  border: 1px solid var(--iot-border);
  border-radius: var(--iot-radius);
  background: var(--iot-surface);
  padding: 0.65rem 0.75rem 0.85rem;
  margin-bottom: 1rem;
  box-shadow: var(--iot-shadow);
}
.iot-workflow-label {
  margin: 0 0 0.5rem 0;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--iot-accent);
}
.iot-wizard-foot {
  margin-top: 0.45rem;
  font-size: 0.8rem;
  color: var(--iot-muted) !important;
}
.iot-wizard-pill-active {
  display: inline-block;
  background: var(--iot-accent-soft);
  border: 1px solid var(--iot-accent-border);
  color: var(--iot-accent-strong) !important;
  font-weight: 700;
  font-size: 0.82rem;
  padding: 0.2rem 0.45rem;
  border-radius: 6px;
}
.iot-wizard-here {
  font-size: 0.72rem;
  color: var(--iot-accent) !important;
  font-weight: 600;
  margin-top: 0.15rem;
}

/* Step page hero */
.iot-step-head {
  background: var(--iot-surface);
  border: 1px solid var(--iot-border);
  border-radius: var(--iot-radius);
  padding: 1rem 1.2rem 1.1rem;
  margin: 0 0 1.15rem 0;
  box-shadow: var(--iot-shadow);
  border-left: 4px solid var(--iot-accent);
}
.iot-home-head {
  border-left-color: #0369a1;
}
.iot-step-badge {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--iot-accent);
  margin-bottom: 0.35rem;
}
.iot-home-head .iot-step-badge {
  color: #0369a1;
}

/* Classic multipage tools — distinct from numbered wizard */
.iot-classic-head {
  border-left-color: #64748b;
}
.iot-classic-head .iot-step-badge {
  color: #475569;
  letter-spacing: 0.05em;
}

/* Wizard strip (bordered block that contains .iot-workflow-label): two rows may wrap on narrow viewports */
[data-testid="stVerticalBlockBorderWrapper"]:has(p.iot-workflow-label) [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
  row-gap: 0.35rem;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(p.iot-workflow-label) [data-testid="stHorizontalBlock"] [data-testid="column"] {
  min-width: 5.5rem;
  flex: 1 1 auto !important;
}

/* Keyboard focus (WCAG 2.4.7) — complements Streamlit widgets */
.main a:focus-visible,
.main button:focus-visible,
[data-testid="stSidebar"] a:focus-visible,
[data-testid="stSidebar"] button:focus-visible {
  outline: 2px solid var(--iot-accent);
  outline-offset: 2px;
}
.iot-step-title {
  margin: 0 0 0.4rem 0 !important;
  font-size: 1.65rem !important;
  color: var(--iot-text) !important;
  font-weight: 700 !important;
  letter-spacing: -0.03em !important;
}
.iot-step-tagline {
  margin: 0 !important;
  font-size: 0.95rem !important;
  line-height: 1.5 !important;
  color: var(--iot-muted) !important;
}
.iot-step-do {
  margin: 0.65rem 0 0 0;
  padding-left: 1.15rem;
  color: var(--iot-text);
  font-size: 0.88rem;
  line-height: 1.5;
}
.iot-step-do li {
  margin-bottom: 0.25rem;
}

/* Visible mini-example (not a replacement for critical steps — use with bullets) */
.iot-mini-example {
  background: var(--iot-accent-soft);
  border: 1px solid var(--iot-accent-border);
  border-radius: var(--iot-radius-sm);
  padding: 0.55rem 0.75rem;
  margin: 0.65rem 0 0.9rem 0;
  font-size: 0.86rem;
  line-height: 1.45;
  color: #134e4a !important;
}
.iot-mini-example strong {
  color: var(--iot-accent-strong) !important;
}

/* Utility card (markdown-driven sections) */
.iot-note-card {
  border: 1px solid var(--iot-border);
  border-radius: var(--iot-radius-sm);
  background: rgba(255, 255, 255, 0.92);
  padding: 0.85rem 1rem;
  margin-bottom: 0.85rem;
  box-shadow: var(--iot-shadow);
}
.iot-soft {
  color: var(--iot-muted) !important;
}

/* Dataframes — subtle frame */
[data-testid="stDataFrame"] {
  border: 1px solid var(--iot-border);
  border-radius: var(--iot-radius-sm);
}
</style>
"""

__all__ = ["IOT_APP_STYLESHEET"]
