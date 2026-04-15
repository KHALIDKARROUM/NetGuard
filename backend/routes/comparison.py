"""
comparison.py — Page 2 : comparaison des performances de tous les modèles.

Les modèles ont été entraînés dans les notebooks 04, 05, 06.
Les métriques ont été calculées dans le notebook 07.
Ce backend charge les résultats déjà produits — pas de réentraînement.

Routes :
  GET /api/models/compare   → Tableau comparatif complet (métriques + classement)
  GET /api/models/viz       → Données graphiques (PCA, scores, confusion, ROC)
"""

import logging
import time
import threading
import numpy as np

from fastapi import APIRouter, HTTPException, Request, Query
from typing import Literal

from config import ENS3_FILE, CONTAMINATION
from utils.data_loader import load_test_data, load_model_comparison
from utils.model_loader import (
    load_qt, load_isolation_forest, load_lof, load_autoencoder, load_ensemble_config,
    get_if_scores, get_lof_scores, get_ae_scores, get_ensemble3_scores, scores_to_preds,
)
from utils.evaluator import (
    compute_metrics, compute_perf_score,
    get_pca_data, get_score_distributions, get_confusion_matrix_data,
)
from utils.exceptions import DataLoadError, ModelError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["Page 2 — Comparaison des modèles"])


def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "app_state"):
        request.app.state.app_state = {}
    return request.app.state.app_state


def _ensure_data(state: dict) -> None:
    """Charge le test set et le QT si pas déjà en mémoire."""
    if "X_test_qt" not in state:
        X_test, y_test, df_test = load_test_data()
        qt = load_qt()
        state["X_test"]     = X_test
        state["X_test_qt"]  = qt.transform(X_test)
        state["y_test"]     = y_test
        state["df_test"]    = df_test
        state["qt"]         = qt


def _ensure_scores(state: dict) -> None:
    """
    Calcule les scores de tous les modèles sur le test set.
    Met les résultats en cache dans l'état applicatif.
    """
    _ensure_data(state)

    if "all_scores" in state:
        return  # Déjà calculés

    X_qt   = state["X_test_qt"]
    y_test = state["y_test"]
    scores = {}
    metrics_list = []

    # 1. Isolation Forest
    try:
        if_model = load_isolation_forest()
        t0 = time.perf_counter()
        sc_if = get_if_scores(if_model, X_qt)
        t_if  = time.perf_counter() - t0
        scores["Isolation Forest"] = sc_if
        metrics_list.append(compute_metrics(
            "Isolation Forest", y_test,
            scores_to_preds(sc_if), sc_if, t_if,
        ))
        logger.info("IF scores calculés")
    except ModelError as e:
        logger.warning(f"IF non disponible : {e.message}")

    # 2. LOF
    try:
        lof_model = load_lof()
        t0 = time.perf_counter()
        sc_lof = get_lof_scores(lof_model, X_qt)
        t_lof  = time.perf_counter() - t0
        scores["LOF"] = sc_lof
        metrics_list.append(compute_metrics(
            "LOF", y_test,
            scores_to_preds(sc_lof), sc_lof, t_lof,
        ))
        logger.info("LOF scores calculés")
    except ModelError as e:
        logger.warning(f"LOF non disponible : {e.message}")

    # 3. Ensemble IF + LOF (si les deux sont disponibles)
    if "Isolation Forest" in scores and "LOF" in scores:
        try:
            from config import ENS2_FILE
            cfg2 = load_ensemble_config(ENS2_FILE)
            t0 = time.perf_counter()
            sc_ens2 = cfg2["w_if"] * scores["Isolation Forest"] + cfg2["w_lof"] * scores["LOF"]
            t_ens2  = time.perf_counter() - t0
            name_ens2 = f"Ensemble IF({cfg2['w_if']})+LOF({cfg2['w_lof']})"
            scores[name_ens2] = sc_ens2
            metrics_list.append(compute_metrics(
                name_ens2, y_test,
                scores_to_preds(sc_ens2), sc_ens2, t_ens2,
            ))
        except ModelError as e:
            logger.warning(f"Ensemble IF+LOF non disponible : {e.message}")

    # 4. Autoencoder PyTorch
    sc_ae = None
    ae_model, device = load_autoencoder()
    if ae_model is not None:
        t0 = time.perf_counter()
        sc_ae = get_ae_scores(ae_model, device, X_qt)
        t_ae  = time.perf_counter() - t0
        scores["Autoencoder (PyTorch)"] = sc_ae
        metrics_list.append(compute_metrics(
            "Autoencoder (PyTorch)", y_test,
            scores_to_preds(sc_ae), sc_ae, t_ae,
        ))
        logger.info("Autoencoder scores calculés")

    # 5. Ensemble IF + LOF + AE (meilleur modèle)
    if sc_ae is not None and "Isolation Forest" in scores and "LOF" in scores:
        try:
            cfg3 = load_ensemble_config(ENS3_FILE)
            t0 = time.perf_counter()
            sc_ens3 = get_ensemble3_scores(
                scores["Isolation Forest"], scores["LOF"], sc_ae, cfg3
            )
            t_ens3 = time.perf_counter() - t0
            name_ens3 = f"Ensemble IF({cfg3['w_if']})+LOF({cfg3['w_lof']})+AE({cfg3['w_ae']})"
            scores[name_ens3] = sc_ens3
            metrics_list.append(compute_metrics(
                name_ens3, y_test,
                scores_to_preds(sc_ens3), sc_ens3, t_ens3,
            ))
            logger.info("Ensemble 3 modèles scores calculés")
        except ModelError as e:
            logger.warning(f"Ensemble 3 non disponible : {e.message}")

    # Calcul du score de sélection composite
    if metrics_list:
        metrics_list = compute_perf_score(metrics_list)

    state["all_scores"]    = scores
    state["metrics_list"]  = metrics_list
    state["best_model_name"] = metrics_list[0]["model"] if metrics_list else ""


