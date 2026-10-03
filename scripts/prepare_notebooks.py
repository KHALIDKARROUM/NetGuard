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
on the fit partition; model selection and a fixed threshold use validation only,
maximizing attack recall under a 1% empirical validation false-positive budget.
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

Outputs go to `artifacts/notebook_workflow/`; the same complete prediction
artifact is published to `models_saved/` for the API. See `notebooks/WORKFLOW.md`.
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
    feature_catalog, feature_quality_report,
    PredictionService,
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

Calculate all domain features from original measurements before fitting any
scaler. `bytes_total = sbytes + dbytes` is bytes and `pkts_total = spkts + dpkts`
is a nonnegative integer packet count. Bytes per packet use the actual packet
count, without adding a packet to the denominator.

The exact byte ratio is `sbytes / dbytes`; zero denominators use a zero sentinel
and an explicit flag. Keep the separately named one-byte-smoothed ratio
`(sbytes + 1)/(dbytes + 1)`. Signed byte balance is
`(sbytes - dbytes)/(sbytes + dbytes)`, with a zero-total flag when undefined.
An undefined-ratio sentinel must not be interpreted as an observed zero ratio.

Log features use `ln(1 + raw value / one reference unit)`, so raw zero maps to
zero. Negative/nonfinite measurements are rejected instead of clipped. Byte
and packet counts are integral; TTL values are integers from 0 through 255.
Low TTL means a recorded value from 1 through 9; it does not prove an attack.

The dictionary below defines every unscaled feature, formula, unit and zero
policy. Full-dataset checks verify both raw CSVs. StandardScaler is fitted on fit
rows only, **after** domain features exist. Scaled values are dimensionless
model inputs and must not be described as physical byte or packet counts.
See `notebooks/FEATURES.md`. Feature schema 2 requires retraining older models.
"""),
        code("current-features", """feature_preview = RawTrafficFeatures().transform(development.iloc[:5])
physical_checks = {
    "development": feature_quality_report(development),
    "previously inspected benchmark": feature_quality_report(benchmark),
}
display(pd.DataFrame(feature_catalog()))
display(feature_preview)
display(pd.DataFrame([
    {"partition": name, "rows_checked": result["rows"], "all_checks_passed": all(result["checks"].values()),
     "zero_destination_packet_rows": result["zero_denominator_rows"]["destination_packets"],
     "zero_destination_byte_rows": result["zero_denominator_rows"]["destination_bytes"]}
    for name, result in physical_checks.items()
]))
print("Engineered predictor count:", feature_preview.shape[1])
"""),
        markdown("current-training-heading", """### 5. Baseline training and validation-only decisions

Compare a class-prior dummy, logistic regression, random forest, histogram
gradient boosting, and one fixed equal-weight soft vote of the three supervised
models. Every candidate uses exactly the same grouped split, 29 physical
features, and the **same fit-only StandardScaler**. Standardization replaces
the earlier robust scaling because it lets logistic regression converge reliably.
Settings are declared in `WorkflowConfig`, not optimized against the benchmark:
logistic regression uses C=1 and up to 2,000 iterations; the forest uses 200
trees, depth 20, and minimum leaf size 2; boosting uses 150 iterations and L2=1.
Early stopping is disabled to avoid an ungrouped internal split. Forest trees
are fitted with two workers and scored in a fixed single-worker order.
For each candidate, maximize attack recall subject to a maximum **1% empirical
validation false-positive rate**. All equal scores move together; do not
interpolate an unattainable operating point. Equal recall prefers fewer false
positives, then the higher threshold. Rank eligible individual models by recall,
lower false-positive rate, average precision, then name. This budget is declared
before benchmark evaluation and is not a guarantee on future traffic.

The three-model soft vote is retained only if its validation recall exceeds the
best individual by at least **2 percentage points**, and its complete median
256-row prediction latency is no more than **2x** that individual's. These
complexity rules are declared before evaluation. Nonconverged fits are ineligible.

Report accuracy, balanced accuracy, precision, recall, F1, ROC-AUC, average
precision, false-positive rate/counts, and complete prediction latency. Timing
covers raw feature creation, fitted scaling, scoring, the fixed decision and
result creation through `predict_raw`, including contract/thread checks. It uses
loaded models, one single and batch warmup, and 11 repeated calls; report median
and descriptive p95 for singles and 256-row batches. Artifact loading and
HTTP/network transport are excluded. Timings depend on this machine.

