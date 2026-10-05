"""Exercise the public HTTP contract against the fitted notebook pipeline."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.config import Settings
from netguard_workflow.inference import (
    ArtifactError, PredictionService, artifact_manifest_path,
    load_prediction_artifact, save_prediction_artifact,
)
from netguard_workflow.workflow import WorkflowConfig, fit_baselines, split_development
from test_notebook_workflow import traffic


class SharedPredictionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = traffic()
        config = WorkflowConfig(max_iter=12, forest_trees=12, latency_repeats=3)
        fit, validation, _ = split_development(data, config)
        cls.bundle, _ = fit_baselines(data, fit, validation, config)
        cls.rows = data.loc[:7, cls.bundle["raw_inputs"]].copy()
        cls.rows.loc[0, ["sbytes", "dbytes", "spkts", "dpkts", "sttl", "dttl"]] = [16777217, 0, 0, 0, 9, 0]
        cls.rows.loc[0, "dur"] = np.nextafter(0.121478, 1.0)

    def artifact(self, folder, bundle=None):
        path = Path(folder) / "model.joblib"
        save_prediction_artifact(self.bundle if bundle is None else bundle, path)
        return path

    def test_http_singles_batches_and_field_order_match_saved_notebook_pipeline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.artifact(folder)
            service = PredictionService(path)
            expected = service.predict(self.rows)
            app = create_app(path, enable_logging=False)
            # Block CSV reads before cold startup as well as during requests.
            with patch("pandas.read_csv", side_effect=AssertionError("Prediction must not read datasets")), TestClient(app, base_url="http://localhost") as client:
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertEqual(client.get("/api/predict/info").json()["best_model"]["precision"], "float64")
                records = self.rows.to_dict(orient="records")
                batch = client.post("/api/predict/batch", json={"connections": records})
                self.assertEqual(batch.status_code, 200, batch.text)
                results = batch.json()["predictions"]
                np.testing.assert_allclose([r["score"] for r in results], expected.attack_score, rtol=0, atol=1e-12)
                np.testing.assert_array_equal([r["prediction"]["label"] for r in results], expected.predicted_label)
                for i, record in enumerate(records):
                    single = client.post("/api/predict/single", json=dict(reversed(list(record.items()))))
                    self.assertEqual(single.status_code, 200, single.text)
                    value = single.json()
                    self.assertEqual(value["score"], results[i]["score"])
                    self.assertEqual(value["prediction"], results[i]["prediction"])
                    self.assertEqual(value["threshold"], service.bundle["threshold"])
                    self.assertEqual(value["artifact_sha256"], service.artifact_sha256)
                    self.assertEqual(value["input"], record)
                reversed_batch = client.post("/api/predict/batch", json={"connections": records[::-1]}).json()["predictions"]
                self.assertEqual([r["score"] for r in reversed_batch], [r["score"] for r in results][::-1])
                self.assertTrue(any(r["score"] != round(r["score"], 6) for r in results))

    def test_missing_invalid_and_unknown_measurements_return_422(self):
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app(self.artifact(folder), enable_logging=False), base_url="http://localhost") as client:
            valid = self.rows.iloc[1].to_dict()
            variants = [{}, {**valid, "dur": -1}, {**valid, "sttl": 256},
                        {**valid, "spkts": 1.25}, {**valid, "dbytes": 2**53},
                        {**valid, "label": 1}, {**valid, "sbytes": "missing"},
                        {**valid, "sbytes": 2**53-1, "dbytes": 1}]
            for payload in variants:
                response = client.post("/api/predict/single", json=payload)
                self.assertEqual(response.status_code, 422, response.text)
            # JSON's huge finite literal is parsed as infinity and must be rejected.
            text = json.dumps({**valid, "dur": "PLACEHOLDER"}).replace('"PLACEHOLDER"', '1e999')
            self.assertEqual(client.post("/api/predict/single", content=text, headers={"Content-Type": "application/json"}).status_code, 422)
            self.assertEqual(client.post("/api/predict/batch", json={"connections": []}).status_code, 422)
            self.assertEqual(client.post("/api/predict/batch", json={"connections": [valid]*1001}).status_code, 422)

    def test_authenticated_predictions_preserve_scores_and_block_unauthorized_inference(self):
        key = "test-only-key-" + "x" * 32
        config = Settings(_env_file=None, api_key=key, deployment_mode="shared")
        with tempfile.TemporaryDirectory() as folder:
            path = self.artifact(folder)
            expected = PredictionService(path).predict(self.rows.iloc[[1]])
            app = create_app(path, enable_logging=False, service_settings=config)
            with TestClient(app, base_url="http://localhost") as client:
                row = self.rows.iloc[1].to_dict()
                service = app.state.cache["shared_prediction_service"]
                with patch.object(service, "predict", wraps=service.predict) as predict:
                    for headers in [{}, {"X-API-Key":"incorrect"}]:
                        self.assertEqual(client.post("/api/predict/single", json=row, headers=headers).status_code, 401)
                    predict.assert_not_called()
                    response = client.post("/api/predict/single", json=row, headers={"X-API-Key":key})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["score"], expected.attack_score.iloc[0])
                    self.assertEqual(response.json()["prediction"]["label"], expected.predicted_label.iloc[0])
                    predict.assert_called_once()

    def test_fixed_threshold_boundary_is_identical_for_single_and_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.artifact(folder)
            score = PredictionService(path).predict(self.rows.iloc[[1]]).attack_score.iloc[0]
            self.artifact(folder, {**self.bundle, "threshold": float(score)})
            with TestClient(create_app(path, enable_logging=False), base_url="http://localhost") as client:
                row = self.rows.iloc[1].to_dict()
                single = client.post("/api/predict/single", json=row).json()
                batch = client.post("/api/predict/batch", json={"connections": [row, row]}).json()
                self.assertEqual(single["score"], single["threshold"])
                self.assertEqual(single["prediction"]["label"], 1)
                self.assertEqual([r["prediction"]["label"] for r in batch["predictions"]], [1, 1])

    def test_missing_or_modified_artifact_returns_503_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"model.joblib"
            for damage in ("missing", "hash", "runtime", "calibration"):
                if damage != "missing":
                    self.artifact(folder)
                    manifest_path = artifact_manifest_path(path)
                    manifest = json.loads(manifest_path.read_text())
                    if damage == "hash":
                        manifest["artifact_sha256"] = "0"*64
                    elif damage == "runtime":
                        manifest["runtime"]["packages"]["scikit-learn"] = "1.5.1"
                    else:
                        manifest["score_calibration"]["method"] = "test_percentile"
                    manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(ArtifactError):
                    load_prediction_artifact(path)
                with TestClient(create_app(path, enable_logging=False), base_url="http://localhost") as client:
                    self.assertEqual(client.get("/health").status_code, 503)
                    response = client.post("/api/predict/single", json=self.rows.iloc[1].to_dict())
                    self.assertEqual(response.status_code, 503, response.text)


if __name__ == "__main__":
    unittest.main()
