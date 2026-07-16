"""Government Panel — active agents, policies, events, and reports."""

import json
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
    c4.metric("Day", state.get("simulation_day", state.get("tick", 0)))

st.divider()

# ── Policies ──────────────────────────────────────────────────────

st.subheader("📜 Enacted Policies")

# Effect keys to display with nice labels and emoji
_EFFECT_LABELS = {
    "economic_health":      ("💹 Economic Health",    "normal"),
    "avg_happiness":        ("😊 Avg Happiness",       "normal"),
    "political_stability":  ("⚖️ Political Stability", "normal"),
    "wealth":               ("💰 Wealth",              "normal"),
    "health":               ("🏥 Health",              "normal"),
    "crime_rate":           ("🔒 Crime Rate",          "inverse"),  # negative = good
    "tax_revenue":          ("🏦 Tax Revenue",         "normal"),
}

def _status_badge(status: str) -> str:
    """Return a coloured emoji badge for approval status."""
    s = (status or "approved").lower()
    if "approved" in s:
        return "✅ Approved"
    if "rejected" in s:
        return "❌ Rejected"
    if "modified" in s:
        return "🔄 Modified"
    return f"📋 {status.title()}"


policies = api_get("/queries/policies")

if policies:
    # Sort newest first
    policies_sorted = sorted(policies, key=lambda p: p.get("id", 0), reverse=True)

    for policy in policies_sorted:
        name = policy.get("name", "Unnamed Policy")
        description = policy.get("description", "No description available.")
        enacted_day = policy.get("enacted_day")
        decision_status = policy.get("decision_status", "approved")
        effects_parsed = policy.get("effects_parsed", {})
        reasoning_summary = policy.get("reasoning_summary", "")
        is_active = policy.get("is_active", True)

        day_label = f"Day {enacted_day}" if enacted_day is not None else "Day unknown"
        active_badge = "🟢 Active" if is_active else "🔴 Inactive"

        with st.container(border=True):
            # ── Header row
            header_cols = st.columns([6, 2, 2])
            with header_cols[0]:
                st.markdown(f"#### {name}")
            with header_cols[1]:
                st.markdown(f"**{_status_badge(decision_status)}**")
            with header_cols[2]:
                st.markdown(f"**{active_badge}** &nbsp;|&nbsp; 📅 {day_label}")

            # ── Description
            st.markdown(f"*{description}*")

            # ── Ministerial adjustments
            if effects_parsed:
                st.markdown("**📊 Ministerial Adjustments:**")
                effect_cols = st.columns(min(len(effects_parsed), 4))
                for idx, (key, val) in enumerate(effects_parsed.items()):
                    label_text, direction = _EFFECT_LABELS.get(key, (f"🔧 {key.replace('_', ' ').title()}", "normal"))
                    col_idx = idx % 4
                    with effect_cols[col_idx]:
                        # Invert delta colour for "inverse" metrics (e.g. crime_rate)
                        display_val = val
                        if direction == "inverse":
                            display_val = -val  # show green for crime reduction
                        delta_str = f"{'+' if val >= 0 else ''}{val}"
                        st.metric(label_text, delta_str, delta=display_val)
            else:
                st.caption("_No numeric adjustments recorded._")

            # ── Reasoning summary (collapsible)
            if reasoning_summary:
                with st.expander("🧠 Governor Reasoning & LLM Output"):
                    # Show a cleaner excerpt first, full text available
                    st.text_area(
                        "Full reasoning text",
                        value=reasoning_summary,
                        height=200,
                        disabled=True,
                        key=f"reasoning_{policy.get('id', 0)}",
                        label_visibility="collapsed",
                    )
            else:
                st.caption("_No reasoning summary available (policy created before this feature was added)._")

    st.caption(f"Total policies: {len(policies)}")

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
