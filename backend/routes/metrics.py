"""Compatibility endpoints forwarding to current shared-model evaluation."""
from typing import Literal

from fastapi import APIRouter, Query, Request
from backend.routes.comparison import compare_models, get_visualization as shared_visualization

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@router.get("/evaluate")
def get_evaluation(request: Request):
    result = compare_models(request)
    return {"status": 200, "model": result["best_model"], "metrics": result["metrics"][0]}


@router.get("/viz")
def get_visualization(request: Request,
                      type: Literal["pca", "scores", "confusion", "roc"] = Query(default="pca")):
    result = shared_visualization(request, type=type, model="")
    if type in ("roc", "confusion"):
        data = result["data"]
        result["data"] = next(iter(data.values())) if isinstance(data, dict) else data[0]
    return result
