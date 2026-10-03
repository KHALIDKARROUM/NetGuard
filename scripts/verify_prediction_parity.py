"""Verify saved notebook predictions against individual/batch HTTP requests."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
import numpy as np
import pandas as pd

from netguard_workflow import PredictionService
from netguard_workflow.inference import runtime_versions


@contextmanager
def api_client(live, artifact, output):
    if not live:
        from fastapi.testclient import TestClient
        from backend.main import create_app
        with TestClient(create_app(artifact, enable_logging=False)) as client:
            yield client, "FastAPI HTTP adapter"
        return
    # Launch a temporary loopback server with this environment's interpreter.
    # Keep process/logs local, and always stop the server after verification.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    env = dict(os.environ, PREDICTION_ARTIFACT=str(artifact),
               NETGUARD_LOG_DIR=str(output/"logs"), LOKY_MAX_CPU_COUNT="2")
    with (output/"uvicorn.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60, trust_env=False) as client:
                deadline = time.monotonic()+30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"API startup failed; inspect {output/'uvicorn.log'}")
                    try:
                        response = client.get("/health")
                        if response.status_code == 200:
                            break
                        raise RuntimeError(response.text)
                    except httpx.ConnectError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("API did not start within 30 seconds")
                        time.sleep(0.2)
                yield client, "live Uvicorn loopback HTTP server in a separate process"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def response_json(response):
    if response.status_code != 200:
        raise AssertionError(f"HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use a real HTTP server in a separate process")
    parser.add_argument("--rows", type=int, default=512)
    parser.add_argument("--artifact", type=Path, default=ROOT/"models_saved/shared_pipeline.joblib")
    parser.add_argument("--report", type=Path, default=ROOT/"data/reports/shared_prediction_parity.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"artifacts/prediction_verification")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    service = PredictionService(args.artifact.resolve())
    raw = pd.read_csv(ROOT/"data/UNSW_NB15_testing-set.csv", encoding="utf-8-sig")
    if not 1 <= args.rows <= len(raw):
        raise ValueError("--rows must be between 1 and the benchmark row count")
    indices = np.sort(np.random.default_rng(42).choice(len(raw), args.rows, replace=False))
    sample = raw.iloc[indices].loc[:, service.bundle["raw_inputs"]].reset_index(drop=True)
    base = {"sbytes": 0, "dbytes": 0, "spkts": 0, "dpkts": 0, "dur": 0.0,
            "rate": 0.0, "sload": 0.0, "dload": 0.0, "sttl": 0, "dttl": 0}
    boundaries = pd.DataFrame([
        base,
        {**base, "sbytes": 16777217, "dbytes": 16777216, "spkts": 3, "dpkts": 1,
         "dur": float(np.nextafter(0.121478, 1.0)), "sttl": 9, "dttl": 10},
        {**base, "sbytes": 2**53-1, "spkts": 1, "dur": 1.0, "sttl": 255},
        {**base, "sbytes": 100, "dbytes": 50, "sttl": 1, "dttl": 255},
        {**base, "spkts": 1, "dpkts": 1, "sttl": 10, "dttl": 9},
        {**base, "dbytes": 2**24+1, "dpkts": 2, "rate": 1e12, "dload": 1e12},
    ])
    corpus = pd.concat([sample, boundaries], ignore_index=True)
    expected = service.predict(corpus)
    # Golden predictions were saved during the notebook's full benchmark run.
    golden_path = ROOT/"artifacts/notebook_workflow/benchmark_predictions.csv"
    golden = pd.read_csv(golden_path, float_precision="round_trip").iloc[indices]
    np.testing.assert_array_equal(golden.row_id.to_numpy(), raw.iloc[indices].id.to_numpy())
    np.testing.assert_allclose(expected.attack_score.iloc[:args.rows], golden.attack_score, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(expected.predicted_label.iloc[:args.rows], golden.predicted_label)
    notebook_evidence = json.loads((ROOT/"data/reports/notebook_workflow_verification.json").read_text())
    assert notebook_evidence["manifest"]["shared_prediction_artifact"]["sha256"] == service.artifact_sha256

    records = corpus.to_dict(orient="records")
    scores_checked = []
    labels_checked = []
    comparisons = 0
    endpoint_checks = []
    batch_sizes = [1, 7, 64, 1000]
    print(f"Comparing {len(corpus)} raw connections, including {len(boundaries)} boundary cases", flush=True)
    with api_client(args.live, args.artifact.resolve(), output) as (client, transport):
        health = response_json(client.get("/health"))
        assert health["artifact_sha256"] == service.artifact_sha256 and health["precision"] == "float64"
        def check(results, positions):
            nonlocal comparisons
            api_scores = np.array([r["score"] for r in results])
            api_labels = np.array([r["prediction"]["label"] for r in results])
            reference = expected.iloc[positions]
            np.testing.assert_allclose(api_scores, reference.attack_score, rtol=0, atol=1e-12)
            np.testing.assert_array_equal(api_labels, reference.predicted_label)
            assert all(r["artifact_sha256"] == service.artifact_sha256 and
                       r["threshold"] == service.bundle["threshold"] for r in results)
            scores_checked.extend(np.abs(api_scores-reference.attack_score.to_numpy()).tolist())
            labels_checked.extend((api_labels != reference.predicted_label.to_numpy()).tolist())
            comparisons += len(results)
        for size in batch_sizes:
            for start in range(0, len(records), size):
                results = response_json(client.post("/api/predict/batch", json={"connections": records[start:start+size]}))["predictions"]
                check(results, list(range(start, min(start+size, len(records)))))
        for i, record in enumerate(records):
            result = response_json(client.post("/api/predict/single", json=dict(reversed(list(record.items())))))
            check([result], [i])
        reverse_results = []
        reverse_records = records[::-1]
        for start in range(0, len(records), 1000):
            reverse_results.extend(response_json(client.post("/api/predict/batch", json={"connections": reverse_records[start:start+1000]}))["predictions"])
        check(reverse_results, list(range(len(records)-1, -1, -1)))
        print("Single/batch/field-order/row-order parity passed; checking dashboard endpoints", flush=True)
        comparison = response_json(client.get("/api/models/compare"))
        assert comparison["best_model"] == service.bundle["model_name"] and comparison["n_models"] == 1
        for name, value in service.bundle["benchmark_metrics"].items():
            assert comparison["metrics"][0][name] == value, name
        endpoints = ["/", "/api/predict/info", "/api/predict/best_model", "/api/dataset/info",
                     "/api/dataset/sample?n=3", "/api/dataset/distributions?top_n=20",
                     "/api/metrics/evaluate"]
        endpoints += [f"/api/{route}/viz?type={kind}" for route in ("models", "metrics")
                      for kind in ("pca", "roc", "confusion", "scores")]
        for endpoint in endpoints:
            response_json(client.get(endpoint))
            endpoint_checks.append(endpoint)
        assert client.post("/api/predict/single", json={}).status_code == 422
    report = {
        "status": "passed", "verified_utc": datetime.now(timezone.utc).isoformat(),
        "transport": transport, "runtime": runtime_versions(), "artifact_sha256": service.artifact_sha256,
        "model": service.bundle["model_name"], "threshold": service.bundle["threshold"],
        "raw_connections": len(corpus), "benchmark_connections": args.rows, "boundary_connections": len(boundaries),
        "prediction_comparisons": comparisons, "batch_sizes": batch_sizes,
        "maximum_score_difference": max(scores_checked), "decision_mismatches": int(sum(labels_checked)),
        "score_tolerance": 1e-12, "notebook_saved_predictions_match": True,
        "dashboard_metrics_match_notebook": True, "endpoint_checks": endpoint_checks,
        "checks": {"individual_and_batch_match": True, "reordered_input_fields_match": True,
                   "reordered_batch_rows_match": True, "full_precision_scores": True,
                   "fixed_saved_threshold": True, "artifact_identity_matches": True},
        "evaluation_status": service.bundle["evaluation_status"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(f"Passed {comparisons} comparisons: maximum score difference {max(scores_checked)}, zero decision mismatches", flush=True)
    print(f"Evidence: {args.report}", flush=True)


if __name__ == "__main__":
    main()
