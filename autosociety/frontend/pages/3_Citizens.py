"""Society Explorer — searchable citizen table with stats."""

import streamlit as st
import requests
import pandas as pd

API_BASE = "http://localhost:8243"

st.set_page_config(page_title="Citizens — AutoSociety", page_icon="👥", layout="wide")
st.title("👥 Society Explorer")


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


# ── Fetch citizens ─────────────────────────────────────────────────

data = api_get("/queries/citizens")
if not data or "citizens" not in data:
    st.warning("No citizens found. Seed the database first.")
    st.stop()

citizens = data["citizens"]
if not citizens:
    st.warning("No citizens found. Seed the database first.")
    st.stop()
df = pd.DataFrame(citizens)

# Reorder columns for readability
display_cols = ["id", "name", "age", "job", "happiness", "wealth", "health", "social_score"]
available = [c for c in display_cols if c in df.columns]


# ── Filters ────────────────────────────────────────────────────────

st.subheader("🔍 Search & Filter")
with st.expander("Filters", expanded=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        search = st.text_input("Search by name", placeholder="Type a name...")

    with col2:
        jobs = sorted(df["job"].dropna().unique())
        selected_job = st.selectbox("Filter by job", ["All"] + list(jobs))

    with col3:
        min_happiness = st.slider("Min happiness", 0.0, 100.0, 0.0, 0.5)


# ── Apply filters ──────────────────────────────────────────────────

filtered = df.copy()
if search:
    filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]
if selected_job != "All":
    filtered = filtered[filtered["job"] == selected_job]
if min_happiness > 0:
    filtered = filtered[filtered["happiness"] >= min_happiness]


# ── Display ────────────────────────────────────────────────────────

st.subheader(f"👤 Citizens ({len(filtered)} / {len(df)})")

display = filtered[available].copy()
for col in ["happiness", "wealth", "health", "social_score"]:
    if col in display.columns:
        display[col] = display[col].round(1)

st.dataframe(display, use_container_width=True, hide_index=True)


# ── Statistics ──────────────────────────────────────────────────────

st.subheader("📊 Population Statistics")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", len(df))
c2.metric("Avg Age", f'{df["age"].mean():.1f}')
c3.metric("Avg Happiness", f'{df["happiness"].mean():.1f}')
c4.metric("Avg Wealth", f'${df["wealth"].mean():.0f}')
c5.metric("Avg Health", f'{df["health"].mean():.1f}')

# Job distribution
st.subheader("💼 Job Distribution")
job_counts = df["job"].value_counts()
st.bar_chart(job_counts)

# Happiness distribution
st.subheader("😊 Happiness Distribution")
st.bar_chart(
    pd.cut(df["happiness"], bins=list(range(0, 101, 10))).value_counts().sort_index()
)
