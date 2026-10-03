"""FastAPI router exports."""

from backend.routes.comparison import router as comparison_router
from backend.routes.dataset import router as dataset_router
from backend.routes.metrics import router as metrics_router
from backend.routes.prediction import router as prediction_router

__all__ = [
    "comparison_router",
    "dataset_router",
    "metrics_router",
    "prediction_router",
]
