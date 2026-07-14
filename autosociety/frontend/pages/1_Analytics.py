"""Deeper analytics — economy, crime, employment trends."""

import streamlit as st
import requests
from typing import Optional

from autosociety.frontend.components.charts import (
    time_series_line, multi_line, bar_chart,
)

API_BASE = "http://localhost:8243"

st.set_page_config(page_title="Analytics — AutoSociety", page_icon="📊", layout="wide")
st.title("📊 Deep Analytics")


def api_get(path: str):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=3)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


# Check backend
health = api_get("/health")
if health is None:
    st.error("🚫 Backend not reachable. Start the API server first.")
    st.stop()

snapshots = api_get("/queries/analytics")
analytics = snapshots.get("snapshots", []) if snapshots else []
world = api_get("/simulation/state")

if not analytics:
    st.info("No analytics data yet. Start the simulation to populate charts.")
    st.stop()


# ── Economy Section ────────────────────────────────────────────────

st.subheader("💰 Economy")

col1, col2 = st.columns(2)
with col1:
    gdp_fig = time_series_line(analytics, "tick", "gdp",
                                "GDP Over Time", color="#1f77b4")
    st.plotly_chart(gdp_fig, use_container_width=True)

with col2:
    tax_fig = time_series_line(analytics, "tick", "tax_revenue",
                                "Tax Revenue Over Time", color="#2ca02c")
    st.plotly_chart(tax_fig, use_container_width=True)

bus_fig = time_series_line(analytics, "tick", "active_businesses",
                            "Active Businesses", color="#9467bd")
st.plotly_chart(bus_fig, use_container_width=True)


# ── Crime Section ──────────────────────────────────────────────────

st.subheader("🚨 Crime & Safety")
crime_fig = time_series_line(analytics, "tick", "crime_rate",
                              "Crime Rate Over Time", color="#d62728")
st.plotly_chart(crime_fig, use_container_width=True)

if world:
    st.metric("Current Crime Rate",
              f'{world.get("crime_rate", 0)*100:.2f}%',
              help="Fraction of citizens involved in crime per tick")


# ── Employment Section ─────────────────────────────────────────────

st.subheader("💼 Employment")
emp_fig = time_series_line(analytics, "tick", "employment_rate",
                            "Employment Rate Over Time", color="#ff7f0e")
st.plotly_chart(emp_fig, use_container_width=True)

if world:
    st.metric("Current Employment",
              f'{world.get("employment_rate", 0)*100:.1f}%')


# ── Overall Trends ─────────────────────────────────────────────────

st.subheader("📈 Overall Trends")
multi = multi_line(analytics, "tick",
                   ["avg_happiness", "avg_wealth", "avg_health"],
                   "Average Citizen Stats Over Time")
st.plotly_chart(multi, use_container_width=True)
