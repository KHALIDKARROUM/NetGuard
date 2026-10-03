"""Current data/evaluation utilities; historical model loading is opt-in."""

from backend.utils.data_loader import (
    DataLoader,
    get_dataset_overview,
    get_feature_distributions,
    load_model_comparison,
    load_raw_test_data,
    load_test_clean_data,
    load_test_data,
    load_train_data,
    read_csv_chunks,
)
from backend.utils.evaluator import (
    compute_metrics,
    compute_perf_score,
    get_confusion_matrix_data,
    get_pca_data,
    get_score_distribution,
    get_score_distributions,
)
from backend.utils.exceptions import APIError, DataLoadError, ModelError

__all__ = [
    "APIError",
    "DataLoadError",
    "ModelError",
    "DataLoader",
    "read_csv_chunks",
    "load_test_data",
    "load_train_data",
    "load_test_clean_data",
    "load_raw_test_data",
    "load_model_comparison",
    "get_dataset_overview",
    "get_feature_distributions",
    "compute_metrics",
    "compute_perf_score",
    "get_pca_data",
    "get_score_distribution",
    "get_score_distributions",
    "get_confusion_matrix_data",
]
