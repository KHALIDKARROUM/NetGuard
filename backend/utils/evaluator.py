"""
evaluator.py — Calcule les métriques de comparaison pour la Page 2.
Reproduit exactement la logique du notebook 07 (register(), scores_to_preds()).

Les métriques peuvent être :
  - Chargées depuis data/reports/model_comparison.csv (déjà calculées)
  - Recalculées à la demande sur le test set
"""

import logging
import time
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, average_precision_score,
    f1_score, precision_score, recall_score,
    roc_curve,
)
from sklearn.decomposition import PCA

from config import CONTAMINATION, VIZ_MAX_POINTS, PCA_N_COMPONENTS

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
    Identique à la fonction register() du notebook 07.

    Args:
        name (str)           : Nom du modèle.
        y_true (np.ndarray)  : Labels réels.
        y_pred (np.ndarray)  : Prédictions binaires (0/1).
        y_scores (np.ndarray): Scores continus [0,1].
        inference_s (float)  : Temps d'inférence en secondes.

    Returns:
        dict: precision, recall, f1, roc_auc, avg_precision, confusion_matrix...
    """
    report  = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    cm      = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    roc_auc     = float(roc_auc_score(y_true, y_scores))
    avg_prec    = float(average_precision_score(y_true, y_scores))

    # Courbe ROC pour le graphique
    fpr_arr, tpr_arr, _ = roc_curve(y_true, y_scores)
    # Sous-échantillonnage de la courbe ROC pour alléger le JSON
    step = max(1, len(fpr_arr) // 500)
    roc_curve_data = {
        "fpr": fpr_arr[::step].tolist(),
        "tpr": tpr_arr[::step].tolist(),
    }

    metrics = {
        "model":           name,
        "precision":       round(float(report.get("1", {}).get("precision", 0)), 4),
        "recall":          round(float(report.get("1", {}).get("recall", 0)), 4),
        "f1":              round(float(report.get("1", {}).get("f1-score", 0)), 4),
        "roc_auc":         round(roc_auc, 4),
        "avg_precision":   round(avg_prec, 4),
        "inference_s":     round(inference_s, 4),
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp),
            "fn": int(fn), "tp": int(tp),
        },
        "roc_curve":       roc_curve_data,
        "n_anomalies_detected": int(y_pred.sum()),
        "n_true_anomalies":     int(y_true.sum()),
    }

    logger.info(
        f"[{name}]  P={metrics['precision']}  R={metrics['recall']}  "
        f"F1={metrics['f1']}  AUC={metrics['roc_auc']}"
    )
    return metrics


def compute_perf_score(metrics_list: list[dict]) -> list[dict]:
    """
    Calcule le score de sélection composite pour chaque modèle.
    Formule du notebook 07 :
      Score = 0.35 × ROC-AUC + 0.30 × F1 + 0.20 × Recall + 0.15 × Precision

    Args:
        metrics_list (list[dict]): Liste des métriques par modèle.

    Returns:
        list[dict]: Métriques enrichies avec perf_score, triées par score décroissant.
    """
    def norm(values):
        arr = np.array(values, dtype=float)
        mn, mx = arr.min(), arr.max()
        if mx == mn:
            return np.zeros_like(arr)
        return (arr - mn) / (mx - mn + 1e-9)

    roc_aucs   = norm([m["roc_auc"]   for m in metrics_list])
    f1s        = norm([m["f1"]        for m in metrics_list])
    recalls    = norm([m["recall"]    for m in metrics_list])
    precisions = norm([m["precision"] for m in metrics_list])

    for i, m in enumerate(metrics_list):
        m["perf_score"] = round(
            0.35 * roc_aucs[i] +
            0.30 * f1s[i] +
            0.20 * recalls[i] +
            0.15 * precisions[i],
            4
        )

    return sorted(metrics_list, key=lambda x: x["perf_score"], reverse=True)


def get_pca_data(
    X: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray = None,
) -> dict:
    """
    Réduit X en 2D avec PCA pour le scatter plot de la Page 2.

    Args:
        X (np.ndarray)      : Données (n_samples, n_features).
        labels (np.ndarray) : Prédictions 0/1.
        scores (np.ndarray) : Scores d'anomalie optionnels.

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
        "x":                  X_2d[:, 0].tolist(),
        "y":                  X_2d[:, 1].tolist(),
        "labels":             labels.tolist(),
        "scores":             scores.tolist() if scores is not None else None,
        "explained_variance": ev,
        "pc1_label":          f"PC1 ({ev[0]:.1%})",
        "pc2_label":          f"PC2 ({ev[1]:.1%})",
    }


def get_score_distributions(scores_dict: dict, y_true: np.ndarray) -> dict:
    """
    Distribution des scores d'anomalie par modèle, séparée par classe.
    Utilisé pour les histogrammes de Page 2.

    Args:
        scores_dict (dict)  : {model_name: scores_array}
        y_true (np.ndarray) : Labels réels.

    Returns:
        dict: {model_name: {all, normal, anomaly, percentiles}}
    """
    result = {}
    n = len(y_true)
    idx = np.random.choice(n, min(n, VIZ_MAX_POINTS), replace=False)

    for name, scores in scores_dict.items():
        sc       = scores[idx]
        y_sample = y_true[idx]
        result[name] = {
            "all":     sc.tolist(),
            "normal":  sc[y_sample == 0].tolist(),
            "anomaly": sc[y_sample == 1].tolist(),
            "percentiles": {
                "p50": round(float(np.percentile(sc, 50)), 4),
                "p90": round(float(np.percentile(sc, 90)), 4),
                "p95": round(float(np.percentile(sc, 95)), 4),
            },
        }
    return result


def get_confusion_matrix_data(metrics_list: list[dict]) -> list[dict]:
    """
    Formate les matrices de confusion pour les heatmaps Plotly.

    Args:
        metrics_list (list[dict]): Liste des métriques par modèle.

    Returns:
        list[dict]: Données formatées pour go.Heatmap.
    """
    result = []
    for m in metrics_list:
        cm = m["confusion_matrix"]
        result.append({
            "model_name": m["model"],
            "z":  [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]],
            "x":  ["Prédit Normal", "Prédit Anomalie"],
            "y":  ["Réel Normal",   "Réel Anomalie"],
            "f1":      m["f1"],
            "roc_auc": m["roc_auc"],
        })
    return result