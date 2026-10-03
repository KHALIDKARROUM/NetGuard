"""Dataset exploration routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.utils.data_loader import (
    get_dataset_overview,
    get_feature_distributions,
    load_test_data,
)
from backend.utils.exceptions import DataLoadError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dataset", tags=["Dataset"])


@router.get("/info", summary="Dataset overview and descriptive statistics")
def get_dataset_info():
    try:
        _, y_test, df_test = load_test_data()
        overview = get_dataset_overview(df_test)
        n_normal = int((y_test == 0).sum())
        n_anomaly = int((y_test == 1).sum())
        return {
            "status": 200,
            "overview": overview,
            "label_distribution": {
                "normal": n_normal,
                "anomaly": n_anomaly,
                "pie_chart": {
                    "labels": ["Normal", "Anomaly"],
                    "values": [n_normal, n_anomaly],
                },
            },
            "source_file": "data/UNSW_NB15_testing-set.csv",
            "feature_representation": "shared raw physical features before scaling",
            "evaluation_status": "previously inspected benchmark; not an untouched holdout",
        }
    except DataLoadError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception:
        logger.exception("Dataset info failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/sample", summary="Sample rows from the featured test set")
def get_dataset_sample(
    n: int = Query(default=100, ge=1, le=500, description="Number of rows to return"),
):
    try:
        _, _, df_test = load_test_data()
        sample = df_test.head(n)
        return {
            "status": 200,
            "n": n,
            "sample": sample.to_dict(orient="records"),
        }
    except DataLoadError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception:
        logger.exception("Dataset sample failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/distributions", summary="Feature distributions by class")
def get_distributions(
    top_n: int = Query(default=10, ge=1, le=20, description="Number of features to include"),
):
    try:
        _, _, df_test = load_test_data()
        return {
            "status": 200,
            "top_n": top_n,
            "distributions": get_feature_distributions(df_test, top_n=top_n),
        }
    except DataLoadError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception:
        logger.exception("Dataset distributions failed")
        raise HTTPException(status_code=500, detail="Internal server error.")
