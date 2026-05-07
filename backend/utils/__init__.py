<<<<<<< HEAD
"""
utils/__init__.py — Exports publics du package utils.

On n'exporte que ce que les routes utilisent vraiment.
"""

from utils.exceptions import DataLoadError, ModelError, APIError
from utils.model_loader import BestModelLoader
from utils.data_loader import DataLoader, read_csv_chunks
from utils.evaluator import (
    compute_metrics,
    get_pca_data,
    get_score_distribution,
    get_confusion_matrix_data,
)

__all__ = [
    # Exceptions
    "DataLoadError", "ModelError", "APIError",
    # Chargement
    "BestModelLoader", "DataLoader", "read_csv_chunks",
    # Métriques et visualisation
    "compute_metrics", "get_pca_data",
    "get_score_distribution", "get_confusion_matrix_data",
=======
from utils.exceptions import DataLoadError, ModelError
from utils.model_loader import (
    load_qt, load_isolation_forest, load_lof,
    load_autoencoder, load_ensemble_config,
    normalize_scores, scores_to_preds,
    get_if_scores, get_lof_scores, get_ae_scores, get_ensemble3_scores,
)
from utils.data_loader import (
    load_test_data, load_train_data,
    load_model_comparison, get_dataset_overview, get_feature_distributions,
)
from utils.evaluator import (
    compute_metrics, compute_perf_score,
    get_pca_data, get_score_distributions, get_confusion_matrix_data,
)

__all__ = [
    "DataLoadError", "ModelError",
    "load_qt", "load_isolation_forest", "load_lof",
    "load_autoencoder", "load_ensemble_config",
    "normalize_scores", "scores_to_preds",
    "get_if_scores", "get_lof_scores", "get_ae_scores", "get_ensemble3_scores",
    "load_test_data", "load_train_data",
    "load_model_comparison", "get_dataset_overview", "get_feature_distributions",
    "compute_metrics", "compute_perf_score",
    "get_pca_data", "get_score_distributions", "get_confusion_matrix_data",
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
]