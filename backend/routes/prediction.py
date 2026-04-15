"""
prediction.py — Page 3 : prédiction sur une connexion réseau saisie manuellement.

Le backend expose le meilleur ensemble sauvegardé dans `ensemble_3models.pkl`
et reconstruit les features utiles depuis un sous-ensemble réduit de variables
éditables côté frontend.

Routes :
  GET  /api/predict/best_model  → Infos sur le meilleur modèle déployé
  POST /api/predict/single      → Prédiction sur une observation saisie
"""

import logging
import threading
import numpy as np
import pandas as pd

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import ENS3_FILE, CONTAMINATION, TARGET_COLUMN
from utils.model_loader import (
    load_qt, load_isolation_forest, load_lof, load_autoencoder,
    load_ensemble_config, get_ensemble3_scores, normalize_with_reference,
    get_if_raw_scores, get_lof_raw_scores, get_ae_raw_scores,
)
from utils.data_loader import load_model_comparison, load_test_data
from utils.exceptions import ModelError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/predict", tags=["Page 3 — Prédiction"])
REFERENCE_SAMPLE_SIZE = 15_000

EDITABLE_INPUTS = (
    {"name": "sbytes", "label": "Bytes envoyés", "type": "int"},
    {"name": "dbytes", "label": "Bytes reçus", "type": "int"},
    {"name": "spkts", "label": "Paquets envoyés", "type": "int"},
    {"name": "dpkts", "label": "Paquets reçus", "type": "int"},
    {"name": "dur", "label": "Durée de connexion (s)", "type": "float"},
    {"name": "rate", "label": "Taux de transfert (pkt/s)", "type": "float"},
    {"name": "sload", "label": "Charge source (bits/s)", "type": "float"},
    {"name": "dload", "label": "Charge destination (bits/s)", "type": "float"},
    {"name": "sttl", "label": "TTL source", "type": "int"},
    {"name": "dttl", "label": "TTL destination", "type": "int"},
)


def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "app_state"):
        request.app.state.app_state = {}
    return request.app.state.app_state


def _best_model_name(cfg: dict) -> str:
    return f"Ensemble IF({cfg['w_if']:.1f})+LOF({cfg['w_lof']:.1f})+AE({cfg['w_ae']:.1f})"


def _percentile_rank(value: float, sorted_reference: np.ndarray) -> float:
    rank = np.searchsorted(sorted_reference, value, side="right")
    return float(rank / len(sorted_reference))


def _ensure_best_model(state: dict) -> None:
    """
    Charge le meilleur modèle (Ensemble 3) et le QT en mémoire si besoin.
    On charge une seule fois au premier appel.
    """
    if "best_model_loaded" in state:
        return

    qt = load_qt()
    state["qt"] = qt

    if_model = load_isolation_forest()
    state["if_model"] = if_model

    lof_model = load_lof()
    state["lof_model"] = lof_model

    ae_model, device = load_autoencoder()
    state["ae_model"] = ae_model
    state["ae_device"] = device

    cfg3 = load_ensemble_config(ENS3_FILE)
    state["ens3_cfg"] = cfg3

    state["best_model_loaded"] = True
    logger.info("Meilleur modèle (Ensemble 3) chargé en mémoire")


