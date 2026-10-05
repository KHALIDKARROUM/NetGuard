"""Startup, browser uploads, predictions, and access through real containers."""
from __future__ import annotations
import csv
import io
import json
import math
import subprocess

import pytest
import requests
from playwright.sync_api import expect

CONNECTION = dict(sbytes=16777217, dbytes=6200, spkts=12, dpkts=18, dur=.5, rate=24., sload=0., dload=0., sttl=64, dttl=64)
ROWS = [CONNECTION, {**CONNECTION, "sbytes":60,"dbytes":0,"spkts":1,"dpkts":0,"dur":.001,"rate":1200.,"sttl":255,"dttl":0},
        {**CONNECTION,"sbytes":500000,"spkts":6000,"dur":4.2,"rate":10000.}]

def csv_bytes(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CONNECTION))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")

def request(api, deployment, method, path, **kwargs):
    response = api.request(method, deployment["api_url"] + path, timeout=90, allow_redirects=False, **kwargs)
    return response

def test_service_startup_and_container_restrictions(api, deployment, compose):
    health = request(api, deployment, "GET", "/health")
    assert health.status_code == 200
    assert health.json()["models_ready"] is True
    if deployment["mode"] == "shared":
        assert "artifact_sha256" not in health.json()
    frontend = requests.get(deployment["ui_url"] + "/_stcore/health", timeout=10)
    assert frontend.status_code == 200
    assert frontend.text == "ok"
    template = '{"user":{{json .Config.User}},"read_only":{{json .HostConfig.ReadonlyRootfs}},"cap_drop":{{json .HostConfig.CapDrop}},"security_opt":{{json .HostConfig.SecurityOpt}},"health":{{json .State.Health.Status}}}'
    for service in ("backend", "frontend"):
        container = compose("ps", "-q", service).stdout.strip()
        assert container
        inspected = subprocess.run(["docker","inspect","--format",template,container], capture_output=True, text=True, check=True, timeout=20)
        config = json.loads(inspected.stdout)
        assert config["user"] == "10001:10001"
        assert config["read_only"] is True
        assert "ALL" in config["cap_drop"]
        assert any(option.startswith("no-new-privileges") for option in config["security_opt"])
        assert config["health"] == "healthy"

def test_api_access_and_documentation_follow_deployment_mode(api, deployment):
    expected = 401 if deployment["mode"] == "shared" else 200
    for headers in ({}, {"X-API-Key":"incorrect-test-key"}):
        response = requests.post(deployment["api_url"] + "/api/predict/single", json=CONNECTION, headers=headers, timeout=30)
        assert response.status_code == expected
    allowed = request(api, deployment, "GET", "/api/predict/best_model")
    assert allowed.status_code == 200
    assert allowed.headers["x-content-type-options"] == "nosniff"
    assert allowed.headers["cache-control"] == "no-store"
    docs = request(api, deployment, "GET", "/docs")
    assert docs.status_code == (404 if deployment["mode"] == "shared" else 200)

def test_shared_startup_without_key_is_rejected(compose):
    result = compose("exec", "-T", "-e", "NETGUARD_DEPLOYMENT_MODE=shared", "-e", "NETGUARD_API_KEY=", "backend", "python", "-c", "import backend.config", check=False)
    assert result.returncode != 0
    assert "Shared deployments require NETGUARD_API_KEY" in result.stderr

def test_single_batch_and_maximum_batch_predictions(api, deployment):
    batch = request(api, deployment, "POST", "/api/predict/batch", json={"connections":ROWS})
    assert batch.status_code == 200, batch.text
    assert batch.json()["n"] == len(ROWS)
    for connection, predicted in zip(ROWS, batch.json()["predictions"]):
        single = request(api, deployment, "POST", "/api/predict/single", json=connection)
        assert single.status_code == 200, single.text
        result = single.json()
        assert result["input"] == connection
        assert result["precision"] == "float64"
        assert math.isclose(result["score"], predicted["score"], rel_tol=0, abs_tol=1e-12)
        assert result["prediction"] == predicted["prediction"]
        assert result["threshold"] == predicted["threshold"]
        assert result["artifact_sha256"] == predicted["artifact_sha256"]
    maximum = request(api, deployment, "POST", "/api/predict/batch", json={"connections":[CONNECTION]*1000})
    assert maximum.status_code == 200, maximum.text
    assert maximum.json()["n"] == 1000

@pytest.mark.parametrize("payload", [{**CONNECTION,"sttl":256}, {k:v for k,v in CONNECTION.items() if k != "dur"}, {**CONNECTION,"label":1}], ids=["invalid-ttl", "missing-duration", "unexpected-field"])
def test_invalid_api_measurements_are_rejected(api, deployment, payload):
    assert request(api, deployment, "POST", "/api/predict/single", json=payload).status_code == 422

