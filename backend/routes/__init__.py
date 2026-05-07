"""routes/__init__.py — Exports des routeurs FastAPI."""

from routes.dataset    import router as dataset_router
from routes.metrics    import router as metrics_router
from routes.prediction import router as prediction_router

__all__ = ["dataset_router", "metrics_router", "prediction_router"]