# ── GET /api/models/compare ───────────────────────────────────────────────────

@router.get("/compare", summary="Tableau comparatif de tous les modèles")
def compare_models(request: Request):
    """
    Retourne le tableau comparatif complet pour la **Page 2**.

    Métriques calculées sur le test set (82 332 connexions) :
    - Precision, Recall, F1-Score, ROC-AUC, Average Precision
    - Score de sélection composite : 0.35×AUC + 0.30×F1 + 0.20×Recall + 0.15×Precision
    - Temps d'inférence

    **Modèle sélectionné** : Ensemble IF(0.1)+LOF(0.1)+AE(0.8)
    → F1=0.8443, ROC-AUC=0.9069, Score=0.9597

    Si `data/reports/model_comparison.csv` existe (produit par notebook 07),
    les métriques sont retournées directement depuis ce fichier.
    Sinon, elles sont recalculées à la demande.
    """
    state = get_state(request)

    try:
        # Essayer d'abord le CSV pré-calculé du notebook 07
        df_report = load_model_comparison()
        if df_report is not None and "all_scores" not in state:
            # Retourner les métriques du CSV directement (réponse rapide)
            records = df_report.reset_index().rename(columns={"index": "model"}).to_dict(orient="records")

            # Préchauffer le cache en arrière-plan pour que /viz soit rapide
            def _warm_cache(s):
                try:
                    _ensure_scores(s)
                    logger.info("[COMPARE] Cache scores préchauffé en arrière-plan.")
                except Exception as bg_exc:
                    logger.warning(f"[COMPARE] Préchauffage échoué : {bg_exc}")

            threading.Thread(target=_warm_cache, args=(state,), daemon=True).start()

            return {
                "status":       200,
                "source":       "model_comparison.csv (notebook 07)",
                "n_models":     len(records),
                "metrics":      records,
                "best_model":   records[0]["model"] if records else "",
            }

        # Sinon recalculer de façon synchrone
        _ensure_scores(state)
        return {
            "status":      200,
            "source":      "recalculé sur test set",
            "n_models":    len(state["metrics_list"]),
            "metrics":     state["metrics_list"],
            "best_model":  state["best_model_name"],
        }

    except DataLoadError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception:
        logger.exception("[COMPARE] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")


# ── GET /api/models/viz ───────────────────────────────────────────────────────

@router.get("/viz", summary="Données graphiques pour Page 2")
def get_visualization(
    request: Request,
    type: Literal["pca", "scores", "confusion", "roc"] = Query(
        default="pca",
        description="Type : pca | scores | confusion | roc",
    ),
    model: str = Query(
        default="Ensemble IF(0.1)+LOF(0.1)+AE(0.8)",
        description="Nom du modèle pour PCA (ignoré pour scores/confusion/roc)",
    ),
):
    """
    Données structurées pour les graphiques Plotly de la **Page 2**.

    - **pca** : scatter plot 2D des données réduites par PCA
    - **scores** : histogrammes des scores d'anomalie par modèle
    - **confusion** : matrices de confusion de tous les modèles
    - **roc** : courbes ROC comparatives de tous les modèles
    """
    state = get_state(request)

    try:
        _ensure_scores(state)

        X_qt        = state["X_test_qt"]
        y_test      = state["y_test"]
        all_scores  = state["all_scores"]
        metrics_list = state["metrics_list"]

        if type == "pca":
            # Utiliser les scores du modèle demandé, ou le premier disponible
            chosen = model if model in all_scores else (list(all_scores.keys())[-1] if all_scores else None)
            if chosen is None:
                raise HTTPException(status_code=400, detail="Aucun score disponible.")
            sc     = all_scores[chosen]
            preds  = scores_to_preds(sc)
            data   = get_pca_data(X=X_qt, labels=preds, scores=sc)
            data["model_used"] = chosen

        elif type == "scores":
            data = get_score_distributions(all_scores, y_test)

        elif type == "confusion":
            data = get_confusion_matrix_data(metrics_list)

        elif type == "roc":
            # Courbes ROC déjà calculées dans compute_metrics
            data = {
                m["model"]: m["roc_curve"]
                for m in metrics_list
                if "roc_curve" in m
            }

        return {"status": 200, "type": type, "data": data}

    except HTTPException:
        raise
    except Exception:
        logger.exception("[VIZ] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")