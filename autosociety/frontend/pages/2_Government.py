"""Government Panel — active agents, policies, events, and reports."""

import streamlit as st
import pandas as pd

from autosociety.frontend.components import check_backend_or_retry, api_get

st.set_page_config(page_title="Government — AutoSociety", page_icon="🏛️", layout="wide")
st.title("🏛️ Government Panel")

if not check_backend_or_retry():
    st.stop()

# ── Active Government Agents ──────────────────────────────────────

st.subheader("👥 Active Government Cabinet")
gov_agents = [
    ("Finance Minister", "Manage the society's economy — propose tax rates, budget allocations, and economic policies."),
    ("Police Chief", "Maintain public order and safety — propose crime prevention and law enforcement policies."),
    ("Education Minister", "Develop the society's human capital — propose education funding and skill development programs."),
    ("Health Minister", "Protect public health — propose healthcare policies, sanitation, and wellness programs."),
    ("Policy Coordinator", "Review all ministerial proposals, resolve conflicts, and produce a single unified policy recommendation."),
    ("Governor", "Review the Policy Coordinator's unified recommendation and issue a final binding policy decision for the society."),
]

cols = st.columns(3)
for i, (name, goal) in enumerate(gov_agents):
    with cols[i % 3]:
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(goal[:100] + ("..." if len(goal) > 100 else ""))

st.divider()

# ── Current World State ───────────────────────────────────────────

st.subheader("🌍 World Overview")
state = api_get("/simulation/state")
if state:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Political Stability", f'{state.get("political_stability", 0):.1f}')
    c2.metric("Economic Health", f'{state.get("economic_health", 0):.1f}')
    c3.metric("Avg Happiness", f'{state.get("avg_happiness", 0):.1f}')
    c4.metric("Day", state.get("tick", 0))

st.divider()

# ── Policies ──────────────────────────────────────────────────────

st.subheader("📜 Enacted Policies")
policies = api_get("/queries/policies")
if policies:
    df = pd.DataFrame(policies)
    if not df.empty:
        cols = ["id", "name", "description", "is_active", "created_at"]
        display_cols = [c for c in cols if c in df.columns]
        st.dataframe(
            df[display_cols].sort_values("id", ascending=False),
            width="stretch", hide_index=True,
        )
        st.caption(f"Total policies: {len(policies)}")
    else:
        st.info("No policies enacted yet.")
else:
    st.info("No policies found. The government meets every policy cycle to enact new policies.")

st.divider()

# ── Recent Events ─────────────────────────────────────────────────

st.subheader("📰 Recent Government & World Events")
events = api_get("/queries/events?limit=50")
if events:
    for e in events[:15]:
        etype = e.get("event_type", "event")
        sev = e.get("severity", 1)
        desc = e.get("description", "")
        label = "🔴" if sev >= 5 else "🟡" if sev >= 3 else "🟢"
        with st.container(border=True):
            st.write(f"{label} **{etype}** (severity: {sev}/10)")
            st.caption(desc[:200])
else:
    st.info("No events recorded yet.")

st.divider()

# ── Reports ───────────────────────────────────────────────────────

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
