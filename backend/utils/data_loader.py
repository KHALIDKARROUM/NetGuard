"""Data loading helpers for datasets produced by the notebooks."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd

from config import (
    CHUNK_SIZE,
    FEATURE_NAMES,
    MODEL_COMPARISON_FILE,
    RAW_TEST_FILE,
    TARGET_COLUMN,
    TEST_CLEAN_FILE,
    TEST_FEATURED_FILE,
    TRAIN_FEATURED_FILE,
    VIZ_MAX_POINTS,
)
from utils.exceptions import DataLoadError

logger = logging.getLogger(__name__)


def _missing_file(path: Path, stage: str) -> DataLoadError:
    return DataLoadError(
        f"Required file not found: {path.name}",
        details=f"{path}. Run the notebook pipeline through {stage}.",
    )


def _read_csv(path: Path, stage: str, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise _missing_file(path, stage)
    df = pd.read_csv(path, **kwargs)
    return df.replace([np.inf, -np.inf], np.nan).fillna(0)


def read_csv_chunks(
    filepath: Path,
    chunksize: int = CHUNK_SIZE,
) -> Generator[pd.DataFrame, None, None]:
    """Read a CSV file in chunks."""

    if not filepath.exists():
        raise _missing_file(filepath, "the data preparation notebooks")
    for chunk in pd.read_csv(filepath, chunksize=chunksize):
        yield chunk.replace([np.inf, -np.inf], np.nan).fillna(0)


@lru_cache(maxsize=1)
def load_test_frame() -> pd.DataFrame:
    logger.info("Loading featured test data from %s", TEST_FEATURED_FILE)
    df = _read_csv(TEST_FEATURED_FILE, "notebooks 01-03")
    missing = [col for col in [*FEATURE_NAMES, TARGET_COLUMN] if col not in df.columns]
    if missing:
        raise DataLoadError(
            "Featured test data has missing columns.",
            details=", ".join(missing),
        )
    return df


@lru_cache(maxsize=1)
def load_train_frame() -> pd.DataFrame:
    logger.info("Loading featured train data from %s", TRAIN_FEATURED_FILE)
    return _read_csv(TRAIN_FEATURED_FILE, "notebooks 01-03")


@lru_cache(maxsize=1)
def load_test_clean_data() -> pd.DataFrame:
    logger.info("Loading clean test data from %s", TEST_CLEAN_FILE)
    return _read_csv(TEST_CLEAN_FILE, "notebook 02")


@lru_cache(maxsize=1)
def load_raw_test_data() -> pd.DataFrame:
    logger.info("Loading raw test data from %s", RAW_TEST_FILE)
    return _read_csv(RAW_TEST_FILE, "the raw data download")


def load_test_data() -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    """Return X_test as a DataFrame, y_test, and the full featured frame."""

    df = load_test_frame()
    X = df[FEATURE_NAMES].astype(np.float32)
    y = df[TARGET_COLUMN].astype(np.int8).to_numpy()
    return X, y, df


def load_train_data() -> tuple[pd.DataFrame, np.ndarray]:
    df = load_train_frame()
    feature_cols = [col for col in df.columns if col != TARGET_COLUMN]
    X = df[feature_cols].astype(np.float32)
    y = df[TARGET_COLUMN].astype(np.int8).to_numpy()
    return X, y


def load_model_comparison() -> pd.DataFrame | None:
    """Load the precomputed model comparison table when available."""

    if not MODEL_COMPARISON_FILE.exists():
        logger.warning("Model comparison report not found: %s", MODEL_COMPARISON_FILE)
        return None

    try:
        df = pd.read_csv(MODEL_COMPARISON_FILE, index_col=0)
    except Exception as exc:
        logger.warning("Could not read model comparison report: %s", exc)
        return None

    if df.empty:
        return None
    df.index.name = "model"
    return df


def get_dataset_overview(df_test: pd.DataFrame) -> dict:
    y = df_test[TARGET_COLUMN].astype(int)
    feature_cols = [col for col in df_test.columns if col != TARGET_COLUMN]
    numeric = df_test[feature_cols].select_dtypes(include=[np.number])
    stats = numeric.describe(percentiles=[0.25, 0.5, 0.75, 0.95]).T

    try:
        train_rows = int(sum(1 for _ in read_csv_chunks(TRAIN_FEATURED_FILE)))
        # Chunk count is not row count; fall back to the known full load below.
        train_rows = int(len(load_train_frame()))
    except Exception:
        train_rows = 175_341

    n_total = int(len(df_test))
    n_anomaly = int(y.sum())
    n_normal = int((y == 0).sum())

    return {
        "test_set": {
            "n_rows": n_total,
            "n_features": len(feature_cols),
            "n_anomalies": n_anomaly,
            "n_normal": n_normal,
            "anomaly_rate": round(100 * n_anomaly / max(n_total, 1), 2),
        },
        "train_set": {
            "n_rows": train_rows,
            "n_features": len(feature_cols),
        },
        "feature_names": feature_cols,
        "numeric_stats": {
            col: {name: round(float(value), 4) for name, value in stats.loc[col].items()}
            for col in stats.index
        },
    }


def _series_stats(series: pd.Series) -> dict:
    series = series.dropna()
    if series.empty:
        return {}
    return {
        "mean": round(float(series.mean()), 4),
        "std": round(float(series.std()), 4),
        "p50": round(float(np.percentile(series, 50)), 4),
        "p95": round(float(np.percentile(series, 95)), 4),
    }


def get_feature_distributions(df_test: pd.DataFrame, top_n: int = 10) -> dict:
    """Return sampled normal/anomaly distributions for selected features."""

    feature_cols = [col for col in FEATURE_NAMES if col in df_test.columns][:top_n]
    sample_size = max(100, VIZ_MAX_POINTS // 2)
    result: dict[str, dict] = {}

    for feature in feature_cols:
        normal = df_test.loc[df_test[TARGET_COLUMN] == 0, feature].dropna()
        anomaly = df_test.loc[df_test[TARGET_COLUMN] == 1, feature].dropna()
        result[feature] = {
            "normal": normal.sample(min(len(normal), sample_size), random_state=42).tolist(),
            "anomaly": anomaly.sample(min(len(anomaly), sample_size), random_state=42).tolist(),
            "stats_normal": _series_stats(normal),
            "stats_anomaly": _series_stats(anomaly),
        }

    return result


class DataLoader:
    """Compatibility wrapper used by older route code."""

    def load_test(self) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
        return load_test_data()

    def load_train(self) -> tuple[pd.DataFrame, np.ndarray]:
        return load_train_data()

    def load_model_comparison(self) -> pd.DataFrame | None:
        return load_model_comparison()

    def get_overview(self, df_test: pd.DataFrame) -> dict:
        return get_dataset_overview(df_test)

    def get_feature_distributions(self, df_test: pd.DataFrame, top_n: int = 10) -> dict:
        return get_feature_distributions(df_test, top_n=top_n)
