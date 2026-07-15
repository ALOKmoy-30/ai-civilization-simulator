"""Shared helpers for frontend pages."""

import requests
import streamlit as st
import time

API_BASE = "http://localhost:8243"


def api_get(path: str, timeout: int = 3):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def check_backend_or_retry():
    """Check backend health. If unreachable, show retry UI instead of hard-stopping."""
    health = api_get("/health")
    if health is None:
        st.error("🚫 Backend not reachable.")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Retry"):
                st.rerun()
        with col2:
            st.info("Is the API server running on port 8243?")
        return False
    return True
