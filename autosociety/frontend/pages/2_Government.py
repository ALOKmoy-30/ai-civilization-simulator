"""Government Panel — policies, budget, decisions."""

import streamlit as st
import requests
import pandas as pd

API_BASE = "http://localhost:8243"

st.set_page_config(page_title="Government — AutoSociety", page_icon="🏛️", layout="wide")
st.title("🏛️ Government Panel")


def api_get(path: str):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=3)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


health = api_get("/health")
if health is None:
    st.error("🚫 Backend not reachable. Start the API server first.")
    st.stop()


# ── Current World State ────────────────────────────────────────────

state = api_get("/simulation/state")

if state:
    st.subheader("🌍 World Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Political Stability", f'{state.get("political_stability", 0):.1f}')
    c2.metric("Economic Health", f'{state.get("economic_health", 0):.1f}')
    c3.metric("Avg Happiness", f'{state.get("avg_happiness", 0):.1f}')
    c4.metric("Day", state.get("tick", 0))
else:
    st.warning("World state not available")


# ── Policies ────────────────────────────────────────────────────────

st.subheader("📜 Enacted Policies")
policies = api_get("/queries/policies")

if policies:
    df = pd.DataFrame(policies)
    if not df.empty:
        cols = ["id", "name", "description", "is_active", "created_at"]
        display_cols = [c for c in cols if c in df.columns]
        st.dataframe(
            df[display_cols].sort_values("id", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Total policies: {len(policies)}")
    else:
        st.info("No policies enacted yet.")
else:
    st.info("No policies found. The Government crew will create policies during simulation.")


# ── Recent Events ──────────────────────────────────────────────────

st.subheader("📰 Recent Events")
events = api_get("/queries/events")

if events:
    for e in events[:10]:
        with st.container(border=True):
            st.write(f"**{e.get('event_type', 'Event').title()}** (severity: {e.get('severity', '?')})")
            st.caption(e.get("description", ""))
else:
    st.info("No events recorded yet.")


# ── Reports ─────────────────────────────────────────────────────────

st.subheader("📋 Society Report")
report = api_get("/queries/reports")
if report:
    c1, c2 = st.columns(2)
    with c1:
        st.json({
            "Population": report.get("total_population"),
            "Avg Happiness": report.get("average_happiness"),
            "Avg Wealth": report.get("average_wealth"),
            "Avg Health": report.get("average_health"),
            "Employment Rate": f'{report.get("employment_rate", 0)*100:.1f}%',
        })
    with c2:
        st.json({
            "Political Stability": report.get("political_stability"),
            "Economic Health": report.get("economic_health"),
            "Simulation Day": report.get("simulation_day"),
        })
