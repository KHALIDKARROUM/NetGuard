"""Restore conflicted notebooks from the verified combined preservation archive.

This one-time migration refuses to overwrite notebooks whose original hashes
do not match the archive. Existing original cell payloads are never edited.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import nbformat

from notebook_integrity import cell_digest, validate_all

ROOT = Path(__file__).resolve().parents[1]


def markdown(cell_id, text):
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": text.splitlines(keepends=True)}


def code(cell_id, text):
    return {"cell_type": "code", "id": cell_id, "metadata": {"tags": ["netguard-current"]},
            "source": text.splitlines(keepends=True), "outputs": [], "execution_count": None}


def corrected_cells():
    return [
        markdown("current-overview", """# NetGuard: reproducible project report

## Current corrected workflow

This is the main project report. The current sections below run from the two raw
UNSW-NB15 CSVs to a saved model, predictions, metrics and a provenance manifest.
They use ten measured fields supported by the application input form, with
deterministic domain features calculated **before** fitted scaling. No missing
measurement is reconstructed from benchmark neighbours.

Training/validation input signatures are kept together. Preprocessing is fitted
on the fit partition; model selection and a fixed threshold use validation only.
The existing test file is a **previously inspected benchmark**, not an untouched
holdout. These results do not establish future or unknown-attack performance.

Every original cell, saved output and execution count remains in the historical
sections below. Their displayed scores describe the earlier approach.

**Run the corrected workflow:** install `requirements-notebooks.txt` in CPython
3.13.9, then run `python scripts/run_notebook.py` from the repository root.
The runner executes only the current sections in a fresh kernel, preserving
historical cells exactly. In an interactive editor, execute the current code
cells in order and stop at **Historical reference**. Do not use the editor's
unfiltered Run All: historical cells can rerun old training and overwrite legacy
artifacts. No historical cell is silently rewritten or removed.

Outputs go to `artifacts/notebook_workflow/`; the existing dashboard artifacts
remain separate. See `notebooks/WORKFLOW.md` for setup and limitations.
"""),
        markdown("current-environment-heading", """### 1. Environment and reproducibility

Use the locked environment, fixed seed and a fresh kernel. Project paths resolve
from either the repository root or the notebooks directory.
"""),
        code("current-environment", """from pathlib import Path
from importlib.metadata import version
import os
import sys
import platform
import pandas as pd
from IPython.display import display

configured_root = os.environ.get("NETGUARD_PROJECT_ROOT")
ROOT = Path(configured_root).resolve() if configured_root else next(
    p for p in [Path.cwd(), *Path.cwd().parents]
    if (p / "netguard_workflow/workflow.py").is_file()
)
sys.path.insert(0, str(ROOT))
from netguard_workflow import (
    WorkflowConfig, RawTrafficFeatures, load_raw_data, split_development,
    fit_baselines, evaluate_benchmark, save_run, predict_raw,
)

expected_versions = {
    "numpy": "2.2.6", "pandas": "2.2.3", "scipy": "1.15.3",
    "scikit-learn": "1.6.1", "joblib": "1.4.2", "threadpoolctl": "3.6.0",
    "nbformat": "5.10.4", "nbclient": "0.10.2", "ipykernel": "6.29.5",
}
assert platform.python_version() == "3.13.9", "Use the documented CPython 3.13.9 environment."
for package, expected in expected_versions.items():
    assert version(package) == expected, f"Install the notebook lock: {package} differs."
config = WorkflowConfig()
OUTPUT = Path(os.environ.get("NETGUARD_OUTPUT_DIR", ROOT / "artifacts/notebook_workflow"))
print("Python", platform.python_version(), "| seed", config.seed)
display(pd.DataFrame(expected_versions.items(), columns=["package", "version"]))
"""),
        markdown("current-data-heading", """### 2. Raw data and input contract

Read original CSVs directly. Validate labels and require ten finite, nonnegative
measurements. Packet counts and TTL must be integers. IDs and attack categories
are retained as reporting metadata, never model predictors. Loading the benchmark
does not give it any role in fitting, selection or threshold choice.
"""),
        code("current-data", """development, benchmark = load_raw_data(ROOT)
