"""
Multipage Streamlit: live simulation — replay IoT connections as a real-time feed.

Loads the scored test set (data/processed/test_scores.csv) and replays rows
at a configurable speed, mimicking a live network monitoring dashboard.

Demonstrates the model operating as a continuous anomaly detector rather than
a static batch scorer — the most compelling demo for a viva or presentation.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.app_core import load_scoring_bundle, render_sidebar_metrics, render_sidebar_placeholder
from src.plots import live_mse_figure
from src.ui_helpers import render_classic_page_header, render_multipage_navigation_hint, setup_page

st.set_page_config(
    page_title="Live Simulation · IoT-23 anomaly detection",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_page()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SCORES_PATH = PROJECT_ROOT / "data" / "processed" / "test_scores.csv"

render_classic_page_header(
    title="Live simulation",
    tagline="Replay scored test rows at a chosen speed to mimic a monitoring dashboard — not live PCAP capture.",
    bullets=("Run `python evaluate.py` to generate `data/processed/test_scores.csv` when missing.",),
)

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading scored test data…")
def _load_test_data() -> pd.DataFrame | None:
    """Load scored test rows produced by ``evaluate.py``.

    Returns:
        Reset-index dataframe when the score file exists and has required
        columns; otherwise ``None``.
    """
    if not TEST_SCORES_PATH.is_file():
        return None
    df = pd.read_csv(TEST_SCORES_PATH, low_memory=False)
    if "mse_score" not in df.columns or "flagged" not in df.columns:
        return None
    return df.reset_index(drop=True)


data = _load_test_data()

if data is None:
    # Fall back to the full bundle if test_scores.csv doesn't exist
    bundle, err = load_scoring_bundle()
    if err or bundle is None:
        st.error("Test scores and main bundle both unavailable. Run `python evaluate.py` first.")
        render_sidebar_placeholder("Simulation unavailable")
        render_multipage_navigation_hint()
        st.stop()
    render_sidebar_metrics(bundle)
    data = bundle.df.copy()
    data["mse_score"] = bundle.errors
    data["flagged"] = bundle.flagged
    st.info("Using full dataset (test_scores.csv not found). Run `python evaluate.py` to get the clean test split.")
else:
    bundle, _ = load_scoring_bundle()
    if bundle:
        render_sidebar_metrics(bundle)
    else:
        render_sidebar_placeholder("Main bundle unavailable")

threshold = float(data["mse_score"].quantile(0.99)) if "mse_score" in data.columns else 0.01
# Use the actual saved threshold if the bundle is available
if bundle is not None:
    threshold = bundle.threshold

n_total = len(data)
has_labels = "label" in data.columns

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "sim_running": False,
    "sim_pos": 0,
    "sim_mse": [],
    "sim_flagged": [],
    "sim_indices": [],
    "sim_alerts": [],
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _reset_sim() -> None:
    """Reset all live simulation session-state values to defaults."""
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# Controls
# ─────────────────────────────────────────────────────────────────────────────
ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1, 1, 1, 3])

start_label = "⏸ Pause" if st.session_state.sim_running else "▶ Start"
if ctrl1.button(start_label, use_container_width=True):
    st.session_state.sim_running = not st.session_state.sim_running

if ctrl2.button("⏮ Reset", use_container_width=True):
    _reset_sim()
    st.rerun()

speed = ctrl3.slider("Rows / tick", min_value=1, max_value=100, value=20, step=1)
tick_delay = ctrl4.slider("Tick delay (seconds)", min_value=0.05, max_value=1.0, value=0.2, step=0.05)

# Progress bar
progress_pct = st.session_state.sim_pos / n_total if n_total > 0 else 0.0
st.progress(min(progress_pct, 1.0), text=f"{st.session_state.sim_pos:,} / {n_total:,} connections processed")

# ─────────────────────────────────────────────────────────────────────────────
# KPI header (updates each tick)
# ─────────────────────────────────────────────────────────────────────────────
n_processed = st.session_state.sim_pos
n_alerts = len(st.session_state.sim_alerts)
alert_rate = n_alerts / max(n_processed, 1) * 100

k1, k2, k3, k4 = st.columns(4)
k1.metric("Connections processed", f"{n_processed:,}")
k2.metric("Anomalies detected", f"{n_alerts:,}", delta=None)
k3.metric("Alert rate", f"{alert_rate:.1f}%")
k4.metric("Threshold (MSE)", f"{threshold:.6f}")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Charts
# ─────────────────────────────────────────────────────────────────────────────
chart_col, feed_col = st.columns([2, 1])

with chart_col:
    mse_chart_placeholder = st.empty()
    cumulative_chart_placeholder = st.empty()

with feed_col:
    st.markdown("#### Recent anomaly alerts")
    alert_feed_placeholder = st.empty()

# Draw initial (possibly empty) charts
def _render_charts() -> None:
    """Render the live MSE and cumulative alert charts from session history."""
    idx_hist = st.session_state.sim_indices
    mse_hist = st.session_state.sim_mse
    flag_hist = st.session_state.sim_flagged
    alerts = st.session_state.sim_alerts

    with mse_chart_placeholder.container():
        if idx_hist:
            mse_chart_placeholder.plotly_chart(
                live_mse_figure(idx_hist, mse_hist, flag_hist, threshold),
                use_container_width=True,
            )
        else:
            st.caption("MSE chart will appear once simulation starts.")

    with cumulative_chart_placeholder.container():
        if idx_hist:
            cum_alert = np.cumsum([int(f) for f in flag_hist])
            cum_df = pd.DataFrame({"connection": idx_hist, "cumulative_alerts": cum_alert})
            st.line_chart(cum_df.set_index("connection")["cumulative_alerts"], height=200)
            st.caption("Cumulative anomaly count")
        else:
            st.caption("Cumulative alert chart will appear once simulation starts.")

    with alert_feed_placeholder.container():
        if alerts:
            feed_df = pd.DataFrame(alerts[-15:][::-1])
            display_cols = [c for c in ["idx", "mse_score", "label", "proto", "service", "conn_state", "detailed-label"] if c in feed_df.columns]
            st.dataframe(
                feed_df[display_cols].style.format({"mse_score": "{:.4f}"}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Anomaly alerts will appear here.")


_render_charts()

# ─────────────────────────────────────────────────────────────────────────────
# Simulation loop
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.sim_running:
    pos = st.session_state.sim_pos
    if pos >= n_total:
        st.session_state.sim_running = False
        st.success(f"Simulation complete — {n_total:,} connections processed, {n_alerts:,} anomalies detected.")
    else:
        # Process next batch
        end = min(pos + speed, n_total)
        batch = data.iloc[pos:end]

        for local_i, (_, row) in enumerate(batch.iterrows()):
            global_i = pos + local_i
            mse = float(row["mse_score"])
            flagged = bool(row["flagged"])

            st.session_state.sim_indices.append(global_i)
            st.session_state.sim_mse.append(mse)
            st.session_state.sim_flagged.append(flagged)

            if flagged:
                alert_record = {"idx": global_i, "mse_score": mse}
                if has_labels:
                    alert_record["label"] = row.get("label", "?")
                for col in ("proto", "service", "conn_state", "detailed-label"):
                    if col in data.columns:
                        alert_record[col] = row.get(col, "?")
                st.session_state.sim_alerts.append(alert_record)

        st.session_state.sim_pos = end
        time.sleep(tick_delay)
        st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Download alert log
# ─────────────────────────────────────────────────────────────────────────────
alerts = st.session_state.sim_alerts
if alerts:
    st.subheader("Simulation alert log")
    alert_df = pd.DataFrame(alerts)
    st.dataframe(alert_df.style.format({"mse_score": "{:.5f}"}), use_container_width=True, hide_index=True)
    st.download_button(
        "Download alert log (CSV)",
        data=alert_df.to_csv(index=False).encode("utf-8"),
        file_name="simulation_alerts.csv",
        mime="text/csv",
    )

render_multipage_navigation_hint()
