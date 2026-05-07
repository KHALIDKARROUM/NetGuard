"""
<<<<<<< HEAD
model_loader.py — Chargement et inférence du meilleur modèle.

On déploie uniquement l'Isolation Forest.
Les données sont dans l'espace normalisé du dataset (après preprocessing notebook 03).
Le QuantileTransformer N'EST PAS appliqué — IF a été entraîné sans lui.

Utilisation :
    from utils.model_loader import BestModelLoader

    loader = BestModelLoader()
    loader.load()
    scores = loader.predict_scores(X_raw)   # X_raw = données normalisées
    preds  = loader.scores_to_preds(scores)
"""

import logging
import time
import functools
import numpy as np
import joblib

from config import IF_FILE, QT_IF_FILE, CONTAMINATION, CONTAMINATION_PREDICT
=======
model_loader.py — Charge tous les modèles pré-entraînés depuis models_saved/.
Les modèles ont été produits par les notebooks 04, 05 et 06.
Ce module est le seul endroit où on touche aux fichiers .pkl et .pt.

Modèles disponibles :
  1. Isolation Forest        → if_base.pkl
  2. LOF                     → lof.pkl
  3. Ensemble IF+LOF         → ensemble_if_lof.pkl + if_base.pkl + lof.pkl
  4. Autoencoder (PyTorch)   → autoencoder.pt
  5. Ensemble IF+LOF+AE      → ensemble_3models.pkl  ← meilleur (F1=0.8443, AUC=0.9069)

Tous utilisent le même QuantileTransformer : qt_improvements.pkl
"""

import logging
import numpy as np
import joblib
from pathlib import Path

from config import (
    QT_FILE, IF_FILE, LOF_FILE, ENS2_FILE,
    AE_FILE, ENS3_FILE, BEST_CONFIG_FILE, SCALER_FILE,
    AE_INPUT_DIM, CONTAMINATION,
)
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
from utils.exceptions import ModelError

logger = logging.getLogger(__name__)


<<<<<<< HEAD
# ── Décorateur @timer ──────────────────────────────────────────────────────────

def timer(func):
    """
    Mesure le temps d'exécution d'une fonction.
    Retourne (résultat, durée_secondes) au lieu du résultat seul.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        return result, time.perf_counter() - t0
    return wrapper


# ── Classe principale ──────────────────────────────────────────────────────────

