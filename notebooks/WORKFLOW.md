# Reproduce the NetGuard notebook report

`00_netguard_complete.ipynb` is the main report. Its first eight code cells are
the current workflow. The seven original stages and alternate merge content
follow as a historical archive, with every original cell payload preserved.
The seven standalone notebooks are also valid historical archives.

## Fresh environment

Use **CPython 3.13.9**. Notebook and backend locks share the numerical versions
in `requirements-model.in`. The notebook environment also includes the backend
HTTP adapter so its final cell verifies API parity. Historical model files
created with earlier library versions are not loaded by the current workflow.
The `.in` file lists direct dependencies; the `.txt` lock pins transitive
dependencies with package hashes and operating-system markers.

From the repository root on Windows PowerShell, using uv:

```powershell
uv venv .venv-workflow --python 3.13.9
uv pip sync requirements-notebooks.txt --python .venv-workflow/Scripts/python.exe --require-hashes
.venv-workflow/Scripts/python.exe scripts/run_notebook.py
```

With an installed Python 3.13.9 and pip instead:

```powershell
py -3.13 -m venv .venv-workflow
.venv-workflow/Scripts/python.exe -m pip install --require-hashes -r requirements-notebooks.txt
.venv-workflow/Scripts/python.exe scripts/run_notebook.py
```

On Linux/macOS with Python 3.13.9:

```bash
python3.13 -m venv .venv-workflow
.venv-workflow/bin/python -m pip install --require-hashes -r requirements-notebooks.txt
.venv-workflow/bin/python scripts/run_notebook.py
```

The notebook checks the Python and core package versions before training.
Both original CSVs must exist under `data/` with their committed filenames.
No preprocessed CSV, historical model or saved visualization is required.

The runner starts a fresh kernel with the same interpreter that invokes it;
no globally registered Jupyter kernel is needed. It validates all eight
notebooks, runs only the explicitly identified current code cells, and retains
every historical cell unchanged. It saves an executed report and updates only
the current outputs in the main notebook.

For interactive work, select the matching environment, run the current code
cells in order, and stop at **Historical reference**. Do not use an editor's
unfiltered Run All: archived code retains its original behaviour and may write
legacy artifacts. Skipping history is enforced by the documented runner,
not by standard Jupyter itself.

## Workflow and outputs

1. Validate raw measurements, row IDs and binary labels.
2. Split the development CSV into fit and validation partitions. Exact
   signatures across the ten measured inputs remain in a single partition,
   including signatures associated with conflicting labels.
3. Calculate physical features from raw values and fit StandardScaler only on
   fit rows. Every transformation uses float64 and fixed feature order.
   [The feature dictionary](FEATURES.md) documents all formulas, units and
   zero-denominator policies. Schema 2 includes exact and explicitly smoothed
   ratios; older workflow artifacts must be retrained.
4. Fit a dummy prior, logistic regression, random forest and histogram gradient
   boosting with identical preprocessing and split membership. Compare a fixed
   equal-weight soft vote of the three supervised models. Choose model
   and a fixed decision threshold by maximizing validation attack recall under
   a 1% empirical false-positive budget. Equal recall prefers fewer false
   positives, then a higher threshold. Candidate selection uses constrained
   recall, lower false-positive rate, average precision, then name. All score
   ties move together; the target is not an interpolated ROC point. Do not
   refit after selection. Retain the soft vote only if it gains at least two
   percentage points of validation recall with no more than twice the best
   individual's median 256-row prediction latency. Record convergence and
   exclude nonconverged candidates from selection.
5. Evaluate the previously inspected benchmark, including category and
   seen/unseen input-signature slices.
6. Save the fitted pipeline and threshold, verify artifact reload and
   individual/batch parity, and demonstrate raw-input inference through both
   Python and the API adapter. Publish the same artifact and compatibility
   manifest under `models_saved/` for the backend.

Generated outputs under `artifacts/notebook_workflow/` are ignored by Git:

