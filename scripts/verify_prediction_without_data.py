"""Check cold-start live prediction in an isolated checkout containing no dataset.

Run with the locked backend interpreter. Only Python sources and the saved model
and its manifest are copied. An audit hook, installed before importing the API,
rejects CSV opens and access to the original checkout's data directory. The
temporary Uvicorn server is always stopped and its isolated checkout removed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
import numpy as np
import pandas as pd

from netguard_workflow import PredictionService
from netguard_workflow.deployment import NotebookPredictionService
from netguard_workflow.inference import artifact_manifest_path


def example_connections():
    """Synthetic measurements; no sampled or retrieved training/test records."""
    zero = {"sbytes": 0, "dbytes": 0, "spkts": 0, "dpkts": 0, "dur": 0.0,
            "rate": 0.0, "sload": 0.0, "dload": 0.0, "sttl": 0, "dttl": 0}
    return [
        zero,
        {**zero, "sbytes": 1500, "dbytes": 5000, "spkts": 10, "dpkts": 15,
         "dur": 0.5, "rate": 48.0, "sload": 24000.0, "dload": 80000.0,
         "sttl": 64, "dttl": 64},
        {**zero, "sbytes": 512, "spkts": 1, "dur": 0.00001, "rate": 100000.0,
         "sload": 409600000.0, "sttl": 254},
        {**zero, "sbytes": 1048576, "dbytes": 2097152, "spkts": 1024, "dpkts": 2048,
         "dur": 120.0, "rate": 25.591666666666665, "sload": 69905.06666666667,
         "dload": 139810.13333333333, "sttl": 128, "dttl": 60},
        {**zero, "sbytes": 16777217, "dbytes": 16777216, "spkts": 3, "dpkts": 1,
         "dur": float(np.nextafter(0.121478, 1.0)), "sttl": 9, "dttl": 10},
        {**zero, "sbytes": 2**53-1, "spkts": 1, "dur": 1.0, "sttl": 255},
        {**zero, "sbytes": 100, "dbytes": 50, "spkts": 1, "dpkts": 1,
         "sttl": 10, "dttl": 9},
    ]


def copy_minimal_checkout(destination, artifact):
    """Copy only executable project source and the requested prediction bundle."""
    destination = Path(destination).resolve()
    for package in ("backend", "netguard_workflow"):
        source = ROOT/package
        for path in source.rglob("*.py"):
            relative = path.relative_to(source)
            if any(part in {"__pycache__", "logs", "backend_venv", ".venv"} for part in relative.parts):
                continue
            target = destination/package/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    isolated_artifact = destination/"models_saved"/Path(artifact).name
    isolated_artifact.parent.mkdir()
    shutil.copyfile(artifact, isolated_artifact)
    shutil.copyfile(artifact_manifest_path(artifact), artifact_manifest_path(isolated_artifact))
    assert not (destination/"data").exists()
    assert not list(destination.rglob("*.csv"))
    return isolated_artifact


def write_guarded_server(destination):
    launcher = Path(destination)/"_serve_without_data.py"
    launcher.write_text('''from pathlib import Path
import json
import os
import sys

isolated_root = Path(__file__).resolve().parent
original_data = Path(os.environ["NETGUARD_FORBIDDEN_DATA"]).resolve()
guard_log = (isolated_root / "dataset_access_attempts.jsonl").open("w", encoding="utf-8")

def reject_dataset_access(event, args):
    if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if path.suffix.lower() == ".csv" or path == original_data or original_data in path.parents:
        guard_log.write(json.dumps({"event": event, "path": str(path)}) + "\\n")
        guard_log.flush()
        raise PermissionError("Dataset access is forbidden during this isolation check")

sys.addaudithook(reject_dataset_access)
sys.path.insert(0, str(isolated_root))
import uvicorn
uvicorn.run("backend.main:app", host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
''', encoding="utf-8", newline="\n")
    return launcher


@contextmanager
def isolated_api(artifact, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="no-data-", dir=output) as temporary:
        isolated_root = Path(temporary).resolve()
        # TemporaryDirectory cleanup is confined to the verified output folder.
        if isolated_root.parent != output:
            raise RuntimeError("Unexpected temporary checkout location")
        isolated_artifact = copy_minimal_checkout(isolated_root, artifact)
        launcher = write_guarded_server(isolated_root)
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        env = dict(os.environ, PREDICTION_ARTIFACT=str(isolated_artifact),
                   NETGUARD_LOG_DIR=str(isolated_root/"logs"),
                   NETGUARD_FORBIDDEN_DATA=str(ROOT/"data"), LOKY_MAX_CPU_COUNT="2")
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        with (output/"without_data_uvicorn.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-I", str(launcher), str(port)], cwd=isolated_root, env=env,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30, trust_env=False) as client:
                    deadline = time.monotonic()+30
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError(f"Isolated API exited; inspect {output/'without_data_uvicorn.log'}")
                        try:
                            health = client.get("/health")
                            require_success(health)
                            break
                        except httpx.ConnectError:
                            if time.monotonic() >= deadline:
                                raise RuntimeError("Isolated API did not start within 30 seconds")
                            time.sleep(0.2)
                    yield client, isolated_root
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                guard_log = isolated_root/"dataset_access_attempts.jsonl"
                if guard_log.exists():
                    shutil.copyfile(guard_log, output/"without_data_access_attempts.jsonl")


def require_success(response):
    if response.status_code != 200:
        raise AssertionError(f"HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def verify(artifact, output):
    loader = NotebookPredictionService if Path(artifact).suffix == ".pkl" else PredictionService
    service = loader(Path(artifact).resolve())
    records = example_connections()
    expected = service.predict(pd.DataFrame(records))
    differences = []
    comparisons = 0
    with isolated_api(artifact, output) as (client, isolated_root):
        health = require_success(client.get("/health"))
        assert health["models_ready"] and health["precision"] == "float64"
        assert health["artifact_sha256"] == service.artifact_sha256
        metadata = require_success(client.get("/api/predict/info"))["best_model"]
        assert metadata["raw_inputs"] == service.bundle["raw_inputs"]
        assert metadata["artifact_sha256"] == service.artifact_sha256
        assert metadata["precision"] == "float64"
        assert metadata["threshold"] == service.bundle["threshold"]
        assert metadata["threshold_policy"] == service.bundle["threshold_policy"]
        assert metadata["threshold_selection"] == service.bundle["threshold_selection"]
        assert metadata["score_calibration"] == service.bundle["score_calibration"]

        def compare(result, index):
            nonlocal comparisons
            reference = expected.iloc[index]
            difference = abs(result["score"]-float(reference.attack_score))
            assert difference <= 1e-12, difference
            assert result["prediction"]["label"] == int(reference.predicted_label)
            assert result["threshold"] == service.bundle["threshold"]
            assert result["artifact_sha256"] == service.artifact_sha256
            assert result["precision"] == "float64"
            differences.append(difference)
            comparisons += 1

        for i, record in enumerate(records):
            compare(require_success(client.post("/api/predict/single", json=record)), i)
        for order in (list(range(len(records))), list(reversed(range(len(records))))):
            batch = require_success(client.post("/api/predict/batch", json={
                "connections": [dict(reversed(list(records[i].items()))) for i in order]}))
            assert batch["n"] == len(records) and len(batch["predictions"]) == len(records)
            for result, index in zip(batch["predictions"], order):
                compare(result, index)
        access_log = isolated_root/"dataset_access_attempts.jsonl"
        assert access_log.read_text(encoding="utf-8") == "", "Prediction attempted to open a dataset"
        dataset_response = client.get("/api/dataset/info")
        assert dataset_response.status_code == 404, dataset_response.text
        # A failed exploration request must not change subsequent prediction.
        compare(require_success(client.post("/api/predict/single", json=records[1])), 1)
        assert access_log.read_text(encoding="utf-8") == "", "An endpoint attempted to open a dataset"
        assert not (isolated_root/"data").exists()
        assert not list(isolated_root.rglob("*.csv"))

    return {
        "status": "passed", "verified_utc": datetime.now(timezone.utc).isoformat(),
        "transport": "live Uvicorn loopback HTTP server in a cold separate process",
        "runtime": service.bundle["runtime"], "artifact_sha256": service.artifact_sha256,
        "model": service.bundle["model_name"], "threshold": service.bundle["threshold"],
        "threshold_policy": service.bundle["threshold_policy"],
        "threshold_selection": service.bundle["threshold_selection"],
        "score_calibration": service.bundle["score_calibration"],
        "raw_inputs": service.bundle["raw_inputs"], "precision": "float64",
        "synthetic_connections": len(records), "prediction_comparisons": comparisons,
        "maximum_score_difference": max(differences), "decision_mismatches": 0,
        "score_tolerance": 1e-12, "dataset_endpoint_http_status": 404,
        "dataset_open_attempts": 0,
        "isolation": {
            "copied": ["backend Python sources", "netguard_workflow Python sources",
                       "shared prediction artifact", "artifact manifest"],
            "data_directory_present": False, "csv_files_present": False,
            "source_checkout_removed_from_import_path": True,
            "audit_hook_installed_before_api_import": True,
            "audit_hook_rejects": ["all CSV opens", "opens within original checkout data directory"],
            "process_stopped_and_temporary_checkout_removed": True,
        },
        "checks": {"cold_start_health": True, "single_and_batch_parity": True,
                   "row_and_field_order_parity": True, "artifact_identity_matches": True,
                   "fixed_saved_threshold": True, "full_precision_scores": True,
                   "prediction_still_works_after_dataset_404": True},
        "scope": "Synthetic measurement parity and absence of dataset reads; not an accuracy evaluation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=ROOT/"models_saved/deployed/xgboost.pkl")
    parser.add_argument("--report", type=Path, default=ROOT/"data/reports/prediction_without_data.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"artifacts/prediction_verification")
    args = parser.parse_args()
    report = verify(args.artifact.resolve(), args.output_dir.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(f"Passed {report['prediction_comparisons']} live API comparisons without any dataset; "
          f"maximum score difference {report['maximum_score_difference']}", flush=True)
    print(f"Evidence: {args.report}", flush=True)


if __name__ == "__main__":
    main()
