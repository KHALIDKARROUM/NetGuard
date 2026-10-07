"""Validate the single, self-contained NetGuard analysis notebook."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import re

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_NAME = "00_netguard_complete.ipynb"


def cell_digest(cell):
    payload = {key: value for key, value in cell.items() if key != "id"}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_all(root=ROOT):
    directory = Path(root) / "notebooks"
    paths = sorted(directory.glob("*.ipynb"))
    if [path.name for path in paths] != [NOTEBOOK_NAME]:
        raise AssertionError("Expected exactly one consolidated analysis notebook")
    path = paths[0]
    source = path.read_text(encoding="utf-8")
    if re.search(r"^(<<<<<<<|=======|>>>>>>>)(?: |$)", source, re.MULTILINE):
        raise AssertionError(f"Unresolved merge conflict in {path}")
    notebook = nbformat.reads(source, as_version=4)
    nbformat.validate(notebook)
    ids = [cell.id for cell in notebook.cells]
    if len(ids) != len(set(ids)):
        raise AssertionError("Duplicate notebook cell IDs")
    workflow = notebook.metadata.netguard_workflow
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    if workflow.get("schema_version") != 2 or not workflow.get("self_contained"):
        raise AssertionError("The notebook must declare its standalone workflow")
    if workflow.executable_cell_ids != [cell.id for cell in code_cells]:
        raise AssertionError("Every code cell must run, in notebook order")
    for cell in code_cells:
        if "netguard-current" not in cell.metadata.get("tags", []):
            raise AssertionError(f"Untagged executable cell: {cell.id}")
        tree = ast.parse(cell.source, filename=f"<notebook:{cell.id}>")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
                if node.level:
                    raise AssertionError(f"Relative project import in {cell.id}")
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            if any(module.split(".")[0] in {"netguard_workflow", "backend", "frontend", "scripts"}
                   for module in modules):
                raise AssertionError(f"External project import in {cell.id}")
        if any(output.output_type == "error" for output in cell.outputs):
            raise AssertionError(f"Saved execution error in {cell.id}")
    legacy = notebook.metadata.netguard_consolidation.legacy_sources
    if len(legacy) != 7:
        raise AssertionError("Original source text from all seven stages must be retained")
    preserved = 0
    for entry in legacy:
        digest = sha256(json.dumps(entry["cells"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if digest != entry["source_sha256"]:
            raise AssertionError(f"Preserved source changed: {entry['notebook']}")
        preserved += len(entry["cells"])
    return [{"notebook": path.name, "cells": len(notebook.cells),
             "current_code_cells": len(code_cells), "preserved_source_cells_checked": preserved,
             "self_contained": True, "run_all_supported": True}]


if __name__ == "__main__":
    print(json.dumps(validate_all(), indent=2))
