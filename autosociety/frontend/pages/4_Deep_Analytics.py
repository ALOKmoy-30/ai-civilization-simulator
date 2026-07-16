"""Deep Analysis — AI event log with server-side filtering and historical run overlay."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from autosociety.frontend.components import check_backend_or_retry, api_get

st.set_page_config(page_title="Deep Analytics — AutoSociety", page_icon="📋", layout="wide")
st.title("📋 Deep Analysis & AI Event Log")

if not check_backend_or_retry():
    st.stop()

# ── Simulation state header ───────────────────────────────────────

state = api_get("/simulation/state")

st.subheader("📊 Simulation State")
if state:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tick", state.get("tick", 0))
    c2.metric("Day", state.get("simulation_day", state.get("tick", 0)))
    c3.metric("Population", state.get("population", 0))
    c4.metric("Avg Happiness", f'{state.get("avg_happiness", 0):.1f}')
    c5.metric("GDP", f'${state.get("gdp", 0):.0f}')
    c6.metric("Crime Rate", f'{state.get("crime_rate", 0)*100:.2f}%')

st.divider()

# ── Historical Analytics Overlay ─────────────────────────────────

st.subheader("📈 Historical Runs Analytics")

historical = api_get("/queries/analytics/historical")
current = api_get("/queries/analytics")
current_snapshots = current.get("snapshots", []) if current else []

# Combine: current run + historical backup runs
all_runs: dict = {}
if current_snapshots:
    all_runs["▶ Current Run"] = current_snapshots

if historical:
    hist_by_label: dict = {}
    for row in historical:
        label = row.get("run_label", "Unknown Run")
        hist_by_label.setdefault(label, []).append(row)
    for label, rows in hist_by_label.items():
        all_runs[label] = rows

if len(all_runs) > 1:
    hist_tab1, hist_tab2 = st.tabs(["💰 Wealth & GDP", "😊 Society Indicators"])
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    with hist_tab1:
        fig_wealth = go.Figure()
        fig_gdp = go.Figure()
        for i, (run_label, snaps) in enumerate(all_runs.items()):
            x = [s.get("simulation_day", s.get("tick", 0)) for s in snaps]
            color = colors[i % len(colors)]
            y_wealth = [s.get("avg_wealth", 0) for s in snaps]
            fig_wealth.add_trace(go.Scatter(x=x, y=y_wealth, mode="lines",
                                             name=run_label, line=dict(color=color)))
            y_gdp = [s.get("gdp", 0) for s in snaps]
            fig_gdp.add_trace(go.Scatter(x=x, y=y_gdp, mode="lines",
                                          name=run_label, line=dict(color=color, dash="dot")))

        fig_wealth.update_layout(title="Average Wealth — All Runs",
                                  xaxis_title="Simulation Day", yaxis_title="Avg Wealth ($)",
                                  height=350)
        fig_gdp.update_layout(title="GDP — All Runs",
                               xaxis_title="Simulation Day", yaxis_title="GDP ($)",
                               height=350)
        st.plotly_chart(fig_wealth, use_container_width=True)
        st.plotly_chart(fig_gdp, use_container_width=True)

    with hist_tab2:
        fig_hap = go.Figure()
        fig_crime = go.Figure()
        for i, (run_label, snaps) in enumerate(all_runs.items()):
            x = [s.get("simulation_day", s.get("tick", 0)) for s in snaps]
            color = colors[i % len(colors)]
            y_hap = [s.get("avg_happiness", 0) for s in snaps]
            fig_hap.add_trace(go.Scatter(x=x, y=y_hap, mode="lines",
                                          name=run_label, line=dict(color=color)))
            y_crime = [s.get("crime_rate", 0) * 100 for s in snaps]
            fig_crime.add_trace(go.Scatter(x=x, y=y_crime, mode="lines",
                                            name=run_label, line=dict(color=color, dash="dot")))

        fig_hap.update_layout(title="Average Happiness — All Runs",
                               xaxis_title="Simulation Day", yaxis_title="Happiness",
                               height=350)
        fig_crime.update_layout(title="Crime Rate % — All Runs",
                                 xaxis_title="Simulation Day", yaxis_title="Crime Rate (%)",
                                 height=350)
        st.plotly_chart(fig_hap, use_container_width=True)
        st.plotly_chart(fig_crime, use_container_width=True)

    st.caption(f"Showing {len(all_runs)} run(s). Historical data loaded from data_storage/backups/.")
elif current_snapshots:
    st.info("Only one run found. Restart the simulation to accumulate historical runs — they will appear here as overlay charts.")
else:
    st.info("No analytics data yet. Start the simulation to see charts.")

st.divider()

# ══════════════════════════════════════════════════════════════════
# ── Advanced Event Search & Filter ────────────────────────────────
# ══════════════════════════════════════════════════════════════════

st.subheader("🔍 Event Search & Filter")

# Fetch distinct event types from the backend and combine with required base options cleanly
base_options = ["All", "Crime", "Disaster", "Policy", "Agent_Failure", "Economic"]
raw_types = api_get("/queries/events/types") or []
event_type_options = list(base_options)
seen_lower = {o.lower() for o in event_type_options}
for opt in raw_types:
    if opt and opt.lower() not in seen_lower:
        formatted = opt.title() if "_" not in opt else "_".join(part.capitalize() for part in opt.split("_"))
        event_type_options.append(formatted)
        seen_lower.add(opt.lower())

# ── Filter controls row ──────────────────────────────────────────

filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([3, 2, 2, 1])

with filter_col1:
    search_query = st.text_input(
        "🔍 Search events by keyword...",
        placeholder="e.g. Citizen #5, storm, tax, timeout...",
        key="event_search_query",
    )

with filter_col2:
    selected_type = st.selectbox(
        "Filter by Event Type",
        options=event_type_options,
        key="event_type_filter",
    )

with filter_col3:
    min_severity = st.slider(
        "⚠️ Min Severity",
        min_value=1,
        max_value=10,
        value=1,
        key="event_min_severity",
    )

with filter_col4:
    event_limit = st.selectbox(
        "📊 Limit",
        options=[50, 100, 200, 500],
        index=0,
        key="event_limit",
    )

# ── Build query parameters and fetch filtered events ─────────────

query_params = {"limit": event_limit}
if selected_type and selected_type != "All":
    query_params["event_type"] = selected_type
if search_query:
    query_params["search_query"] = search_query
if min_severity > 1:
    query_params["min_severity"] = min_severity

events = api_get("/queries/events", params=query_params)

# ── Active filter chips display ──────────────────────────────────

active_filters = []
if selected_type and selected_type != "All":
    active_filters.append(f"Type: `{selected_type}`")
if search_query:
    active_filters.append(f"Search: `{search_query}`")
if min_severity > 1:
    active_filters.append(f"Severity ≥ `{min_severity}`")

if active_filters:
    st.caption("**Active Filters:** " + " · ".join(active_filters))

# ── Render filtered event list ────────────────────────────────────

if not events:
    if active_filters:
        st.warning("No matching events found for the selected criteria.")
    else:
        st.info("No events recorded yet. Start the simulation to see AI decisions.")
    st.stop()

st.subheader(f"📜 AI Decision Log ({len(events)} events)")

for e in events:
    sev = e.get("severity", 1)
    etype = e.get("event_type", "event")
    ts = e.get("created_at", "")
    desc = e.get("description", "")
    affected = e.get("affected_citizens")

    if sev >= 5:
        label = "🔴 CRITICAL"
    elif sev >= 3:
        label = "🟡 WARNING"
    else:
        label = "🟢 INFO"

    with st.expander(f"{label} [{etype}] — {desc[:90]}..."):
        md = f"**Type:** `{etype}`  |  **Severity:** {sev}/10  |  **Time:** {ts[:19]}\n\n"
        md += f"**Description:**\n{desc}\n\n"
        if affected:
            md += f"**Affected citizens:** {affected}\n"
        st.markdown(md)

# ── Event distribution chart ──────────────────────────────────────

st.divider()
st.subheader("📊 Event Distribution")

# For the distribution chart, always fetch unfiltered event types
all_events = api_get("/queries/events?limit=500")
if all_events:
    df = pd.DataFrame(all_events)
    if "event_type" in df.columns:
        type_counts = df["event_type"].value_counts()
        st.bar_chart(type_counts)
        st.caption("Severity breakdown by event type. Lower severity (1-2) = routine decisions; higher (5+) = incidents.")
