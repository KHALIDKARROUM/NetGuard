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
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
from backend.security import RequestGuardMiddleware, SECURITY_HEADERS, SecurityHeadersMiddleware


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


def create_app(artifact_path=None, enable_logging=True, service_settings=None, registry_path=None) -> FastAPI:
    configuration = service_settings or settings
    docs_enabled = configuration.deployment_mode == "local"
    app = FastAPI(
        title="NetGuard Anomaly Detection API",
        description=(
            "FastAPI service for UNSW-NB15 dataset exploration, model comparison, "
            "and raw single/batch inference through the shared notebook pipeline."
        ),
        version="5.0.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.prediction_artifact_path = Path(artifact_path or configuration.prediction_artifact)
    candidate_registry = registry_path or configuration.prediction_registry
    app.state.prediction_registry_path = (
        Path(candidate_registry) if candidate_registry and artifact_path is None
        and app.state.prediction_artifact_path.parent == Path(candidate_registry).parent else None
    )
    app.state.enable_logging = enable_logging
    app.state.security_settings = configuration

    app.add_middleware(RequestGuardMiddleware, settings=configuration)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuration.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
        allow_credentials=False,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=configuration.allowed_hosts, www_redirect=False)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(dataset_router)
    app.include_router(comparison_router)
    app.include_router(metrics_router)
    app.include_router(prediction_router)

    @app.exception_handler(StarletteHTTPException)
    async def service_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            logging.getLogger(__name__).error("Service error (%s) on %s: %s", exc.status_code, request.url.path, exc.detail)
            detail = "The analysis service is unavailable. Check the server configuration." if exc.status_code == 503 else "Internal server error."
            return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)
        return await http_exception_handler(request, exc)

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
                "models_ready": False, "detail": "The saved model is unavailable. Check the server configuration.",
            })
        if configuration.api_key is not None:
            return {"status": "ok", "service": "netguard-backend", "models_ready": True}
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
            "docs": "/docs" if docs_enabled else None,
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
        logging.getLogger(__name__).exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
            headers={**SECURITY_HEADERS, "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"},
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
        proxy_headers=False,
    )