class BestModelLoader:
    """
    Charge et expose l'Isolation Forest — modèle déployé en production.

    Le modèle a été entraîné directement sur les données normalisées
    (espace du dataset après preprocessing notebook 03).
    Pas de QuantileTransformer en inférence.

    Exemple :
        loader = BestModelLoader()
        loader.load()
        scores = loader.predict_scores(X_raw)
        preds  = loader.scores_to_preds(scores)
    """

    MODEL_NAME = "Isolation Forest"

    def __init__(self):
        self._qt       = None
        self._if_model = None
        self._loaded   = False

    # ── Propriétés publiques ───────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return self.MODEL_NAME

    @property
    def cfg(self) -> dict:
        """Config factice pour compatibilité avec les routes."""
        return {
            "w_if":          1.0,
            "w_lof":         0.0,
            "w_ae":          0.0,
            "contamination": CONTAMINATION_PREDICT,
        }

    @property
    def has_autoencoder(self) -> bool:
        return False

    # ── Chargement ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Charge l'Isolation Forest et son QuantileTransformer depuis models_saved/.
        Idempotent — un deuxième appel ne fait rien.

        Raises:
            ModelError : Si if_base.pkl ou qt_if.pkl est absent.
        """
        if self._loaded:
            return

        if not IF_FILE.exists():
            raise ModelError("Isolation Forest introuvable.", details=str(IF_FILE))

        if not QT_IF_FILE.exists():
            raise ModelError("QuantileTransformer IF introuvable.", details=str(QT_IF_FILE))

        self._qt       = joblib.load(QT_IF_FILE)
        self._if_model = joblib.load(IF_FILE)
        self._loaded   = True
        logger.info(f"Isolation Forest chargé depuis {IF_FILE}")
        logger.info(f"QT IF chargé depuis {QT_IF_FILE}")

    # ── Inférence ──────────────────────────────────────────────────────────────

    @timer
    def predict_scores(self, X) -> np.ndarray:
        """
        Calcule les scores d'anomalie normalisés [0,1].
        Accepte un DataFrame (avec noms de colonnes) ou un numpy array.
        Le décorateur @timer retourne (scores, durée).

        Args:
            X : DataFrame ou np.ndarray, shape (n, 20).

        Returns:
            tuple: (scores np.ndarray [0,1], durée float)
        """
        self._check_loaded()
        return self._normalize(self._get_if_raw(X))

    def predict_scores_with_detail(self, X) -> dict:
        """
        Scores avec détail par composant (compatibilité routes).

        Args:
            X_raw (np.ndarray) : Données normalisées.

        Returns:
            dict: {"if", "lof", "ae", "final"}
        """
        self._check_loaded()
        sc = self._normalize(self._get_if_raw(X))
        zeros = np.zeros_like(sc)
        return {"if": sc, "lof": zeros, "ae": zeros, "final": sc}

    def predict_scores_with_reference(
        self,
        X,
        raw_ref: dict,
    ) -> dict:
        """
        Inférence unitaire — rang percentile du score brut dans la référence.

        On utilise le rang percentile plutôt que min-max pour éviter
        que le score soit clippé à 0 ou 1 quand la connexion sort du range.
        Plus le rang est élevé, plus la connexion est anormale.

        Args:
            X        : DataFrame ou np.ndarray (1 ligne).
            raw_ref  : {"if_raw": scores bruts de référence (array trié)}

        Returns:
            dict: {"if", "lof", "ae", "final"} — valeurs dans [0,1]
        """
        self._check_loaded()
        # Inférence unitaire SANS QT — le QT sur 1 ligne est instable
        raw_if     = self._get_if_raw_no_qt(X)
        ref_sorted = np.sort(raw_ref["if_raw"])
        rank       = float(np.searchsorted(ref_sorted, raw_if[0], side="right"))
        sc_if      = np.array([rank / len(ref_sorted)], dtype=np.float32)
        zeros      = np.zeros_like(sc_if)
        return {"if": sc_if, "lof": zeros, "ae": zeros, "final": sc_if}

    def scores_to_preds(
        self,
        scores: np.ndarray,
        contamination: float | None = None,
    ) -> np.ndarray:
        """
        Convertit les scores en prédictions binaires (0=normal, 1=anomalie).

        Args:
            scores (np.ndarray)        : Scores [0,1].
            contamination (float|None) : Taux d'anomalies attendu.

        Returns:
            np.ndarray : Prédictions int8.
        """
        self._check_loaded()
        c = contamination if contamination is not None else CONTAMINATION
        threshold = np.percentile(scores, 100 * (1 - c))
        return np.where(scores >= threshold, 1, 0).astype(np.int8)

    def available_files(self) -> dict:
        """Vérifie l'existence des artefacts sur le disque."""
        from config import IF_FILE, LOF_FILE, AE_FILE, ENS3_FILE, QT_FILE
        return {
            "qt":               QT_FILE.exists(),
            "isolation_forest": IF_FILE.exists(),
            "lof":              LOF_FILE.exists(),
            "autoencoder":      AE_FILE.exists(),
            "ensemble3":        ENS3_FILE.exists(),
        }

    # ── Méthodes privées ───────────────────────────────────────────────────────

    def _check_loaded(self) -> None:
        if not self._loaded:
            raise ModelError("Le modèle n'est pas chargé. Appeler load() d'abord.")

    def _get_if_raw(self, X) -> np.ndarray:
        """
        Score brut IF avec QuantileTransformer.
        Accepte un DataFrame (batch) ou np.ndarray.
        Le QT est stable sur des batches — pour l'inférence unitaire,
        utiliser _get_if_raw_no_qt() à la place.
        """
        import pandas as pd
        from config import FEATURE_NAMES
        if not hasattr(X, "columns"):
            X = pd.DataFrame(X, columns=FEATURE_NAMES)
        X_qt = self._qt.transform(X)
        return self._if_model.decision_function(X_qt).astype(np.float32)

    def _get_if_raw_no_qt(self, X) -> np.ndarray:
        """
        Score brut IF SANS QuantileTransformer.
        Utilisé pour l'inférence unitaire — le QT sur 1 ligne est instable.
        Les données sont déjà dans l'espace normalisé du dataset.
        """
        import pandas as pd
        from config import FEATURE_NAMES
        if not hasattr(X, "columns"):
            X = pd.DataFrame(X, columns=FEATURE_NAMES)
        return self._if_model.decision_function(X.values).astype(np.float32)

    @staticmethod
    def _normalize(scores: np.ndarray) -> np.ndarray:
        """Min-max normalisation vectorisée."""
        s_min, s_max = scores.min(), scores.max()
        if s_max == s_min:
            return np.zeros_like(scores, dtype=np.float32)
        return ((scores - s_min) / (s_max - s_min)).astype(np.float32)

    @staticmethod
    def _normalize_with_ref(scores: np.ndarray, ref: np.ndarray) -> np.ndarray:
        """Normalise par rapport à une distribution de référence."""
        ref_min, ref_max = ref.min(), ref.max()
        if ref_max == ref_min:
            return np.zeros_like(scores, dtype=np.float32)
        return np.clip(
            (scores - ref_min) / (ref_max - ref_min), 0.0, 1.0
        ).astype(np.float32)
