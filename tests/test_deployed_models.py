"""Real frozen-model HTTP routing, parity, isolation and pre-load integrity checks."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import numpy as np
import pandas as pd

from backend.config import Settings
from backend.main import create_app
from netguard_workflow.deployment import NotebookPredictionService, PredictionRegistry
from netguard_workflow.inference import ArtifactError, artifact_manifest_path

ROOT = Path(__file__).resolve().parents[1]
DEPLOYED = ROOT / "models_saved/deployed"
ZERO = dict(sbytes=0, dbytes=0, spkts=0, dpkts=0, dur=0., rate=0., sload=0., dload=0., sttl=0, dttl=0)
ROWS = [ZERO, {**ZERO, "sbytes":1500, "dbytes":5000, "spkts":10, "dpkts":15, "dur":.5, "rate":48., "sttl":64, "dttl":64},
        {**ZERO, "sbytes":16777217, "dbytes":16777216, "spkts":3, "dpkts":1, "dur":float(np.nextafter(.121478, 1.)), "sttl":9, "dttl":10},
        {**ZERO, "sbytes":2**53-1, "spkts":1, "sttl":255}]


class DeployedModelChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = PredictionRegistry(DEPLOYED / "registry.json")

    def test_default_and_model_selection_without_dataset_reads(self):
        expected = {name: service.predict(pd.DataFrame(ROWS)) for name, service in self.registry.services.items()}
        with patch("pandas.read_csv", side_effect=AssertionError("Inference cannot read datasets")), TestClient(create_app(enable_logging=False), base_url="http://localhost") as client:
            self.assertEqual(client.get("/health").status_code, 200)
            info = client.get("/api/predict/best_model").json()
            self.assertEqual(info["best_model"]["name"], "xgboost")
            self.assertEqual({m["id"] for m in info["available_models"]}, {"xgboost", "lightgbm", "tabm"})
            self.assertEqual(client.post("/api/predict/single", json=ROWS[0]).json()["model"], "xgboost")
            for name, reference in expected.items():
                response = client.post(f"/api/predict/batch?model={name}", json={"connections":ROWS})
                self.assertEqual(response.status_code, 200, response.text)
                results = response.json()["predictions"]
                np.testing.assert_allclose([r["score"] for r in results], reference.attack_score, rtol=0, atol=1e-12)
                np.testing.assert_array_equal([r["prediction"]["label"] for r in results], reference.predicted_label)
                for i, row in enumerate(ROWS):
                    single = client.post(f"/api/predict/single?model={name}", json=dict(reversed(list(row.items())))).json()
                    self.assertEqual(single["model"], name)
                    self.assertEqual(single["threshold"], self.registry.get(name).bundle["threshold"])
                    self.assertAlmostEqual(single["score"], results[i]["score"], delta=1e-12)
                    self.assertEqual(single["prediction"], results[i]["prediction"])

    def test_unknown_model_is_rejected_without_loading_a_path(self):
        with TestClient(create_app(enable_logging=False), base_url="http://localhost") as client:
            for name in ("../shared_pipeline.joblib", "missing", "catboost"):
                with patch("cloudpickle.load", side_effect=AssertionError("No request may load an arbitrary artifact")):
                    self.assertEqual(client.post("/api/predict/single", params={"model":name}, json=ROWS[0]).status_code, 422)

    def test_hash_and_runtime_checked_before_deserialization(self):
        for damage in ("hash", "runtime", "feature_order", "threshold", "calibration"):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as folder:
                target = Path(folder) / "xgboost.pkl"
                shutil.copyfile(DEPLOYED / target.name, target)
                manifest = json.loads(artifact_manifest_path(DEPLOYED / target.name).read_text())
                if damage == "hash":
                    manifest["artifact_sha256"] = "0"*64
                elif damage == "runtime":
                    manifest["runtime"]["packages"]["xgboost"] = "0.0.0"
                elif damage == "feature_order":
                    manifest["features"].reverse()
                elif damage == "threshold":
                    manifest["threshold"] = -1
                else:
                    manifest["score_calibration"]["method"] = "percentile"
                artifact_manifest_path(target).write_text(json.dumps(manifest))
                with patch("cloudpickle.load") as load, self.assertRaises(ArtifactError):
                    NotebookPredictionService(target)
                load.assert_not_called()

    def test_registry_pins_manifests_and_rejects_unavailable_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "models"
            shutil.copytree(DEPLOYED, target)
            manifest = target / "tabm.manifest.json"
            manifest.write_text(manifest.read_text() + " ")
            with self.assertRaises(ArtifactError):
                PredictionRegistry(target / "registry.json")
            configuration = Settings(_env_file=None, prediction_artifact=target / "xgboost.pkl",
                                     prediction_registry=target / "registry.json")
            with TestClient(create_app(enable_logging=False, service_settings=configuration), base_url="http://localhost") as client:
                self.assertEqual(client.get("/health").status_code, 503)
                self.assertEqual(client.post("/api/predict/single", json=ZERO).status_code, 503)

    def test_explicit_default_artifact_override_within_registry(self):
        configuration = Settings(_env_file=None, prediction_artifact=DEPLOYED / "lightgbm.pkl")
        with TestClient(create_app(enable_logging=False, service_settings=configuration), base_url="http://localhost") as client:
            self.assertEqual(client.get("/health").json()["model"], "lightgbm")
            self.assertEqual(client.post("/api/predict/single", json=ZERO).json()["model"], "lightgbm")

    def test_authentication_applies_to_each_model(self):
        key = "deployment-test-" + "x"*32
        configuration = Settings(_env_file=None, api_key=key, deployment_mode="shared")
        with TestClient(create_app(enable_logging=False, service_settings=configuration), base_url="http://localhost") as client:
            for name in self.registry.services:
                self.assertEqual(client.post(f"/api/predict/single?model={name}", json=ROWS[0]).status_code, 401)
                response = client.post(f"/api/predict/single?model={name}", json=ROWS[0], headers={"X-API-Key":key})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["model"], name)

    def test_invalid_raw_inputs_rejected_for_each_model(self):
        with TestClient(create_app(enable_logging=False), base_url="http://localhost") as client:
            for name in self.registry.services:
                for invalid in ({}, {**ZERO, "dur":-1}, {**ZERO, "label":1}, {**ZERO, "sbytes":2**53-1, "dbytes":1}):
                    self.assertEqual(client.post(f"/api/predict/single?model={name}", json=invalid).status_code, 422)


if __name__ == "__main__":
    unittest.main()
