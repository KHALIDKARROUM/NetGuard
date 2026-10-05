"""Short-lived read caching keeps controls responsive without caching predictions."""
from __future__ import annotations
import os
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/")

@st.cache_data(ttl=60, show_spinner=False, max_entries=64)
def api_get(path: str, params: dict | None = None, timeout: int = 15) -> dict:
    response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()

def api_post(path: str, payload: dict, timeout: int = 90) -> dict:
    response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()

def explain_api_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            detail = exc.response.json().get("detail", "Request failed")
        except ValueError:
            detail = "The service could not complete this request."
        if isinstance(detail, list):
            detail = "; ".join(f"{'.'.join(str(p) for p in e.get('loc', [])[1:])}: {e.get('msg', 'Invalid value')}" for e in detail)
        return f"{detail} (HTTP {exc.response.status_code})"
    if isinstance(exc, requests.ConnectionError):
        return "The analysis service is offline. Start the backend, then select Refresh data."
    if isinstance(exc, requests.Timeout):
        return "The analysis service took too long to respond. Select Refresh data to try again."
    return str(exc)
