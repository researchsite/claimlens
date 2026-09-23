import time
import streamlit as st


RATE_LIMIT_DELAY = 1.5


@st.cache_data(ttl=600, show_spinner=False)
def search_web(query: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo search with TTL caching and rate-limit delay."""
    try:
        time.sleep(RATE_LIMIT_DELAY)
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception:
        return []