def _ensure_prediction_reference(state: dict) -> None:
    """
    Prépare les distributions de référence utilisées pour l'inférence unitaire.

    On compare chaque nouvelle connexion aux scores du test set afin d'obtenir
    un score stable, un seuil cohérent et un pourcentage d'anomalie exploitable.
    """
    _ensure_best_model(state)

    if "prediction_reference_scores" in state:
        return

    _, _, df_test = load_test_data()
    feature_names = [c for c in df_test.columns if c != TARGET_COLUMN]
    feature_defaults = (
        df_test[feature_names]
        .median(numeric_only=True)
        .astype(float)
        .to_dict()
    )

    df_reference = (
        df_test.sample(min(len(df_test), REFERENCE_SAMPLE_SIZE), random_state=42)
        .reset_index(drop=True)
    )
    X_test_qt = state["qt"].transform(df_reference[feature_names]).astype(np.float32)

    raw_if_ref = get_if_raw_scores(state["if_model"], X_test_qt)
    raw_lof_ref = get_lof_raw_scores(state["lof_model"], X_test_qt)

    if state["ae_model"] is not None:
        raw_ae_ref = get_ae_raw_scores(state["ae_model"], state["ae_device"], X_test_qt)
    else:
        raw_ae_ref = ((raw_if_ref + raw_lof_ref) / 2.0).astype(np.float32)

    sc_if_ref = normalize_with_reference(raw_if_ref, raw_if_ref)
    sc_lof_ref = normalize_with_reference(raw_lof_ref, raw_lof_ref)
    sc_ae_ref = normalize_with_reference(raw_ae_ref, raw_ae_ref)

    cfg3 = state["ens3_cfg"]
    contamination = float(cfg3.get("contamination", CONTAMINATION))
    sc_final_ref = get_ensemble3_scores(sc_if_ref, sc_lof_ref, sc_ae_ref, cfg3)

    state["feature_names"] = feature_names
    state["feature_defaults"] = feature_defaults
    state["prediction_reference_scores"] = {
        "if_raw": raw_if_ref,
        "lof_raw": raw_lof_ref,
        "ae_raw": raw_ae_ref,
        "final": sc_final_ref,
        "sorted_final": np.sort(sc_final_ref),
    }
    state["prediction_threshold"] = float(
        np.percentile(sc_final_ref, 100 * (1 - contamination))
    )
    state["prediction_contamination"] = contamination


# ── Schéma du formulaire Page 3 ───────────────────────────────────────────────

class ConnectionRequest(BaseModel):
    """
    Champs du formulaire Page 3.
    On garde uniquement les variables réseau qui modifient réellement la
    prédiction unitaire. Les autres features du modèle sont reconstruites
    ou figées sur une valeur médiane du dataset de référence.
    """
    # Durée et débit
    dur:    float = Field(default=0.0,   ge=0,       description="Durée de connexion (s)")
    rate:   float = Field(default=0.0,   ge=0,       description="Taux de transfert (pkt/s)")
    sbytes: int   = Field(default=100,   ge=0,       description="Bytes envoyés")
    dbytes: int   = Field(default=100,   ge=0,       description="Bytes reçus")
    spkts:  int   = Field(default=5,     ge=0,       description="Paquets envoyés")
    dpkts:  int   = Field(default=5,     ge=0,       description="Paquets reçus")

    # TTL
    sttl:   int   = Field(default=64,    ge=0, le=255, description="TTL source")
    dttl:   int   = Field(default=64,    ge=0, le=255, description="TTL destination")

    # Charge
    sload:  float = Field(default=0.0,   ge=0,       description="Charge source (bits/s)")
    dload:  float = Field(default=0.0,   ge=0,       description="Charge destination (bits/s)")


# ── GET /api/predict/best_model ───────────────────────────────────────────────

