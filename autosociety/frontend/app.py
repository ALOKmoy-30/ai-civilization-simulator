"""AutoSociety — Streamlit Dashboard (main entry point)."""

import time
import requests
import streamlit as st
from typing import Optional, Dict, Any

from autosociety.frontend.components.charts import (
    time_series_line, multi_line, gauge_chart,
)
from autosociety.frontend.components import check_backend_or_retry, api_get, API_BASE

# ── Config ─────────────────────────────────────────────────────────

POLL_INTERVAL = 2.5

st.set_page_config(page_title="AutoSociety", page_icon="🏛️", layout="wide")


# ── POST helper ─────────────────────────────────────────────────────

def api_post(path: str):
    try:
        r = requests.post(f"{API_BASE}{path}", timeout=3)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


# ── Init session state ─────────────────────────────────────────────

if "poll_counter" not in st.session_state:
    st.session_state.poll_counter = 0
if "world_state" not in st.session_state:
    st.session_state.world_state = None
if "analytics" not in st.session_state:
    st.session_state.analytics = []


def poll():
    """Fetch latest data from API and store in session state."""
    state = api_get("/simulation/state")
    if state:
        st.session_state.world_state = state

    snapshots = api_get("/queries/analytics")
    if snapshots and "snapshots" in snapshots:
        st.session_state.analytics = snapshots["snapshots"]


# ── Layout ─────────────────────────────────────────────────────────

st.title("🏛️ AutoSociety — Multi-Agent Simulator")

# Check backend connectivity (with retry button)
if not check_backend_or_retry():
    st.stop()


# ── Simulation Controls ────────────────────────────────────────────

st.subheader("🎮 Simulation Controls")
cols = st.columns(5)

with cols[0]:
    if st.button("▶️ Start", width="stretch"):
        result = api_post("/simulation/start")
        if result:
            st.success(result.get("message", "Started"))
        else:
            st.error("Failed to start")

with cols[1]:
    if st.button("⏸️ Pause", width="stretch"):
        result = api_post("/simulation/pause")
        if result:
            st.success(result.get("message", "Paused"))

with cols[2]:
    if st.button("▶️ Resume", width="stretch"):
        result = api_post("/simulation/resume")
        if result:
            st.success(result.get("message", "Resumed"))

with cols[3]:
    if st.button("⏹️ Stop", width="stretch"):
        result = api_post("/simulation/stop")
        if result:
            st.success(result.get("message", "Stopped"))

with cols[4]:
    if st.button("🔄 Reset", width="stretch"):
        result = api_post("/simulation/reset")
        if result:
            st.success(result.get("message", "Reset"))


# Auto-poll every POLL_INTERVAL seconds
if st.session_state.world_state and st.session_state.world_state.get("running"):
    time.sleep(0.1)  # yield so button callbacks complete
    now = time.monotonic()
    if "last_poll" not in st.session_state:
        st.session_state.last_poll = now
    if now - st.session_state.last_poll >= POLL_INTERVAL:
        poll()
        st.session_state.last_poll = now
        st.rerun()
else:
    poll()
    st.session_state.last_poll = time.monotonic()


# ── Key Metrics Row ────────────────────────────────────────────────

state = st.session_state.world_state
if state:
    m_cols = st.columns(6)
    with m_cols[0]:
        st.metric("📅 Day", state.get("tick", 0))
    with m_cols[1]:
        st.metric("👥 Population", state.get("population", 0))
    with m_cols[2]:
        st.metric("😊 Happiness", f'{state.get("avg_happiness", 0):.1f}')
    with m_cols[3]:
        st.metric("💰 Avg Wealth", f'${state.get("avg_wealth", 0):.0f}')
    with m_cols[4]:
        st.metric("🏥 Avg Health", f'{state.get("avg_health", 0):.1f}')
    with m_cols[5]:
        emoji = "🟢" if state.get("running") else "🔴"
        st.metric("Status", f"{emoji} {'Running' if state.get('running') else 'Stopped'}")

    st.caption(f"Political Stability: {state.get('political_stability', 0):.1f}  |  "
               f"Economic Health: {state.get('economic_health', 0):.1f}  |  "
               f"Employment: {state.get('employment_rate', 0)*100:.1f}%")


# ── Live Charts ────────────────────────────────────────────────────

st.subheader("📊 Live Analytics")

analytics = st.session_state.analytics
if analytics:
    tab1, tab2 = st.tabs(["GDP & Economy", "Society Health"])

    with tab1:
        gdp_fig = time_series_line(analytics, "tick", "gdp",
                                    "GDP Over Time", color="#1f77b4")
        st.plotly_chart(gdp_fig, width="stretch")

        wealth_fig = time_series_line(analytics, "tick", "avg_wealth",
                                       "Average Wealth Over Time", color="#ff7f0e")
        st.plotly_chart(wealth_fig, width="stretch")

    with tab2:
        multi = multi_line(analytics, "tick",
                           ["avg_happiness", "political_stability", "economic_health"],
                           "Society Indicators")
        st.plotly_chart(multi, width="stretch")

        crime_fig = time_series_line(analytics, "tick", "crime_rate",
                                      "Crime Rate Over Time", color="#d62728")
        st.plotly_chart(crime_fig, width="stretch")

    st.caption("Data refreshes every ~2.5 seconds while simulation is running.")
else:
    st.info("No analytics data yet. Start the simulation to see charts.")
