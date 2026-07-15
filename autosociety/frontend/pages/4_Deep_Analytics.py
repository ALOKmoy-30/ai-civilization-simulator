"""Deep Analysis — detailed event feed showing every AI decision."""

import streamlit as st
import pandas as pd

from autosociety.frontend.components import check_backend_or_retry, api_get

st.set_page_config(page_title="Deep Analytics — AutoSociety", page_icon="📋", layout="wide")
st.title("📋 Deep Analysis & AI Event Log")

if not check_backend_or_retry():
    st.stop()

# ── Event feed ────────────────────────────────────────────────────

events = api_get("/queries/events?limit=500")
state = api_get("/simulation/state")

st.subheader("📊 Simulation State")
if state:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tick", state.get("tick", 0))
    c2.metric("Population", state.get("population", 0))
    c3.metric("Avg Happiness", f'{state.get("avg_happiness", 0):.1f}')
    c4.metric("GDP", f'${state.get("gdp", 0):.0f}')
    c5.metric("Crime Rate", f'{state.get("crime_rate", 0)*100:.2f}%')

st.divider()

# ── Filters ───────────────────────────────────────────────────────

st.subheader("🔍 Event Filter")
col1, col2, col3 = st.columns(3)
with col1:
    event_types = ["All"]
    if events:
        event_types += sorted(set(e.get("event_type", "unknown") for e in events))
    filter_type = st.selectbox("Event type", event_types)
with col2:
    min_severity = st.slider("Min severity", 1, 10, 1)
with col3:
    search = st.text_input("Search description", placeholder="Keywords...")

# ── Filtered events ───────────────────────────────────────────────

if not events:
    st.info("No events recorded yet. Start the simulation to see AI decisions.")
    st.stop()

filtered = list(events)
if filter_type != "All":
    filtered = [e for e in filtered if e.get("event_type") == filter_type]
filtered = [e for e in filtered if e.get("severity", 1) >= min_severity]
if search:
    filtered = [e for e in filtered if search.lower() in e.get("description", "").lower()]

st.subheader(f"📜 AI Decision Log ({len(filtered)} events)")

if not filtered:
    st.info("No events match your filters.")
    st.stop()

for e in filtered:
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

    with st.expander(f"{label} [{etype}] Tick {desc.split(']')[0].lstrip('[') if '[' in desc else '?'} — {desc[:90]}..."):
        md = f"**Type:** `{etype}`  |  **Severity:** {sev}/10  |  **Time:** {ts[:19]}\n\n"
        md += f"**Description:**\n{desc}\n\n"
        if affected:
            md += f"**Affected citizens:** {affected}\n"
        st.markdown(md)

# ── Event distribution chart ──────────────────────────────────────

st.subheader("📊 Event Distribution")
if events:
    df = pd.DataFrame(events)
    type_counts = df["event_type"].value_counts()
    st.bar_chart(type_counts)

    sev_counts = df.groupby(["event_type", "severity"]).size().reset_index(name="count")
    st.caption("Severity breakdown by event type. Lower severity (1-2) = routine decisions; higher (5+) = incidents.")
