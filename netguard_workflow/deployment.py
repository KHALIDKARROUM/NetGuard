"""Serve trusted, by-value notebook exports without importing notebook code."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import re

import numpy as np
import pandas as pd
from sklearn.utils.validation import check_is_fitted
from threadpoolctl import threadpool_limits

from .features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, RAW_INPUTS
from .inference import (ArtifactError, PredictionService, SCORE_CALIBRATION,
                        _file_hash, artifact_manifest_path)

PORTABLE_FORMAT = "netguard-notebook-cloudpickle-v1"
SUPPORTED_MODELS = {"xgboost", "lightgbm", "tabm"}
PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl",
            "catboost", "xgboost", "lightgbm", "torch", "tabm", "rtdl-num-embeddings")
CONTRACT_KEYS = ("artifact_schema_version", "feature_schema_version", "runtime", "precision",
                 "raw_inputs", "features", "threshold", "threshold_policy", "model_name",
                 "score_calibration", "threshold_selection", "feature_implementation_sha256",
                 "model_implementation_sha256")


def _read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return value
    except (OSError, ValueError) as exc:
        raise ArtifactError("The deployed model configuration is missing or invalid.") from exc


def _check_contract(value):
    if value.get("artifact_schema_version") != 3 or value.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ArtifactError("Unsupported notebook prediction schema.")
    if value.get("precision") != "float64" or value.get("raw_inputs") != list(RAW_INPUTS) or value.get("features") != list(FEATURE_NAMES):
        raise ArtifactError("The deployed input, feature order or precision is incompatible.")
    if value.get("model_name") not in SUPPORTED_MODELS:
        raise ArtifactError("Unsupported deployed notebook model.")
    threshold = value.get("threshold")
    if not isinstance(threshold, (int, float)) or not np.isfinite(threshold) or not 0 <= threshold <= np.nextafter(1., np.inf):
        raise ArtifactError("The saved decision threshold is invalid.")
    if value.get("score_calibration") != SCORE_CALIBRATION:
        raise ArtifactError("Unsupported score calibration.")
    budget = value.get("threshold_selection", {}).get("max_false_positive_rate")
    if not isinstance(budget, (int, float)) or not np.isfinite(budget) or not 0 <= budget < 1:
        raise ArtifactError("The saved validation false-positive budget is invalid.")
    for key in ("feature_implementation_sha256", "model_implementation_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", value.get(key, "")):
            raise ArtifactError("Notebook source provenance is missing.")


def verify_portable_manifest(path):
    """Check the complete contract, runtime and file hash BEFORE unpickling."""
    path = Path(path)
    manifest = _read_json(artifact_manifest_path(path))
    if manifest.get("format") != PORTABLE_FORMAT:
        raise ArtifactError("Unsupported deployed artifact format.")
    _check_contract(manifest)
    try:
        current = {"python": platform.python_version(), "packages": {p: version(p) for p in PACKAGES}}
        if manifest.get("runtime") != current or manifest.get("cloudpickle_version") != version("cloudpickle"):
            raise ArtifactError("Prediction runtime differs from training. Install the locked backend environment.")
        if manifest.get("artifact_sha256") != _file_hash(path):
            raise ArtifactError("The deployed model hash does not match its manifest.")
    except (OSError, PackageNotFoundError) as exc:
        raise ArtifactError("The deployed model or its locked dependencies are missing.") from exc
    return manifest


class NotebookPredictionService(PredictionService):
    """Read the exact frozen notebook pipeline, including its fitted preprocessing."""
    def __init__(self, artifact_path):
        self.artifact_path = Path(artifact_path)
        manifest = verify_portable_manifest(self.artifact_path)
        try:
            import cloudpickle
            with self.artifact_path.open("rb") as handle:
                bundle = cloudpickle.load(handle)
            if not isinstance(bundle, dict) or any(bundle.get(k) != manifest.get(k) for k in CONTRACT_KEYS):
                raise ArtifactError("The deployed model and manifest are inconsistent.")
            _check_contract(bundle)
            pipeline = bundle["pipeline"]
            if list(pipeline.named_steps) != ["raw_features", "scaler", "model"]:
                raise ArtifactError("The full fitted notebook pipeline is required.")
            for step in pipeline.named_steps.values():
                check_is_fitted(step)
            if list(pipeline.named_steps["scaler"].feature_names_in_) != list(FEATURE_NAMES):
                raise ArtifactError("Fitted preprocessing uses the wrong feature order.")
            model = pipeline.named_steps["model"]
            if model.n_features_in_ != len(FEATURE_NAMES) or not np.array_equal(model.classes_, [0, 1]):
                raise ArtifactError("Model dimensions or label order are incompatible.")
            if bundle["config"]["max_false_positive_rate"] != bundle["threshold_selection"]["max_false_positive_rate"]:
                raise ArtifactError("The saved threshold budget is inconsistent.")
            if not isinstance(bundle["config"].get("threads"), int) or not 1 <= bundle["config"]["threads"] <= 8:
                raise ArtifactError("Invalid inference thread budget.")
            allowed_reports = {"validation_comparison", "benchmark_comparison", "ensemble_decision",
                               "latency_protocol", "benchmark_metrics"}
            reports = manifest.get("report_metadata", {})
            if not isinstance(reports, dict) or set(reports) - allowed_reports:
                raise ArtifactError("Invalid deployed reporting metadata.")
            if getattr(pipeline.named_steps["raw_features"], "feature_schema_version_", None) != FEATURE_SCHEMA_VERSION:
                raise ArtifactError("The fitted feature transformer uses the wrong schema.")
            self.bundle = {**bundle, **reports}
            self.artifact_sha256 = manifest["artifact_sha256"]
        except ArtifactError:
            raise
        except Exception as exc:
            raise ArtifactError("Could not load the frozen notebook model in the locked environment.") from exc

    def predict(self, raw_frame):
        if not isinstance(raw_frame, pd.DataFrame) or not len(raw_frame):
            raise ValueError("Supply at least one measured connection.")
        with threadpool_limits(limits=self.bundle["config"]["threads"]):
            scores = np.asarray(self.bundle["pipeline"].predict_proba(raw_frame)[:, 1], dtype=np.float64)
        if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
            raise ArtifactError("The deployed pipeline produced an invalid attack score.")
        return pd.DataFrame({"attack_score": scores,
                             "predicted_label": (scores >= self.bundle["threshold"]).astype(np.int8)}, index=raw_frame.index)


class PredictionRegistry:
    """An explicit model allowlist; request values never become filesystem paths."""
    def __init__(self, path):
        path = Path(path)
        config = _read_json(path)
        entries = config.get("models", {})
        if config.get("schema_version") != 1 or not isinstance(entries, dict) or not entries or set(entries) - SUPPORTED_MODELS or config.get("default") not in entries:
            raise ArtifactError("Invalid deployed model registry.")
        self.default = config["default"]
        self.services = {}
        for name, entry in entries.items():
            if not isinstance(entry, dict):
                raise ArtifactError("Invalid model registry entry.")
            filename = entry.get("file")
            if not isinstance(filename, str) or filename != f"{name}.pkl":
                raise ArtifactError("Model registry paths must be explicit local filenames.")
            model_path = path.parent / filename
            sidecar = artifact_manifest_path(model_path)
            if not sidecar.is_file() or entry.get("manifest_sha256") != _file_hash(sidecar):
                raise ArtifactError("A deployed model manifest differs from the registry.")
            service = NotebookPredictionService(model_path)
            if service.bundle["model_name"] != name:
                raise ArtifactError("The registry model name differs from the saved artifact.")
            self.services[name] = service

    def get(self, name=None):
        return self.services[name or self.default]

    @property
    def metadata(self):
        return [{"id": name, "default": name == self.default, **service.metadata}
                for name, service in self.services.items()]