=======
# ── Normalisation (identique aux notebooks) ────────────────────────────────────

def normalize_scores(scores: np.ndarray) -> np.ndarray:
    """Normalise les scores entre 0 et 1 (min-max vectorisé NumPy)."""
    s_min, s_max = scores.min(), scores.max()
    if s_max == s_min:
        return np.zeros_like(scores, dtype=np.float32)
    return ((scores - s_min) / (s_max - s_min)).astype(np.float32)


def normalize_with_reference(scores: np.ndarray, reference_scores: np.ndarray) -> np.ndarray:
    """
    Normalise des scores en utilisant la distribution d'un jeu de référence.

    Utile pour l'inférence unitaire : on évite de normaliser un seul score
    par rapport à lui-même, ce qui annulerait l'information.
    """
    ref_min, ref_max = reference_scores.min(), reference_scores.max()
    if ref_max == ref_min:
        return np.zeros_like(scores, dtype=np.float32)
    normalized = (scores - ref_min) / (ref_max - ref_min)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def scores_to_preds(scores: np.ndarray, contamination: float = CONTAMINATION) -> np.ndarray:
    """Convertit les scores en 0/1 selon le seuil percentile (identique aux notebooks)."""
    threshold = np.percentile(scores, 100 * (1 - contamination))
    return np.where(scores >= threshold, 1, 0).astype(np.int8)


# ── Chargement du QuantileTransformer ─────────────────────────────────────────

def load_qt():
    """
    Charge le QuantileTransformer commun sauvegardé dans le notebook 06.
    Utilisé pour transformer toutes les données avant inférence.

    Returns:
        QuantileTransformer: Transformateur ajusté sur le train set.

    Raises:
        ModelError: Si qt_improvements.pkl est introuvable.
    """
    if not QT_FILE.exists():
        raise ModelError(f"QuantileTransformer introuvable : {QT_FILE}")
    qt = joblib.load(QT_FILE)
    logger.info(f"QuantileTransformer chargé depuis {QT_FILE}")
    return qt


def load_scaler():
    """
    Charge le RobustScaler du notebook 02.
    Utilisé pour remettre les inputs bruts du formulaire dans le même espace
    que `test_clean.csv` avant le feature engineering.
    """
    if not SCALER_FILE.exists():
        raise ModelError(f"RobustScaler introuvable : {SCALER_FILE}")
    scaler = joblib.load(SCALER_FILE)
    logger.info(f"RobustScaler chargé depuis {SCALER_FILE}")
    return scaler


# ── Chargement des modèles individuels ────────────────────────────────────────

def load_isolation_forest():
    """
    Charge le modèle Isolation Forest (if_base.pkl).
    Entraîné sur train_featured.csv avec contamination='auto', 200 estimators.

    Returns:
        IsolationForest: Modèle sklearn prêt pour decision_function().
    """
    if not IF_FILE.exists():
        raise ModelError(f"Isolation Forest introuvable : {IF_FILE}")
    model = joblib.load(IF_FILE)
    logger.info("Isolation Forest chargé")
    return model


def load_lof():
    """
    Charge le modèle LOF (lof.pkl).
    Entraîné en mode novelty=True sur un échantillon de 20k points.

    Returns:
        LocalOutlierFactor: Modèle sklearn prêt pour score_samples().
    """
    if not LOF_FILE.exists():
        raise ModelError(f"LOF introuvable : {LOF_FILE}")
    model = joblib.load(LOF_FILE)
    logger.info("LOF chargé")
    return model


def load_autoencoder():
    """
    Charge l'Autoencoder PyTorch (autoencoder.pt).
    Architecture : Linear(20→16→8→4→8→16→20) avec ReLU.
    Entraîné uniquement sur le trafic normal (56k connexions).

    Returns:
        tuple: (ae_model, device) ou (None, None) si PyTorch indisponible.
    """
    if not AE_FILE.exists():
        logger.warning(f"Autoencoder introuvable : {AE_FILE}")
        return None, None

    try:
        import torch
        import torch.nn as nn

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Architecture identique au notebook 06
        ae = nn.Sequential(
            nn.Linear(AE_INPUT_DIM, 16), nn.ReLU(),
            nn.Linear(16, 8),            nn.ReLU(),
            nn.Linear(8, 4),
            nn.Linear(4, 8),             nn.ReLU(),
            nn.Linear(8, 16),            nn.ReLU(),
            nn.Linear(16, AE_INPUT_DIM),
        ).to(device)

        ae.load_state_dict(torch.load(AE_FILE, map_location=device))
        ae.eval()
        logger.info(f"Autoencoder PyTorch chargé ({device})")
        return ae, device

    except ImportError:
        logger.warning("PyTorch non installé — Autoencoder indisponible.")
        return None, None


