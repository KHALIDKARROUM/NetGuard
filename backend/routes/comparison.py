"""Benchmark metrics and visualizations of the same model served by prediction."""
from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from netguard_workflow import ArtifactError
from netguard_workflow.workflow import score_metrics
from backend.utils.data_loader import load_model_comparison, load_raw_test_data
from backend.utils.evaluator import (
    compute_metrics, get_confusion_matrix_data, get_pca_data, get_score_distributions,
)
from backend.utils.exceptions import DataLoadError
from backend.utils.prediction_pipeline import get_prediction_service

router = APIRouter(prefix="/api/models", tags=["Models"])


def get_state(request):
    get_prediction_service(request.app)
    return request.app.state.cache


def _ensure_scores(state):
    if "metrics_list" in state:
        return
    default_service = state["shared_prediction_service"]
    registry = state.get("prediction_registry")
    services = [default_service]
    if registry:
        services += [service for name, service in registry.services.items() if name != registry.default]
    raw = load_raw_test_data()
    truth = raw.label.to_numpy()
    all_scores, all_predictions, metrics_list = {}, {}, []
    for service in services:
        started = time.perf_counter()
        predictions = service.predict(raw)
        inference_s = time.perf_counter() - started
        name = service.bundle["model_name"]
        scores = predictions.attack_score.to_numpy()
        labels = predictions.predicted_label.to_numpy()
        metrics = compute_metrics(name, truth, labels, scores, inference_s)
        metrics.update(score_metrics(truth, scores, service.bundle["threshold"]))
        metrics["evaluation_status"] = service.bundle["evaluation_status"]
        all_scores[name], all_predictions[name] = scores, labels
        metrics_list.append(metrics)
    state.update({"all_scores": all_scores, "all_predictions": all_predictions,
                  "metrics_list": metrics_list, "best_model_name": default_service.bundle["model_name"], "y_test": truth,
                  "raw_benchmark": raw})


@router.get("/compare", summary="Evaluate the validation-selected deployed pipeline")
def compare_models(request: Request):
    try:
        state = get_state(request)
        _ensure_scores(state)
        historical = load_model_comparison()
        return {"status": 200, "source": "shared pipeline on raw benchmark measurements",
                "n_models": len(state["metrics_list"]), "metrics": state["metrics_list"],
                "best_model": state["best_model_name"],
                "validation_comparison": state["shared_prediction_service"].bundle.get("validation_comparison", []),
                "ensemble_decision": state["shared_prediction_service"].bundle.get("ensemble_decision", {}),
                "latency_protocol": state["shared_prediction_service"].bundle.get("latency_protocol", {}),
                "benchmark_comparison": state["shared_prediction_service"].bundle.get("benchmark_comparison", []),
                "selection": "frozen using validation; benchmark metrics do not select the deployed model",
                "historical_metrics": historical.reset_index().to_dict(orient="records") if historical is not None else [],
                "historical_status": "earlier test-informed experiments; not comparable independent evaluations"}
    except ArtifactError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DataLoadError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.get("/viz", summary="Visualizations of the deployed pipeline's benchmark predictions")
def get_visualization(request: Request,
                      type: Literal["pca", "scores", "confusion", "roc"] = Query(default="pca"),
                      model: str = Query(default="")):
    try:
        state = get_state(request)
        _ensure_scores(state)
        name = model or state["best_model_name"]
        if name not in state["all_scores"]:
            raise HTTPException(status_code=422, detail="Select an available deployed model for current visualizations.")
        if type == "pca":
            # PCA is descriptive only; features use the already fitted training scaler.
            key = f"X_test_{name}"
            if key not in state:
                pipeline = get_prediction_service(request.app, name).bundle["pipeline"]
                state[key] = pipeline[:-1].transform(state["raw_benchmark"])
            data = get_pca_data(state[key], state["all_predictions"][name], state["all_scores"][name])
            data["model_used"] = name
        elif type == "scores":
            data = get_score_distributions(state["all_scores"], state["y_test"])
        elif type == "confusion":
            data = get_confusion_matrix_data(state["metrics_list"])
        else:
            data = {item["model"]: item["roc_curve"] for item in state["metrics_list"]}
        return {"status": 200, "type": type, "data": data,
                "evaluation_status": "previously inspected benchmark; not an untouched holdout"}
    except ArtifactError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DataLoadError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
