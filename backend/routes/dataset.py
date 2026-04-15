"""
dataset.py — Page 1 : informations sur le dataset.

Routes :
  GET /api/dataset/info         → Vue d'ensemble + stats descriptives
  GET /api/dataset/sample       → Aperçu tabulaire (n premières lignes)
  GET /api/dataset/distributions → Distributions des features par classe
"""

import logging
import numpy as np
from fastapi import APIRouter, HTTPException, Request, Query

from utils.data_loader import (
    load_test_data, get_dataset_overview, get_feature_distributions,
)
from utils.exceptions import DataLoadError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dataset", tags=["Page 1 — Dataset"])


def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "app_state"):
        request.app.state.app_state = {}
    return request.app.state.app_state


# ── GET /api/dataset/info ─────────────────────────────────────────────────────

@router.get("/info", summary="Informations complètes sur le dataset")
def get_dataset_info(request: Request):
    """
    Retourne toutes les informations pour la **Page 1** :

    - Dimensions du train set et du test set
    - Taux d'anomalies (55.1% sur le test set UNSW-NB15)
    - Liste des 20 features utilisées
    - Statistiques descriptives (mean, std, percentiles) par feature
    - Distribution normal vs anomalie

    Les données viennent de `data/featured/test_featured.csv`
    produit par le notebook 03.
    """
    state = get_state(request)

    try:
        # Charger si pas déjà en mémoire
        if "df_test" not in state:
            X_test, y_test, df_test = load_test_data()
            state["X_test"]  = X_test
            state["y_test"]  = y_test
            state["df_test"] = df_test

        df_test  = state["df_test"]
        overview = get_dataset_overview(df_test)

        # Distribution des labels
        y = state["y_test"]
        label_dist = {
            "normal":   int((y == 0).sum()),
            "anomaly":  int((y == 1).sum()),
            "pie_chart": {
                "labels": ["Normal (0)", "Anomalie (1)"],
                "values": [int((y == 0).sum()), int((y == 1).sum())],
            },
        }

        return {
            "status":             200,
            "overview":           overview,
            "label_distribution": label_dist,
            "source_file":        "data/featured/test_featured.csv",
        }

    except DataLoadError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception:
        logger.exception("[DATASET INFO] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")


# ── GET /api/dataset/sample ───────────────────────────────────────────────────

@router.get("/sample", summary="Aperçu tabulaire du dataset")
def get_dataset_sample(
    request: Request,
    n: int = Query(default=100, ge=1, le=500, description="Nombre de lignes à retourner"),
):
    """
    Retourne les **n** premières lignes du test set pour l'affichage tabulaire.
    Utilisé par la Page 1 pour montrer un extrait des données.
    """
    state = get_state(request)

    try:
        if "df_test" not in state:
            X_test, y_test, df_test = load_test_data()
            state["X_test"]  = X_test
            state["y_test"]  = y_test
            state["df_test"] = df_test

        sample = state["df_test"].head(n)
        return {
            "status": 200,
            "n":      n,
            "sample": sample.to_dict(orient="records"),
        }

    except DataLoadError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception:
        logger.exception("[DATASET SAMPLE] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")


# ── GET /api/dataset/distributions ────────────────────────────────────────────

@router.get("/distributions", summary="Distributions des features par classe")
def get_distributions(
    request: Request,
    top_n: int = Query(default=10, ge=1, le=20, description="Nombre de features à inclure"),
):
    """
    Retourne la distribution des **top_n** features numériques,
    séparée entre trafic normal et anomalies.

    Utilisé par la Page 1 pour les histogrammes comparatifs Plotly.
    """
    state = get_state(request)

    try:
        if "df_test" not in state:
            X_test, y_test, df_test = load_test_data()
            state["X_test"]  = X_test
            state["y_test"]  = y_test
            state["df_test"] = df_test

        distributions = get_feature_distributions(state["df_test"], top_n=top_n)
        return {
            "status":        200,
            "top_n":         top_n,
            "distributions": distributions,
        }

    except DataLoadError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception:
        logger.exception("[DISTRIBUTIONS] Erreur inattendue")
        raise HTTPException(status_code=500, detail="Erreur interne.")