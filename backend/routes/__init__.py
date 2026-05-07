<<<<<<< HEAD
"""routes/__init__.py — Exports des routeurs FastAPI."""

from routes.dataset    import router as dataset_router
from routes.metrics    import router as metrics_router
from routes.prediction import router as prediction_router

__all__ = ["dataset_router", "metrics_router", "prediction_router"]
=======
from routes.dataset import router as dataset_router
from routes.comparison import router as comparison_router
from routes.prediction import router as prediction_router

__all__ = ["dataset_router", "comparison_router", "prediction_router"]
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
