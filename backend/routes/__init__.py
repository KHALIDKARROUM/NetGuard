from routes.dataset import router as dataset_router
from routes.comparison import router as comparison_router
from routes.prediction import router as prediction_router

__all__ = ["dataset_router", "comparison_router", "prediction_router"]