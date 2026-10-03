"""Metric and visualization data builders for the API."""

from __future__ import annotations

import logging

import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)

from backend.config import PCA_N_COMPONENTS, VIZ_MAX_POINTS

logger = logging.getLogger(__name__)


def compute_metrics(
    name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: np.ndarray,
    inference_s: float = 0.0,
) -> dict:
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    try:
        roc_auc = float(roc_auc_score(y_true, y_scores))
        fpr, tpr, _ = roc_curve(y_true, y_scores)
    except Exception:
        roc_auc = 0.0
        fpr = np.array([0.0, 1.0])
        tpr = np.array([0.0, 1.0])

    try:
        avg_precision = float(average_precision_score(y_true, y_scores))
    except Exception:
        avg_precision = 0.0

    step = max(1, len(fpr) // 500)
    metrics = {
        "model": name,
        "precision": round(float(report.get("1", {}).get("precision", 0.0)), 4),
        "recall": round(float(report.get("1", {}).get("recall", 0.0)), 4),
        "f1": round(float(report.get("1", {}).get("f1-score", 0.0)), 4),
        "roc_auc": round(roc_auc, 4),
        "avg_precision": round(avg_precision, 4),
        "inference_s": round(float(inference_s), 4),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "roc_curve": {
            "fpr": fpr[::step].tolist(),
            "tpr": tpr[::step].tolist(),
        },
        "n_anomalies_detected": int(np.sum(y_pred)),
        "n_true_anomalies": int(np.sum(y_true)),
    }
    logger.info(
        "%s metrics: precision=%s recall=%s f1=%s auc=%s",
        name,
        metrics["precision"],
        metrics["recall"],
        metrics["f1"],
        metrics["roc_auc"],
    )
    return metrics


def compute_perf_score(metrics_list: list[dict]) -> list[dict]:
    if not metrics_list:
        return []

    def norm(values: list[float]) -> np.ndarray:
        arr = np.asarray(values, dtype=np.float32)
        mn = float(arr.min())
        mx = float(arr.max())
        if mx == mn:
            return np.ones_like(arr)
        return (arr - mn) / (mx - mn)

    auc = norm([m.get("roc_auc", 0.0) for m in metrics_list])
    f1 = norm([m.get("f1", 0.0) for m in metrics_list])
    recall = norm([m.get("recall", 0.0) for m in metrics_list])
    precision = norm([m.get("precision", 0.0) for m in metrics_list])

    for idx, metric in enumerate(metrics_list):
        metric["perf_score"] = round(
            float(0.35 * auc[idx] + 0.30 * f1[idx] + 0.20 * recall[idx] + 0.15 * precision[idx]),
            4,
        )

    return sorted(metrics_list, key=lambda item: item.get("perf_score", 0.0), reverse=True)


def get_pca_data(
    X: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray | None = None,
) -> dict:
    n = len(X)
    if n > VIZ_MAX_POINTS:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, VIZ_MAX_POINTS, replace=False)
        X = X[idx]
        labels = labels[idx]
        if scores is not None:
            scores = scores[idx]

    pca = PCA(n_components=PCA_N_COMPONENTS, random_state=42)
    X_2d = pca.fit_transform(X)
    explained = pca.explained_variance_ratio_.tolist()

    return {
        "x": X_2d[:, 0].tolist(),
        "y": X_2d[:, 1].tolist(),
        "labels": labels.tolist(),
        "scores": scores.tolist() if scores is not None else None,
        "explained_variance": explained,
        "pc1_label": f"PC1 ({explained[0]:.1%})",
        "pc2_label": f"PC2 ({explained[1]:.1%})",
    }


def get_score_distributions(scores_dict: dict[str, np.ndarray], y_true: np.ndarray) -> dict:
    rng = np.random.default_rng(42)
    n = len(y_true)
    idx = rng.choice(n, min(n, VIZ_MAX_POINTS), replace=False)
    y_sample = y_true[idx]

    result: dict[str, dict] = {}
    for name, scores in scores_dict.items():
        sc = scores[idx]
        result[name] = {
            "all": sc.tolist(),
            "normal": sc[y_sample == 0].tolist(),
            "anomaly": sc[y_sample == 1].tolist(),
            "percentiles": {
                "p50": round(float(np.percentile(sc, 50)), 4),
                "p90": round(float(np.percentile(sc, 90)), 4),
                "p95": round(float(np.percentile(sc, 95)), 4),
            },
        }
    return result


def get_score_distribution(scores: np.ndarray, y_true: np.ndarray, model_name: str) -> dict:
    return get_score_distributions({model_name: scores}, y_true)


def get_confusion_matrix_data(metrics_list: list[dict] | dict) -> list[dict] | dict:
    if isinstance(metrics_list, dict):
        cm = metrics_list["confusion_matrix"]
        return {
            "model_name": metrics_list["model"],
            "z": [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]],
            "x": ["Pred normal", "Pred anomaly"],
            "y": ["Real normal", "Real anomaly"],
            "f1": metrics_list.get("f1", 0.0),
            "roc_auc": metrics_list.get("roc_auc", 0.0),
        }

    matrices = []
    for metrics in metrics_list:
        cm = metrics["confusion_matrix"]
        matrices.append(
            {
                "model_name": metrics["model"],
                "z": [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]],
                "x": ["Pred normal", "Pred anomaly"],
                "y": ["Real normal", "Real anomaly"],
                "f1": metrics.get("f1", 0.0),
                "roc_auc": metrics.get("roc_auc", 0.0),
            }
        )
    return matrices
