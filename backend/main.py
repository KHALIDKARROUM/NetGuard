"""
main.py — Point d'entrée FastAPI.
<<<<<<< HEAD

Le backend charge le meilleur modèle au démarrage, une seule fois.
Toutes les routes partagent la même instance via app.state.

Lancement :
    uvicorn main:app --host 0.0.0.0 --port 5000
    python main.py   (développement)
=======
Les modèles sont déjà entraînés — le backend ne fait que les charger et servir.
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
"""

import logging
import logging.handlers

<<<<<<< HEAD
from contextlib import asynccontextmanager
=======
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

<<<<<<< HEAD
from config import settings, LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT, LOG_MAX_BYTES, LOG_BACKUP_COUNT
from utils import BestModelLoader, ModelError
from routes import dataset_router, metrics_router, prediction_router


# ── Logging ────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure le logger racine avec rotation des fichiers."""
=======
from config import settings, LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT
from routes import dataset_router, comparison_router, prediction_router


def setup_logging() -> None:
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    level = getattr(logging, settings.log_level, logging.INFO)
    fmt   = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    fh = logging.handlers.RotatingFileHandler(
<<<<<<< HEAD
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)

=======
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    logging.basicConfig(level=level, handlers=[fh, ch])
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


<<<<<<< HEAD
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
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736

**Meilleur modèle** : Ensemble IF(0.1)+LOF(0.1)+AE(0.8) — F1=0.8443, AUC=0.9069
        """,
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
<<<<<<< HEAD
        lifespan=lifespan,
    )

    # CORS — autorise le frontend Streamlit à appeler l'API
=======
    )

>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

<<<<<<< HEAD
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
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
            "routes": {
                "Page 1 — Dataset": {
                    "GET /api/dataset/info":          "Vue d'ensemble + stats",
                    "GET /api/dataset/sample":        "Aperçu tabulaire (?n=100)",
                    "GET /api/dataset/distributions": "Distributions par feature (?top_n=10)",
                },
<<<<<<< HEAD
                "Page 2 — Métriques": {
                    "GET /api/metrics/evaluate": "Métriques du meilleur modèle",
                    "GET /api/metrics/viz":      "Graphiques (?type=pca|scores|confusion|roc)",
                },
                "Page 3 — Prédiction": {
                    "GET  /api/predict/info":   "Infos sur le modèle déployé",
                    "POST /api/predict/single": "Prédire une connexion réseau",
=======
                "Page 2 — Comparaison": {
                    "GET /api/models/compare": "Tableau comparatif des 5 modèles",
                    "GET /api/models/viz":     "Graphiques (?type=pca|scores|confusion|roc)",
                },
                "Page 3 — Prédiction": {
                    "GET  /api/predict/best_model": "Infos sur le meilleur modèle",
                    "POST /api/predict/single":     "Prédire une connexion réseau",
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                },
            },
        }

<<<<<<< HEAD
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
=======
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.getLogger(__name__).exception(f"Erreur non interceptée : {request.url}")
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
        return JSONResponse(
            status_code=500,
            content={"error": "Erreur interne du serveur.", "status": 500},
        )

    return app


<<<<<<< HEAD
# ── Point d'entrée ─────────────────────────────────────────────────────────────

=======
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
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