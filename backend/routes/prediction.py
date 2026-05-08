"""Single-connection prediction routes."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from config import (
    CONTAMINATION,
    EDITABLE_INPUT_FIELDS,
    ENS3_FILE,
    FEATURE_NAMES,
    INFERRED_RAW_FIELDS,
    REFERENCE_SAMPLE_SIZE,
    TARGET_COLUMN,
)
from utils.data_loader import load_model_comparison, load_raw_test_data, load_test_clean_data, load_test_data
from utils.exceptions import DataLoadError, ModelError
from utils.model_loader import (
    available_model_files,
    get_ae_raw_scores,
    get_ensemble3_scores,
    get_if_raw_scores,
    get_lof_raw_scores,
    load_autoencoder,
    load_ensemble_config,
    load_isolation_forest,
    load_lof,
    load_qt,
    load_scaler,
    normalize_scores,
    normalize_with_reference,
    percentile_rank,
    score_threshold,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/predict", tags=["Prediction"])


class ConnectionRequest(BaseModel):
    sbytes: int = Field(default=1500, ge=0, description="Source bytes")
    dbytes: int = Field(default=5000, ge=0, description="Destination bytes")
    spkts: int = Field(default=10, ge=0, description="Source packets")
    dpkts: int = Field(default=15, ge=0, description="Destination packets")
    dur: float = Field(default=0.5, ge=0, description="Connection duration in seconds")
    rate: float = Field(default=20.0, ge=0, description="Transfer rate")
    sload: float = Field(default=0.0, ge=0, description="Source load")
    dload: float = Field(default=0.0, ge=0, description="Destination load")
    sttl: int = Field(default=64, ge=0, le=255, description="Source TTL")
    dttl: int = Field(default=64, ge=0, le=255, description="Destination TTL")

    @field_validator("spkts", "dpkts")
    @classmethod
    def packet_count_is_reasonable(cls, value: int) -> int:
        if value > 2_000_000:
            raise ValueError("Packet counts above 2,000,000 are not accepted.")
        return value


EDITABLE_INPUTS = [
    {"name": "sbytes", "label": "Bytes sent", "type": "int"},
    {"name": "dbytes", "label": "Bytes received", "type": "int"},
    {"name": "spkts", "label": "Packets sent", "type": "int"},
    {"name": "dpkts", "label": "Packets received", "type": "int"},
    {"name": "dur", "label": "Duration", "type": "float"},
    {"name": "rate", "label": "Rate", "type": "float"},
    {"name": "sload", "label": "Source load", "type": "float"},
    {"name": "dload", "label": "Destination load", "type": "float"},
    {"name": "sttl", "label": "Source TTL", "type": "int"},
    {"name": "dttl", "label": "Destination TTL", "type": "int"},
]

DEFAULT_INPUT = {
    "sbytes": 1500,
    "dbytes": 5000,
    "spkts": 10,
    "dpkts": 15,
    "dur": 0.5,
    "rate": 20.0,
    "sload": 0.0,
    "dload": 0.0,
    "sttl": 64,
    "dttl": 64,
}


def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "cache"):
        request.app.state.cache = {}
    return request.app.state.cache


def _best_model_name(cfg: dict) -> str:
    return f"Ensemble IF({cfg['w_if']:.1f})+LOF({cfg['w_lof']:.1f})+AE({cfg['w_ae']:.1f})"


def _scaler_stats(scaler) -> dict[str, tuple[float, float]]:
    names = list(getattr(scaler, "feature_names_in_", []))
    centers = getattr(scaler, "center_", np.zeros(len(names), dtype=np.float32))
    scales = getattr(scaler, "scale_", np.ones(len(names), dtype=np.float32))
    return {
        name: (float(centers[idx]), float(scales[idx]) if float(scales[idx]) else 1.0)
        for idx, name in enumerate(names)
    }


def _scale_raw(value: float, feature: str, stats: dict[str, tuple[float, float]]) -> float:
    center, scale = stats[feature]
    return float((float(value) - center) / scale)


def _build_lookup(stats: dict[str, tuple[float, float]]) -> tuple[np.ndarray, pd.DataFrame]:
    raw_df = load_raw_test_data()
    lookup_fields = [field for field in EDITABLE_INPUT_FIELDS if field in raw_df.columns and field in stats]
    hidden_fields = [field for field in INFERRED_RAW_FIELDS if field in raw_df.columns]
    if not lookup_fields or not hidden_fields:
        return np.empty((0, len(EDITABLE_INPUT_FIELDS)), dtype=np.float32), pd.DataFrame()

    lookup = raw_df[lookup_fields].fillna(0).astype(float).copy()
    for field in lookup_fields:
        lookup[field] = lookup[field].map(lambda value: _scale_raw(value, field, stats))

    return lookup.to_numpy(dtype=np.float32), raw_df[hidden_fields].fillna(0).astype(float)


def _infer_hidden_fields(
    form: dict[str, Any],
    lookup_matrix: np.ndarray,
    hidden_df: pd.DataFrame,
    stats: dict[str, tuple[float, float]],
    k_neighbors: int = 5,
) -> dict[str, float]:
    if lookup_matrix.size == 0 or hidden_df.empty:
        spkts = max(float(form["spkts"]), 1.0)
        dpkts = max(float(form["dpkts"]), 1.0)
        return {
            "ct_state_ttl": 0.0,
            "smean": float(form["sbytes"]) / spkts,
            "dmean": float(form["dbytes"]) / dpkts,
            "dinpkt": float(form["dur"]) / (dpkts + 1.0),
        }

    query = np.array(
        [_scale_raw(float(form[field]), field, stats) for field in EDITABLE_INPUT_FIELDS],
        dtype=np.float32,
    )
    distances = np.sum((lookup_matrix - query) ** 2, axis=1)
    k = min(k_neighbors, len(distances))
    nearest_idx = np.argpartition(distances, kth=k - 1)[:k]
    nearest = hidden_df.iloc[nearest_idx]

    inferred = {}
    for field in INFERRED_RAW_FIELDS:
        if field in nearest:
            inferred[field] = float(np.median(nearest[field].astype(float).to_numpy()))
    return inferred


def _build_feature_row(
    form: dict[str, Any],
    clean_defaults: dict[str, float],
    stats: dict[str, tuple[float, float]],
    lookup_matrix: np.ndarray,
    hidden_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    row_clean = dict(clean_defaults)

    for field in EDITABLE_INPUT_FIELDS:
        if field in stats:
            row_clean[field] = _scale_raw(float(form[field]), field, stats)

    inferred_raw = _infer_hidden_fields(form, lookup_matrix, hidden_df, stats)
    for field, raw_value in inferred_raw.items():
        if field in stats:
            row_clean[field] = _scale_raw(raw_value, field, stats)

    sbytes = float(row_clean.get("sbytes", 0.0))
    dbytes = float(row_clean.get("dbytes", 0.0))
    spkts = float(row_clean.get("spkts", 0.0))
    dpkts = float(row_clean.get("dpkts", 0.0))

    row_featured = {feature: float(row_clean.get(feature, 0.0)) for feature in FEATURE_NAMES}
    row_featured.update(
        {
            "bytes_total": sbytes + dbytes,
            "bytes_per_pkt_src": sbytes / (spkts + 1.0),
            "bytes_ratio": sbytes / (dbytes + 1.0),
            "bytes_diff_norm": abs(sbytes - dbytes) / (sbytes + dbytes + 1.0),
            "bytes_per_pkt_dst": dbytes / (dpkts + 1.0),
            "pkts_total": spkts + dpkts,
            "log1p_dbytes": float(np.log1p(np.clip(dbytes, 0.0, None))),
        }
    )

    frame = pd.DataFrame([{feature: row_featured[feature] for feature in FEATURE_NAMES}], columns=FEATURE_NAMES)
    return frame.astype(np.float32), inferred_raw


def _ensure_prediction_bundle(state: dict) -> dict:
    if "prediction_bundle" in state:
        return state["prediction_bundle"]

    scaler = load_scaler()
    stats = _scaler_stats(scaler)
    clean_df = load_test_clean_data()
    clean_feature_cols = [col for col in clean_df.columns if col != TARGET_COLUMN]
    clean_defaults = {
        col: float(clean_df[col].median())
        for col in clean_feature_cols
        if pd.api.types.is_numeric_dtype(clean_df[col])
    }

    lookup_matrix, hidden_df = _build_lookup(stats)
    X_test, _, _ = load_test_data()
    n_ref = min(len(X_test), REFERENCE_SAMPLE_SIZE)
    X_ref = X_test.sample(n=n_ref, random_state=42) if len(X_test) > n_ref else X_test

    qt = load_qt()
    X_ref_qt = qt.transform(X_ref)
    if_model = load_isolation_forest()
    lof_model = load_lof()
    ae_model, device = load_autoencoder()
    cfg = load_ensemble_config(ENS3_FILE)

    raw_if_ref = get_if_raw_scores(if_model, X_ref_qt)
    raw_lof_ref = get_lof_raw_scores(lof_model, X_ref_qt)
    raw_ae_ref = get_ae_raw_scores(ae_model, device, X_ref_qt)

    scores_if_ref = normalize_scores(raw_if_ref)
    scores_lof_ref = normalize_scores(raw_lof_ref)
    scores_ae_ref = normalize_scores(raw_ae_ref)
    final_ref = get_ensemble3_scores(scores_if_ref, scores_lof_ref, scores_ae_ref, cfg)

    bundle = {
        "qt": qt,
        "if_model": if_model,
        "lof_model": lof_model,
        "ae_model": ae_model,
        "device": device,
        "cfg": cfg,
        "stats": stats,
        "clean_defaults": clean_defaults,
        "lookup_matrix": lookup_matrix,
        "hidden_df": hidden_df,
        "raw_ref": {
            "if": raw_if_ref,
            "lof": raw_lof_ref,
            "ae": raw_ae_ref,
        },
        "final_ref": final_ref,
        "threshold": score_threshold(final_ref, cfg.get("contamination", CONTAMINATION)),
        "model_name": _best_model_name(cfg),
    }
    state["prediction_bundle"] = bundle
    return bundle


def _best_metrics_from_report(model_name: str) -> dict:
    df_report = load_model_comparison()
    if df_report is None or df_report.empty:
        return {}

    if model_name in df_report.index:
        row = df_report.loc[model_name]
    else:
        row = df_report.iloc[0]
    return {
        "f1": round(float(row.get("f1", 0.0)), 4),
        "roc_auc": round(float(row.get("roc_auc", 0.0)), 4),
        "precision": round(float(row.get("precision", 0.0)), 4),
        "recall": round(float(row.get("recall", 0.0)), 4),
        "perf_score": round(float(row.get("perf_score", 0.0)), 4),
    }


@router.get("/best_model", summary="Information about the deployed model")
def get_best_model(request: Request):
    try:
        cfg = load_ensemble_config(ENS3_FILE)
        model_name = _best_model_name(cfg)
        return {
            "status": 200,
            "best_model": {
                "name": model_name,
                "threshold": "calibrated at inference",
                "threshold_value": None,
                "contamination": round(float(cfg.get("contamination", CONTAMINATION)), 4),
                "components": [
                    {"name": "Isolation Forest", "weight": float(cfg.get("w_if", 0.0))},
                    {"name": "LOF", "weight": float(cfg.get("w_lof", 0.0))},
                    {"name": "Autoencoder", "weight": float(cfg.get("w_ae", 0.0))},
                ],
                "metrics": _best_metrics_from_report(model_name),
                "files": available_model_files(),
            },
            "editable_inputs": EDITABLE_INPUTS,
            "defaults": DEFAULT_INPUT,
        }
    except (DataLoadError, ModelError) as exc:
        raise HTTPException(status_code=503, detail=exc.message)
    except Exception:
        logger.exception("Best model info failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/info", summary="Compatibility alias for /api/predict/best_model")
def get_model_info(request: Request):
    return get_best_model(request)


@router.post("/single", summary="Predict one network connection")
def predict_single(payload: ConnectionRequest, request: Request):
    try:
        form = payload.model_dump()
        bundle = _ensure_prediction_bundle(get_state(request))
        X_row, inferred_raw = _build_feature_row(
            form,
            bundle["clean_defaults"],
            bundle["stats"],
            bundle["lookup_matrix"],
            bundle["hidden_df"],
        )
        X_qt = bundle["qt"].transform(X_row)

        raw_if = get_if_raw_scores(bundle["if_model"], X_qt)
        raw_lof = get_lof_raw_scores(bundle["lof_model"], X_qt)
        raw_ae = get_ae_raw_scores(bundle["ae_model"], bundle["device"], X_qt)

        score_if = normalize_with_reference(raw_if, bundle["raw_ref"]["if"])
        score_lof = normalize_with_reference(raw_lof, bundle["raw_ref"]["lof"])
        score_ae = normalize_with_reference(raw_ae, bundle["raw_ref"]["ae"])
        final_score = get_ensemble3_scores(score_if, score_lof, score_ae, bundle["cfg"])

        score = float(final_score[0])
        threshold = float(bundle["threshold"])
        is_anomaly = bool(score >= threshold)
        percentile = percentile_rank(score, bundle["final_ref"])
        risk_level = "High" if score >= threshold else ("Watch" if percentile >= 0.75 else "Low")

        return {
            "status": 200,
            "model": bundle["model_name"],
            "prediction": {
                "label": int(is_anomaly),
                "class_name": "Anomaly" if is_anomaly else "Normal",
                "risk_level": risk_level,
            },
            "score": round(score, 6),
            "threshold": round(threshold, 6),
            "percentile": round(percentile, 6),
            "components": {
                "if": round(float(score_if[0]), 6),
                "lof": round(float(score_lof[0]), 6),
                "ae": round(float(score_ae[0]), 6),
                "final": round(score, 6),
            },
            "weights": {
                "if": float(bundle["cfg"].get("w_if", 0.0)),
                "lof": float(bundle["cfg"].get("w_lof", 0.0)),
                "ae": float(bundle["cfg"].get("w_ae", 0.0)),
            },
            "input": form,
            "inferred_raw": {key: round(float(value), 4) for key, value in inferred_raw.items()},
            "feature_vector": {
                key: round(float(value), 6)
                for key, value in X_row.iloc[0].to_dict().items()
            },
        }
    except (DataLoadError, ModelError) as exc:
        raise HTTPException(status_code=503, detail=exc.message)
    except Exception:
        logger.exception("Single prediction failed")
        raise HTTPException(status_code=500, detail="Internal server error.")
