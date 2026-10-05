"""Fixtures for real Compose services; no mocked API or dashboard responses."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess

import pytest
import requests
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture(scope="session")
def deployment():
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    if not re.fullmatch(r"netguard-e2e-[a-z0-9-]+", project):
        pytest.fail("Use an isolated COMPOSE_PROJECT_NAME beginning with netguard-e2e-. See README.md.")
    mode = os.environ.get("NETGUARD_DEPLOYMENT_MODE", "local")
    key = os.environ.get("NETGUARD_API_KEY", "")
    if mode == "shared" and len(key) < 32:
        pytest.fail("Shared-mode tests require the same generated API key as both containers.")
    return {
        "project": project, "mode": mode, "key": key,
        "api_url": os.environ.get("NETGUARD_E2E_API_URL", f"http://localhost:{os.environ.get('NETGUARD_BACKEND_PORT', '5001')}").rstrip("/"),
        "ui_url": os.environ.get("NETGUARD_E2E_UI_URL", f"http://localhost:{os.environ.get('NETGUARD_FRONTEND_PORT', '8502')}").rstrip("/"),
    }

@pytest.fixture(scope="session")
def api(deployment):
    with requests.Session() as session:
        if deployment["key"]:
            session.headers["X-API-Key"] = deployment["key"]
        yield session

@pytest.fixture(scope="session")
def compose(deployment):
    def command(*args, check=True):
        return subprocess.run(
            ["docker", "compose", "-p", deployment["project"], "-f", "docker-compose.yaml", "-f", "docker-compose.e2e.yaml", *args],
            cwd=ROOT, text=True, capture_output=True, check=check, timeout=60,
        )
    return command

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport":{"width":1440,"height":1000}, "accept_downloads":True}

@pytest.fixture
def prediction_page(page, deployment):
    page.set_default_timeout(60_000)
    page.goto(deployment["ui_url"])
    expect(page.get_by_role("heading", name="Workspace overview", exact=True)).to_be_visible(timeout=90_000)
    expect(page.get_by_text("Analysis service online", exact=False)).to_be_visible(timeout=90_000)
    page.locator('[data-testid="stSidebar"]').get_by_role("link", name="Prediction lab").click()
    expect(page.get_by_role("heading", name="Prediction lab", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Analyze connection", exact=True)).to_be_enabled(timeout=90_000)
    yield page
    expect(page.locator('[data-testid="stException"]')).to_have_count(0)
