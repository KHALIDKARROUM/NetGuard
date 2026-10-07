"""Run every cell of the standalone NetGuard notebook in a fresh kernel."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpec

from notebook_integrity import NOTEBOOK_NAME, validate_all

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentKernelManager(KernelManager):
    """Use this script's interpreter without installing a global Jupyter kernel."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kernel_spec = KernelSpec(
            argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            display_name="NetGuard standalone notebook", language="python",
        )


class ProgressNotebookClient(NotebookClient):
    def process_message(self, msg, cell, cell_index):
        if msg.get("msg_type") == "stream":
            print(msg["content"]["text"], end="", flush=True)
        return super().process_message(msg, cell, cell_index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/notebook_report")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout per code cell")
    parser.add_argument("--bootstrap-repeats", type=int, default=100)
    parser.add_argument("--extended", action="store_true", help="Run three grouped refits and every withheld family")
    parser.add_argument("--fast", action="store_true", help="Reduced model sizes for smoke verification only")
    args = parser.parse_args()
    if args.bootstrap_repeats < 20:
        parser.error("Use at least 20 bootstrap repetitions")
    checks = validate_all(ROOT)
    path = ROOT / "notebooks" / NOTEBOOK_NAME
    notebook = nbformat.read(path, as_version=4)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / "jupyter_runtime"
    runtime.mkdir(exist_ok=True)
    environment = dict(os.environ)
    environment.update({
        "NETGUARD_DATA_DIR": str(args.data_dir.resolve()), "NETGUARD_OUTPUT_DIR": str(output),
        "NETGUARD_FAST_RUN": str(int(args.fast)), "NETGUARD_EXTENDED": str(int(args.extended)),
        "NETGUARD_BOOTSTRAP_REPEATS": str(args.bootstrap_repeats),
        "JUPYTER_RUNTIME_DIR": str(runtime), "IPYTHONDIR": str(runtime / "ipython"),
        "MPLCONFIGDIR": str(runtime / "matplotlib"), "PYTHONHASHSEED": "42",
        "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
        "LOKY_MAX_CPU_COUNT": "2",
    })
    client = ProgressNotebookClient(
        notebook, timeout=args.timeout, allow_errors=False,
        resources={"metadata": {"path": str(args.data_dir.resolve())}},
        kernel_manager_class=EnvironmentKernelManager,
    )

    def report_progress(cell, cell_index):
        if cell.cell_type == "code":
            print(f"Running: {cell.id}", flush=True)

    client.on_cell_start = report_progress
    print(f"Executing all {checks[0]['current_code_cells']} code cells in a fresh Python kernel", flush=True)
    client.execute(env=environment)
    if client.code_cells_executed != checks[0]["current_code_cells"]:
        raise AssertionError("Not every notebook code cell executed")
    execution = {
        "status": "passed", "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "executed_current_cells": client.code_cells_executed,
        "historical_cells_executed": 0, "fast_run": args.fast,
        "extended_generalization": args.extended, "bootstrap_repeats": args.bootstrap_repeats,
        "notebook_checks": checks,
    }
    notebook.metadata.netguard_workflow.last_execution = execution
    nbformat.validate(notebook)
    report = output / "00_netguard_complete.executed.ipynb"
    nbformat.write(notebook, report)
    pending = path.with_suffix(".pending")
    nbformat.write(notebook, pending)
    pending.replace(path)
    validate_all(ROOT)
    (output / "execution_check.json").write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
    print(f"Passed: all cells executed; outputs and figures saved in {output}", flush=True)


if __name__ == "__main__":
    main()
