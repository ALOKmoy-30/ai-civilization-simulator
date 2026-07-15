"""Deeper analytics — economy, crime, employment trends."""

import streamlit as st

from autosociety.frontend.components.charts import (
    time_series_line, multi_line, bar_chart,
)
from autosociety.frontend.components import check_backend_or_retry, api_get

st.set_page_config(page_title="Analytics — AutoSociety", page_icon="📊", layout="wide")
st.title("📊 Deep Analytics")

if not check_backend_or_retry():
    st.stop()

snapshots = api_get("/queries/analytics")
analytics = snapshots.get("snapshots", []) if snapshots else []
world = api_get("/simulation/state")

if not analytics:
    st.info("No analytics data yet. Start the simulation to populate charts.")
    st.stop()

st.subheader("💰 Economy")
c1, c2 = st.columns(2)
with c1:
    gdp_fig = time_series_line(analytics, "tick", "gdp", "GDP Over Time", color="#1f77b4")
    st.plotly_chart(gdp_fig, width="stretch")
with c2:
    tax_fig = time_series_line(analytics, "tick", "tax_revenue", "Tax Revenue Over Time", color="#2ca02c")
    st.plotly_chart(tax_fig, width="stretch")

bus_fig = time_series_line(analytics, "tick", "active_businesses", "Active Businesses", color="#9467bd")
st.plotly_chart(bus_fig, width="stretch")

st.subheader("🚨 Crime & Safety")
crime_fig = time_series_line(analytics, "tick", "crime_rate", "Crime Rate Over Time", color="#d62728")
st.plotly_chart(crime_fig, width="stretch")

if world:
    st.metric("Current Crime Rate", f'{world.get("crime_rate", 0)*100:.2f}%')

st.subheader("💼 Employment")
emp_fig = time_series_line(analytics, "tick", "employment_rate", "Employment Rate Over Time", color="#ff7f0e")
st.plotly_chart(emp_fig, width="stretch")
if world:
    st.metric("Current Employment", f'{world.get("employment_rate", 0)*100:.1f}%')

st.subheader("📈 Overall Trends")
multi = multi_line(analytics, "tick", ["avg_happiness", "avg_wealth", "avg_health"], "Average Citizen Stats Over Time")
st.plotly_chart(multi, width="stretch")
