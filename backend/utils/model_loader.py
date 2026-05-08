"""Model loading and inference utilities for the deployed anomaly detectors."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from config import (
    AE_FILE,
    AE_INPUT_DIM,
    CONTAMINATION,
    ENS2_FILE,
    ENS3_FILE,
    FEATURE_NAMES,
    IF_FILE,
    LOF_FILE,
    QT_FILE,
    SCALER_FILE,
    SELECTED_FEATURES_FILE,
)
from utils.exceptions import ModelError

logger = logging.getLogger(__name__)


def normalize_scores(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float32)
    s_min = float(np.min(scores))
    s_max = float(np.max(scores))
    if s_max == s_min:
        return np.zeros_like(scores, dtype=np.float32)
    return ((scores - s_min) / (s_max - s_min)).astype(np.float32)


def normalize_with_reference(scores: np.ndarray, reference_scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float32)
    reference_scores = np.asarray(reference_scores, dtype=np.float32)
    r_min = float(np.min(reference_scores))
    r_max = float(np.max(reference_scores))
    if r_max == r_min:
        return np.zeros_like(scores, dtype=np.float32)
    return np.clip((scores - r_min) / (r_max - r_min), 0.0, 1.0).astype(np.float32)


def percentile_rank(value: float, reference_scores: np.ndarray) -> float:
    sorted_ref = np.sort(np.asarray(reference_scores, dtype=np.float32))
    if len(sorted_ref) == 0:
        return 0.0
    return float(np.searchsorted(sorted_ref, value, side="right") / len(sorted_ref))


def scores_to_preds(scores: np.ndarray, contamination: float = CONTAMINATION) -> np.ndarray:
    threshold = np.percentile(scores, 100 * (1 - contamination))
    return np.where(scores >= threshold, 1, 0).astype(np.int8)


def score_threshold(scores: np.ndarray, contamination: float = CONTAMINATION) -> float:
    return float(np.percentile(scores, 100 * (1 - contamination)))


def _load_pickle(path: Path, label: str):
    if not path.exists():
        raise ModelError(f"{label} not found.", details=str(path))
    try:
        return joblib.load(path)
    except Exception as exc:
        raise ModelError(f"Could not load {label}.", details=str(exc)) from exc


@lru_cache(maxsize=1)
def load_qt():
    qt = _load_pickle(QT_FILE, "QuantileTransformer")
    logger.info("QuantileTransformer loaded from %s", QT_FILE)
    return qt


@lru_cache(maxsize=1)
def load_scaler():
    scaler = _load_pickle(SCALER_FILE, "RobustScaler")
    logger.info("RobustScaler loaded from %s", SCALER_FILE)
    return scaler


@lru_cache(maxsize=1)
def load_isolation_forest():
    model = _load_pickle(IF_FILE, "Isolation Forest")
    logger.info("Isolation Forest loaded from %s", IF_FILE)
    return model


@lru_cache(maxsize=1)
def load_lof():
    model = _load_pickle(LOF_FILE, "Local Outlier Factor")
    logger.info("LOF loaded from %s", LOF_FILE)
    return model


@lru_cache(maxsize=2)
def load_ensemble_config(ens_file: Path = ENS3_FILE) -> dict:
    cfg = _load_pickle(ens_file, "ensemble configuration")
    if not isinstance(cfg, dict):
        raise ModelError("Ensemble configuration must be a dictionary.", details=str(ens_file))
    return cfg


@lru_cache(maxsize=1)
def load_selected_features() -> list[str]:
    if SELECTED_FEATURES_FILE.exists():
        features = joblib.load(SELECTED_FEATURES_FILE)
        if isinstance(features, list) and features:
            return features
    return FEATURE_NAMES


@lru_cache(maxsize=1)
def load_autoencoder():
    """Return (model, device), or (None, None) when PyTorch is unavailable."""

    if not AE_FILE.exists():
        logger.warning("Autoencoder not found: %s", AE_FILE)
        return None, None

    try:
        import torch
        import torch.nn as nn
    except ImportError:
        logger.warning("PyTorch is not installed; autoencoder disabled.")
        return None, None

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = nn.Sequential(
        nn.Linear(AE_INPUT_DIM, 16),
        nn.ReLU(),
        nn.Linear(16, 8),
        nn.ReLU(),
        nn.Linear(8, 4),
        nn.Linear(4, 8),
        nn.ReLU(),
        nn.Linear(8, 16),
        nn.ReLU(),
        nn.Linear(16, AE_INPUT_DIM),
    ).to(device)

    try:
        state_dict = torch.load(AE_FILE, map_location=device)
        model.load_state_dict(state_dict)
        model.eval()
    except Exception as exc:
        raise ModelError("Could not load the autoencoder.", details=str(exc)) from exc

    logger.info("Autoencoder loaded from %s on %s", AE_FILE, device)
    return model, device


def ensure_feature_frame(X) -> pd.DataFrame:
    if isinstance(X, pd.DataFrame):
        return X[load_selected_features()].astype(np.float32)
    return pd.DataFrame(X, columns=load_selected_features()).astype(np.float32)


def transform_features(X) -> np.ndarray:
    return load_qt().transform(ensure_feature_frame(X))


def get_if_raw_scores(if_model, X_qt: np.ndarray) -> np.ndarray:
    """Isolation Forest raw anomaly score; higher means more anomalous in this project."""

    return if_model.decision_function(X_qt).astype(np.float32)


def get_lof_raw_scores(lof_model, X_qt: np.ndarray) -> np.ndarray:
    """LOF raw anomaly score; sklearn returns lower scores for outliers."""

    return (-lof_model.score_samples(X_qt)).astype(np.float32)


def get_ae_raw_scores(ae_model, device, X_qt: np.ndarray) -> np.ndarray:
    if ae_model is None:
        return np.zeros(X_qt.shape[0], dtype=np.float32)

    import torch

    X_t = torch.as_tensor(X_qt, dtype=torch.float32, device=device)
    with torch.no_grad():
        recon = ae_model(X_t)
        errors = ((X_t - recon) ** 2).mean(dim=1).detach().cpu().numpy()
    return errors.astype(np.float32)


def get_if_scores(if_model, X_qt: np.ndarray) -> np.ndarray:
    return normalize_scores(get_if_raw_scores(if_model, X_qt))


def get_lof_scores(lof_model, X_qt: np.ndarray) -> np.ndarray:
    return normalize_scores(get_lof_raw_scores(lof_model, X_qt))


def get_ae_scores(ae_model, device, X_qt: np.ndarray) -> np.ndarray:
    return normalize_scores(get_ae_raw_scores(ae_model, device, X_qt))


def get_ensemble3_scores(
    scores_if: np.ndarray,
    scores_lof: np.ndarray,
    scores_ae: np.ndarray,
    cfg: dict,
) -> np.ndarray:
    return (
        float(cfg.get("w_if", 0.0)) * scores_if
        + float(cfg.get("w_lof", 0.0)) * scores_lof
        + float(cfg.get("w_ae", 0.0)) * scores_ae
    ).astype(np.float32)


def get_ensemble2_scores(scores_if: np.ndarray, scores_lof: np.ndarray, cfg: dict) -> np.ndarray:
    return (
        float(cfg.get("w_if", 0.0)) * scores_if
        + float(cfg.get("w_lof", 0.0)) * scores_lof
    ).astype(np.float32)


def available_model_files() -> dict[str, bool]:
    return {
        "quantile_transformer": QT_FILE.exists(),
        "robust_scaler": SCALER_FILE.exists(),
        "isolation_forest": IF_FILE.exists(),
        "lof": LOF_FILE.exists(),
        "autoencoder": AE_FILE.exists(),
        "ensemble_if_lof": ENS2_FILE.exists(),
        "ensemble_if_lof_ae": ENS3_FILE.exists(),
    }
