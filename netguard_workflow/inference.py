"""One inference contract for notebooks, saved artifacts and HTTP adapters."""
from __future__ import annotations

from hashlib import sha256
from functools import lru_cache
from importlib.metadata import version
import json
from pathlib import Path
import platform

import joblib
import numpy as np
import pandas as pd
from sklearn.utils.validation import check_is_fitted
from threadpoolctl import threadpool_limits

from .features import FEATURE_SCHEMA_VERSION, RAW_INPUTS, FEATURE_NAMES

ARTIFACT_SCHEMA_VERSION = 1
RUNTIME_PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl")


class ArtifactError(ValueError):
    """A saved prediction artifact is missing, incompatible or inconsistent."""


@lru_cache(maxsize=1)
def runtime_versions():
    return {"python": platform.python_version(), "packages": {p: version(p) for p in RUNTIME_PACKAGES}}


@lru_cache(maxsize=1)
def feature_implementation_hash():
    source = Path(__file__).with_name("features.py").read_text(encoding="utf-8")
    return sha256(source.encode("utf-8")).hexdigest()


def validate_bundle(bundle):
    if not isinstance(bundle, dict):
        raise ArtifactError("The prediction artifact must contain a complete pipeline bundle.")
    if bundle.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactError("Unsupported prediction artifact schema; retrain with the corrected notebook.")
    if bundle.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ArtifactError("Unsupported feature schema; retrain with the corrected notebook.")
    if bundle.get("precision") != "float64":
        raise ArtifactError("The prediction artifact must declare float64 precision.")
    if bundle.get("runtime") != runtime_versions():
        raise ArtifactError("Prediction runtime differs from training. Install the shared locked environment.")
    if bundle.get("feature_implementation_sha256") != feature_implementation_hash():
        raise ArtifactError("Feature implementation differs from training; retrain the shared artifact.")
    if bundle.get("raw_inputs") != list(RAW_INPUTS) or bundle.get("features") != list(FEATURE_NAMES):
        raise ArtifactError("The artifact feature order does not match the shared feature contract.")
    threshold = bundle.get("threshold")
    if not isinstance(threshold, (int, float)) or not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ArtifactError("The fixed classification threshold must be finite and between 0 and 1.")
    pipeline = bundle.get("pipeline")
    if pipeline is None or list(pipeline.named_steps) != ["raw_features", "scaler", "model"]:
        raise ArtifactError("The saved artifact must contain feature creation, scaling and model scoring.")
    feature_step = pipeline.named_steps["raw_features"]
    if getattr(feature_step, "feature_schema_version_", None) != FEATURE_SCHEMA_VERSION:
        raise ArtifactError("The fitted feature transformer uses an incompatible schema.")
    scaler = pipeline.named_steps["scaler"]
    model = pipeline.named_steps["model"]
    check_is_fitted(scaler)
    check_is_fitted(model)
    if list(scaler.feature_names_in_) != list(FEATURE_NAMES) or getattr(model, "n_features_in_", len(FEATURE_NAMES)) != len(FEATURE_NAMES):
        raise ArtifactError("Fitted preprocessing and model dimensions do not match the feature contract.")
    if not np.array_equal(model.classes_, [0, 1]):
        raise ArtifactError("The model must score 0=normal and 1=attack in that order.")
    return bundle


def predict_raw(bundle, frame):
    """Preserve full float64 scores and use the saved, batch-independent threshold."""
    validate_bundle(bundle)
    if not isinstance(frame, pd.DataFrame) or not len(frame):
        raise ValueError("Supply at least one raw connection as a pandas DataFrame.")
    with threadpool_limits(limits=bundle["config"]["threads"]):
        scores = bundle["pipeline"].predict_proba(frame)[:, 1].astype(np.float64, copy=False)
    if not np.isfinite(scores).all():
        raise ArtifactError("The shared pipeline produced nonfinite scores.")
    return pd.DataFrame({"attack_score": scores,
                         "predicted_label": (scores >= bundle["threshold"]).astype(np.int8)}, index=frame.index)


def _file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_manifest_path(path):
    return Path(path).with_suffix(".manifest.json")


def save_prediction_artifact(bundle, path):
    """Save the full fitted bundle with a hash and pre-load compatibility manifest."""
    validate_bundle(bundle)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    manifest = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "artifact_sha256": _file_hash(path), "runtime": bundle["runtime"],
        "precision": bundle["precision"], "raw_inputs": bundle["raw_inputs"],
        "features": bundle["features"], "threshold": bundle["threshold"],
        "threshold_policy": bundle["threshold_policy"], "model_name": bundle["model_name"],
        "model_selection": bundle["selection_policy"],
        "evaluation_status": bundle["evaluation_status"],
        "feature_implementation_sha256": bundle["feature_implementation_sha256"],
    }
    artifact_manifest_path(path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def load_prediction_artifact(path):
    """Verify a trusted project's saved artifact before deserializing it."""
    path = Path(path)
    sidecar = artifact_manifest_path(path)
    if not path.is_file() or not sidecar.is_file():
        raise ArtifactError("Shared prediction artifact is missing. Run scripts/run_notebook.py to retrain and save it.")
    try:
        manifest = json.loads(sidecar.read_text(encoding="utf-8"))
        if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ArtifactError("Unsupported artifact manifest schema.")
        if manifest.get("runtime") != runtime_versions():
            raise ArtifactError("Prediction runtime differs from training. Install the shared locked environment.")
        if manifest.get("artifact_sha256") != _file_hash(path):
            raise ArtifactError("The prediction artifact hash does not match its manifest.")
        bundle = validate_bundle(joblib.load(path))
        if any(bundle.get(key) != manifest.get(key) for key in (
            "runtime", "threshold", "precision", "raw_inputs", "features", "feature_schema_version", "model_name"
        )):
            raise ArtifactError("The prediction artifact and manifest are inconsistent.")
        return bundle
    except ArtifactError:
        raise
    except Exception as exc:
        raise ArtifactError("Could not load the shared prediction artifact; retrain it in the locked environment.") from exc


class PredictionService:
    """Loaded, immutable-by-convention artifact used by any transport adapter."""
    def __init__(self, artifact_path):
        self.artifact_path = Path(artifact_path)
        self.bundle = load_prediction_artifact(self.artifact_path)
        self.artifact_sha256 = _file_hash(self.artifact_path)

    def predict(self, raw_frame):
        return predict_raw(self.bundle, raw_frame)

    @property
    def metadata(self):
        return {
            "name": self.bundle["model_name"], "threshold": self.bundle["threshold"],
            "threshold_policy": self.bundle["threshold_policy"],
            "selection_policy": self.bundle["selection_policy"],
            "feature_count": len(FEATURE_NAMES), "raw_inputs": list(RAW_INPUTS),
            "precision": self.bundle["precision"], "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "artifact_sha256": self.artifact_sha256,
            "metrics": self.bundle.get("benchmark_metrics", {}),
            "evaluation_status": self.bundle["evaluation_status"],
            "components": [{"name": self.bundle["model_name"], "weight": 1.0}],
        }