display(pd.DataFrame([
    {"partition": "development CSV", "rows": len(development), "attack_fraction": development.label.mean()},
    {"partition": "previously inspected benchmark", "rows": len(benchmark), "attack_fraction": benchmark.label.mean()},
]))
display(development.head(3))
"""),
        markdown("current-split-heading", """### 3. Grouped development split

One deterministic fold from a five-fold stratified group splitter becomes
validation (approximately 20%; actual size is reported). Groups identify exact
matches across the ten measured predictors, excluding ID, label and category.
Conflicting-label signatures stay together. This reduces signature leakage;
it does not substitute for capture-time or host-based separation, which needs
additional provenance. No final test data is used to build this split.
"""),
        code("current-split", """import numpy as np
fit_idx, val_idx, signatures = split_development(development, config)
assert not np.intersect1d(signatures[fit_idx], signatures[val_idx]).size
display(pd.DataFrame([
    {"partition": name, "rows": len(idx), "attack_fraction": development.iloc[idx].label.mean(),
     "unique_input_signatures": len(np.unique(signatures[idx]))}
    for name, idx in [("fit", fit_idx), ("validation", val_idx)]
]))
"""),
        markdown("current-features-heading", """### 4. Features from physical measurements

Calculate byte/packet totals, bytes per packet, log1p features and TTL indicators
from raw values. Zero packet denominators return zero, with explicit zero-packet
indicators. The byte ratio is `(sbytes + 1)/(dbytes + 1)` and normalized byte
difference is `(sbytes - dbytes)/(sbytes + dbytes + 1)`. Low TTL means a measured
value between 1 and 9; it is a candidate feature, not a proven attack rule.
Float64 is used consistently. RobustScaler is fitted inside each model pipeline
on the fit partition only. Neither labels nor attack categories enter features.
"""),
        code("current-features", """feature_preview = RawTrafficFeatures().transform(development.iloc[:5])
assert (feature_preview[["bytes_total", "pkts_total"]] >= 0).all().all()
display(feature_preview)
print("Engineered predictor count:", feature_preview.shape[1])
"""),
        markdown("current-training-heading", """### 5. Baseline training and validation-only decisions

Compare a class-prior dummy with a supervised histogram gradient boosting
baseline. Settings are declared in `WorkflowConfig`, not optimized against the
benchmark. Early stopping is disabled to avoid an ungrouped internal split.
For each candidate, choose the threshold maximizing validation F1; equal F1
chooses the higher threshold. Select the candidate using validation F1, then
average precision. A deployment false-alarm budget is a future policy decision.
The selected pipeline remains fitted on the fit partition, so its threshold
matches its validation scores; it is not silently refitted on validation rows.
"""),
        code("current-training", """bundle, validation_comparison = fit_baselines(development, fit_idx, val_idx, config)
display(validation_comparison)
print("Frozen model:", bundle["model_name"], "| fixed threshold:", bundle["threshold"])
"""),
        markdown("current-evaluation-heading", """### 6. Previously inspected benchmark evaluation

Evaluate only after freezing model and threshold. Report false-positive rate,
precision, recall, F1, ROC-AUC and average precision (a PR summary). Show seen and
unseen development-input signatures and category-level recall with sample counts.
Slice metrics have different class mixtures and should not be compared as if
they were matched experiments. These are binary connection classifications,
not time forecasts; a new untouched/prospective holdout is still required.
"""),
        code("current-evaluation", """predictions, benchmark_metrics, slice_metrics, category_metrics = evaluate_benchmark(
    bundle, benchmark, development
)
display(pd.DataFrame([benchmark_metrics]))
display(slice_metrics)
display(category_metrics)
display(predictions.head(5))
"""),
        markdown("current-save-heading", """### 7. Persist artifacts and verify prediction parity

Save the complete fitted pipeline and fixed threshold, row-level predictions,
development membership, validation comparison, category/slice metrics and hashes.
Reload the artifact and verify that scores and decisions match both before/after
serialization and for individual versus batch inputs. The model needs the ten
raw measured fields; it does not need the benchmark table for inference.
"""),
        code("current-save", """manifest = save_run(
    ROOT, OUTPUT, bundle, development, fit_idx, val_idx, predictions,
    validation_comparison, benchmark_metrics, slice_metrics, category_metrics,
)
print("Saved outputs:", OUTPUT)
print("Parity checks:", manifest["checks"])
display(pd.DataFrame([
    {"file": name, "sha256": digest} for name, digest in manifest["output_sha256"].items()
]))
"""),
        markdown("current-predict-heading", """### 8. Raw input to a saved prediction