def load_ensemble_config(ens_file: Path) -> dict:
    """
    Charge la configuration d'un modèle ensemble (poids + contamination).

    Args:
        ens_file (Path): Chemin vers le fichier .pkl de config.

    Returns:
        dict: {w_if, w_lof, [w_ae], contamination}
    """
    if not ens_file.exists():
        raise ModelError(f"Config ensemble introuvable : {ens_file}")
    cfg = joblib.load(ens_file)
    logger.info(f"Config ensemble chargée depuis {ens_file} → {cfg}")
    return cfg


# ── Inférence par modèle ───────────────────────────────────────────────────────

def get_if_scores(if_model, X_qt: np.ndarray) -> np.ndarray:
    """
    Scores Isolation Forest normalisés [0,1].
    decision_function retourne des valeurs négatives pour les anomalies → on normalise.

    Args:
        if_model: Modèle IsolationForest chargé.
        X_qt (np.ndarray): Données transformées par QuantileTransformer.

    Returns:
        np.ndarray: Scores entre 0 (normal) et 1 (anomalie).
    """
    return normalize_scores(get_if_raw_scores(if_model, X_qt))


def get_if_raw_scores(if_model, X_qt: np.ndarray) -> np.ndarray:
    """
    Score brut d'anomalie IF.
    Plus le score est grand, plus l'observation est anormale.
    """
    return (-if_model.decision_function(X_qt)).astype(np.float32)


def get_lof_scores(lof_model, X_qt: np.ndarray) -> np.ndarray:
    """
    Scores LOF normalisés [0,1].
    score_samples retourne des valeurs négatives pour les anomalies → on inverse.

    Args:
        lof_model: Modèle LOF chargé.
        X_qt (np.ndarray): Données transformées par QuantileTransformer.

    Returns:
        np.ndarray: Scores entre 0 (normal) et 1 (anomalie).
    """
    return normalize_scores(get_lof_raw_scores(lof_model, X_qt))


def get_lof_raw_scores(lof_model, X_qt: np.ndarray) -> np.ndarray:
    """
    Score brut d'anomalie LOF.
    Plus le score est grand, plus l'observation est anormale.
    """
    return (-lof_model.score_samples(X_qt)).astype(np.float32)


def get_ae_scores(ae_model, device, X_qt: np.ndarray) -> np.ndarray:
    """
    Scores Autoencoder = erreur de reconstruction MSE normalisée [0,1].
    Une erreur élevée → connexion anormale (le réseau ne sait pas la reconstruire).

    Args:
        ae_model: Modèle PyTorch chargé.
        device: torch.device (cpu ou cuda).
        X_qt (np.ndarray): Données transformées par QuantileTransformer.

    Returns:
        np.ndarray: Scores entre 0 (normal) et 1 (anomalie).
    """
    return normalize_scores(get_ae_raw_scores(ae_model, device, X_qt))


def get_ae_raw_scores(ae_model, device, X_qt: np.ndarray) -> np.ndarray:
    """
    Score brut Autoencoder = erreur de reconstruction.
    Plus l'erreur est grande, plus l'observation est anormale.
    """
    import torch
    X_t = torch.FloatTensor(X_qt).to(device)
    with torch.no_grad():
        recon_err = ((X_t - ae_model(X_t)) ** 2).mean(dim=1).cpu().numpy()
    return recon_err.astype(np.float32)


def get_ensemble3_scores(
    scores_if: np.ndarray,
    scores_lof: np.ndarray,
    scores_ae: np.ndarray,
    cfg: dict,
) -> np.ndarray:
    """
    Score de l'ensemble 3 modèles : moyenne pondérée des scores IF, LOF, AE.
    Meilleur modèle : w_if=0.1, w_lof=0.1, w_ae=0.8 → F1=0.8443, AUC=0.9069.

    Args:
        scores_if  : Scores Isolation Forest normalisés.
        scores_lof : Scores LOF normalisés.
        scores_ae  : Scores Autoencoder normalisés.
        cfg (dict) : {w_if, w_lof, w_ae}

    Returns:
        np.ndarray: Scores combinés entre 0 et 1.
    """
    return (
        cfg["w_if"]  * scores_if  +
        cfg["w_lof"] * scores_lof +
        cfg["w_ae"]  * scores_ae
    ).astype(np.float32)
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
