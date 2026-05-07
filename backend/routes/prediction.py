"""
prediction.py — Page 3 : prédiction avec Isolation Forest.

Le formulaire expose 10 features normalisées (espace du dataset après
preprocessing notebook 03). Les autres features utilisent les médianes
des connexions normales comme valeur par défaut.

Routes :
    GET  /api/predict/info    → infos sur le modèle déployé
    POST /api/predict/single  → prédiction sur une connexion saisie
"""

import logging
import threading
import numpy as np

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import TARGET_COLUMN, REFERENCE_SAMPLE_SIZE, CONTAMINATION_PREDICT, FEATURE_NAMES
from utils import DataLoader, BestModelLoader, ModelError, DataLoadError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/predict", tags=["Page 3 — Prédiction"])

# FEATURE_NAMES importé depuis config.py

# ── Médianes des connexions NORMALES (valeurs par défaut du formulaire) ────────
NORMAL_MEDIANS = {
    "bytes_total":       0.757,
    "bytes_per_pkt_src": 0.213,
    "bytes_ratio":       0.095,
    "bytes_diff_norm":   0.290,
    "sbytes":            0.417,
    "sttl":             -1.000,
    "bytes_per_pkt_dst": 0.108,
    "dbytes":            0.172,
    "ct_state_ttl":      0.000,
    "dttl":              0.000,
    "rate":             -0.025,
    "sload":            -0.009,
    "dur":               0.331,
    "smean":             0.000,
    "log1p_dbytes":      0.159,
    "dmean":             0.360,
    "pkts_total":        1.400,
    "dinpkt":            0.024,
    "dload":             0.224,
    "dpkts":             0.600,
}

# ── Médianes des connexions ANOMALIES (pour les presets) ──────────────────────
ANOMALY_MEDIANS = {
    "bytes_total":      -0.325,
    "bytes_per_pkt_src":-0.176,
    "bytes_ratio":      -0.207,
    "bytes_diff_norm":   0.154,
    "sbytes":           -0.176,
    "sttl":              0.000,
    "bytes_per_pkt_dst":-0.186,
    "dbytes":           -0.149,
    "ct_state_ttl":      1.000,
    "dttl":             -0.115,
    "rate":              0.774,
    "sload":             0.560,
    "dur":              -0.002,
    "smean":            -0.372,
    "log1p_dbytes":      0.000,
    "dmean":            -0.494,
    "pkts_total":       -0.200,
    "dinpkt":           -0.000,
    "dload":            -0.052,
    "dpkts":            -0.200,
}

# ── Features exposées dans le formulaire ─────────────────────────────────────
EDITABLE_INPUTS = [
    {"name": "sbytes",       "label": "sbytes",       "normal":  0.417, "anomaly": -0.176},
    {"name": "dbytes",       "label": "dbytes",       "normal":  0.172, "anomaly": -0.149},
    {"name": "dpkts",        "label": "dpkts",        "normal":  0.600, "anomaly": -0.200},
    {"name": "dur",          "label": "dur",           "normal":  0.331, "anomaly": -0.002},
    {"name": "rate",         "label": "rate ★",        "normal": -0.025, "anomaly":  0.774},
    {"name": "sload",        "label": "sload",         "normal": -0.009, "anomaly":  0.560},
    {"name": "dload",        "label": "dload",         "normal":  0.224, "anomaly": -0.052},
    {"name": "sttl",         "label": "sttl ★",        "normal": -1.000, "anomaly":  0.000},
    {"name": "dttl",         "label": "dttl",          "normal":  0.000, "anomaly": -0.115},
    {"name": "ct_state_ttl", "label": "ct_state_ttl ★","normal":  0.000, "anomaly":  1.000},
]


# ── Schéma Pydantic ────────────────────────────────────────────────────────────

