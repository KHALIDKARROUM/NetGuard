"""UI flow checks and validation for the raw CSV prediction contract.

Run from the repository root: python -m pytest frontend/tests/test_dashboard.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd
import pytest
import requests
from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))
from api import api_get
from prediction_inputs import DEFAULTS, MAX_EXACT_COUNT, validate_connections

METRICS = dict(model="test_model", precision=.97, recall=.86, f1=.91, roc_auc=.98, false_positive_rate=.03, inference_s=.1)
MODEL = dict(name="test_model", threshold=.86, metrics=METRICS, components=[{"name":"test"}], threshold_selection={"max_false_positive_rate":.01})
DATASET = dict(overview=dict(train_set=dict(n_rows=1000), test_set=dict(n_rows=100, n_normal=40, n_anomalies=60, anomaly_rate=60., n_features=2),
    feature_names=["sbytes", "dur"], numeric_stats={"sbytes":{"mean":100., "std":50.}}), label_distribution={"pie_chart":{"labels":["Normal","Anomaly"],"values":[40,60]}})

@pytest.fixture
def service(monkeypatch):
    calls = []
    def get(url, params=None, **kwargs):
        path = url.split("5000")[-1]
        calls.append((path, params))
        data = {
            "/health": {"status":"ok"}, "/api/dataset/info": DATASET,
            "/api/predict/best_model": {"best_model":MODEL},
            "/api/models/compare": {"metrics":[METRICS],"best_model":"test_model","validation_comparison":[{**METRICS,"selected":True,"single_latency_median_ms":1.}]},
            "/api/dataset/sample": {"sample":[{**DEFAULTS,"label":0},{**DEFAULTS,"label":1}]},
            "/api/dataset/distributions": {"distributions":{"sbytes":{"normal":[1,2],"anomaly":[3,4],"stats_normal":{"mean":1.5},"stats_anomaly":{"mean":3.5}}}},
        }.get(path)
        if path == "/api/models/viz":
            kind = params["type"]
            data = {"data": {
                "roc":{"test_model":{"fpr":[0,1],"tpr":[0,1]}},
                "confusion":[{"model_name":"test_model","z":[[38,2],[5,55]]}],
                "scores":{"test_model":{"normal":[.1,.2],"anomaly":[.8,.9],"percentiles":{"p50":.5}}},
                "pca":{"x":[1,2],"y":[2,1],"labels":[0,1],"scores":[.1,.9]},
            }[kind]}
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(data).encode()
        return response
    def post(url, json, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = __import__("json").dumps({"prediction":{"label":0,"class_name":"Normal"},"score":.2,"threshold":.86,"model":"test_model","input":json}).encode()
        return response
    api_get.clear()
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)
    yield calls
    api_get.clear()

def app(page=None):
    test = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=20).run()
    assert not test.exception
    if page:
        test.switch_page(f"pages/{page}").run()
        assert not test.exception
    return test

def test_dataset_views_and_filters(service):
    test = app("01_dataset.py")
    assert not any(path.endswith("sample") or path.endswith("distributions") for path, _ in service)
    test.radio(key="dataset_view").set_value("Browse records").run()
    assert not test.exception
    assert len(test.dataframe[0].value) == 2
    test.selectbox[1].set_value("Anomaly").run()
    assert len(test.dataframe[0].value) == 1
    test.radio(key="dataset_view").set_value("Feature distributions").run()
    assert not test.exception
    test.radio(key="dataset_view").set_value("Feature statistics").run()
    test.text_input[0].set_value("no_such_feature").run()
    assert not test.exception
    assert any("No matching features" in m.value for m in test.markdown)

def test_performance_loads_only_requested_chart(service):
    test = app("02_performance.py")
    assert not any(path.endswith("viz") for path, _ in service)
    for view, kind in [("ROC curve","roc"),("Confusion matrix","confusion"),("Score distribution","scores"),("Feature projection","pca")]:
        test.radio(key="performance_view").set_value(view).run()
        assert not test.exception
        assert ("/api/models/viz", {"type":kind}) in service

def test_prediction_submission_and_preset_reset(service):
    test = app("03_prediction.py")
    assert len(test.number_input) == 10
    submit = next(b for b in test.button if b.label == "Analyze connection")
    submit.click().run()
    assert not test.exception
    assert test.session_state.prediction_result["input"]["sbytes"] == 1800
    assert any("Normal connection" in m.value for m in test.markdown)
    test.selectbox(key="prediction_preset").set_value("Scan-like example").run()
    assert not test.exception
    assert test.session_state.prediction_result is None
    assert test.number_input(key="prediction_sbytes").value == 60
    test.switch_page("pages/01_dataset.py").run()
    test.switch_page("pages/03_prediction.py").run()
    assert not test.exception
    assert test.number_input(key="prediction_sbytes").value == 60
    assert test.selectbox(key="prediction_preset").value == "Scan-like example"
    test.radio(key="prediction_mode").set_value("CSV batch").run()
    assert not test.exception
    assert next(b for b in test.button if b.label == "Analyze batch").disabled

def test_offline_pages_keep_navigation(monkeypatch):
    api_get.clear()
    def offline(*args, **kwargs):
        raise requests.ConnectionError()
    monkeypatch.setattr(requests, "get", offline)
    for page in [None, "01_dataset.py", "02_performance.py", "03_prediction.py"]:
        test = app(page)
        assert not test.exception
        assert any("Analysis service offline" in m.value for m in test.markdown)
    api_get.clear()

def test_sharing_account_link_leaves_dashboard_in_same_tab(service, monkeypatch):
    monkeypatch.setenv("NETGUARD_AUTH_PORTAL_URL", "https://netguard.example.com/auth/")
    test = app("03_prediction.py")
    link = next(m.value for m in test.markdown if "Account &amp; sign out" in m.value)
    assert 'href="https://netguard.example.com/auth/"' in link
    assert 'target="_self"' in link

def test_csv_preserves_exact_counts():
    row = {**DEFAULTS, "sbytes":str(MAX_EXACT_COUNT-1), "dbytes":"1"}
    result = validate_connections(pd.DataFrame([row]))
    assert result[0]["sbytes"] == MAX_EXACT_COUNT-1

@pytest.mark.parametrize("field,value", [("dur", "NaN"),("sload","Infinity"),("dbytes",-1),("spkts","1.5"),("sttl",256),("rate","1e10000"),("sbytes",str(MAX_EXACT_COUNT+1))])
def test_csv_rejects_invalid_measurements(field, value):
    with pytest.raises(ValueError, match=f"Row 1 · {field}"):
        validate_connections(pd.DataFrame([{**DEFAULTS, field:value}]))

def test_csv_requires_schema_and_batch_limit():
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_connections(pd.DataFrame([{"sbytes":1}]))
    with pytest.raises(ValueError, match="1,000"):
        validate_connections(pd.DataFrame([DEFAULTS]*1001))
    with pytest.raises(ValueError, match="combined"):
        validate_connections(pd.DataFrame([{**DEFAULTS,"sbytes":MAX_EXACT_COUNT,"dbytes":1}]))
    frame = pd.DataFrame([DEFAULTS])
    frame.columns = ["sbytes"]*len(frame.columns)
    with pytest.raises(ValueError, match="unique"):
        validate_connections(frame)
