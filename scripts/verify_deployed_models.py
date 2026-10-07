"""Verify all deployed model routes against the exact notebook exports over HTTP."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cloudpickle
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from netguard_workflow.deployment import PredictionRegistry
from verify_prediction_parity import api_client, response_json
from verify_prediction_without_data import example_connections


def main():
    source = ROOT / "artifacts/notebook_report"
    output = ROOT / "artifacts/prediction_verification/deployed"
    output.mkdir(parents=True, exist_ok=True)
    registry = PredictionRegistry(ROOT / "models_saved/deployed/registry.json")
    benchmark = pd.read_csv(ROOT / "data/UNSW_NB15_testing-set.csv")
    indices = np.sort(np.random.default_rng(42).choice(len(benchmark), 256, replace=False))
    corpus = pd.concat([benchmark.iloc[indices].loc[:, registry.get().bundle["raw_inputs"]],
                        pd.DataFrame(example_connections())], ignore_index=True)
    records = corpus.to_dict(orient="records")
    checks = {}
    with api_client(True, registry.get().artifact_path, output, {"REQUESTS_PER_MINUTE":"10000"}) as (client, transport):
        info = response_json(client.get("/api/predict/best_model"))
        assert info["best_model"]["name"] == "xgboost"
        assert {item["id"] for item in info["available_models"]} == set(registry.services)
        for name, filename in {"xgboost":"netguard_model.pkl", "lightgbm":"lightgbm_model.pkl", "tabm":"tabm_model.pkl"}.items():
            with (source / filename).open("rb") as handle:
                original = cloudpickle.load(handle)
            with threadpool_limits(limits=2):
                scores = original["pipeline"].predict_proba(corpus)[:, 1]
            labels = scores >= original["threshold"]
            if name == "xgboost":
                golden = pd.read_csv(source / "benchmark_predictions.csv", float_precision="round_trip").iloc[indices]
                np.testing.assert_allclose(scores[:len(indices)], golden.attack_score, rtol=0, atol=1e-12)
                np.testing.assert_array_equal(labels[:len(indices)], golden.predicted_label)
            differences = []
            def compare(results, positions):
                actual = np.array([r["score"] for r in results])
                np.testing.assert_allclose(actual, scores[positions], rtol=0, atol=1e-12)
                np.testing.assert_array_equal([r["prediction"]["label"] for r in results], labels[positions])
                assert all(r["model"] == name and r["threshold"] == original["threshold"]
                           and r["artifact_sha256"] == registry.get(name).artifact_sha256 for r in results)
                differences.extend(np.abs(actual - scores[positions]))
            for size in (7, 64, 1000):
                for start in range(0, len(records), size):
                    positions = list(range(start, min(start + size, len(records))))
                    result = response_json(client.post(f"/api/predict/batch?model={name}", json={"connections":[records[i] for i in positions]}))
                    compare(result["predictions"], positions)
            for i in list(range(16)) + list(range(len(indices), len(records))):
                result = response_json(client.post(f"/api/predict/single?model={name}", json=dict(reversed(list(records[i].items())))))
                compare([result], [i])
            positions = list(range(len(records)-1, -1, -1))
            result = response_json(client.post(f"/api/predict/batch?model={name}", json={"connections":records[::-1]}))
            compare(result["predictions"], positions)
            maximum = response_json(client.post(f"/api/predict/batch?model={name}", json={"connections":[records[0]]*1000}))
            compare(maximum["predictions"], [0]*1000)
            checks[name] = {"comparisons":len(differences), "max_score_difference":float(max(differences)),
                            "decision_mismatches":0, "maximum_batch":1000, "notebook_export_parity":True}
        assert client.post("/api/predict/single?model=unknown", json=records[0]).status_code == 422
        result = response_json(client.get("/api/models/compare"))
        assert result["n_models"] == 3 and result["best_model"] == "xgboost"
        for metrics in result["metrics"]:
            expected = registry.get(metrics["model"]).metadata["metrics"]
            for key in ("tn", "fp", "fn", "tp", "threshold", "recall", "false_positive_rate"):
                assert metrics[key] == expected[key], (metrics["model"], key)
        for kind in ("pca", "roc", "confusion", "scores"):
            response_json(client.get(f"/api/models/viz?type={kind}"))
    report = {"status":"passed", "utc":datetime.now(timezone.utc).isoformat(), "transport":transport,
              "score_tolerance":1e-12, "default":"xgboost", "models":checks,
              "dashboard_benchmark_metrics_match":True, "visualization_routes_pass":True,
              "scope":"Serving parity with the previously inspected notebook benchmark, not new accuracy testing."}
    target = ROOT / "data/reports/deployed_models_verification.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
