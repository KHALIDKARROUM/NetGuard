"""Compatibility metrics routes backed by the model comparison cache."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from routes.comparison import _ensure_scores, get_state
from utils.evaluator import get_confusion_matrix_data, get_score_distribution
from utils.model_loader import scores_to_preds

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@router.get("/evaluate", summary="Metrics for the best available model")
def get_evaluation(request: Request):
    try:
        state = get_state(request)
        _ensure_scores(state)
        best_name = state["best_model_name"]
        best_metrics = next(
            item for item in state["metrics_list"] if item["model"] == best_name
        )
        return {
            "status": 200,
            "model": best_name,
            "metrics": best_metrics,
        }
    except Exception:
        logger.exception("Compatibility metrics evaluation failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/viz", summary="Visualization payloads for the best model")
def get_visualization(
    request: Request,
    type: Literal["pca", "scores", "confusion", "roc"] = Query(default="pca"),
):
    try:
        from utils.evaluator import get_pca_data

        state = get_state(request)
        _ensure_scores(state)
        best_name = state["best_model_name"]
        best_scores = state["all_scores"][best_name]
        best_metrics = next(
            item for item in state["metrics_list"] if item["model"] == best_name
        )

        if type == "pca":
            data = get_pca_data(
                X=state["X_test_qt"],
                labels=scores_to_preds(best_scores),
                scores=best_scores,
            )
            data["model_used"] = best_name
        elif type == "scores":
            data = get_score_distribution(best_scores, state["y_test"], best_name)
        elif type == "confusion":
            data = get_confusion_matrix_data(best_metrics)
        else:
            data = best_metrics.get("roc_curve", {})

        return {"status": 200, "type": type, "data": data}
    except Exception:
        logger.exception("Compatibility metrics visualization failed")
        raise HTTPException(status_code=500, detail="Internal server error.")