def test_api_body_and_batch_limits(api, deployment):
    assert request(api, deployment, "POST", "/api/predict/batch", json={"connections":[CONNECTION]*1001}).status_code == 422
    assert request(api, deployment, "POST", "/api/predict/single", data=b"x"*(1024*1024+1), headers={"Content-Type":"application/json"}).status_code == 413
    assert request(api, deployment, "POST", "/api/predict/single", data="{}", headers={"Content-Type":"text/plain"}).status_code == 415

def test_untrusted_hosts_and_origins_are_rejected(api, deployment):
    assert request(api, deployment, "GET", "/api/predict/best_model", headers={"Host":"attacker.example"}).status_code == 400
    assert request(api, deployment, "GET", "/api/predict/best_model", headers={"Origin":"https://attacker.example"}).status_code == 403

def test_browser_single_prediction_export(prediction_page, api, deployment, tmp_path):
    page = prediction_page
    exposed_key_headers = []
    page.on("request", lambda req: exposed_key_headers.append(True) if "x-api-key" in req.headers else None)
    page.get_by_role("spinbutton", name="Source bytes", exact=True).fill(str(CONNECTION["sbytes"]))
    page.get_by_role("button", name="Analyze connection", exact=True).click()
    download_button = page.get_by_role("button", name="Download analysis", exact=True)
    expect(download_button).to_be_visible(timeout=90_000)
    with page.expect_download() as download:
        download_button.click()
    path = tmp_path / "single.json"
    download.value.save_as(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    expected = request(api, deployment, "POST", "/api/predict/single", json=CONNECTION).json()
    assert result["input"] == CONNECTION
    assert result["prediction"] == expected["prediction"]
    assert math.isclose(result["score"], expected["score"], rel_tol=0, abs_tol=1e-12)
    assert result["artifact_sha256"] == expected["artifact_sha256"]
    assert not exposed_key_headers
    if deployment["key"]:
        assert deployment["key"] not in page.content()

def test_browser_csv_upload_prediction_and_export(prediction_page, api, deployment, tmp_path):
    page = prediction_page
    page.get_by_text("CSV batch", exact=True).click()
    expect(page.get_by_role("radio", name="CSV batch", exact=True)).to_be_checked()
    page.locator('input[type="file"]').set_input_files({"name":"connections.csv","mimeType":"text/csv","buffer":csv_bytes(ROWS)})
    expect(page.get_by_text("3 connections validated and ready to analyze.", exact=True)).to_be_visible(timeout=30_000)
    page.get_by_role("button", name="Analyze batch", exact=True).click()
    button = page.get_by_role("button", name="Download batch results", exact=True)
    expect(button).to_be_visible(timeout=90_000)
    with page.expect_download() as download:
        button.click()
    path = tmp_path / "batch.csv"
    download.value.save_as(path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = request(api, deployment, "POST", "/api/predict/batch", json={"connections":ROWS}).json()["predictions"]
    assert len(rows) == len(expected)
    for row, predicted in zip(rows, expected):
        assert row["Classification"] == predicted["prediction"]["class_name"]
        assert math.isclose(float(row["Model score"]), predicted["score"], rel_tol=0, abs_tol=1e-12)
        assert int(row["sbytes"]) == predicted["input"]["sbytes"]

@pytest.mark.parametrize("raw,message", [
    (b"sbytes,dur\n1,2\n", "Missing required columns"),
    (b"sbytes,sbytes\n1,2\n", "CSV headers must be unique"),
    (csv_bytes([{**CONNECTION,"dur":"NaN"}]), "measurement must be finite"),
    (csv_bytes([CONNECTION]*1001), "Provide between 1 and 1,000"),
    (b"x"*(2*1024*1024+1), "smaller"),
], ids=["missing-columns", "duplicate-headers", "nonfinite", "too-many-rows", "too-large"])
def test_browser_rejects_invalid_uploads(prediction_page, raw, message):
    page = prediction_page
    page.get_by_text("CSV batch", exact=True).click()
    expect(page.get_by_role("radio", name="CSV batch", exact=True)).to_be_checked()
    page.locator('input[type="file"]').set_input_files({"name":"invalid.csv","mimeType":"text/csv","buffer":raw})
    expect(page.get_by_text(message, exact=False)).to_be_visible(timeout=30_000)
    expect(page.get_by_role("button", name="Analyze batch", exact=True)).to_be_disabled()
