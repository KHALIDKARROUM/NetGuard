"""Model comparison routes."""

from __future__ import annotations

import logging
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from config import CONTAMINATION, ENS2_FILE, ENS3_FILE
from utils.data_loader import load_model_comparison, load_test_data
from utils.evaluator import (
    compute_metrics,
    compute_perf_score,
    get_confusion_matrix_data,
    get_pca_data,
    get_score_distributions,
)
from utils.exceptions import DataLoadError, ModelError
from utils.model_loader import (
    get_ae_scores,
    get_ensemble2_scores,
    get_ensemble3_scores,
    get_if_scores,
    get_lof_scores,
    load_autoencoder,
    load_ensemble_config,
    load_isolation_forest,
    load_lof,
    load_qt,
    scores_to_preds,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["Models"])


def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "cache"):
        request.app.state.cache = {}
    return request.app.state.cache


def _ensure_data(state: dict) -> None:
    if "X_test_qt" in state:
        return
    X_test, y_test, df_test = load_test_data()
    state["X_test"] = X_test
    state["y_test"] = y_test
    state["df_test"] = df_test
    state["qt"] = load_qt()
    state["X_test_qt"] = state["qt"].transform(X_test)


def _ensure_scores(state: dict) -> None:
    _ensure_data(state)
    if "all_scores" in state and "metrics_list" in state:
        return

    X_qt = state["X_test_qt"]
    y_test = state["y_test"]
    scores: dict[str, object] = {}
    metrics_list: list[dict] = []

    if_model = load_isolation_forest()
    t0 = time.perf_counter()
    scores_if = get_if_scores(if_model, X_qt)
    t_if = time.perf_counter() - t0
    scores["Isolation Forest"] = scores_if
    metrics_list.append(
        compute_metrics(
            "Isolation Forest",
            y_test,
            scores_to_preds(scores_if, CONTAMINATION),
            scores_if,
            t_if,
        )
    )

    lof_model = load_lof()
    t0 = time.perf_counter()
    scores_lof = get_lof_scores(lof_model, X_qt)
    t_lof = time.perf_counter() - t0
    scores["LOF"] = scores_lof
    metrics_list.append(
        compute_metrics(
            "LOF",
            y_test,
            scores_to_preds(scores_lof, CONTAMINATION),
            scores_lof,
            t_lof,
        )
    )

    cfg2 = load_ensemble_config(ENS2_FILE)
    t0 = time.perf_counter()
    scores_ens2 = get_ensemble2_scores(scores_if, scores_lof, cfg2)
    t_ens2 = time.perf_counter() - t0
    ens2_name = f"Ensemble IF({cfg2['w_if']:.1f})+LOF({cfg2['w_lof']:.1f})"
    scores[ens2_name] = scores_ens2
    metrics_list.append(
        compute_metrics(
            ens2_name,
            y_test,
            scores_to_preds(scores_ens2, cfg2.get("contamination", CONTAMINATION)),
            scores_ens2,
            t_ens2,
        )
    )

    ae_model, device = load_autoencoder()
    if ae_model is not None:
        t0 = time.perf_counter()
        scores_ae = get_ae_scores(ae_model, device, X_qt)
        t_ae = time.perf_counter() - t0
        scores["Autoencoder (PyTorch)"] = scores_ae
        metrics_list.append(
            compute_metrics(
                "Autoencoder (PyTorch)",
                y_test,
                scores_to_preds(scores_ae, CONTAMINATION),
                scores_ae,
                t_ae,
            )
        )

        cfg3 = load_ensemble_config(ENS3_FILE)
        t0 = time.perf_counter()
        scores_ens3 = get_ensemble3_scores(scores_if, scores_lof, scores_ae, cfg3)
        t_ens3 = time.perf_counter() - t0
        ens3_name = f"Ensemble IF({cfg3['w_if']:.1f})+LOF({cfg3['w_lof']:.1f})+AE({cfg3['w_ae']:.1f})"
        scores[ens3_name] = scores_ens3
        metrics_list.append(
            compute_metrics(
                ens3_name,
                y_test,
                scores_to_preds(scores_ens3, cfg3.get("contamination", CONTAMINATION)),
                scores_ens3,
                t_ens3,
            )
        )

    metrics_list = compute_perf_score(metrics_list)
    state["all_scores"] = scores
    state["metrics_list"] = metrics_list
    state["best_model_name"] = metrics_list[0]["model"] if metrics_list else ""


def _records_from_report() -> list[dict]:
    df_report = load_model_comparison()
    if df_report is None:
        return []
    records = df_report.reset_index().to_dict(orient="records")
    return sorted(records, key=lambda row: row.get("perf_score", 0), reverse=True)


@router.get("/compare", summary="Compare available anomaly detection models")
def compare_models(request: Request):
    state = get_state(request)
    try:
        if "metrics_list" in state:
            return {
                "status": 200,
                "source": "runtime cache",
                "n_models": len(state["metrics_list"]),
                "metrics": state["metrics_list"],
                "best_model": state["best_model_name"],
            }

        records = _records_from_report()
        if records:
            return {
                "status": 200,
                "source": "data/reports/model_comparison.csv",
                "n_models": len(records),
                "metrics": records,
                "best_model": records[0]["model"] if records else "",
            }

        _ensure_scores(state)
        return {
            "status": 200,
            "source": "computed on test set",
            "n_models": len(state["metrics_list"]),
            "metrics": state["metrics_list"],
            "best_model": state["best_model_name"],
        }
    except (DataLoadError, ModelError) as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception:
        logger.exception("Model comparison failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/viz", summary="Visualization payloads for model comparison")
def get_visualization(
    request: Request,
    type: Literal["pca", "scores", "confusion", "roc"] = Query(default="pca"),
    model: str = Query(default=""),
):
    state = get_state(request)
    try:
        _ensure_scores(state)
        all_scores = state["all_scores"]
        y_test = state["y_test"]
        metrics_list = state["metrics_list"]

        if type == "pca":
            chosen = model if model in all_scores else state["best_model_name"]
            if chosen not in all_scores:
                chosen = next(iter(all_scores))
            scores = all_scores[chosen]
            data = get_pca_data(
                X=state["X_test_qt"],
                labels=scores_to_preds(scores),
                scores=scores,
            )
            data["model_used"] = chosen
        elif type == "scores":
            data = get_score_distributions(all_scores, y_test)
        elif type == "confusion":
            data = get_confusion_matrix_data(metrics_list)
        else:
            data = {
                item["model"]: item["roc_curve"]
                for item in metrics_list
                if "roc_curve" in item
            }

        return {"status": 200, "type": type, "data": data}
    except (DataLoadError, ModelError) as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception:
        logger.exception("Model visualization failed")
        raise HTTPException(status_code=500, detail="Internal server error.")
