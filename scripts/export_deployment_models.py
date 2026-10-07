"""Promote verified full-run notebook exports into the API's model registry."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cloudpickle
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from netguard_workflow.deployment import CONTRACT_KEYS, PORTABLE_FORMAT, PredictionRegistry
from netguard_workflow.inference import _file_hash, artifact_manifest_path

FILES = {"xgboost": "netguard_model.pkl", "lightgbm": "lightgbm_model.pkl", "tabm": "tabm_model.pkl"}
REPORT_KEYS = ("validation_comparison", "benchmark_comparison", "ensemble_decision", "latency_protocol")


def export_models(source, destination):
    source, destination = Path(source), Path(destination)
    run = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if run.get("fast_run") is not False or run.get("selected_model") != "xgboost":
        raise ValueError("Deploy only the completed full-data run with validation-selected XGBoost.")
    benchmark = pd.read_csv(ROOT / "data/UNSW_NB15_testing-set.csv")
    if run["input_sha256"]["UNSW_NB15_testing-set.csv"] != _file_hash(ROOT / "data/UNSW_NB15_testing-set.csv"):
        raise ValueError("Benchmark measurements differ from the verified notebook run.")
    comparison = pd.read_csv(source / "benchmark_comparison.csv", float_precision="round_trip")
    recorded = pd.read_csv(source / "benchmark_predictions.csv", float_precision="round_trip")
    with (source / FILES["xgboost"]).open("rb") as handle:
        selected = cloudpickle.load(handle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Verify all staged files before changing the serving directory. Restart workers
    # after publication; existing workers keep their immutable loaded pipelines.
    with tempfile.TemporaryDirectory(prefix="netguard-deployment-", dir=destination.parent) as folder:
        staged = Path(folder)
        registry = {"schema_version": 1, "default": "xgboost", "models": {}}
        checks = {}
        for name, filename in FILES.items():
            original = source / filename
            expected_hash = run["model_sha256"] if name == "xgboost" else run["additional_models"][name]["sha256"]
            if _file_hash(original) != expected_hash:
                raise ValueError(f"The verified {name} export has changed.")
            with original.open("rb") as handle:
                bundle = cloudpickle.load(handle)
            if bundle["model_name"] != name:
                raise ValueError(f"Unexpected model in {filename}.")
            with threadpool_limits(limits=2):
                scores = bundle["pipeline"].predict_proba(benchmark)[:, 1]
            expected = comparison.loc[comparison.model.eq(name)].iloc[0]
            labels = scores >= bundle["threshold"]
            counts = {"tn": int(((benchmark.label == 0) & ~labels).sum()),
                      "fp": int(((benchmark.label == 0) & labels).sum()),
                      "fn": int(((benchmark.label == 1) & ~labels).sum()),
                      "tp": int(((benchmark.label == 1) & labels).sum())}
            if bundle["threshold"] != expected.threshold or any(counts[k] != expected[k] for k in counts):
                raise ValueError(f"{name} no longer reproduces notebook benchmark decisions.")
            if name == "xgboost":
                np.testing.assert_allclose(scores, recorded.attack_score, rtol=0, atol=1e-12)
                np.testing.assert_array_equal(labels, recorded.predicted_label)
            target = staged / f"{name}.pkl"
            shutil.copyfile(original, target)
            metadata = {k: selected.get(k, {} if k != "validation_comparison" else []) for k in REPORT_KEYS}
            metadata["benchmark_metrics"] = {k: v.item() if isinstance(v, np.generic) else v
                                              for k, v in expected.to_dict().items() if k not in {"model", "selected"}}
            manifest = {"format": PORTABLE_FORMAT, "artifact_sha256": expected_hash,
                        "cloudpickle_version": version("cloudpickle"),
                        **{k: bundle[k] for k in CONTRACT_KEYS}, "report_metadata": metadata,
                        "source_run_manifest_sha256": _file_hash(source / "manifest.json"),
                        "source_notebook_sha256": _file_hash(ROOT / "notebooks/00_netguard_complete.ipynb")}
            sidecar = artifact_manifest_path(target)
            sidecar.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
            registry["models"][name] = {"file": target.name, "manifest_sha256": _file_hash(sidecar)}
            checks[name] = {"benchmark_rows": len(benchmark), "counts": counts,
                            "threshold": bundle["threshold"], "byte_identical_notebook_export": True}
        (staged / "registry.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8", newline="\n")
        deployed = PredictionRegistry(staged / "registry.json")
        sample = benchmark.iloc[:16].loc[:, selected["raw_inputs"]]
        for name in FILES:
            service = deployed.get(name)
            batch = service.predict(sample)
            singles = pd.concat([service.predict(sample.iloc[[i]]) for i in range(len(sample))])
            np.testing.assert_allclose(batch.attack_score, singles.attack_score, rtol=0, atol=1e-12)
            np.testing.assert_array_equal(batch.predicted_label, singles.predicted_label)
        destination.mkdir(parents=True, exist_ok=True)
        for path in staged.iterdir():
            if path.name != "registry.json":
                shutil.copyfile(path, destination / path.name)
        shutil.copyfile(staged / "registry.json", destination / "registry.json")
    report = {"status": "passed", "utc": datetime.now(timezone.utc).isoformat(),
              "default": "xgboost", "models": checks}
    (source / "deployment_export_check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "artifacts/notebook_report")
    parser.add_argument("--output", type=Path, default=ROOT / "models_saved/deployed")
    args = parser.parse_args()
    print(json.dumps(export_models(args.source, args.output), indent=2))
