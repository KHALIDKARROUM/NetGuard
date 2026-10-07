# Application prediction contract

The app serves the exact frozen XGBoost, LightGBM and TabM neural network
exports from the [self-contained notebook](../notebooks/00_netguard_complete.ipynb).
XGBoost is the validation-selected default. Choose a model in the prediction
lab, or add `?model=xgboost`, `?model=lightgbm`, or `?model=tabm` to either
prediction endpoint. `GET /api/predict/best_model` returns the default and
`available_models`, including each model's threshold and recorded metrics.

## Frozen models and measured inputs

Each export includes physical feature creation, fitted preprocessing, the
trained classifier and its validation threshold. All three create the same
29 features from ten measured inputs. The boosted trees use the notebook's
fitted StandardScaler. TabM applies its fitted sign-preserving log transform,
normal-quantile transform and standardization inside the estimator; its 16
members' probabilities are averaged. TabM trained with float32 CPU tensors
and its saved network scores in float64, as verified in the notebook.

| Model | Saved threshold | Benchmark attack recall | Benchmark false-positive rate |
| --- | ---: | ---: | ---: |
| XGBoost (default) | 0.9051103591918945 | 87.269% | 2.895% |
| LightGBM | 0.9578912437183693 | 84.040% | 1.241% |
| TabM | 0.9044449631483704 | 81.117% | 0.711% |

Decisions use `attack_score >= saved_threshold`; responses retain full
precision. Each threshold maximizes attack recall within a validation
false-positive budget of 1%. Benchmark data does not select the default or
thresholds. The benchmark was previously inspected and is not an untouched
final holdout. Scores are uncalibrated classifier outputs, not production
attack probabilities. No ensemble passed the notebook's recall gain and
latency requirements, so the default remains the individual XGBoost.

| Required fields | Accepted measurements |
| --- | --- |
| `sbytes`, `dbytes`, `spkts`, `dpkts` | Nonnegative integer byte/packet counts |
| `dur`, `rate`, `sload`, `dload` | Finite nonnegative recorded values |
| `sttl`, `dttl` | Integer TTL values from 0 through 255 |

Counts and their byte/packet totals must be at most `2**53-1` for exact
float64 representation. Missing, invalid or unknown fields return HTTP 422.
Unknown model identifiers return HTTP 422 and never become file paths.
Object field order and batch composition do not affect prediction decisions.
UI presets are editable examples, not inferred measurements.

`POST /api/predict/single?model=tabm` accepts a connection object:

```json
{"sbytes":258,"dbytes":172,"spkts":6,"dpkts":4,"dur":0.121478,"rate":74.08749,"sload":14158.94238,"dload":8495.365234,"sttl":252,"dttl":254}
```

`POST /api/predict/batch?model=lightgbm` accepts
`{"connections": [connection, ...]}` with 1-1,000 connections. Both endpoints
return the model, score, fixed threshold, decision, precision and artifact
SHA-256. Prediction reads no CSVs and fits no preprocessing or model.

`GET /api/models/compare` evaluates all three deployed pipelines on raw
benchmark measurements with their frozen thresholds. ROC, confusion and
score-distribution views include all three. PCA defaults to XGBoost;
its `model` parameter can select another deployed pipeline. PCA is descriptive.
Saved validation and benchmark comparison tables include other notebook
candidates; those candidates are not all deployed.

## Artifacts and runtime

`netguard_workflow/deployment.py` loads `models_saved/deployed/registry.json`,
whose explicit allowlist pins each manifest hash. Each `.manifest.json`
pins its model bytes, runtime, source provenance, raw input/feature order,
precision, score calibration and threshold-selection contract. Loading
checks these declarations and hashes before deserialization, then validates
the full fitted pipeline, label order and dimensions. All registered models
must load successfully for the app to be ready. Missing or incompatible
artifacts return HTTP 503; no historical artifact is used as a fallback.
Only load trusted project exports: replacing both model and its trusted
registry can replace executable pickle content.

Use CPython **3.13.9** and the hashed `backend/requirements.txt`. Its model
packages match notebook training: NumPy 2.2.6, pandas 2.2.3, SciPy 1.15.3,
scikit-learn 1.6.1, XGBoost 3.0.5, LightGBM 4.7.0, Torch 2.8.0, TabM 0.0.3,
and the remaining dependencies declared in `requirements-serving.in`.
The exports include notebook classes by value; serving needs no notebook.
Docker includes the three exports and the OpenMP runtime for the boosting
libraries. Docker image execution must be checked on the target host;
current local verification uses Windows processes because no Docker daemon
is running here. The Linux lock includes Torch's standard PyPI dependencies
although the models perform inference on CPU.

Run from the repository root:

```powershell
uv venv .venv-api --python 3.13.9
uv pip sync backend/requirements.txt --python .venv-api/Scripts/python.exe --require-hashes
.venv-api/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 5000 --no-proxy-headers
```

Use `.venv-api/bin/python` on Linux/macOS. Each worker caches its pipelines.
After running the notebook again, promote the verified full-data exports
and **restart every API worker**:

```powershell
.venv-workflow/Scripts/python.exe scripts/export_deployment_models.py
```

The exporter checks source export hashes, the full 82,332-row benchmark
decisions, default-model golden scores and single/batch parity before
publishing. It copies each notebook export byte-for-byte. Fast preview runs
cannot be promoted. `PREDICTION_ARTIFACT` can override the default with a
trusted compatible artifact; custom artifacts outside the registry directory
run as standalone services. `NETGUARD_LOG_DIR` sets the log folder.

`models_saved/shared_pipeline.joblib` remains the historical soft-vote
artifact. Its loader and original parity verifier remain available for
reproducing that older result; they are not the app's default.

## Verify serving

```powershell
.venv-api/Scripts/python.exe -m unittest discover -s tests -v
.venv-api/Scripts/python.exe scripts/verify_deployed_models.py
.venv-api/Scripts/python.exe scripts/verify_prediction_without_data.py --artifact models_saved/deployed/xgboost.pkl --report data/reports/deployed_xgboost_without_data.json
.venv-api/Scripts/python.exe scripts/verify_prediction_without_data.py --artifact models_saved/deployed/lightgbm.pkl --report data/reports/deployed_lightgbm_without_data.json
.venv-api/Scripts/python.exe scripts/verify_prediction_without_data.py --artifact models_saved/deployed/tabm.pkl --report data/reports/deployed_tabm_without_data.json
```

The deployment verifier starts a separate live HTTP server, compares all
three models with their original notebook exports on 256 sampled benchmark
connections and seven synthetic boundary inputs, exercises single requests,
7/64/1,000-row batches, field/row permutations and a maximum-size batch, and
checks all dashboard metrics and visualization routes. Evidence is saved
in `data/reports/deployed_models_verification.json`.

The no-data verifier copies only source and one model/manifest into an
isolated checkout. A guard installed before API import rejects every CSV
open and every open under the original data directory. A cold live server
must reproduce 22 synthetic single/batch decisions while the dataset page
returns 404. These checks establish serving parity and dataset independence;
they do not establish accuracy on future network traffic.

For HTTPS hosting with approved accounts, use the existing
[public deployment guide](../deploy/README.md). A GitHub push alone does
not publish an online API or dashboard.
