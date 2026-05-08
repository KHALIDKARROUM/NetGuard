"""FastAPI router exports."""

from routes.comparison import router as comparison_router
from routes.dataset import router as dataset_router
from routes.metrics import router as metrics_router
from routes.prediction import router as prediction_router

__all__ = [
    "comparison_router",
    "dataset_router",
    "metrics_router",
    "prediction_router",
]
