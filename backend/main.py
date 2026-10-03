"""FastAPI entrypoint for the NetGuard anomaly detection backend."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
import sys
from contextlib import asynccontextmanager

# Keep both repository-root package startup and the existing backend/ command usable.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend.config import (
    LOG_BACKUP_COUNT,
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_FORMAT,
    LOG_MAX_BYTES,
    settings,
)
from backend.routes import comparison_router, dataset_router, metrics_router, prediction_router
from backend.utils.prediction_pipeline import get_prediction_service
from netguard_workflow import ArtifactError


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
    if app.state.enable_logging:
        setup_logging()
    try:
        get_prediction_service(app)
    except ArtifactError as exc:
        logging.getLogger(__name__).warning("Shared model unavailable: %s", exc)
    logging.getLogger(__name__).info("NetGuard API started")
    yield
    logging.getLogger(__name__).info("NetGuard API stopped")


def create_app(artifact_path=None, enable_logging=True) -> FastAPI:
    app = FastAPI(
        title="NetGuard Anomaly Detection API",
        description=(
            "FastAPI service for UNSW-NB15 dataset exploration, model comparison, "
            "and raw single/batch inference through the shared notebook pipeline."
        ),
        version="5.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.prediction_artifact_path = Path(artifact_path or settings.prediction_artifact)
    app.state.enable_logging = enable_logging

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

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Invalid measurements may contain infinity/NaN. Return useful field errors
        # without echoing values that cannot be serialized as standards-compliant JSON.
        errors = [{key: error[key] for key in ("type", "loc", "msg")}
                  for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.get("/health", tags=["Infra"])
    def health():
        try:
            service = get_prediction_service(app)
        except ArtifactError as exc:
            return JSONResponse(status_code=503, content={
                "status": "unavailable", "service": "netguard-backend", "version": "5.0.0",
                "models_ready": False, "detail": str(exc),
            })
        return {
            "status": "ok",
            "service": "netguard-backend",
            "version": "5.0.0", "models_ready": True,
            "model": service.metadata["name"], "artifact_sha256": service.artifact_sha256,
            "precision": "float64",
        }

    @app.get("/", tags=["Infra"])
    def index():
        return {
            "service": "NetGuard Anomaly Detection API",
            "version": "5.0.0",
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
                    "POST /api/predict/batch",
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
