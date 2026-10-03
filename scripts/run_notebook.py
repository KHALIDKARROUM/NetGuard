"""Execute only the corrected sections, retaining historical cells unchanged."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpec

from notebook_integrity import validate_all

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentKernelManager(KernelManager):
    """Use the interpreter running this script, without a global kernel install."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kernel_spec = KernelSpec(
            argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            display_name="NetGuard notebook workflow", language="python",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT/"artifacts/notebook_workflow")
    parser.add_argument("--timeout", type=int, default=1200, help="Timeout per current code cell")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checks = validate_all(ROOT)
    path = ROOT/"notebooks/00_netguard_complete.ipynb"
    original = json.loads(path.read_text(encoding="utf-8"))
    current_ids = set(original["metadata"]["netguard_workflow"]["executable_cell_ids"])
    nb = nbformat.reads(json.dumps(original), as_version=4)
    for cell in nb.cells:
        if cell.id not in current_ids and cell.cell_type == "code":
            cell.metadata.setdefault("tags", []).append("netguard-history-skip")
    # Local runtime state avoids writing kernels, history or configuration outside
    # the workspace and does not rely on the caller's installed Jupyter kernels.
    runtime = output/"jupyter_runtime"
    runtime.mkdir(exist_ok=True)
    kernel_env = dict(os.environ)
    kernel_env.update({"NETGUARD_PROJECT_ROOT": str(ROOT), "NETGUARD_OUTPUT_DIR": str(output),
                       "JUPYTER_RUNTIME_DIR": str(runtime), "IPYTHONDIR": str(runtime/"ipython"),
                       "PYTHONHASHSEED": "42", "OMP_NUM_THREADS": "2",
                       "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"})
    client = NotebookClient(
        nb, timeout=args.timeout, kernel_name="python3", allow_errors=False,
        resources={"metadata": {"path": str(ROOT)}},
        skip_cells_with_tag="netguard-history-skip", kernel_manager_class=EnvironmentKernelManager,
    )
    def report_progress(cell, cell_index):
        if cell.id in current_ids:
            print(f"Running: {cell.id}", flush=True)
    client.on_cell_start = report_progress
    print(f"Executing {len(current_ids)} corrected cells in Python {sys.version.split()[0]}", flush=True)
    client.execute(env=kernel_env)
    # nbformat canonicalizes cell payloads. Restore original JSON objects for all
    # archived/nonexecuting cells before saving the executed copy.
    result = deepcopy(original)
    executed = json.loads(nbformat.writes(nb))
    for i, cell in enumerate(executed["cells"]):
        if cell["id"] in current_ids:
            result["cells"][i] = cell
    result["metadata"]["language_info"] = executed["metadata"]["language_info"]
    result["metadata"]["kernelspec"] = {
        "display_name": "NetGuard workflow (Python 3.13.9)",
        "language": "python", "name": "python3",
    }
    result["metadata"]["netguard_workflow"]["last_execution"] = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "executed_current_cells": client.code_cells_executed,
        "historical_cells_executed": 0,
    }
    if client.code_cells_executed != len(current_ids):
        raise AssertionError("Not every current workflow cell executed")
    nbformat.validate(nbformat.from_dict(result))
    report = output/"00_netguard_complete.executed.ipynb"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    # Copy compact fresh outputs into the main report; historical payloads remain
    # byte-for-byte equivalent as JSON values and the full executed copy is saved.
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    validate_all(ROOT)
    evidence = {"status": "passed", "current_cells_executed": client.code_cells_executed,
                "historical_cells_executed": 0, "notebook_checks": checks,
                "python": sys.version.split()[0], "executed_notebook": report.name}
    (output/"execution_check.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    verification = {
        "status": "passed", "execution": evidence,
        "manifest": json.loads((output/"manifest.json").read_text(encoding="utf-8")),
        "metrics": json.loads((output/"metrics.json").read_text(encoding="utf-8")),
    }
    (ROOT/"data/reports/notebook_workflow_verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Passed: raw data -> model -> {output/'benchmark_predictions.csv'}", flush=True)
    print(f"Executed report: {report}", flush=True)


if __name__ == "__main__":
    main()
