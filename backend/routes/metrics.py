"""
routes/metrics.py — Page 2 : métriques et visualisations du meilleur modèle.

On évalue uniquement le meilleur modèle (Ensemble IF+LOF+AE).
Pas de comparaison entre modèles : on a fait ce choix dans les notebooks.

Routes :
    GET /api/metrics/evaluate  → Métriques du modèle sur le test set
    GET /api/metrics/viz       → Données graphiques (PCA, scores, confusion, ROC)
"""

import logging
import threading
import numpy as np

from fastapi import APIRouter, HTTPException, Request, Query
from typing import Literal

from utils import (
    DataLoader, BestModelLoader, DataLoadError, ModelError,
    compute_metrics, get_pca_data, get_score_distribution, get_confusion_matrix_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["Page 2 — Métriques"])


def _get_loader(request: Request) -> BestModelLoader:
    """
    Retourne le BestModelLoader partagé depuis l'état de l'app.
    Lève une ModelError si le modèle n'a pas pu être chargé au démarrage.
    """
    loader = getattr(request.app.state, "model_loader", None)
    if loader is None or not loader.is_loaded:
        raise ModelError("Le modèle n'est pas disponible. Vérifier les fichiers dans models_saved/.")
    return loader


def _get_data_loader(request: Request) -> DataLoader:
    state = request.app.state
    if not hasattr(state, "data_loader"):
        state.data_loader = DataLoader()
    return state.data_loader


def _ensure_evaluation(request: Request) -> None:
    """
    Calcule les métriques du modèle sur le test set si elles ne sont pas en cache.
    Stocke les résultats dans request.app.state pour éviter de recalculer.
    """
    state = request.app.state

    if hasattr(state, "evaluation_cache"):
        return  # déjà calculé

    data_loader  = _get_data_loader(request)
    model_loader = _get_loader(request)

    X_test, y_test, df_test = data_loader.load_test()

    # On passe le DataFrame pour que le QT conserve les noms de colonnes
    from config import FEATURE_NAMES
    X_df = df_test[FEATURE_NAMES]  # DataFrame avec noms de colonnes
    scores, inference_s = model_loader.predict_scores(X_df)
    preds = model_loader.scores_to_preds(scores)

    metrics = compute_metrics(
        name=model_loader.model_name,
        y_true=y_test,
        y_pred=preds,
        y_scores=scores,
        inference_s=inference_s,
    )

    state.evaluation_cache = {
        "X_test": X_test,  # numpy array pour la PCA
        "y_test": y_test,
        "scores": scores,
        "preds":  preds,
        "metrics": metrics,
    }
    logger.info("Évaluation mise en cache.")


# ── GET /api/metrics/evaluate ─────────────────────────────────────────────────

@router.get("/evaluate", summary="Métriques du meilleur modèle sur le test set")
def get_evaluation(request: Request):
    """
    Évalue le meilleur modèle (Ensemble IF+LOF+AE) sur le test set complet
    (82 332 connexions réseau).

    Métriques retournées :
    - Precision, Recall, F1, ROC-AUC, Average Precision
    - Matrice de confusion
    - Temps d'inférence
    """
    try:
        _ensure_evaluation(request)
        cache = request.app.state.evaluation_cache

        return {
            "status":  200,
            "model":   cache["metrics"]["model"],
            "metrics": cache["metrics"],
        }

    except (DataLoadError, ModelError) as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception:
        logger.exception("[EVALUATE] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")


# ── GET /api/metrics/viz ──────────────────────────────────────────────────────

@router.get("/viz", summary="Données graphiques pour la Page 2")
def get_visualization(
    request: Request,
    type: Literal["pca", "scores", "confusion", "roc"] = Query(
        default="pca",
        description="Type de graphique : pca | scores | confusion | roc",
    ),
):
    """
    Données structurées pour les graphiques Plotly de la **Page 2**.

    - **pca**      : scatter plot 2D des données réduites par PCA
    - **scores**   : histogramme des scores d'anomalie (normal vs anomalie)
    - **confusion** : matrice de confusion
    - **roc**      : courbe ROC
    """
    try:
        _ensure_evaluation(request)
        cache = request.app.state.evaluation_cache

        X_test  = cache["X_test"]
        y_test  = cache["y_test"]
        scores  = cache["scores"]
        preds   = cache["preds"]
        metrics = cache["metrics"]

        if type == "pca":
            data = get_pca_data(X=X_test, labels=preds, scores=scores)  # X_test numpy pour PCA

        elif type == "scores":
            data = get_score_distribution(
                scores=scores,
                y_true=y_test,
                model_name=metrics["model"],
            )

        elif type == "confusion":
            data = get_confusion_matrix_data(metrics)

        elif type == "roc":
            data = metrics.get("roc_curve", {})

        return {"status": 200, "type": type, "data": data}

    except (DataLoadError, ModelError) as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception:
        logger.exception("[VIZ] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")