@router.get("/best_model", summary="Infos sur le meilleur modèle déployé")
def get_best_model_info(request: Request):
    """
    Retourne les informations sur le meilleur modèle pour la **Page 3**.

    **Meilleur modèle** : ensemble chargé depuis `ensemble_3models.pkl`.

    **Pourquoi l'Autoencoder domine ?**
    L'AE est entraîné uniquement sur le trafic normal. Il apprend
    à reconstruire les connexions légitimes. Quand il voit une attaque,
    l'erreur de reconstruction est élevée → anomalie détectée.
    """
    state = get_state(request)
    cfg3 = load_ensemble_config(ENS3_FILE)
    best_model_name = _best_model_name(cfg3)
    df_report = load_model_comparison()
    best_metrics = {}

    if df_report is not None and best_model_name in df_report.index:
        row = df_report.loc[best_model_name]
        best_metrics = {
            "f1_score":      round(float(row.get("f1", 0.0)), 4),
            "roc_auc":       round(float(row.get("roc_auc", 0.0)), 4),
            "precision":     round(float(row.get("precision", 0.0)), 4),
            "recall":        round(float(row.get("recall", 0.0)), 4),
            "avg_precision": round(float(row.get("avg_precision", 0.0)), 4),
            "perf_score":    round(float(row.get("perf_score", 0.0)), 4),
        }

    if "prediction_reference_scores" not in state and not state.get("prediction_reference_warming"):
        state["prediction_reference_warming"] = True

        def _warm_prediction_cache(app_state: dict) -> None:
            try:
                _ensure_prediction_reference(app_state)
                logger.info("[PREDICT] Cache de référence préchauffé en arrière-plan.")
            except Exception as warm_exc:
                logger.warning(f"[PREDICT] Préchauffage échoué : {warm_exc}")
            finally:
                app_state.pop("prediction_reference_warming", None)

        threading.Thread(target=_warm_prediction_cache, args=(state,), daemon=True).start()

    return {
        "status": 200,
        "best_model": {
            "name":        best_model_name,
            "components": [
                {"name": "Isolation Forest", "weight": cfg3["w_if"], "file": "if_base.pkl"},
                {"name": "LOF",              "weight": cfg3["w_lof"], "file": "lof.pkl"},
                {"name": "Autoencoder",      "weight": cfg3["w_ae"], "file": "autoencoder.pt"},
            ],
            "metrics": best_metrics,
            "decision_formula": (
                f"score = {cfg3['w_if']:.1f} × score_IF + "
                f"{cfg3['w_lof']:.1f} × score_LOF + "
                f"{cfg3['w_ae']:.1f} × score_AE"
            ),
            "threshold":        f"score > percentile({(1 - cfg3.get('contamination', CONTAMINATION))*100:.0f}%) → Anomalie",
        },
        "editable_inputs": EDITABLE_INPUTS,
        "available_files": {
            "qt":         ENS3_FILE.parent.joinpath("qt_improvements.pkl").exists(),
            "if":         ENS3_FILE.parent.joinpath("if_base.pkl").exists(),
            "lof":        ENS3_FILE.parent.joinpath("lof.pkl").exists(),
            "autoencoder": ENS3_FILE.parent.joinpath("autoencoder.pt").exists(),
            "ensemble3":  ENS3_FILE.exists(),
        },
    }


# ── POST /api/predict/single ──────────────────────────────────────────────────

