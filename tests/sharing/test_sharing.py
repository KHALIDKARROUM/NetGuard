import csv
import io
import json
import math
import os
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import expect
import pytest

def call(client, sharing, method, path, **kwargs):
    return client.request(method, sharing["url"] + path, timeout=30, allow_redirects=False, **kwargs)


def login(client, sharing, username="alice", password=None):
    return call(client, sharing, "POST", "/auth/api/firstfactor", json={
        "username": username, "password": password or sharing["password"],
        "keepMeLoggedIn": False, "targetURL": sharing["url"] + "/prediction", "requestMethod": "GET",
    })


def test_https_redirect_certificate_headers_and_private_services(client, sharing, compose):
    response = client.get(sharing["url"].replace("https://", "http://") + "/prediction", timeout=10, allow_redirects=False)
    assert response.status_code == 308
    assert response.headers["Location"] == sharing["url"] + "/prediction"
    portal = call(client, sharing, "GET", "/auth/")
    assert portal.status_code == 200
    assert portal.headers["Strict-Transport-Security"] == "max-age=31536000"
    assert portal.headers["X-Content-Type-Options"] == "nosniff"
    assert portal.headers["Cache-Control"] == "no-store"
    template = '{"ports":{{json .HostConfig.PortBindings}},"user":{{json .Config.User}},"read_only":{{json .HostConfig.ReadonlyRootfs}},"cap_drop":{{json .HostConfig.CapDrop}},"health":{{json .State.Health.Status}}}'
    for service in ("backend", "frontend", "auth", "gateway"):
        container = compose("ps", "-q", service).stdout.strip()
        config = json.loads(subprocess.check_output(["docker", "inspect", "--format", template, container], text=True, timeout=20))
        assert config["user"] == "10001:10001"
        assert config["read_only"] is True
        assert "ALL" in config["cap_drop"]
        assert config["health"] == "healthy"
        if service != "gateway":
            assert not config["ports"], f"{service} must not publish a bypass port"
        else:
            assert set(config["ports"]) == {"8080/tcp", "8443/tcp"}


@pytest.mark.parametrize("method,path,headers", [
    ("GET", "/", {}),
    ("GET", "/prediction", {"Remote-User": "alice", "Remote-Groups": "netguard-users", "X-Forwarded-Host": "attacker.example", "X-Forwarded-Proto": "http"}),
    ("GET", "/dataset", {"X-API-Key": os.environ.get("NETGUARD_API_KEY", "")}),
    ("POST", "/_stcore/upload_file/session/file", {"Content-Type": "text/csv"}),
    ("GET", "/media/private-result.json", {}),
    ("GET", "/_stcore/stream", {"Connection": "Upgrade", "Upgrade": "websocket", "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}),
], ids=["overview", "spoofed-identity", "service-key-is-not-login", "upload", "download", "websocket"])
def test_anonymous_access_never_reaches_dashboard(client, sharing, method, path, headers):
    response = call(client, sharing, method, path, headers=headers)
    assert response.status_code in (302, 303, 401, 403)
    if "Location" in response.headers:
        target = urlsplit(response.headers["Location"])
        assert target.netloc == urlsplit(sharing["url"]).netloc
        assert target.path.startswith("/auth/")
    assert "Workspace overview" not in response.text


def test_wrong_password_and_unapproved_account_are_rejected(client, sharing):
    assert login(client, sharing, password="incorrect synthetic password").status_code == 401
    assert login(client, sharing, username="denied").status_code == 200
    assert call(client, sharing, "GET", "/prediction").status_code == 403


def test_browser_sign_in_and_single_prediction_download(dashboard, sharing, expected_predictions, tmp_path):
    page = dashboard
    connection, predicted = expected_predictions
    page.get_by_role("spinbutton", name="Source bytes", exact=True).fill(str(connection["sbytes"]))
    page.get_by_role("button", name="Analyze connection", exact=True).click()
    button = page.get_by_role("button", name="Download analysis", exact=True)
    expect(button).to_be_visible(timeout=90_000)
    with page.expect_download() as download:
        button.click()
    output = tmp_path / "single.json"
    download.value.save_as(output)
    result = json.loads(output.read_text())
    assert result["input"] == connection
    assert result["prediction"] == predicted["prediction"]
    assert math.isclose(result["score"], predicted["score"], rel_tol=0, abs_tol=1e-12)
    assert result["artifact_sha256"] == predicted["artifact_sha256"]
    assert os.environ["NETGUARD_API_KEY"] not in page.content()
    cookie = next(cookie for cookie in page.context.cookies() if cookie["name"] == "netguard_session")
    assert cookie["secure"] is True
    assert cookie["httpOnly"] is True
    assert cookie["sameSite"] == "Lax"


def test_authenticated_csv_upload_and_download(dashboard, expected_predictions, tmp_path):
    page = dashboard
    connection, predicted = expected_predictions
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=list(connection))
    writer.writeheader()
    writer.writerows([connection] * 3)
    page.get_by_text("CSV batch", exact=True).click()
    page.locator('input[type="file"]').set_input_files({"name": "connections.csv", "mimeType": "text/csv", "buffer": text.getvalue().encode()})
    expect(page.get_by_text("3 connections validated and ready to analyze.", exact=True)).to_be_visible(timeout=30_000)
    page.get_by_role("button", name="Analyze batch", exact=True).click()
    button = page.get_by_role("button", name="Download batch results", exact=True)
    expect(button).to_be_visible(timeout=90_000)
    with page.expect_download() as download:
        button.click()
    output = tmp_path / "batch.csv"
    download.value.save_as(output)
    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert all(row["Classification"] == predicted["prediction"]["class_name"] for row in rows)
    assert all(int(row["sbytes"]) == connection["sbytes"] for row in rows)


def test_browser_sign_out_and_server_session_revocation(dashboard, sharing, client):
    page = dashboard
    cookie = next(cookie for cookie in page.context.cookies() if cookie["name"] == "netguard_session")
    page.get_by_role("link", name="Account & sign out", exact=True).click()
    expect(page).to_have_url(re.compile(re.escape(sharing["url"]) + r"/auth/.*"))
    page.locator("#logout-button").click()
    expect(page.locator("#username-textfield")).to_be_visible(timeout=30_000)
    replay = call(client, sharing, "GET", "/prediction", headers={"Cookie": "netguard_session=" + cookie["value"]})
    assert replay.status_code in (302, 303, 401)
    page.goto(sharing["url"] + "/prediction")
    expect(page.locator("#username-textfield")).to_be_visible(timeout=30_000)


def test_backend_api_is_not_published_for_signed_in_users(client, sharing):
    assert login(client, sharing).status_code == 200
    assert call(client, sharing, "GET", "/api/predict/best_model").status_code == 404
    assert call(client, sharing, "GET", "/docs").status_code == 404


def test_gateway_fails_closed_when_authentication_is_unavailable(client, sharing, compose):
    assert login(client, sharing).status_code == 200
    compose("stop", "auth")
    try:
        response = call(client, sharing, "GET", "/prediction")
        assert response.status_code == 502
        assert "Prediction lab" not in response.text
    finally:
        compose("up", "-d", "--no-build", "--wait", "--wait-timeout", "90", "auth")


def test_repeated_wrong_passwords_trigger_lockout(client, sharing):
    for _ in range(5):
        assert login(client, sharing, username="locked", password="incorrect synthetic password").status_code == 401
    assert login(client, sharing, username="locked").status_code == 401
