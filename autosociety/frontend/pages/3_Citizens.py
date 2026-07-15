"""Society Explorer — searchable citizen table with stats."""

import streamlit as st
import pandas as pd

from autosociety.frontend.components import check_backend_or_retry, api_get

st.set_page_config(page_title="Citizens — AutoSociety", page_icon="👥", layout="wide")
st.title("👥 Society Explorer")

if not check_backend_or_retry():
    st.stop()

data = api_get("/queries/citizens")
if not data or "citizens" not in data or not data["citizens"]:
    st.warning("No citizens found. Seed the database first.")
    st.stop()

citizens = data["citizens"]
df = pd.DataFrame(citizens)

display_cols = ["id", "name", "age", "job", "happiness", "wealth", "health", "social_score"]
available = [c for c in display_cols if c in df.columns]

st.subheader("🔍 Search & Filter")
with st.expander("Filters", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        search = st.text_input("Search by name", placeholder="Type a name...")
    with c2:
        if "job" in df.columns:
            jobs = sorted(df["job"].dropna().unique())
            selected_job = st.selectbox("Filter by job", ["All"] + list(jobs))
        else:
            selected_job = "All"
    with c3:
        min_happiness = st.slider("Min happiness", 0.0, 100.0, 0.0, 0.5)

filtered = df.copy()
if search and "name" in filtered.columns:
    filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]
if selected_job != "All" and "job" in filtered.columns:
    filtered = filtered[filtered["job"] == selected_job]
if min_happiness > 0 and "happiness" in filtered.columns:
    filtered = filtered[filtered["happiness"] >= min_happiness]

st.subheader(f"👤 Citizens ({len(filtered)} / {len(df)})")

display = filtered[available].copy()
for col in ["happiness", "wealth", "health", "social_score"]:
    if col in display.columns:
        display[col] = display[col].round(1)
st.dataframe(display, width="stretch", hide_index=True)

st.subheader("📊 Population Statistics")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", len(df))
if "age" in df.columns:
    c2.metric("Avg Age", f'{df["age"].mean():.1f}')
if "happiness" in df.columns:
    c3.metric("Avg Happiness", f'{df["happiness"].mean():.1f}')
if "wealth" in df.columns:
    c4.metric("Avg Wealth", f'${df["wealth"].mean():.0f}')
if "health" in df.columns:
    c5.metric("Avg Health", f'{df["health"].mean():.1f}')

if "job" in df.columns:
    st.subheader("💼 Job Distribution")
    st.bar_chart(df["job"].value_counts())

if "happiness" in df.columns:
    st.subheader("😊 Happiness Distribution")
    bins = pd.cut(df["happiness"], bins=list(range(0, 101, 10)))
    chart_data = bins.value_counts().sort_index()
    chart_data.index = chart_data.index.astype(str)
    st.bar_chart(chart_data)
