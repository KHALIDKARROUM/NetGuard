import json
import os
from pathlib import Path
import re
import subprocess

from playwright.sync_api import expect
import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def sharing():
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    if not re.fullmatch(r"netguard-e2e-[a-z0-9-]+", project):
        pytest.fail("Sharing tests require an isolated netguard-e2e- Compose project.")
    password = os.environ.get("NETGUARD_TEST_PASSWORD", "")
    if not password:
        pytest.fail("Generate an ephemeral sharing test account first.")
    return {"project": project, "url": "https://" + os.environ["NETGUARD_PUBLIC_HOST"],
            "ca": os.environ["NETGUARD_TEST_CA"], "password": password}


@pytest.fixture(scope="session")
def compose(sharing):
    def command(*arguments, check=True):
        return subprocess.run(["docker", "compose", "-p", sharing["project"], *arguments],
                              cwd=ROOT, text=True, capture_output=True, timeout=90, check=check)
    return command


@pytest.fixture
def client(sharing):
    with requests.Session() as session:
        # Requests validates the real TLS connection against the isolated CA.
        session.verify = sharing["ca"]
        yield session


def sign_in(page, sharing):
    page.set_default_timeout(60_000)
    page.goto(sharing["url"] + "/prediction")
    page.locator("#username-textfield").fill("alice")
    page.locator("#password-textfield").fill(sharing["password"])
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("heading", name="Prediction lab", exact=True)).to_be_visible(timeout=90_000)
    expect(page.get_by_role("button", name="Analyze connection", exact=True)).to_be_enabled(timeout=90_000)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # Chromium is allowed this isolated CA only in this test fixture. HTTPS
    # certificate validation is tested independently by the Requests client.
    return {**browser_context_args, "ignore_https_errors": True,
            "viewport": {"width": 1440, "height": 1000}, "accept_downloads": True}


@pytest.fixture
def dashboard(page, sharing):
    sign_in(page, sharing)
    yield page
    expect(page.locator('[data-testid="stException"]')).to_have_count(0)


@pytest.fixture(scope="session")
def expected_predictions(compose):
    connection = dict(sbytes=16777217, dbytes=6200, spkts=12, dpkts=18, dur=.5, rate=24., sload=0., dload=0., sttl=64, dttl=64)
    code = """import json,os,urllib.request,sys
payload={'connections':[json.loads(sys.argv[1])]}
request=urllib.request.Request('http://localhost:5000/api/predict/batch',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-API-Key':os.environ['NETGUARD_API_KEY']})
with urllib.request.urlopen(request,timeout=30) as response: print(response.read().decode())
"""
    output = compose("exec", "-T", "backend", "python", "-c", code, json.dumps(connection))
    return connection, json.loads(output.stdout)["predictions"][0]
