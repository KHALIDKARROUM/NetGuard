"""Short-lived read caching keeps controls responsive without caching predictions."""
from __future__ import annotations
import os
from urllib.parse import urlsplit
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/")

def request_options() -> dict:
    parsed = urlsplit(BACKEND_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Configure BACKEND_URL as an HTTP(S) service URL without credentials or query parameters.")
    key = os.getenv("NETGUARD_API_KEY", "")
    if key and parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1", "backend"}:
        raise ValueError("Authenticated remote API access requires HTTPS.")
    return {"headers": {"X-API-Key": key} if key else {}, "allow_redirects": False}

def check_response(response) -> dict:
    # X-API-Key is a custom header, so never let redirects forward it to another host.
    if 300 <= response.status_code < 400:
        raise ValueError("The analysis service returned a redirect. Check BACKEND_URL.")
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=60, show_spinner=False, max_entries=64)
def api_get(path: str, params: dict | None = None, timeout: int = 15) -> dict:
    response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=timeout, **request_options())
    return check_response(response)

def api_post(path: str, payload: dict, timeout: int = 90) -> dict:
    response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=timeout, **request_options())
    return check_response(response)

def explain_api_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code >= 500:
            return "The analysis service is unavailable. Check the service and saved model, then try again."
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
    if isinstance(exc, ValueError):
        return str(exc)
    return "The request could not be completed. Review the service configuration and try again."
