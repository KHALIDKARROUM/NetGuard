"""
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
from utils.exceptions import ModelError

logger = logging.getLogger(__name__)


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