class ConnectionRequest(BaseModel):
    """
    Features normalisées d'une connexion réseau.
    Valeurs dans l'espace normalisé du dataset (notebook 03).
    ★ = features très discriminantes pour l'Isolation Forest.
    Normal typique  : sttl≈-1.0 | rate≈-0.025 | ct_state_ttl≈0.0
    Anomalie typique: sttl≈ 0.0 | rate≈ 0.774 | ct_state_ttl≈1.0
    """
    sbytes:       float = Field(default= 0.417, description="Volume envoyé normalisé")
    dbytes:       float = Field(default= 0.172, description="Volume reçu normalisé")
    dpkts:        float = Field(default= 0.600, description="Paquets reçus normalisés")
    dur:          float = Field(default= 0.331, description="Durée normalisée")
    rate:         float = Field(default=-0.025, description="Débit normalisé ★")
    sload:        float = Field(default=-0.009, description="Charge source normalisée")
    dload:        float = Field(default= 0.224, description="Charge destination normalisée")
    sttl:         float = Field(default=-1.000, description="TTL source normalisé ★")
    dttl:         float = Field(default= 0.000, description="TTL destination normalisé")
    ct_state_ttl: float = Field(default= 0.000, description="État TTL normalisé ★")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_model_loader(request: Request) -> BestModelLoader:
    loader = getattr(request.app.state, "model_loader", None)
    if loader is None or not loader.is_loaded:
        raise ModelError("Le modèle n'est pas disponible.")
    return loader


def _get_data_loader(request: Request) -> DataLoader:
    state = request.app.state
    if not hasattr(state, "data_loader"):
        state.data_loader = DataLoader()
    return state.data_loader


def _ensure_reference(request: Request) -> None:
    """
    Calcule la distribution de référence des scores IF sur un échantillon
    du test set. Utilisé pour normaliser le score d'une connexion unique.
    """
    state = request.app.state
    if hasattr(state, "prediction_reference"):
        return

    loader      = _get_model_loader(request)
    data_loader = _get_data_loader(request)

    _, _, df_test = data_loader.load_test()

    df_ref = (
        df_test
        .sample(min(len(df_test), REFERENCE_SAMPLE_SIZE), random_state=42)
        .reset_index(drop=True)
    )

    X_ref = df_ref[FEATURE_NAMES]  # DataFrame avec noms de colonnes

    # Scores IF SANS QT sur la référence — cohérent avec l'inférence unitaire
    # Le QT est instable sur des lignes individuelles, on l'évite ici
    raw_if_ref = loader._if_model.decision_function(X_ref.values).astype(np.float32)

    # Seuil optimal calculé sur la référence sans QT.
    # On utilise contamination=0.35 : seuil au 65e percentile des scores bruts.
    # Cela correspond au seuil qui sépare correctement normal et anomalie
    # dans l'espace des données normalisées du dataset (sans QT).
    BEST_CONTAMINATION = 0.35
    raw_threshold = float(np.percentile(raw_if_ref, 100 * (1 - BEST_CONTAMINATION)))
    raw_sorted    = np.sort(raw_if_ref)

    state.prediction_reference = {
        "raw_ref":       {"if_raw": raw_if_ref},
        "raw_sorted":    raw_sorted,
        "raw_threshold": raw_threshold,
        "contamination": BEST_CONTAMINATION,
    }
    logger.info(f"Référence IF (sans QT). Seuil={raw_threshold:.6f} (contamination={BEST_CONTAMINATION})")


def _build_feature_vector(form: dict):
    """
    Construit le vecteur de 20 features dans l'ordre exact du modèle.
    Les features non exposées dans le formulaire utilisent les médianes normales.
    """
    row = {feat: NORMAL_MEDIANS[feat] for feat in FEATURE_NAMES}
    for key, value in form.items():
        if key in row:
            row[key] = float(value)
    import pandas as pd
    return pd.DataFrame([row], columns=FEATURE_NAMES)


def _percentile_rank(value: float, sorted_ref: np.ndarray) -> float:
    return float(np.searchsorted(sorted_ref, value, side="right") / len(sorted_ref))


# ── GET /api/predict/info ─────────────────────────────────────────────────────

