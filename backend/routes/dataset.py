"""
<<<<<<< HEAD
routes/dataset.py — Page 1 : informations sur le dataset.

Routes :
    GET /api/dataset/info          → Vue d'ensemble + statistiques
    GET /api/dataset/sample        → Aperçu tabulaire (n premières lignes)
    GET /api/dataset/distributions → Distributions des features par classe
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Query

from utils import DataLoader, DataLoadError
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dataset", tags=["Page 1 — Dataset"])


<<<<<<< HEAD
def _get_data_loader(request: Request) -> DataLoader:
    """
    Retourne le DataLoader partagé depuis l'état de l'app.
    On crée l'instance une seule fois au premier appel.
    """
    state = request.app.state
    if not hasattr(state, "data_loader"):
        state.data_loader = DataLoader()
    return state.data_loader
=======
def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "app_state"):
        request.app.state.app_state = {}
    return request.app.state.app_state
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736


# ── GET /api/dataset/info ─────────────────────────────────────────────────────

@router.get("/info", summary="Informations complètes sur le dataset")
def get_dataset_info(request: Request):
    """
    Retourne toutes les informations pour la **Page 1** :

<<<<<<< HEAD
    - Dimensions du train set et du test set (175k / 82k lignes)
    - Taux d'anomalies (55.1% sur le test set UNSW-NB15)
    - Liste des 20 features utilisées
    - Statistiques descriptives (mean, std, percentiles) par feature

    Données depuis `data/featured/test_featured.csv`.
    """
    loader = _get_data_loader(request)

    try:
        _, y_test, df_test = loader.load_test()
        overview = loader.get_overview(df_test)

        label_dist = {
            "normal":  int((y_test == 0).sum()),
            "anomaly": int((y_test == 1).sum()),
            "pie_chart": {
                "labels": ["Normal (0)", "Anomalie (1)"],
                "values": [int((y_test == 0).sum()), int((y_test == 1).sum())],
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
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
<<<<<<< HEAD
    Retourne les **n** premières lignes du test set.
    Utilisé par la Page 1 pour montrer un extrait des données.
    """
    loader = _get_data_loader(request)

    try:
        _, _, df_test = loader.load_test()
        sample = df_test.head(n)
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
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
<<<<<<< HEAD
    top_n: int = Query(default=10, ge=1, le=20, description="Nombre de features"),
):
    """
    Distribution des **top_n** features numériques séparée entre trafic
    normal et anomalies. Utilisé pour les histogrammes de la Page 1.
    """
    loader = _get_data_loader(request)

    try:
        _, _, df_test = loader.load_test()
        distributions = loader.get_feature_distributions(df_test, top_n=top_n)
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
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