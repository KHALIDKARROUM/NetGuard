# NetGuard Anomaly Detection

[![NetGuard checks](https://github.com/KHALIDKARROUM/NetGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/KHALIDKARROUM/NetGuard/actions/workflows/ci.yml)

Streamlit + FastAPI workspace for exploring UNSW-NB15 network traffic,
evaluating a supervised baseline, and scoring individual connections or batches.

## What Changed

- Backend moved to a clean FastAPI API surface with cached loaders and stable routes.
- Runtime merge conflicts were resolved across backend, frontend, Dockerfiles, requirements, and model reports.
- The deployed backend serves the notebook's frozen XGBoost, LightGBM, and TabM neural network pipelines. XGBoost is the validation-selected default; the prediction lab lets you choose any of the three.
- All analysis stages and guides are consolidated into one self-contained notebook with consistent charts, inline implementations, portable model export, and standard Run All support.
- All four screens share a navy sidebar, light workspace, teal accents, responsive layouts, and consistent chart and card components.
- Dataset exploration includes filtered record previews, feature search, and CSV downloads. Performance charts load only when selected.
- The prediction lab groups the ten measured inputs, explains decisions beside the form, and supports validated CSV batches of up to 1,000 connections with downloadable results.
- Prediction requires ten measured raw fields and uses the same 29 physical features, training-fitted preprocessing, float64 precision and feature order as training.
- Single/batch predictions and dashboard metrics are verified against the notebook's saved predictions. Historical ensemble artifacts remain reference material.
- Security controls include optional API authentication, explicit host/origin allowlists, bounded requests and uploads, safer CSV exports, and restricted Docker services. See [security and deployment](SECURITY.md).

## Stack

- Backend: FastAPI, scikit-learn, XGBoost, LightGBM, PyTorch/TabM, pandas (CPython 3.13.9, locked training-compatible runtime)
- Frontend: Streamlit, Plotly
- Model artifacts: `models_saved/`
- Data artifacts: `data/featured/`, `data/preprocessed/`, `data/reports/`

## Project Layout

```text
NetGuard/
|-- docker-compose.yaml              # Docker Compose orchestration
|-- README.md                        # Project documentation
|
|-- backend/                         # FastAPI service
|   |-- Dockerfile
|   |-- main.py                      # API entry point
|   |-- config.py                    # Backend configuration
|   |-- requirements.txt
|   |-- test_api.py
|   |
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- comparison.py            # Model comparison endpoints
|   |   |-- dataset.py               # Dataset exploration endpoints
|   |   |-- metrics.py               # Compatibility metrics endpoints
|   |   `-- prediction.py            # Prediction endpoints
|   |
|   `-- utils/
|       |-- __init__.py
|       |-- data_loader.py
|       |-- evaluator.py
|       |-- exceptions.py
|       `-- model_loader.py
|
|-- frontend/                        # Streamlit dashboard
|   |-- Dockerfile
|   |-- app.py                       # Overview page
|   |-- config.py                    # Public shared imports
|   |-- api.py                       # API client and short-lived read caching
|   |-- theme.py                     # Color and chart tokens
|   |-- ui.py                        # Shared navigation and UI components
|   |-- styles.css                   # Responsive visual system
|   |-- charts.py                    # Shared chart builders
|   |-- prediction_inputs.py         # Input definitions and CSV validation
|   |-- .streamlit/config.toml       # Native widget theme
|   |-- requirements.txt
|   |
|   `-- pages/
|       |-- 01_dataset.py
|       |-- 02_performance.py
|       `-- 03_prediction.py
|
|-- data/
|   |-- UNSW_NB15_training-set.csv
|   |-- UNSW_NB15_testing-set.csv
|   |-- featured/
|   |-- preprocessed/
|   |-- reports/
|   `-- visualizations/
|
|-- models_saved/                    # Trained model artifacts
|   |-- deployed/                     # Current XGBoost, LightGBM and TabM pipelines
|   |   |-- registry.json             # Allowlisted models, default and manifest hashes
|   |   |-- xgboost.pkl               # Validation-selected default
|   |   |-- lightgbm.pkl
|   |   |-- tabm.pkl
|   |   `-- *.manifest.json           # Runtime, input order, thresholds and provenance
|   |-- shared_pipeline.joblib        # Historical supervised soft-vote pipeline
|   |-- shared_pipeline.manifest.json # Historical artifact compatibility manifest
|   |-- autoencoder.pt
|   |-- best_model.pkl
|   |-- ensemble_3models.pkl
|   |-- ensemble_if_lof.pkl
|   |-- isolation_forest.pkl
|   `-- lof.pkl
|
`-- notebooks/                       # Single self-contained analysis report
    `-- 00_netguard_complete.ipynb    # All stages, code, guides, and original source text
```

## API Routes

- `GET /health`
- `GET /api/dataset/info`
- `GET /api/dataset/sample?n=100`
- `GET /api/dataset/distributions?top_n=10`
- `GET /api/models/compare`
- `GET /api/models/viz?type=pca|scores|confusion|roc`
- `GET /api/predict/best_model`
- `POST /api/predict/single`
- `POST /api/predict/batch` (1–1,000 connections)

`GET /api/predict/best_model` includes `available_models`. Add `?model=xgboost`,
`?model=lightgbm`, or `?model=tabm` to either prediction route to choose a model.
Omitting the parameter uses XGBoost. The input body remains the ten raw measurements.

Compatibility routes are also kept under `/api/metrics/*`.

## Run Locally

Backend, from the repository root using CPython 3.13.9:

```powershell
uv venv .venv-api --python 3.13.9
uv pip sync backend/requirements.txt --python .venv-api/Scripts/python.exe --require-hashes
.venv-api/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 5000 --no-proxy-headers
```

Frontend, in its separate environment with `frontend/requirements.txt` installed:

```powershell
cd frontend
$env:BACKEND_URL="http://localhost:5000"
streamlit run app.py
```

The local frontend opens at `http://localhost:8501`. Start it from `frontend/`
so Streamlit loads the checked-in widget theme. Use **Refresh data** to reload
analysis results; successful reads are otherwise cached for up to 60 seconds.
Predictions are always submitted to the backend and are never cached.

The trained models are included in `models_saved/deployed/`; inference does not
need the notebook, training code, or CSV datasets. Dataset and performance pages
still require the benchmark CSV. To promote a later full notebook run, execute
`scripts/export_deployment_models.py` in the locked notebook environment, then
restart every API worker. The exporter checks all 82,332 benchmark decisions,
preserves the notebook export bytes, and pins every model manifest in the registry.
See [prediction deployment](backend/PREDICTION.md) for model thresholds and verification.

Frontend flow and CSV validation checks, from the root with the frontend
test dependencies installed in its separate environment:

```powershell
python -m pip install -r frontend/requirements-dev.txt
python -m pytest frontend/tests -q
```

Docker Compose:

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:8502`
- API docs: `http://localhost:5001/docs`

Both services are local by default. To configure protected API access or share
the dashboard, follow [security and deployment](SECURITY.md). Shared mode
requires an API key; remote dashboard access also needs an authenticated HTTPS
proxy. Docker backend logs are stored in a named volume.

## Automated Checks

[NetGuard checks](https://github.com/KHALIDKARROUM/NetGuard/actions/workflows/ci.yml)
runs on every push and pull request, and can be started manually from GitHub's
Actions tab. It runs these checks in parallel:

- Backend, security, feature, and model tests under CPython 3.13.9 with the
  hash-locked backend dependencies.
- Dashboard flows, CSV validation, and file-security tests under Python 3.10
  with the pinned frontend requirements and test dependencies.
- Separate backend and frontend Docker image builds, plus Compose configuration
  validation. These builds do not publish images or deploy the application.
- Real Compose stacks in local and protected shared mode, with browser-driven
  CSV uploads, single/batch predictions, downloads, invalid input rejection,
  API-key checks, and verification of the container restrictions.
- A separate four-service sharing stack with named-account sign-in, HTTPS,
  protected uploads/downloads, logout, failed-login lockout, and no bypass ports.

Each job also checks dependency consistency where applicable. Actions are
pinned to commit hashes, the workflow uses read-only repository permissions,
and newer runs cancel superseded checks on the same branch or pull request.
Unit tests use synthetic traffic and mocked dashboard responses. End-to-end
tests start the actual images and saved model with the checked-in dataset and
synthetic upload measurements. Shared-mode checks generate a temporary API key;
no repository secrets or external dataset downloads are needed.

To run the backend suite locally with the configured backend environment:

```powershell
.venv-api/Scripts/python.exe -m unittest discover -s tests -v
```

## Docker End-to-End Verification

For remote sharing, use the [named-account sign-in and HTTPS setup](deploy/README.md).
Its public configuration exposes only the authenticated HTTPS gateway; the
service API key remains separate from dashboard user accounts.

The two `Docker end-to-end` checks in GitHub Actions exercise both services
together after the image builds pass. Services must report healthy before
testing starts. Each run uses its own Compose project and removes its containers
and log volume afterward. Failed runs retain browser screenshots, traces, and
container diagnostics for seven days.

To repeat the shared-mode checks locally, start Docker and use a fresh
PowerShell terminal at the repository root:

```powershell
python -m venv .venv-e2e
.venv-e2e/Scripts/python.exe -m pip install -r tests/e2e/requirements.txt
.venv-e2e/Scripts/python.exe -m playwright install chromium
$env:COMPOSE_PROJECT_NAME = "netguard-e2e-local-" + [guid]::NewGuid().ToString("N")
$env:COMPOSE_FILE = "docker-compose.yaml:docker-compose.e2e.yaml"
$env:COMPOSE_PATH_SEPARATOR = ":"
$env:NETGUARD_BACKEND_PORT = "5101"
$env:NETGUARD_FRONTEND_PORT = "8602"
$env:NETGUARD_DEPLOYMENT_MODE = "shared"
$env:NETGUARD_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
try {
    docker compose up --build --wait --wait-timeout 180
    if ($LASTEXITCODE -ne 0) { throw "Container startup failed" }
    .venv-e2e/Scripts/python.exe -m pytest tests/e2e -v --tracing retain-on-failure --screenshot only-on-failure --output artifacts/docker_e2e/browser
} finally {
    docker compose down --volumes --remove-orphans
}
```

For the local-mode checks, set `NETGUARD_DEPLOYMENT_MODE=local` and an empty
`NETGUARD_API_KEY` before starting the stack. The default application ports stay
5001 and 8502; the test configuration uses 5101 and 8602 to keep the normal
workspace separate. `NETGUARD_BACKEND_PORT` and `NETGUARD_FRONTEND_PORT` can also
select other loopback ports when needed.

## Model Notes

The dashboard serves `models_saved/shared_pipeline.joblib`. It was retrained
using float64 raw features, fit-only preprocessing, and grouped validation for
model and threshold selection. All candidates use the same fit-only StandardScaler.
The fixed threshold is **0.8631127466983196**,
chosen for maximum validation attack recall with false-positive rate at most
**1%**. The API performs no reference-data lookup, fitting or threshold selection.
Score calibration is saved explicitly as identity (no learned calibration).
Missing or incompatible artifacts make prediction and health return HTTP 503.

Validation false-positive rate is **0.996%** (132/13,248 normal rows), with
**79.00% attack recall**. At the same frozen threshold, the benchmark has
**2.959% false-positive rate** (1,095/37,000), **86.51% recall**, and F1 **0.9158**.
These are measured operating points; the validation budget does not guarantee
the same false-alarm rate on other traffic.
The benchmark was previously inspected; scores are not calibrated production
attack probabilities. Historical ensemble results used test-informed choices
and remain explicitly historical.

The current supervised ensemble gained **5.62 percentage points of validation
recall** over the best individual (gradient boosting), with **1.33x** complete
256-row prediction latency. It passed the declared 2-point gain / 2x latency
rules. Its fitted artifact is about 64 MB, versus 0.6 MB for gradient boosting,
so deployment memory and storage costs are higher.
The [single notebook](notebooks/00_netguard_complete.ipynb) explains the comparison
rules, accuracy, false alarms, complete prediction timing, and unfamiliar-attack
experiments. The application still serves its existing verified artifact.

## Reproducible Data Science Workflow

Open [NetGuard's complete notebook](notebooks/00_netguard_complete.ipynb), select
the notebook environment, and use **Restart Kernel → Run All**. It contains the
entire analysis implementation and needs only the two original CSV inputs;
it imports no project Python modules. The setup guide, 29-feature dictionary,
model decision rules, and robustness methodology are included in the report.
Original source text from all seven former notebooks and the four guides is
retained in notebook metadata, with duplicated historical outputs removed.

Create or refresh the reproducible environment from the repository root:

```powershell
uv venv .venv-workflow --python 3.13.9
uv pip sync requirements-notebooks.txt --python .venv-workflow/Scripts/python.exe --require-hashes
.venv-workflow/Scripts/python.exe scripts/run_notebook.py
```

The runner executes every code cell in a fresh kernel and saves the executed
report back to the same notebook. Research outputs go to `artifacts/notebook_report/`:
`netguard_model.pkl`, `neural_network_model.pkl`, `lightgbm_model.pkl`, `tabm_model.pkl`,
row-level predictions, validation and benchmark comparisons,
attack-family tables, signature-cluster intervals, a provenance manifest, and figures.
The portable model includes notebook-defined classes and loads without the project's
helper modules. The notebook export is separate from the backend's serving artifact.
See [the application prediction contract](backend/PREDICTION.md) for API verification.

The upgraded report compares CatBoost, XGBoost, LightGBM, regularized Extra Trees,
an MLP neural network, and TabM against the previous baselines and soft vote. Two fixed
new ensembles test whether combining the upgraded trees or trees and neural network
improves validation recall enough to justify prediction cost. The neural classifier
has ReLU hidden layers of 64 and 32 units, Adam optimization, and L2 regularization.
Its normal-quantile preprocessing is fitted inside an inner grouped training split,
whose monitoring loss chooses training duration. The fixed design is then refitted
on all outer fit rows. Neural learning curves and a separate portable neural artifact are saved.

LightGBM uses 800 histogram boosting rounds, up to 63 leaves and depth 8, with
minimum leaf size 40 and L2 regularization. The official TabM implementation uses
16 members sharing weights, two 64-unit hidden blocks, dropout 0.1, and AdamW.
Each member receives its own binary training loss; inference averages member
probabilities. Its inner grouped monitoring loss chooses the epoch count with
patience 12 within 80 epochs, followed by a fresh refit on all fitting rows.
Both neural designs use training-fitted normal-quantile preprocessing. TabM uses
float32 CPU tensors for training, float64 tensors for final scoring, and no feature embeddings. These are fixed configuration
comparisons, with no benchmark-driven tuning. Separate LightGBM and TabM exports
and TabM learning curves are saved alongside the selected model.

Earlier normal-reference Isolation Forest, novelty LOF, DBSCAN, reconstruction
autoencoder, anomaly votes, and protocol-specific Isolation Forest remain optional
experiments controlled by `RUN_ANOMALY_MODELS` and `RUN_PROTOCOL_MODEL`. Each
operating threshold uses outer validation only.

The completed full-data run selected **XGBoost**. These scores use the same grouped
fit/validation split and each model's frozen validation threshold:

| Model | Validation attack recall | Validation FPR | Benchmark attack recall | Benchmark FPR |
| --- | ---: | ---: | ---: | ---: |
| Previous soft vote | 79.00% | 1.00% | 86.51% | 2.96% |
| **XGBoost (selected)** | 80.22% | 0.99% | 87.27% | 2.89% |
| LightGBM | 75.38% | 0.45% | 84.04% | 1.24% |
| TabM | 70.48% | 0.36% | 81.12% | 0.71% |
| MLP neural network | 75.84% | 1.00% | 84.71% | 2.85% |

The MLP's inner monitoring selected 110 training epochs; TabM selected
79. Both were refitted on all fitting rows. The selected model and the
MLP, LightGBM, and TabM candidates are exported separately. All exports passed
reload and single/batch prediction consistency checks.

The 1% false-alarm budget applies to validation. Benchmark false-alarm rates are
measured separately and can exceed that budget. This is a comparison of fixed
configurations on one grouped validation split, without a new hyperparameter search.

The benchmark is explicitly previously inspected. Feature equality does not prove
connection identity or prospective independence.

For three additional grouped refits and every withheld attack family, enable
`RUN_EXTENDED_GENERALIZATION` in the notebook or run:

```powershell
.venv-workflow/Scripts/python.exe scripts/run_notebook.py --extended --bootstrap-repeats 400
```

For a quick execution check, use `--fast`; those reduced model settings are labelled
as smoke results. Optional t-SNE is controlled in the notebook's settings cell.
A standalone copy can read both CSVs beside itself or in a neighbouring `data/`
folder; `NETGUARD_DATA_DIR` and `NETGUARD_OUTPUT_DIR` override those locations.
