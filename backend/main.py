"""
main.py — Point d'entrée FastAPI.
Les modèles sont déjà entraînés — le backend ne fait que les charger et servir.
"""

import logging
import logging.handlers

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings, LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT
from routes import dataset_router, comparison_router, prediction_router


def setup_logging() -> None:
    level = getattr(logging, settings.log_level, logging.INFO)
    fmt   = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    logging.basicConfig(level=level, handlers=[fh, ch])
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Anomaly Detection API",
        description="""
API de détection d'anomalies réseau — UNSW-NB15.

Les modèles ont été entraînés dans les notebooks 04, 05, 06
et évalués dans le notebook 07. Ce backend sert les résultats.

**Page 1** → `/api/dataset/*` — informations sur le dataset  
**Page 2** → `/api/models/*` — comparaison des 5 modèles  
**Page 3** → `/api/predict/*` — prédiction avec le meilleur modèle  

**Meilleur modèle** : Ensemble IF(0.1)+LOF(0.1)+AE(0.8) — F1=0.8443, AUC=0.9069
        """,
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dataset_router)
    app.include_router(comparison_router)
    app.include_router(prediction_router)

    @app.get("/health", tags=["Infra"])
    def health():
        """Health check pour Docker Compose."""
        return {"status": "ok", "service": "anomaly-detection-backend", "version": "3.0.0"}

    @app.get("/", tags=["Infra"])
    def index():
        return {
            "service": "Anomaly Detection API v3",
            "docs": "/docs",
            "routes": {
                "Page 1 — Dataset": {
                    "GET /api/dataset/info":          "Vue d'ensemble + stats",
                    "GET /api/dataset/sample":        "Aperçu tabulaire (?n=100)",
                    "GET /api/dataset/distributions": "Distributions par feature (?top_n=10)",
                },
                "Page 2 — Comparaison": {
                    "GET /api/models/compare": "Tableau comparatif des 5 modèles",
                    "GET /api/models/viz":     "Graphiques (?type=pca|scores|confusion|roc)",
                },
                "Page 3 — Prédiction": {
                    "GET  /api/predict/best_model": "Infos sur le meilleur modèle",
                    "POST /api/predict/single":     "Prédire une connexion réseau",
                },
            },
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.getLogger(__name__).exception(f"Erreur non interceptée : {request.url}")
        return JSONResponse(
            status_code=500,
            content={"error": "Erreur interne du serveur.", "status": 500},
        )

    return app


setup_logging()
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level=settings.log_level.lower(),
    )