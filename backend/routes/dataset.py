"""
routes/dataset.py — Page 1 : informations sur le dataset.

Routes :
    GET /api/dataset/info          → Vue d'ensemble + statistiques
    GET /api/dataset/sample        → Aperçu tabulaire (n premières lignes)
    GET /api/dataset/distributions → Distributions des features par classe
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Query

from utils import DataLoader, DataLoadError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dataset", tags=["Page 1 — Dataset"])


def _get_data_loader(request: Request) -> DataLoader:
    """
    Retourne le DataLoader partagé depuis l'état de l'app.
    On crée l'instance une seule fois au premier appel.
    """
    state = request.app.state
    if not hasattr(state, "data_loader"):
        state.data_loader = DataLoader()
    return state.data_loader


# ── GET /api/dataset/info ─────────────────────────────────────────────────────

@router.get("/info", summary="Informations complètes sur le dataset")
def get_dataset_info(request: Request):
    """
    Retourne toutes les informations pour la **Page 1** :

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
    Retourne les **n** premières lignes du test set.
    Utilisé par la Page 1 pour montrer un extrait des données.
    """
    loader = _get_data_loader(request)

    try:
        _, _, df_test = loader.load_test()
        sample = df_test.head(n)
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