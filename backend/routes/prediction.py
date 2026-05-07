"""
<<<<<<< HEAD
prediction.py — Page 3 : prédiction avec Isolation Forest.

Le formulaire expose 10 features normalisées (espace du dataset après
preprocessing notebook 03). Les autres features utilisent les médianes
des connexions normales comme valeur par défaut.

Routes :
    GET  /api/predict/info    → infos sur le modèle déployé
    POST /api/predict/single  → prédiction sur une connexion saisie
=======
prediction.py — Page 3 : prédiction sur une connexion réseau saisie manuellement.

Le backend expose le meilleur ensemble sauvegardé dans `ensemble_3models.pkl`
et reconstruit les features utiles depuis un sous-ensemble réduit de variables
éditables côté frontend.

Routes :
  GET  /api/predict/best_model  → Infos sur le meilleur modèle déployé
  POST /api/predict/single      → Prédiction sur une observation saisie
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
"""

import logging
import threading
import numpy as np
<<<<<<< HEAD
=======
import pandas as pd
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

<<<<<<< HEAD
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
=======
from config import ENS3_FILE, CONTAMINATION, TARGET_COLUMN
from utils.model_loader import (
    load_qt, load_scaler, load_isolation_forest, load_lof, load_autoencoder,
    load_ensemble_config, get_ensemble3_scores, normalize_with_reference,
    get_if_raw_scores, get_lof_raw_scores, get_ae_raw_scores,
)
from utils.data_loader import (
    load_model_comparison,
    load_raw_test_data,
    load_test_clean_data,
    load_test_data,
)
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
EDITABLE_INPUT_NAMES = tuple(item["name"] for item in EDITABLE_INPUTS)
INFERRED_RAW_FIELDS = ("ct_state_ttl", "smean", "dmean", "dinpkt")


def get_state(request: Request) -> dict:
    if not hasattr(request.app.state, "app_state"):
        request.app.state.app_state = {}
    return request.app.state.app_state


def _best_model_name(cfg: dict) -> str:
    return f"Ensemble IF({cfg['w_if']:.1f})+LOF({cfg['w_lof']:.1f})+AE({cfg['w_ae']:.1f})"


def _percentile_rank(value: float, sorted_reference: np.ndarray) -> float:
    rank = np.searchsorted(sorted_reference, value, side="right")
    return float(rank / len(sorted_reference))


def _build_scaler_stats(scaler) -> dict[str, tuple[float, float]]:
    names = list(getattr(scaler, "feature_names_in_", []))
    centers = getattr(scaler, "center_", np.zeros(len(names), dtype=np.float32))
    scales = getattr(scaler, "scale_", np.ones(len(names), dtype=np.float32))
    return {
        name: (float(centers[idx]), float(scales[idx]) if float(scales[idx]) != 0 else 1.0)
        for idx, name in enumerate(names)
    }


def _scale_raw_feature(raw_value: float, feature_name: str, scaler_stats: dict[str, tuple[float, float]]) -> float:
    center, scale = scaler_stats[feature_name]
    return float((raw_value - center) / scale)


def _infer_hidden_raw_features(
    form: dict,
    raw_lookup_matrix: np.ndarray,
    raw_lookup_hidden: pd.DataFrame,
    scaler_stats: dict[str, tuple[float, float]],
    k_neighbors: int = 5,
) -> dict[str, float]:
    """
    Infère les variables non exposées du formulaire à partir des connexions les
    plus proches dans le jeu de test brut.

    On travaille dans l'espace RobustScaler des 10 champs éditables afin de
    comparer des grandeurs hétérogènes (bytes, TTL, durées, charges) sans
    qu'une seule domine artificiellement la distance.
    """
    query = np.array(
        [_scale_raw_feature(float(form[name]), name, scaler_stats) for name in EDITABLE_INPUT_NAMES],
        dtype=np.float32,
    )

    distances = np.sum((raw_lookup_matrix - query) ** 2, axis=1)
    k = min(k_neighbors, len(distances))
    nearest_idx = np.argpartition(distances, kth=k - 1)[:k]
    nearest_idx = nearest_idx[np.argsort(distances[nearest_idx])]
    nearest_rows = raw_lookup_hidden.iloc[nearest_idx]

    if distances[nearest_idx[0]] < 1e-12:
        return {
            key: float(nearest_rows.iloc[0][key])
            for key in INFERRED_RAW_FIELDS
        }

    inferred = {}
    for key in INFERRED_RAW_FIELDS:
        vals = nearest_rows[key].astype(float).values
        if key in {"ct_state_ttl", "smean", "dmean"}:
            inferred[key] = float(np.round(np.median(vals)))
        else:
            inferred[key] = float(np.median(vals))
    return inferred


