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
]