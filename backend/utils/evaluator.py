"""
evaluator.py — Calcul des métriques et données de visualisation.

Ce module ne fait que calculer — il ne charge aucun modèle ni aucun fichier.
Toutes les entrées sont des arrays numpy déjà calculés.

Utilisation :
    from utils.evaluator import compute_metrics, get_pca_data

    metrics = compute_metrics("Ensemble", y_true, y_pred, scores, t=0.42)
    pca     = get_pca_data(X_qt, preds, scores)
"""

import logging
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, average_precision_score,
    roc_curve,
)
from sklearn.decomposition import PCA

from config import VIZ_MAX_POINTS, PCA_N_COMPONENTS

logger = logging.getLogger(__name__)


def compute_metrics(
    name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: np.ndarray,
    inference_s: float = 0.0,
) -> dict:
    """
    Calcule toutes les métriques pour un modèle.

    Args:
        name (str)           : Nom du modèle.
        y_true (np.ndarray)  : Labels réels (0/1).
        y_pred (np.ndarray)  : Prédictions binaires (0/1).
        y_scores (np.ndarray): Scores continus [0,1].
        inference_s (float)  : Temps d'inférence en secondes.

    Returns:
        dict : precision, recall, f1, roc_auc, avg_precision,
               confusion_matrix, roc_curve, n_anomalies_detected.
    """
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    cm     = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    roc_auc  = float(roc_auc_score(y_true, y_scores))
    avg_prec = float(average_precision_score(y_true, y_scores))

    # Courbe ROC sous-échantillonnée pour alléger le JSON
    fpr_arr, tpr_arr, _ = roc_curve(y_true, y_scores)
    step = max(1, len(fpr_arr) // 500)
    roc_curve_data = {
        "fpr": fpr_arr[::step].tolist(),
        "tpr": tpr_arr[::step].tolist(),
    }

    metrics = {
        "model":      name,
        "precision":  round(float(report.get("1", {}).get("precision", 0)), 4),
        "recall":     round(float(report.get("1", {}).get("recall", 0)), 4),
        "f1":         round(float(report.get("1", {}).get("f1-score", 0)), 4),
        "roc_auc":    round(roc_auc, 4),
        "avg_precision": round(avg_prec, 4),
        "inference_s":   round(inference_s, 4),
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp),
            "fn": int(fn), "tp": int(tp),
        },
        "roc_curve":             roc_curve_data,
        "n_anomalies_detected":  int(y_pred.sum()),
        "n_true_anomalies":      int(y_true.sum()),
    }

    logger.info(
        f"[{name}] P={metrics['precision']}  R={metrics['recall']}  "
        f"F1={metrics['f1']}  AUC={metrics['roc_auc']}"
    )
    return metrics


def get_pca_data(
    X: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray | None = None,
) -> dict:
    """
    Réduit X en 2D avec PCA pour le scatter plot de la Page 2.

    Args:
        X (np.ndarray)      : Features (n_samples, n_features).
        labels (np.ndarray) : Prédictions 0/1.
        scores (np.ndarray) : Scores d'anomalie (optionnel, pour la couleur).

    Returns:
        dict: {x, y, labels, scores, explained_variance, pc1_label, pc2_label}
    """
    n = len(X)
    if n > VIZ_MAX_POINTS:
        idx    = np.random.choice(n, VIZ_MAX_POINTS, replace=False)
        X      = X[idx]
        labels = labels[idx]
        if scores is not None:
            scores = scores[idx]

    pca  = PCA(n_components=PCA_N_COMPONENTS, random_state=42)
    X_2d = pca.fit_transform(X)
    ev   = pca.explained_variance_ratio_.tolist()

    return {
        "x":      X_2d[:, 0].tolist(),
        "y":      X_2d[:, 1].tolist(),
        "labels": labels.tolist(),
        "scores": scores.tolist() if scores is not None else None,
        "explained_variance": ev,
        "pc1_label": f"PC1 ({ev[0]:.1%})",
        "pc2_label": f"PC2 ({ev[1]:.1%})",
    }


def get_score_distribution(
    scores: np.ndarray,
    y_true: np.ndarray,
    model_name: str,
) -> dict:
    """
    Distribution des scores d'anomalie séparée par classe (normal vs anomalie).
    Utilisé pour l'histogramme de la Page 2.

    Args:
        scores (np.ndarray) : Scores [0,1].
        y_true (np.ndarray) : Labels réels.
        model_name (str)    : Nom du modèle (pour la clé du résultat).

    Returns:
        dict: {model_name: {all, normal, anomaly, percentiles}}
    """
    n   = len(y_true)
    idx = np.random.choice(n, min(n, VIZ_MAX_POINTS), replace=False)
    sc  = scores[idx]
    y_s = y_true[idx]

    return {
        model_name: {
            "all":     sc.tolist(),
            "normal":  sc[y_s == 0].tolist(),
            "anomaly": sc[y_s == 1].tolist(),
            "percentiles": {
                "p50": round(float(np.percentile(sc, 50)), 4),
                "p90": round(float(np.percentile(sc, 90)), 4),
                "p95": round(float(np.percentile(sc, 95)), 4),
            },
        }
    }


def get_confusion_matrix_data(metrics: dict) -> dict:
    """
    Formate la matrice de confusion pour un heatmap Plotly.

    Args:
        metrics (dict) : Résultat de compute_metrics().

    Returns:
        dict: {model_name, z, x, y, f1, roc_auc}
    """
    cm = metrics["confusion_matrix"]
    return {
        "model_name": metrics["model"],
        "z":  [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]],
        "x":  ["Prédit Normal", "Prédit Anomalie"],
        "y":  ["Réel Normal",   "Réel Anomalie"],
        "f1":      metrics["f1"],
        "roc_auc": metrics["roc_auc"],
    }