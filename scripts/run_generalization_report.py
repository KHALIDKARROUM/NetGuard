"""Execute only the new evaluation section; preserve previous notebook results."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

import nbformat
from nbclient import NotebookClient

from notebook_integrity import validate_all
from run_notebook import EnvironmentKernelManager

ROOT = Path(__file__).resolve().parents[1]
CELL_ID = "current-generalization"


class ProgressNotebookClient(NotebookClient):
    def process_message(self, msg, cell, cell_index):
        if msg.get("msg_type") == "stream":
            print(msg["content"]["text"], end="", flush=True)
        return super().process_message(msg, cell, cell_index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-repeats", type=int, default=400)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    validate_all(ROOT)
    path = ROOT/"notebooks/00_netguard_complete.ipynb"
    original = json.loads(path.read_text(encoding="utf-8"))
    position = next(i for i, cell in enumerate(original["cells"]) if cell["id"] == CELL_ID)
    mini = nbformat.v4.new_notebook(cells=[nbformat.from_dict(deepcopy(original["cells"][position]))])
    # Normalize JSON source lists into the string format nbclient executes.
    mini = nbformat.reads(nbformat.writes(mini), as_version=4)
    output = ROOT/"artifacts/generalization"
    runtime = output/"jupyter_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.update({"NETGUARD_PROJECT_ROOT": str(ROOT), "NETGUARD_BOOTSTRAP_REPEATS": str(args.bootstrap_repeats),
        "JUPYTER_RUNTIME_DIR": str(runtime), "IPYTHONDIR": str(runtime/"ipython"),
        "PYTHONHASHSEED": "42", "LOKY_MAX_CPU_COUNT": "2", "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"})
    client = ProgressNotebookClient(mini, timeout=args.timeout, allow_errors=False,
        resources={"metadata": {"path": str(ROOT)}}, kernel_manager_class=EnvironmentKernelManager)
    print("Executing generalization evaluation in a fresh kernel; existing results remain preserved", flush=True)
    client.execute(env=environment)
    result = deepcopy(original)
    result["cells"][position] = json.loads(nbformat.writes(mini))["cells"][0]
    execution = {"status": "passed", "executed_utc": datetime.now(timezone.utc).isoformat(),
        "current_cell_ids_executed": [CELL_ID], "previous_cells_preserved": True,
        "historical_cells_executed": 0, "bootstrap_repeats": args.bootstrap_repeats}
    result["metadata"]["netguard_workflow"]["generalization_execution"] = execution
    for index, cell in enumerate(original["cells"]):
        if index != position and result["cells"][index] != cell:
            raise AssertionError("Previous notebook cell changed")
    # Preserve a complete recoverable copy before replacing a large notebook.
    # Atomic replacement also avoids in-place truncation of a mapped/open file.
    saved = output/"00_netguard_complete.executed.ipynb"
    saved.write_text(json.dumps(result, ensure_ascii=False, indent=1)+"\n", encoding="utf-8", newline="\n")
    pending = output/"00_netguard_complete.pending.ipynb"
    shutil.copyfile(saved, pending)
    pending.replace(path)
    execution["notebook_checks"] = validate_all(ROOT)
    evidence = json.loads((ROOT/"data/reports/generalization.json").read_text(encoding="utf-8"))
    execution["evaluation_checks"] = evidence["checks"]
    execution["serving_artifact_sha256"] = evidence["serving_artifact_sha256"]
    (ROOT/"data/reports/generalization_notebook_execution.json").write_text(
        json.dumps(execution, indent=2)+"\n", encoding="utf-8", newline="\n")
    print("Passed: fresh evaluation cell, prior cells preserved, original benchmark/artifact unchanged", flush=True)


if __name__ == "__main__":
    main()
