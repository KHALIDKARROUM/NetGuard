"""Upload, export, and authenticated API boundaries used by the dashboard."""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path
import sys

import pandas as pd
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import api
from file_security import MAX_UPLOAD_BYTES, read_connection_csv, safe_csv
from prediction_inputs import DEFAULTS, MAX_EXACT_COUNT, validate_connections

TEST_KEY = "test-only-key-" + "x" * 32

def connection_csv(rows):
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")

def test_upload_round_trip_preserves_bom_counts_and_measurements():
    row = {**DEFAULTS, "sbytes":MAX_EXACT_COUNT - 1, "dbytes":1}
    raw = b"\xef\xbb\xbf" + connection_csv([row])
    assert validate_connections(read_connection_csv(raw)) == [row]

@pytest.mark.parametrize("raw,message", [
    (b"", "nonempty"), (b"a\n\x00", "binary"), (b"a\n\xff", "UTF-8"),
    (b"a,a\n1,2", "unique"), (b"a,b\n1,2,3", "same number"),
    (b'a,b\n"unfinished,2', "valid UTF-8 CSV"),
    (b"a" * 4097, "header"), (b"a" * 129 + b"\n1", "header"),
    (",".join(f"col{i}" for i in range(65)).encode() + b"\n", "header"),
])
def test_upload_rejects_invalid_files(raw, message):
    with pytest.raises(ValueError, match=message):
        read_connection_csv(raw)

def test_upload_size_and_row_limits_apply_before_submission():
    with pytest.raises(ValueError, match="2 MB"):
        read_connection_csv(b"x" * (MAX_UPLOAD_BYTES + 1))
    frame = read_connection_csv(connection_csv([DEFAULTS] * 2000))
    assert len(frame) == 1001
    with pytest.raises(ValueError, match="1,000"):
        validate_connections(frame)
    with pytest.raises(ValueError, match="numeric measurement is too long"):
        validate_connections(read_connection_csv(connection_csv([{**DEFAULTS, "dur":"9" * 129}])))

def test_export_neutralizes_formula_text_and_preserves_numeric_values():
    strings = ["=1+1", " +cmd", "-cmd", "@SUM(A1)", "\t=1", "\n=1", "＝1+1", "＋1", "－1", "＠SUM(A1)"]
    frame = pd.DataFrame({"=formula_header":strings, "measurement":[-1.5] * len(strings), "text":["quoted,\ntext"] * len(strings)})
    exported = safe_csv(frame).decode("utf-8")
    rows = list(csv.reader(io.StringIO(exported)))
    assert rows[0] == ["'=formula_header", "measurement", "text"]
    assert [row[0] for row in rows[1:]] == ["'" + value for value in strings]
    assert all(row[1:] == ["-1.5", "quoted,\ntext"] for row in rows[1:])
    assert frame.columns[0] == "=formula_header"
    assert frame.iloc[0, 0] == "=1+1"

@pytest.fixture
def client_environment(monkeypatch):
    monkeypatch.setenv("NETGUARD_API_KEY", TEST_KEY)
    monkeypatch.setattr(api, "BACKEND_URL", "https://api.example.test")
    api.api_get.clear()
    yield monkeypatch
    api.api_get.clear()

def response(status, data):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode("utf-8")
    return result

def test_server_api_client_authenticates_reads_and_predictions(client_environment):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return response(200, {"ok":True})
    client_environment.setattr(requests, "get", request)
    client_environment.setattr(requests, "post", request)
    assert api.api_get("/api/probe") == {"ok":True}
    assert api.api_post("/api/probe", DEFAULTS) == {"ok":True}
    assert len(calls) == 2
    for _, options in calls:
        assert options["headers"] == {"X-API-Key":TEST_KEY}
        assert options["allow_redirects"] is False

@pytest.mark.parametrize("url", ["http://remote.example.test", "https://user:password@api.example.test", "file:///tmp/service", "https://api.example.test?key=secret"])
def test_credentials_require_a_trusted_service_url(client_environment, url):
    client_environment.setattr(api, "BACKEND_URL", url)
    with pytest.raises(ValueError):
        api.api_post("/api/probe", DEFAULTS)

def test_redirects_cannot_forward_the_api_key(client_environment):
    def redirect(url, **options):
        assert options["allow_redirects"] is False
        result = response(302, {})
        result.headers["Location"] = "https://untrusted.example.test"
        return result
    client_environment.setattr(requests, "get", redirect)
    with pytest.raises(ValueError, match="redirect"):
        api.api_get("/api/probe")

def test_server_errors_do_not_display_private_details():
    result = response(503, {"detail":"private/path/model.joblib"})
    with pytest.raises(requests.HTTPError) as error:
        result.raise_for_status()
    assert "private/path" not in api.explain_api_error(error.value)
    assert "private-token" not in api.explain_api_error(RuntimeError("private-token"))