Save score calibration as **identity / no learned calibration**, with no fitted
reference distribution or parameters. Scores are uncalibrated classifier outputs.
The artifact includes this setting, the fixed threshold, target budget, validation
class counts, observed false positives, and attack recall. Actual benchmark
results are reported without moving the threshold to satisfy its labels.
The selected pipeline remains fitted on the fit partition, so its threshold
matches its validation scores; it is not silently refitted on validation rows.
See [scikit-learn threshold guidance](https://scikit-learn.org/stable/modules/classification_threshold.html)
for why threshold selection uses separate validation data.
"""),
        code("current-training", """bundle, validation_comparison = fit_baselines(development, fit_idx, val_idx, config)
display(validation_comparison[["model", "selected", "accuracy", "balanced_accuracy", "precision", "recall",
    "f1", "roc_auc", "average_precision", "false_positive_rate", "fp", "fn"]])
display(validation_comparison[["model", "single_latency_median_ms", "single_latency_p95_ms",
    "batch_latency_median_ms", "batch_latency_p95_ms", "batch_rows", "artifact_bytes",
    "fit_seconds", "converged", "optimization_iterations"]])
print("Ensemble decision:", bundle["ensemble_decision"])
print("Frozen model:", bundle["model_name"], "| fixed threshold:", bundle["threshold"])
print("Maximum validation false-positive rate:", config.max_false_positive_rate)
print("Saved score calibration:", bundle["score_calibration"])
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
display(pd.DataFrame(bundle["benchmark_comparison"]))
validation_point = bundle["threshold_selection"]["validation_metrics"]
display(pd.DataFrame([
    {"partition": name, "target_fpr": config.max_false_positive_rate,
     "observed_fpr": values["false_positive_rate"], "attack_recall": values["recall"],
     "false_positives": values["fp"], "normal_rows": values["tn"] + values["fp"],
     "within_budget": values["false_positive_rate"] <= config.max_false_positive_rate}
    for name, values in [("validation: threshold selection", validation_point),
                         ("previously inspected benchmark: frozen threshold", benchmark_metrics)]
]))
display(slice_metrics)
display(category_metrics)
display(predictions.head(5))
"""),
        markdown("current-save-heading", """### 7. Persist artifacts and verify prediction parity

Save the complete fitted pipeline, fixed threshold and score calibration settings, row-level predictions,
development membership, validation comparison, category/slice metrics and hashes.
Reload the artifact and verify that scores and decisions match both before/after
serialization and for individual versus batch inputs. The model needs the ten
raw measured fields; it does not need the benchmark table for inference.
Publish the same bundle to `models_saved/shared_pipeline.joblib` with a hash and
runtime manifest. Both the notebook and API load this artifact through the same
`PredictionService`; the API does not fit, normalize or select a threshold.
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

This example loads the same saved artifact as the backend. Compare its raw-input
scores and decisions with real API request handling for a single connection and
a batch. The HTTP adapter retains float64 scores without rounding. Artifact
loading verifies feature schema/order, feature implementation and numerical
package versions before serving.
"""),
        code("current-predict", """from fastapi.testclient import TestClient
from backend.main import create_app
saved_service = PredictionService(ROOT / "models_saved/shared_pipeline.joblib")
example_measurements = pd.DataFrame([{
    "sbytes": 258, "dbytes": 172, "spkts": 6, "dpkts": 4,
    "dur": 0.121478, "rate": 74.08749, "sload": 14158.94238,
    "dload": 8495.365234, "sttl": 252, "dttl": 254,
}])
expected_example = saved_service.predict(example_measurements)
display(expected_example)
parity_examples = pd.concat([
    example_measurements,
    development.loc[:, saved_service.bundle["raw_inputs"]].iloc[:32],
], ignore_index=True)
expected_parity = saved_service.predict(parity_examples)
api_app = create_app(artifact_path=ROOT / "models_saved/shared_pipeline.joblib", enable_logging=False)
with TestClient(api_app) as client:
    batch_response = client.post("/api/predict/batch", json={"connections": parity_examples.to_dict(orient="records")})
    assert batch_response.status_code == 200, batch_response.text
    batch_results = batch_response.json()["predictions"]
    np.testing.assert_allclose([r["score"] for r in batch_results], expected_parity.attack_score, rtol=0, atol=1e-12)
    np.testing.assert_array_equal([r["prediction"]["label"] for r in batch_results], expected_parity.predicted_label)
    for i, raw_row in enumerate(parity_examples.to_dict(orient="records")):
        response = client.post("/api/predict/single", json=raw_row)
        assert response.status_code == 200, response.text
        result = response.json()
        assert abs(result["score"] - expected_parity.attack_score.iloc[i]) <= 1e-12
        assert result["prediction"]["label"] == int(expected_parity.predicted_label.iloc[i])
print("Notebook/API parity passed for", len(parity_examples), "raw connections, alone and in a batch.")
print("Completed: raw CSVs -> validation-selected model -> saved predictions.")
"""),
        markdown("current-limitations", """### Interpretation and remaining work

This workflow establishes a supervised baseline with validation-only decisions
under a declared 1% empirical validation false-positive budget. The benchmark
false-positive rate may differ; no benchmark-dependent retuning is performed.
The API now uses its selected saved pipeline and threshold. This does not establish
calibrated probabilities or replace independent final evaluation. Isolation
Forest and novelty LOF remain separate unfamiliar-attack experiments; see
`notebooks/SUPERVISED_COMPARISON.md` for the leave-one-family-out protocol.
Uncertainty estimates, additional families, provenance-based splits, and validation of operational alert costs are
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
    combined["metadata"]["language_info"]["version"] = "3.13.9"
    combined["metadata"]["kernelspec"] = {
        "display_name": "NetGuard workflow (Python 3.13.9)",
        "language": "python", "name": "python3",
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
