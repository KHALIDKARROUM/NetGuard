# Shared notebook and API prediction

`netguard_workflow/inference.py` provides `PredictionService` to both callers.
The complete fitted artifact is `models_saved/shared_pipeline.joblib` with its
`shared_pipeline.manifest.json` sidecar. The corrected combined notebook
recreates both files; it also saves an identical copy in its output directory.

## Contract

The saved pipeline creates 29 physical features from the original measurements,
orders them explicitly, applies the training-fitted RobustScaler, and scores the
validation-selected histogram gradient boosting model. All transformations and
scores use float64. Decisions are `score >= saved_threshold`; responses retain
the full numerical score. See [the feature dictionary](../notebooks/FEATURES.md).

The fixed threshold maximizes attack recall with **validation false-positive
rate at most 1%**. The model is fitted on separate grouped development rows.
Score ties are indivisible; the selector considers real attainable thresholds,
including a finite reject-all threshold if necessary. Equal recall prefers
fewer false positives, then a higher threshold. The model comparison uses
constrained validation recall, lower false-positive rate, average precision,
then name. No benchmark labels select the threshold or deployed model.

Artifact schema 2 requires explicit `score_calibration` settings: `method` is
`identity`, `parameters` is empty, and `fitted_on` is null. Scores remain
uncalibrated classifier outputs; no learned calibration or reference score
distribution is needed at inference. `threshold_selection` stores the budget,
validation normal/attack counts, observed false positives and recall. Both
settings are also exposed by `GET /api/predict/info` and checked against the
artifact's manifest.

Every connection requires these ten measured fields:

| Fields | Accepted measurements |
| --- | --- |
| `sbytes`, `dbytes`, `spkts`, `dpkts` | Nonnegative integer byte/packet counts |
| `dur`, `rate`, `sload`, `dload` | Finite nonnegative recorded values |
| `sttl`, `dttl` | Integer TTL values from 0 through 255 |

Counts and their byte/packet totals must be at most `2**53-1` for exact float64
representation. Missing, invalid or unknown fields return HTTP 422. JSON object
field order and batch row composition do not affect scores. All required values
must be supplied; UI presets are editable examples, not inferred measurements.

`POST /api/predict/single` accepts a connection object:

```json
{"sbytes":258,"dbytes":172,"spkts":6,"dpkts":4,"dur":0.121478,"rate":74.08749,"sload":14158.94238,"dload":8495.365234,"sttl":252,"dttl":254}
```

`POST /api/predict/batch` accepts `{"connections": [connection, ...]}` with
1–1,000 connections and returns predictions in the same order. Both endpoints
return the model name, score, fixed threshold, decision, precision and artifact
SHA-256. Neither prediction endpoint reads training or benchmark CSVs, fits
preprocessing, infers hidden fields from neighbors, or recalibrates scores.

`GET /api/models/compare` and visualizations evaluate the deployed pipeline on
raw benchmark measurements with the saved threshold. Earlier experiment metrics
are a separate `historical_metrics` field and do not select the deployed model.
PCA is descriptive; its labels come from the same saved classification decisions.

## Runtime and artifacts

Use CPython **3.13.9**. `backend/requirements.txt` is a complete hashed lock,
with the same numerical versions as `requirements-notebooks.txt`:
NumPy 2.2.6, pandas 2.2.3, SciPy 1.15.3, scikit-learn 1.6.1,
joblib 1.4.2 and threadpoolctl 3.6.0. Both direct dependency files include
`requirements-model.in`; regenerate both locks together when changing it.

From the repository root in PowerShell:

```powershell
uv venv .venv-api --python 3.13.9
uv pip sync backend/requirements.txt --python .venv-api/Scripts/python.exe --require-hashes
.venv-api/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 5000
```

On Linux/macOS use the corresponding `.venv-api/bin/python` path. Docker uses
the root build context and Python 3.13.9. Prediction needs only the shared code
and artifact; dataset exploration and evaluation additionally need the raw CSVs.

Artifact loading checks its hash and numerical runtime before deserialization,
then validates feature implementation, schema/order, fitted preprocessing,
classes and threshold. Missing or incompatible artifacts return HTTP 503 from
prediction and health. Historical models are not used as a fallback. Use only
trusted project artifacts: a hash check detects accidental mismatch, not a
malicious replacement of both model and manifest.

Each API worker caches its loaded artifact. **Restart every API worker after
retraining or replacing the artifact and manifest together.** `PREDICTION_ARTIFACT`
can point to another compatible trusted bundle; `NETGUARD_LOG_DIR` changes the
log destination.

## Reproduce verification

First run the [corrected notebook workflow](../notebooks/WORKFLOW.md), then:

```powershell
.venv-workflow/Scripts/python.exe -m unittest discover -s tests -v
.venv-api/Scripts/python.exe scripts/verify_prediction_parity.py --live
.venv-api/Scripts/python.exe scripts/verify_prediction_without_data.py
```

The verifier starts and stops a local API process, checks 512 reproducibly
sampled benchmark connections against the notebook's saved predictions, and
adds six boundary cases including zero denominators, TTL edges and counts above
float32's exact-integer range. It compares individual requests, batch sizes
1/7/64/1,000, reordered fields and reordered rows at absolute tolerance `1e-12`,
then checks dashboard metrics and routes. Evidence is saved to
`data/reports/shared_prediction_parity.json`. The final notebook cell separately
checks 33 connections using the actual FastAPI request adapter.

The no-data verifier copies only source files and the model/manifest into an
isolated directory, installs a file-access guard before importing the backend,
and starts a fresh live API process. The guard blocks CSV opens and any opens
under the original data directory. Synthetic single and batch predictions must
match the shared service, while dataset exploration returns 404. Evidence is
saved to `data/reports/prediction_without_data.json`. This check needs no raw
dataset and does not measure predictive accuracy.

This follows scikit-learn's guidance on [consistent preprocessing and pipelines](https://scikit-learn.org/stable/common_pitfalls.html)
and [matching training/serving versions for persisted models](https://scikit-learn.org/stable/model_persistence.html).
The numerical mismatch in the earlier serving path is addressed by retraining
and using this complete pipeline, rather than reusing older fitted artifacts.

## Interpretation

The 1% target applies to the validation partition used for threshold selection.
Benchmark and future traffic can have different false-positive rates and recall.
The current threshold is **0.9458945040124691**. Validation observes 42 false
positives among 13,248 normal rows (**0.317%**) and detects 12,846 of 17,506
attacks (**73.38% recall**). The frozen benchmark result is 248 false positives
among 37,000 normal rows (**0.670%**) and 37,811 detections among 45,332 attacks
(**83.41% recall**, F1 **0.9068**). The threshold favors the fewest false positives
among operating points with the same maximum feasible recall; it need not use
the full 1% budget.
The notebook reports both validation and frozen-threshold benchmark results;
`data/reports/notebook_workflow_verification.json` contains the measured counts.
The benchmark was already inspected and is not an independent final holdout.
Classifier scores are not calibrated production attack probabilities. Checking
alert costs, calibration on separate development data, and prospective evaluation
remain necessary scientific work.