| Output | Purpose |
| --- | --- |
| `model.joblib` | Complete fitted pipeline, threshold and input contract |
| `model.manifest.json` | Artifact hash, precise runtime versions and feature contract |
| `benchmark_predictions.csv` | Score, decision, true label, category and overlap flag for every benchmark row |
| `development_split.csv` | Row IDs and exact fit/validation membership |
| `validation_comparison.csv` | Validation metrics and threshold for each candidate |
| `benchmark_comparison.csv` | All candidates evaluated after freezing selection and thresholds |
| `candidates/*.joblib` | Regenerable complete fitted candidate pipelines and manifests |
| `metrics.json` | Selected model and aggregate metrics |
| `benchmark_slices.csv` | Seen/unseen development-input signature metrics |
| `attack_category_metrics.csv` | Per-category recall and sample counts |
| `manifest.json` | Input/output/source hashes, versions, configuration and parity checks |
| `feature_catalog.json` | Every unscaled feature's meaning, unit, formula and zero policy |
| `feature_quality_report.json` | Physical invariant checks across both complete raw CSVs |
| `execution_check.json` | Notebook validation and execution completion evidence |
| `00_netguard_complete.executed.ipynb` | Executed current report plus unchanged historical cells |

To use the artifact in a separate Python process, run from the repository root
in this environment:

```python
import pandas as pd
from netguard_workflow import PredictionService

service = PredictionService("models_saved/shared_pipeline.joblib")
measurements = pd.read_csv("your_raw_connections.csv")
service.predict(measurements).to_csv("predictions.csv", index=False)
```

Required measured columns are `sbytes`, `dbytes`, `spkts`, `dpkts`, `dur`, `rate`,
`sload`, `dload`, `sttl`, `dttl`. Labels and attack categories are not required.
Load only trusted model artifacts. Keep the package available so custom fitted
transformers can be deserialized.

The artifact and its manifest save `score_calibration` as `identity`, with
empty parameters and no fitting partition: no probability calibration or
reference-data score normalization is applied. They also save
`threshold_selection`, including the configured false-positive budget,
validation class counts, achieved false-positive rate and attack recall.
Change `WorkflowConfig(max_false_positive_rate=...)` before training to declare
a different budget; never adjust it to improve benchmark results.

## Verification and interpretation

```powershell
.venv-workflow/Scripts/python.exe scripts/notebook_integrity.py
.venv-workflow/Scripts/python.exe -m unittest discover -s tests -v
.venv-api/Scripts/python.exe scripts/verify_prediction_parity.py --live
.venv-api/Scripts/python.exe scripts/verify_prediction_without_data.py
```

Integrity checks validate notebook schemas, unique IDs, absence of conflict
markers and the original fingerprints of every preserved historical cell.
Original HEAD/incoming index mappings remain in notebook metadata.
`data/reports/notebook_repair_evidence.json` documents the conflict recovery.
`data/reports/notebook_workflow_verification.json` records the latest successful
run, configuration, dataset/artifact hashes and benchmark metrics.
The dated project audit remains a record of the state before this repair.

The existing test set was previously used for development and must not be
presented as an untouched final holdout. This workflow does not demonstrate
future traffic or unseen attack-family performance, calibrated probabilities,
or prospective deployment accuracy. It establishes a reproducible binary-classification
baseline. Grouping by input signature reduces one leakage route but is not
capture-time or host isolation. Those require additional provenance.

The backend now serves this pipeline and its fixed threshold. Its dashboard
metrics use the same raw benchmark inputs and full inference path. See
[the prediction guide](../backend/PREDICTION.md) for backend setup and the exact
HTTP contract. `data/reports/shared_prediction_parity.json` records verification
against a separate live API process in a fresh backend-only environment.
`data/reports/prediction_without_data.json` records cold startup and live
prediction in an isolated copy with no data directory and dataset reads blocked.
The 1% budget is an empirical validation constraint, not a promise about other
traffic. Benchmark results are measured at the frozen threshold and may exceed
the target. Broader model tuning, checking the budget against real
alert costs, uncertainty estimates and independent final testing remain work.

See [the supervised comparison guide](SUPERVISED_COMPARISON.md) for the full
tables, timing protocol and declared ensemble complexity rules. Compact results
are committed under `data/reports/supervised_*`. The separate anomaly experiment
reads only development data, removes one whole attack family and its matching
signatures from fitting/calibration, and fits Isolation Forest and novelty LOF
on normal traffic. It does not alter the supervised winner or API artifact.