This example loads only the newly saved artifact and raw measurements. It
demonstrates inference independent of benchmark labels and historical models.
The dashboard integration remains a separate next step.
"""),
        code("current-predict", """import joblib
saved_bundle = joblib.load(OUTPUT / "model.joblib")
example_measurements = pd.DataFrame([{
    "sbytes": 258, "dbytes": 172, "spkts": 6, "dpkts": 4,
    "dur": 0.121478, "rate": 74.08749, "sload": 14158.94238,
    "dload": 8495.365234, "sttl": 252, "dttl": 254,
}])
display(predict_raw(saved_bundle, example_measurements))
print("Completed: raw CSVs -> validation-selected model -> saved predictions.")
"""),
        markdown("current-limitations", """### Interpretation and remaining work

This workflow repairs reproducibility and establishes a supervised baseline
with validation-only decisions. It does not certify the old ensemble, change
the live API, establish calibrated probabilities, or replace independent final
evaluation. Additional baselines, uncertainty estimates, unseen attack-family
tests, provenance-based splits, and validation of operational alert costs are
the next scientific improvements. `attack_score` is a classifier output, not a
guarantee of the probability of an attack in production traffic.

## Historical reference — preserved original cells

**Stop interactive execution here.** All sections below, including their saved
outputs, document the earlier workflow and alternate merge versions. Historical
scores were produced using the earlier preprocessing and evaluation policies.
The supported runner skips every historical code cell without modifying it.
"""),
    ]


def recover(text, side):
    output, state = [], None
    for line in text.splitlines(keepends=True):
        if line.startswith("<<<<<<<"):
            if state is not None:
                raise ValueError("Nested conflict")
            state = "head"
        elif line.startswith("=======") and state is not None:
            state = "incoming"
        elif line.startswith(">>>>>>>") and state is not None:
            state = None
        elif state is None or state == side:
            output.append(line)
    if state is not None:
        raise ValueError("Unclosed conflict")
    return json.loads("".join(output))


def main():
    path = ROOT/"notebooks/00_netguard_complete.ipynb"
    combined = json.loads(path.read_text(encoding="utf-8"))
    if "netguard_workflow" in combined["metadata"]:
        print("Already prepared; validating existing notebooks.")
        validate_all(ROOT)
        return
    provenance = combined["metadata"]["netguard_combination"]
    # Verify every original and both conflict reconstructions before any mutation.
    for item in provenance["source_files"]:
        raw = (ROOT/"notebooks"/item["file"]).read_bytes()
        assert sha256(raw).hexdigest() == item["original_file_sha256"], item["file"]
        for side in ("head", "incoming"):
            recovered = recover(raw.decode("utf-8"), side)
            for source_index, combined_index in item["source_cell_to_combined_cell"][side].items():
                original_cell = recovered["cells"][int(source_index)]
                archived_cell = combined["cells"][combined_index]
                assert cell_digest(original_cell) == cell_digest(archived_cell)
    repairs = []
    for item in provenance["source_files"]:
        origins = [o for o in provenance["cell_origins"] if o["source_file"] == item["file"]]
        main_indices = sorted({o["combined_cell_index"] for o in origins if o["location"] == "main"})
        alt_indices = sorted({o["combined_cell_index"] for o in origins if o["location"] == "appendix"})
        restored_cells = [markdown(f"history-{item['file'][:2]}-notice", f"""# Historical notebook: {item['file']}

Merge conflicts have been resolved without discarding either recoverable version.
Every original cell's content, outputs, execution count and metadata is preserved.
Identical cells shared by both versions are stored once; differing alternate cells
appear in the reference appendix. The original version order is recoverable from
the notebook's provenance mappings.