@router.post("/single", summary="Prédire une connexion réseau")
def predict_single(request: Request, data: ConnectionRequest):
    """
    Reçoit les caractéristiques d'une connexion réseau saisies dans le formulaire
    de la **Page 3** et retourne la prédiction du meilleur modèle.

    Pipeline :
    1. Construire le vecteur de features depuis les inputs
    2. Transformer avec le QuantileTransformer du notebook 06
    3. Calculer les scores IF, LOF, AE
    4. Combiner avec les poids réellement sauvegardés dans l'ensemble
    5. Comparer au seuil → Normal ou Anomalie

    Retourne :
    - **prediction** : 0 (Normal) ou 1 (Anomalie)
    - **label** : "Normal ✅" ou "Anomalie 🚨"
    - **score** : score final entre 0 et 1
    - **scores_detail** : contribution de chaque modèle
    """
    state = get_state(request)

    try:
        _ensure_prediction_reference(state)
    except ModelError as e:
        raise HTTPException(status_code=503, detail=f"Modèle non disponible : {e.message}")

    qt        = state["qt"]
    if_model  = state["if_model"]
    lof_model = state["lof_model"]
    ae_model  = state["ae_model"]
    ae_device = state["ae_device"]
    cfg3      = state["ens3_cfg"]

    feature_names = state["feature_names"]
    feature_defaults = state["feature_defaults"]
    reference_scores = state["prediction_reference_scores"]
    threshold = state["prediction_threshold"]
    contamination = state["prediction_contamination"]

    # ── Construire le vecteur de features ─────────────────────────────────────
    # On démarre depuis les médianes du dataset de référence pour les features
    # non exposées, puis on remplace avec les variables éditables et les
    # dérivations exactes du notebook 03 quand elles sont disponibles.
    form = data.model_dump()
    spkts  = max(form["spkts"], 1)
    dpkts  = form["dpkts"]
    sbytes = form["sbytes"]
    dbytes = form["dbytes"]
    dur    = form["dur"]
    dpkts_safe = max(dpkts, 1)

    derived = {
        "bytes_total":        sbytes + dbytes,
        "bytes_per_pkt_src":  sbytes / (spkts + 1),
        "bytes_ratio":        sbytes / (dbytes + 1),
        "bytes_diff_norm":    abs(sbytes - dbytes) / (sbytes + dbytes + 1),
        "bytes_per_pkt_dst":  dbytes / (dpkts + 1),
        "smean":              sbytes / spkts,
        "log1p_dbytes":       np.log1p(max(dbytes, 0)),
        "dmean":              dbytes / dpkts_safe if dpkts > 0 else 0.0,
        "pkts_total":         spkts + dpkts,
        "dinpkt":             dur / (dpkts + 1),
    }

    all_fields = {
        key: float(feature_defaults.get(key, 0.0))
        for key in feature_names
    }
    all_fields.update({key: float(value) for key, value in form.items() if key in all_fields})
    all_fields.update({key: float(value) for key, value in derived.items() if key in all_fields})

    row_df = pd.DataFrame([{col: all_fields[col] for col in feature_names}], columns=feature_names)

    # ── Transformer avec le QuantileTransformer ────────────────────────────────
    try:
        X_qt = qt.transform(row_df).astype(np.float32)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de transformation : {str(e)}")

    # ── Scores individuels ────────────────────────────────────────────────────
    raw_if = get_if_raw_scores(if_model, X_qt)
    raw_lof = get_lof_raw_scores(lof_model, X_qt)
    sc_if = normalize_with_reference(raw_if, reference_scores["if_raw"])
    sc_lof = normalize_with_reference(raw_lof, reference_scores["lof_raw"])

    if ae_model is not None:
        raw_ae = get_ae_raw_scores(ae_model, ae_device, X_qt)
    else:
        raw_ae = ((raw_if + raw_lof) / 2.0).astype(np.float32)
        logger.warning("Autoencoder indisponible — fallback IF+LOF pour le score AE")

    sc_ae = normalize_with_reference(raw_ae, reference_scores["ae_raw"])
    sc_final = get_ensemble3_scores(sc_if, sc_lof, sc_ae, cfg3)
    final_score = float(sc_final[0])
    pred = int(final_score >= threshold)
    anomaly_ratio = _percentile_rank(final_score, reference_scores["sorted_final"])
    normal_ratio = 1.0 - anomaly_ratio
    best_model_name = _best_model_name(cfg3)

    return {
        "status":     200,
        "prediction": pred,
        "label":      "Anomalie 🚨" if pred == 1 else "Normal ✅",
        "score":      round(final_score, 4),
        "model_used": best_model_name,
        "probabilities": {
            "anomaly": round(anomaly_ratio * 100, 1),
            "normal":  round(normal_ratio * 100, 1),
        },
        "scores_detail": {
            "isolation_forest": round(float(sc_if[0]),    4),
            "lof":              round(float(sc_lof[0]),   4),
            "autoencoder":      round(float(sc_ae[0]),    4),
            "ensemble_final":   round(final_score, 4),
            "weights": {
                "if":  cfg3["w_if"],
                "lof": cfg3["w_lof"],
                "ae":  cfg3["w_ae"],
            },
        },
        "threshold":     round(threshold, 4),
        "threshold_percentile": round((1 - contamination) * 100, 1),
        "input_summary": {k: v for k, v in form.items()},
    }
