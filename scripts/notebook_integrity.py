"""Check notebook schemas, conflict markers and archived cell fingerprints."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re

import nbformat

ROOT = Path(__file__).resolve().parents[1]


def cell_digest(cell):
    payload = {k: v for k, v in cell.items() if k != "id"}
    # nbformat normalizes source/output lists to strings, so read original JSON.
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_all(root=ROOT):
    results = []
    for path in sorted((Path(root)/"notebooks").glob("*.ipynb")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^(<<<<<<<|=======|>>>>>>>)(?: |$)", text, re.MULTILINE):
            raise AssertionError(f"Unresolved merge conflict in {path}")
        original = json.loads(text)
        nbformat.validate(nbformat.from_dict(original))
        cells = original["cells"]
        ids = [c["id"] for c in cells]
        if len(ids) != len(set(ids)):
            raise AssertionError(f"Duplicate cell IDs in {path}")
        metadata = original["metadata"]
        combination = metadata.get("netguard_combination")
        if combination:
            origins = combination["cell_origins"]
        else:
            origins = metadata.get("netguard_history", {}).get("cell_origins", [])
        for origin in origins:
            cell = cells[origin["combined_cell_index"]]
            if cell["id"] != origin["cell_id"]:
                raise AssertionError(f"Bad origin mapping in {path}")
            if cell_digest(cell) != origin["original_cell_sha256_without_id"]:
                raise AssertionError(f"Historical cell changed in {path}: {cell['id']}")
        workflow = metadata.get("netguard_workflow", {})
        executable = workflow.get("executable_cell_ids", [])
        if executable:
            indexed = {c["id"]: c for c in cells}
            if len(executable) != len(set(executable)):
                raise AssertionError("Duplicate current cell IDs")
            for cell_id in executable:
                cell = indexed[cell_id]
                if cell["cell_type"] != "code" or "netguard-current" not in cell["metadata"].get("tags", []):
                    raise AssertionError(f"Invalid current workflow cell: {cell_id}")
            historical_ids = {o["cell_id"] for o in origins}
            if historical_ids.intersection(executable):
                raise AssertionError("Historical code cannot be part of the current workflow")
        results.append({"notebook": path.name, "cells": len(cells),
                        "preserved_origins_checked": len(origins), "current_code_cells": len(executable)})
    if len(results) != 8:
        raise AssertionError("Expected the combined notebook and seven originals")
    return results


if __name__ == "__main__":
    print(json.dumps(validate_all(), indent=2))