**Historical results:** this notebook retains the original modelling and evaluation
policies and is a reference archive. Use `00_netguard_complete.ipynb` and
`python scripts/run_notebook.py` for the current reproducible workflow. Executing
historical code can rerun old training and overwrite legacy artifacts.
""")]
        old_to_new = {}
        for i in main_indices:
            old_to_new[i] = len(restored_cells)
            restored_cells.append(deepcopy(combined["cells"][i]))
        restored_cells.append(markdown(f"history-{item['file'][:2]}-alternatives", """## Alternate merge content — historical reference

These differing cells retain alternate saved outputs, code and execution state.
They are preserved for review and are not additional current workflow steps.
"""))
        for i in alt_indices:
            old_to_new[i] = len(restored_cells)
            restored_cells.append(deepcopy(combined["cells"][i]))
        new_origins = deepcopy(origins)
        for origin in new_origins:
            origin["combined_cell_index"] = old_to_new[origin["combined_cell_index"]]
        mapping = {side: {k: old_to_new[v] for k, v in rows.items()}
                   for side, rows in item["source_cell_to_combined_cell"].items()}
        metadata = deepcopy(item["original_metadata"]["head"])
        metadata["netguard_history"] = {
            "schema_version": 1, "original_file_sha256": item["original_file_sha256"],
            "resolved_conflict_blocks": item["merge_conflict_blocks"],
            "original_metadata": item["original_metadata"],
            "original_notebook_format": item["original_notebook_format"],
            "source_cell_to_combined_cell": mapping, "cell_origins": new_origins,
        }
        restored = {"cells": restored_cells, "metadata": metadata, "nbformat": 4, "nbformat_minor": 5}
        nbformat.validate(nbformat.from_dict(deepcopy(restored)))
        destination = ROOT/"notebooks"/item["file"]
        destination.write_text(json.dumps(restored, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        item["repaired_file_sha256"] = sha256(destination.read_bytes()).hexdigest()
        repairs.append({"file": item["file"], "conflicts_resolved": item["merge_conflict_blocks"],
                        "main_preserved_cells": len(main_indices), "alternate_preserved_cells": len(alt_indices),
                        "head_cells_covered": len(mapping["head"]), "incoming_cells_covered": len(mapping["incoming"]),
                        "all_cell_payloads_preserved": True})
    added = corrected_cells()
    shift = len(added)
    # Only generated navigation/summary cells are updated. Original cells stay exact.
    combined["cells"][0]["source"] = ["## Historical seven-stage overview\n\n",
        "The cells below preserve all seven original stages and alternate merge versions.\n",
        "Their saved results are historical; use the corrected workflow above for reproduction.\n"]
    for cell in combined["cells"]:
        if cell["id"].startswith("stage-"):
            cell["source"] = ["**Historical section: saved results from the earlier workflow.**\n\n"] + cell["source"]
    combined["cells"] = added + combined["cells"]
    for origin in provenance["cell_origins"]:
        origin["combined_cell_index"] += shift
    for item in provenance["source_files"]:
        for mapping in item["source_cell_to_combined_cell"].values():
            for k in mapping:
                mapping[k] += shift
    provenance["preservation_policy"] = (
        "All original source cells and differing alternate payloads remain unchanged, including outputs, "
        "execution counts and cell metadata. Only unique IDs were added. The seven source notebooks "
        "are now valid historical archives. Current executable sections are separately identified."
    )
    combined["metadata"]["netguard_workflow"] = {
        "schema_version": 1, "python": "3.13.9", "requirements": "requirements-notebooks.txt",
        "runner": "scripts/run_notebook.py",
        "executable_cell_ids": [c["id"] for c in added if c["cell_type"] == "code"],
        "historical_execution_policy": "preserve unchanged; skipped by supported runner",
    }
    combined["nbformat_minor"] = 5
    nbformat.validate(nbformat.from_dict(deepcopy(combined)))
    path.write_text(json.dumps(combined, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    results = validate_all(ROOT)
    evidence = {"status": "passed", "conflicts_resolved": sum(r["conflicts_resolved"] for r in repairs),
                "current_code_cells": sum(c["cell_type"] == "code" for c in added),
                "combined_original_payloads_preserved": len(provenance["cell_origins"]), "repaired_notebooks": repairs,
                "schema_and_preservation_checks": results}
    (ROOT/"data/reports/notebook_repair_evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