@router.get("/info", summary="Informations sur le modèle déployé")
def get_model_info(request: Request):
    """Retourne les informations sur l'Isolation Forest déployé."""
    try:
        loader = _get_model_loader(request)
    except ModelError as e:
        raise HTTPException(status_code=503, detail=e.message)

    data_loader = _get_data_loader(request)
    best_metrics = {}
    df_report = data_loader.load_model_comparison()
    if df_report is not None:
        # Cherche la ligne IF dans le rapport
        for idx in df_report.index:
            if "Isolation" in str(idx) or "IF" in str(idx):
                row = df_report.loc[idx]
                best_metrics = {
                    "f1_score":  round(float(row.get("f1", 0)), 4),
                    "roc_auc":   round(float(row.get("roc_auc", 0)), 4),
                    "precision": round(float(row.get("precision", 0)), 4),
                    "recall":    round(float(row.get("recall", 0)), 4),
                }
                break

    # Préchauffage en arrière-plan
    if not hasattr(request.app.state, "prediction_reference"):
        def _warm(req):
            try:
                _ensure_reference(req)
            except Exception as e:
                logger.warning(f"Préchauffage échoué : {e}")
        threading.Thread(target=_warm, args=(request,), daemon=True).start()

    return {
        "status": 200,
        "best_model": {
            "name": loader.model_name,
            "components": [
                {"name": "Isolation Forest", "weight": 1.0, "file": "if_base.pkl"},
            ],
            "metrics": best_metrics,
            "decision_formula": "score = normalize(-IF.decision_function(X))",
            "threshold": f"score > percentile({(1-CONTAMINATION_PREDICT)*100:.0f}%)",
            "note": (
                "Features dans l'espace normalisé du dataset. "
                "Normal : sttl≈-1.0 | rate≈-0.025 | ct_state_ttl≈0.0"
            ),
        },
        "editable_inputs":  EDITABLE_INPUTS,
        "normal_medians":   NORMAL_MEDIANS,
        "anomaly_medians":  ANOMALY_MEDIANS,
        "available_files":  loader.available_files(),
    }


# ── POST /api/predict/single ──────────────────────────────────────────────────

@router.post("/single", summary="Prédire une connexion réseau")
def predict_single(request: Request, data: ConnectionRequest):
    """
    Reçoit les features normalisées d'une connexion et retourne
    la prédiction de l'Isolation Forest.

    Pipeline :
    1. Construire le vecteur de 20 features (ordre exact du modèle)
    2. Calculer le score IF brut : -decision_function(X)
    3. Normaliser par rapport à la distribution de référence
    4. Comparer au seuil → Normal ou Anomalie
    """
    try:
        loader = _get_model_loader(request)
    except ModelError as e:
        raise HTTPException(status_code=503, detail=e.message)

    try:
        _ensure_reference(request)
    except (ModelError, DataLoadError) as e:
        raise HTTPException(status_code=503, detail=f"Référence non disponible : {e.message}")

    ref   = request.app.state.prediction_reference
    form  = data.model_dump()
    X_raw = _build_feature_vector(form)

    # Score brut SANS QT — cohérent avec la référence unitaire
    raw_score = float(loader._if_model.decision_function(X_raw.values)[0])

    # Prédiction : comparaison directe au seuil brut
    pred      = int(raw_score >= ref["raw_threshold"])
    threshold = ref["raw_threshold"]

    # Rang percentile pour l'affichage des probabilités
    anomaly_pct = _percentile_rank(raw_score, ref["raw_sorted"])

    # Score normalisé [0,1] pour l'affichage
    raw_ref   = ref["raw_ref"]["if_raw"]
    ref_min, ref_max = raw_ref.min(), raw_ref.max()
    if ref_max > ref_min:
        display_score = float(np.clip((raw_score - ref_min) / (ref_max - ref_min), 0, 1))
    else:
        display_score = 0.0

    return {
        "status":     200,
        "prediction": pred,
        "label":      "Anomalie 🚨" if pred == 1 else "Normal ✅",
        "score":      round(display_score, 4),
        "raw_score":  round(raw_score, 6),
        "model_used": loader.model_name,
        "probabilities": {
            "anomaly": round(anomaly_pct * 100, 1),
            "normal":  round((1 - anomaly_pct) * 100, 1),
        },
        "if_score":             round(display_score, 4),
        "threshold":            round(threshold, 6),
        "threshold_percentile": round((1 - ref["contamination"]) * 100, 1),
        "input_summary":        form,
    }