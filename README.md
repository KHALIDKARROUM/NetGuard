# NetGuard Anomaly Detection

Dark Streamlit + FastAPI application for exploring UNSW-NB15 network traffic,
comparing anomaly-detection models, and scoring a single connection in real time.

## What Changed

- Backend moved to a clean FastAPI API surface with cached loaders and stable routes.
- Runtime merge conflicts were resolved across backend, frontend, Dockerfiles, requirements, and model reports.
- The deployed model is now the saved ensemble: Isolation Forest + LOF + Autoencoder.
- Streamlit was rebuilt as a dark operations dashboard with shared UI components.
- Prediction now accepts raw network fields and reconstructs the 20-feature model vector server-side.

## Stack

- Backend: FastAPI, scikit-learn, PyTorch, pandas
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
|   |-- config.py                    # Shared UI and API helpers
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

Compatibility routes are also kept under `/api/metrics/*`.

## Run Locally

Backend:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

Frontend:

```bash
cd frontend
BACKEND_URL=http://localhost:5000 streamlit run app.py
```

Docker Compose:

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:8502`
- API docs: `http://localhost:5001/docs`

## Model Notes

The dashboard currently serves the historical ensemble. Its notebook results
used test-informed development choices and should be treated as exploratory.
Labels also informed feature selection and normal-only autoencoder training.

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
The new artifacts are separate from the dashboard's historical models.
