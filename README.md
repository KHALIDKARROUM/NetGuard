# NetGuard Anomaly Detection

[![NetGuard checks](https://github.com/KHALIDKARROUM/NetGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/KHALIDKARROUM/NetGuard/actions/workflows/ci.yml)

Streamlit + FastAPI workspace for exploring UNSW-NB15 network traffic,
evaluating a supervised baseline, and scoring individual connections or batches.

## What Changed

- Backend moved to a clean FastAPI API surface with cached loaders and stable routes.
- Runtime merge conflicts were resolved across backend, frontend, Dockerfiles, requirements, and model reports.
- The notebook and backend share a validation-selected supervised pipeline and saved threshold; the current winner is a fixed soft vote of logistic regression, random forest and gradient boosting.
- All four screens share a navy sidebar, light workspace, teal accents, responsive layouts, and consistent chart and card components.
- Dataset exploration includes filtered record previews, feature search, and CSV downloads. Performance charts load only when selected.
- The prediction lab groups the ten measured inputs, explains decisions beside the form, and supports validated CSV batches of up to 1,000 connections with downloadable results.
- Prediction requires ten measured raw fields and uses the same 29 physical features, training-fitted preprocessing, float64 precision and feature order as training.
- Single/batch predictions and dashboard metrics are verified against the notebook's saved predictions. Historical ensemble artifacts remain reference material.
- Security controls include optional API authentication, explicit host/origin allowlists, bounded requests and uploads, safer CSV exports, and restricted Docker services. See [security and deployment](SECURITY.md).

## Stack

- Backend: FastAPI, scikit-learn, pandas (CPython 3.13.9, shared numerical lock)
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
|   |-- shared_pipeline.joblib        # Current complete fitted prediction pipeline
|   |-- shared_pipeline.manifest.json # Artifact hash, runtime, feature order, threshold
|   |-- autoencoder.pt
|   |-- best_model.pkl
|   |-- ensemble_3models.pkl
|   |-- ensemble_if_lof.pkl
|   |-- isolation_forest.pkl
|   `-- lof.pkl
|
`-- notebooks/                       # Main report and preserved historical stages
    |-- 00_netguard_complete.ipynb
    |-- WORKFLOW.md
    |-- 01_eda.ipynb
    |-- 02_preprocessing.ipynb
    |-- 03_feature_engineering.ipynb
    |-- 04_isolation_forest.ipynb
    |-- 05_dbscan.ipynb
    |-- 06_model_improvements.ipynb
    `-- 07_evaluation.ipynb
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
The [comparison guide and tables](notebooks/SUPERVISED_COMPARISON.md) cover
accuracy, false alarms, complete single/batch prediction timing, and the separate
unfamiliar-attack experiments.

## Reproducible Data Science Workflow

Use [the combined notebook](notebooks/00_netguard_complete.ipynb) as the main
project report. Its current sections run from the original raw CSVs to a saved
supervised baseline and row-level predictions. Preprocessing is fitted on
training rows, and model/threshold selection uses grouped validation data.
The existing test file is labelled as a previously inspected benchmark.

All original notebook cells and alternate merge content remain available as
historical reference. The seven source notebooks are repaired JSON notebooks.
The documented runner executes only corrected sections in a fresh kernel.

Follow [the environment setup and execution guide](notebooks/WORKFLOW.md).
The [feature dictionary](notebooks/FEATURES.md) defines physical features and
their zero-denominator policies before training-only scaling.
The same fitted artifact is now used by the notebook and dashboard backend.
See [the shared prediction contract and parity checks](backend/PREDICTION.md).
The [no-data verification](data/reports/prediction_without_data.json) checks
cold startup and live single/batch predictions with no data directory and with
dataset reads blocked.

The [generalization report](notebooks/GENERALIZATION.md) separates benchmark
signatures seen in actual fitting data from unseen signatures, with sample
counts and 95% signature-cluster intervals. It reports precision, recall, F1,
PR-AUC, average precision and false alarms, including every attack category.
Additional three-way grouped splits and all nine withheld-family experiments
refit the fixed design without changing the deployed artifact or its threshold.
Feature equality does not prove identical physical connections. The supplied
CSV files lack verified host/time/capture provenance, so these results support
internal robustness claims and require independent prospective evaluation.