def _build_prediction_row(
    form: dict,
    clean_feature_defaults: dict[str, float],
    selected_feature_names: list[str],
    scaler_stats: dict[str, tuple[float, float]],
    raw_lookup_matrix: np.ndarray,
    raw_lookup_hidden: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recrée une observation dans le même espace que `test_clean.csv`, puis
    reconstruit les 20 features sélectionnées du notebook 03.

    Important :
    - les champs saisis dans le formulaire sont des valeurs brutes ;
    - le notebook 03 fait son feature engineering APRÈS le RobustScaler ;
    - on doit donc d'abord remettre l'observation dans l'espace `test_clean`.
    """
    row_clean = {
        key: float(value)
        for key, value in clean_feature_defaults.items()
    }

    for key, value in form.items():
        if key in scaler_stats:
            row_clean[key] = _scale_raw_feature(float(value), key, scaler_stats)

    spkts_raw = max(float(form["spkts"]), 1.0)
    dpkts_raw = float(form["dpkts"])
    dpkts_safe = max(dpkts_raw, 1.0)
    sbytes_raw = float(form["sbytes"])
    dbytes_raw = float(form["dbytes"])
    dur_raw = float(form["dur"])

    approximated_originals = _infer_hidden_raw_features(
        form,
        raw_lookup_matrix,
        raw_lookup_hidden,
        scaler_stats,
    )
    approximated_originals.setdefault("smean", float(np.round(sbytes_raw / spkts_raw)))
    approximated_originals.setdefault("dmean", float(np.round(dbytes_raw / dpkts_safe if dpkts_raw > 0 else 0.0)))
    approximated_originals.setdefault("dinpkt", dur_raw / (dpkts_raw + 1.0))

    for key, value in approximated_originals.items():
        if key in scaler_stats:
            row_clean[key] = _scale_raw_feature(float(value), key, scaler_stats)

    sb = float(row_clean.get("sbytes", 0.0))
    db = float(row_clean.get("dbytes", 0.0))
    sp = float(row_clean.get("spkts", 0.0))
    dp = float(row_clean.get("dpkts", 0.0))

    derived = {
        "bytes_total":        sb + db,
        "bytes_per_pkt_src":  sb / (sp + 1.0),
        "bytes_ratio":        sb / (db + 1.0),
        "bytes_diff_norm":    abs(sb - db) / (sb + db + 1.0),
        "bytes_per_pkt_dst":  db / (dp + 1.0),
        "pkts_total":         sp + dp,
        "log1p_dbytes":       np.log1p(np.clip(db, 0.0, None)),
    }

    row_featured = {
        key: float(row_clean.get(key, 0.0))
        for key in selected_feature_names
    }
    for key, value in derived.items():
        if key in row_featured:
            row_featured[key] = float(value)

    return pd.DataFrame(
        [{col: row_featured[col] for col in selected_feature_names}],
        columns=selected_feature_names,
    )


def _ensure_best_model(state: dict) -> None:
    """
    Charge le meilleur modèle (Ensemble 3) et le QT en mémoire si besoin.
    On charge une seule fois au premier appel.
    """
    if "best_model_loaded" in state:
        return

    qt = load_qt()
    state["qt"] = qt

    scaler = load_scaler()
    state["scaler"] = scaler
    state["scaler_stats"] = _build_scaler_stats(scaler)

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
    df_test_clean = load_test_clean_data()
    df_test_raw = load_raw_test_data()

    feature_names = [c for c in df_test.columns if c != TARGET_COLUMN]
    clean_feature_names = list(getattr(state["scaler"], "feature_names_in_", []))
    clean_feature_defaults = (
        df_test_clean[clean_feature_names]
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
    state["clean_feature_defaults"] = clean_feature_defaults
    state["raw_lookup_matrix"] = np.column_stack([
        [
            _scale_raw_feature(float(value), name, state["scaler_stats"])
            for value in df_test_raw[name].astype(float).values
        ]
        for name in EDITABLE_INPUT_NAMES
    ]).astype(np.float32)
    state["raw_lookup_hidden"] = df_test_raw.loc[:, list(INFERRED_RAW_FIELDS)].copy()
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736

    return {
        "status": 200,
        "best_model": {
<<<<<<< HEAD
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
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    }


# ── POST /api/predict/single ──────────────────────────────────────────────────

@router.post("/single", summary="Prédire une connexion réseau")
def predict_single(request: Request, data: ConnectionRequest):
    """
<<<<<<< HEAD
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
=======
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
    clean_feature_defaults = state["clean_feature_defaults"]
    raw_lookup_matrix = state["raw_lookup_matrix"]
    raw_lookup_hidden = state["raw_lookup_hidden"]
    scaler_stats = state["scaler_stats"]
    reference_scores = state["prediction_reference_scores"]
    threshold = state["prediction_threshold"]
    contamination = state["prediction_contamination"]

    # ── Construire le vecteur de features ─────────────────────────────────────
    # On démarre depuis les médianes du dataset de référence pour les features
    # non exposées, puis on remplace avec les variables éditables et les
    # dérivations exactes du notebook 03 quand elles sont disponibles.
    form = data.model_dump()
    row_df = _build_prediction_row(
        form,
        clean_feature_defaults,
        feature_names,
        scaler_stats,
        raw_lookup_matrix,
        raw_lookup_hidden,
    )

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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736

    return {
        "status":     200,
        "prediction": pred,
        "label":      "Anomalie 🚨" if pred == 1 else "Normal ✅",
<<<<<<< HEAD
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
=======
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
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
