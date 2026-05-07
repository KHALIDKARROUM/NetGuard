"""
main.py — Point d'entrée FastAPI.

Le backend charge le meilleur modèle au démarrage, une seule fois.
Toutes les routes partagent la même instance via app.state.

Lancement :
    uvicorn main:app --host 0.0.0.0 --port 5000
    python main.py   (développement)
"""

import logging
import logging.handlers

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings, LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT, LOG_MAX_BYTES, LOG_BACKUP_COUNT
from utils import BestModelLoader, ModelError
from routes import dataset_router, metrics_router, prediction_router


# ── Logging ────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure le logger racine avec rotation des fichiers."""
    level = getattr(logging, settings.log_level, logging.INFO)
    fmt   = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    logging.basicConfig(level=level, handlers=[fh, ch])
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ── Lifespan : chargement du modèle au démarrage ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Exécuté une seule fois au démarrage et à l'arrêt.
    On charge le modèle ici pour qu'il soit prêt avant la première requête.
    """
    logger = logging.getLogger(__name__)

    logger.info("Démarrage — chargement du meilleur modèle…")
    loader = BestModelLoader()

    try:
        loader.load()
        app.state.model_loader = loader
        logger.info(f"Modèle prêt : {loader.model_name}")
    except ModelError as e:
        logger.error(f"Impossible de charger le modèle : {e.message}")
        logger.error("Le backend démarre quand même — /health retournera ok.")
        app.state.model_loader = loader  # non chargé, les routes retourneront 503

    yield  # Le serveur tourne ici

    logger.info("Arrêt du serveur.")


# ── Création de l'application ─────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Crée et configure l'application FastAPI."""

    app = FastAPI(
        title="Anomaly Detection API",
        description="""
API de détection d'anomalies réseau — Dataset UNSW-NB15.

Les modèles ont été entraînés dans les notebooks 04, 05, 06.
Ce backend sert uniquement le meilleur modèle (Ensemble IF+LOF+AE).

**Page 1** → `/api/dataset/*`  — informations sur le dataset  
**Page 2** → `/api/metrics/*`  — métriques et visualisations  
**Page 3** → `/api/predict/*`  — prédiction unitaire  

**Meilleur modèle** : Ensemble IF(0.1)+LOF(0.1)+AE(0.8) — F1=0.8443, AUC=0.9069
        """,
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — autorise le frontend Streamlit à appeler l'API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(dataset_router)
    app.include_router(metrics_router)
    app.include_router(prediction_router)

    # ── Routes de base ─────────────────────────────────────────────────────────

    @app.get("/health", tags=["Infra"])
    def health():
        """Health check pour Docker Compose (depends_on)."""
        return {
            "status":  "ok",
            "service": "anomaly-detection-backend",
            "version": "3.0.0",
            "model_loaded": getattr(app.state, "model_loader", None) is not None
                            and app.state.model_loader.is_loaded,
        }

    @app.get("/", tags=["Infra"])
    def index():
        """Carte des routes disponibles."""
        return {
            "service": "Anomaly Detection API v3",
            "docs":    "/docs",
            "routes": {
                "Page 1 — Dataset": {
                    "GET /api/dataset/info":          "Vue d'ensemble + stats",
                    "GET /api/dataset/sample":        "Aperçu tabulaire (?n=100)",
                    "GET /api/dataset/distributions": "Distributions par feature (?top_n=10)",
                },
                "Page 2 — Métriques": {
                    "GET /api/metrics/evaluate": "Métriques du meilleur modèle",
                    "GET /api/metrics/viz":      "Graphiques (?type=pca|scores|confusion|roc)",
                },
                "Page 3 — Prédiction": {
                    "GET  /api/predict/info":   "Infos sur le modèle déployé",
                    "POST /api/predict/single": "Prédire une connexion réseau",
                },
            },
        }

    # ── Gestionnaire d'erreurs global ──────────────────────────────────────────

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Intercepte toutes les erreurs non gérées.
        On log l'erreur complète mais on ne l'expose pas dans la réponse API.
        """
        logging.getLogger(__name__).exception(
            f"Erreur non interceptée sur {request.url}"
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Erreur interne du serveur.", "status": 500},
        )

    return app


# ── Point d'entrée ─────────────────────────────────────────────────────────────

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