"""FastAPI entrypoint for the NetGuard anomaly detection backend."""

from __future__ import annotations

import logging
import logging.handlers
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import (
    LOG_BACKUP_COUNT,
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_FORMAT,
    LOG_MAX_BYTES,
    settings,
)
from routes import comparison_router, dataset_router, metrics_router, prediction_router
from utils.model_loader import available_model_files


def setup_logging() -> None:
    level = getattr(logging, settings.log_level, logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[file_handler, stream_handler])
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cache = {}
    logging.getLogger(__name__).info("NetGuard API started")
    yield
    logging.getLogger(__name__).info("NetGuard API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="NetGuard Anomaly Detection API",
        description=(
            "FastAPI service for UNSW-NB15 dataset exploration, model comparison, "
            "and single-connection anomaly inference."
        ),
        version="4.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dataset_router)
    app.include_router(comparison_router)
    app.include_router(metrics_router)
    app.include_router(prediction_router)

    @app.get("/health", tags=["Infra"])
    def health():
        files = available_model_files()
        return {
            "status": "ok",
            "service": "netguard-backend",
            "version": "4.0.0",
            "models_ready": all(
                files[key]
                for key in (
                    "quantile_transformer",
                    "robust_scaler",
                    "isolation_forest",
                    "lof",
                    "autoencoder",
                    "ensemble_if_lof_ae",
                )
            ),
            "files": files,
        }

    @app.get("/", tags=["Infra"])
    def index():
        return {
            "service": "NetGuard Anomaly Detection API",
            "version": "4.0.0",
            "docs": "/docs",
            "routes": {
                "dataset": [
                    "GET /api/dataset/info",
                    "GET /api/dataset/sample?n=100",
                    "GET /api/dataset/distributions?top_n=10",
                ],
                "models": [
                    "GET /api/models/compare",
                    "GET /api/models/viz?type=pca|scores|confusion|roc",
                ],
                "prediction": [
                    "GET /api/predict/best_model",
                    "POST /api/predict/single",
                ],
            },
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.getLogger(__name__).exception("Unhandled error on %s", request.url)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
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
