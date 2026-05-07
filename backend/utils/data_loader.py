"""
<<<<<<< HEAD
data_loader.py — Chargement des données du projet.

Ce module gère deux choses :
    1. Lire les CSV produits par les notebooks (train/test_featured.csv)
    2. Fournir les données formatées pour les routes API

On utilise un générateur (read_csv_chunks) pour ne pas charger tout le dataset
en mémoire d'un coup — utile pour les grands fichiers.

Utilisation :
    from utils.data_loader import DataLoader

    dl = DataLoader()
    X_test, y_test, df_test = dl.load_test()
    overview = dl.get_overview(df_test)
=======
data_loader.py — Charge les datasets produits par les notebooks.
On travaille directement avec train_featured.csv et test_featured.csv
(déjà prétraités et enrichis par les notebooks 02, 03, 04).
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
<<<<<<< HEAD
from typing import Generator

from config import (
    TEST_FEATURED_FILE, TRAIN_FEATURED_FILE,
    MODEL_COMPARISON_FILE, TARGET_COLUMN,
    CHUNK_SIZE, VIZ_MAX_POINTS,
=======

from config import (
    RAW_TEST_FILE, TEST_FEATURED_FILE, TEST_CLEAN_FILE, TRAIN_FEATURED_FILE,
    MODEL_COMPARISON_FILE, TARGET_COLUMN,
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
)
from utils.exceptions import DataLoadError

logger = logging.getLogger(__name__)


<<<<<<< HEAD
# ── Générateur de lecture par chunks ──────────────────────────────────────────

def read_csv_chunks(
    filepath: Path,
    chunksize: int = CHUNK_SIZE,
) -> Generator[pd.DataFrame, None, None]:
    """
    Lit un CSV par morceaux sans tout charger en mémoire.

    C'est un générateur : il retourne un chunk à la fois avec yield.
    Utile pour les grands fichiers (175k+ lignes).

    Args:
        filepath (Path)  : Chemin vers le fichier CSV.
        chunksize (int)  : Nombre de lignes par chunk.

    Yields:
        pd.DataFrame : Un morceau du dataset.

    Raises:
        DataLoadError : Si le fichier est introuvable.

    Exemple :
        for chunk in read_csv_chunks(TRAIN_FEATURED_FILE):
            process(chunk)
    """
    if not filepath.exists():
        raise DataLoadError(
            f"Fichier introuvable : {filepath.name}",
            details=str(filepath),
        )

    logger.debug(f"Lecture par chunks de {filepath.name} (taille={chunksize})")

    for chunk in pd.read_csv(filepath, chunksize=chunksize):
        yield chunk


# ── Classe principale ──────────────────────────────────────────────────────────

class DataLoader:
    """
    Charge et expose les données du projet.

    Les données sont mises en cache dans l'instance après le premier chargement.
    On n'utilise pas de variable globale : l'état est dans l'objet.

    Exemple :
        dl = DataLoader()
        X, y, df = dl.load_test()    # charge depuis le disque
        X, y, df = dl.load_test()    # retourne le cache (pas de relecture)
    """

    def __init__(self):
        self._X_test:  np.ndarray | None = None
        self._y_test:  np.ndarray | None = None
        self._df_test: pd.DataFrame | None = None

    # ── Chargement du test set ─────────────────────────────────────────────────

    def load_test(self) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        """
        Charge le jeu de test (test_featured.csv).
        Met le résultat en cache pour éviter de relire le fichier.

        Returns:
            tuple: (X_test, y_test, df_test)
                - X_test  (np.ndarray)  : Features, shape (82332, 20)
                - y_test  (np.ndarray)  : Labels 0/1, shape (82332,)
                - df_test (pd.DataFrame): Données complètes

        Raises:
            DataLoadError : Si le fichier n'existe pas.
        """
        if self._df_test is not None:
            return self._X_test, self._y_test, self._df_test

        df = self._read_featured(TEST_FEATURED_FILE)
        X, y = self._split_xy(df)

        self._X_test  = X
        self._y_test  = y
        self._df_test = df

        logger.info(f"Test set : {X.shape[0]:,} lignes × {X.shape[1]} features")
        return X, y, df

    def load_train(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Charge le jeu d'entraînement (train_featured.csv).
        Utilisé uniquement pour les statistiques de la Page 1.

        Returns:
            tuple: (X_train, y_train)

        Raises:
            DataLoadError : Si le fichier n'existe pas.
        """
        df = self._read_featured(TRAIN_FEATURED_FILE)
        X, y = self._split_xy(df)
        logger.info(f"Train set : {X.shape[0]:,} lignes × {X.shape[1]} features")
        return X, y

    def load_model_comparison(self) -> pd.DataFrame | None:
        """
        Charge le rapport de comparaison produit par le notebook 07.
        Retourne None si le fichier n'existe pas (pas d'erreur).

        Returns:
            pd.DataFrame | None : Métriques pré-calculées, ou None.
        """
        if not MODEL_COMPARISON_FILE.exists():
            logger.warning(f"model_comparison.csv absent : {MODEL_COMPARISON_FILE}")
            return None

        df = pd.read_csv(MODEL_COMPARISON_FILE, index_col=0)
        logger.info(f"Rapport de comparaison : {len(df)} modèles")
        return df

    # ── Données formatées pour les routes ─────────────────────────────────────

    def get_overview(self, df_test: pd.DataFrame) -> dict:
        """
        Retourne les informations générales sur le dataset pour la Page 1.

        Args:
            df_test (pd.DataFrame) : Dataset de test (avec colonne label).

        Returns:
            dict: Dimensions, taux d'anomalies, statistiques descriptives.
        """
        y = df_test[TARGET_COLUMN].values
        n_total     = len(y)
        n_anomalies = int(y.sum())
        n_normal    = int((y == 0).sum())

        numeric_cols = df_test.drop(columns=[TARGET_COLUMN]).select_dtypes(include=[np.number])
        stats        = numeric_cols.describe(percentiles=[0.25, 0.5, 0.75, 0.95]).T

        return {
            "test_set": {
                "n_rows":       n_total,
                "n_features":   int(df_test.shape[1] - 1),
                "n_anomalies":  n_anomalies,
                "n_normal":     n_normal,
                "anomaly_rate": round(n_anomalies / n_total * 100, 2),
            },
            "train_set": {
                "n_rows":     175_341,
                "n_features": 20,
            },
            "feature_names": list(numeric_cols.columns),
            "numeric_stats": {
                col: {k: round(float(v), 4) for k, v in stats.loc[col].items()}
                for col in stats.index
            },
        }

    def get_feature_distributions(
        self,
        df_test: pd.DataFrame,
        top_n: int = 10,
    ) -> dict:
        """
        Distribution des features numériques séparée par classe.
        Utilisé pour les histogrammes comparatifs de la Page 1.

        Args:
            df_test (pd.DataFrame) : Dataset de test.
            top_n (int)            : Nombre de features à inclure.

        Returns:
            dict: {feature: {normal: [...], anomaly: [...], stats_normal, stats_anomaly}}
        """
        feature_cols = [c for c in df_test.columns if c != TARGET_COLUMN][:top_n]
        n_sample = VIZ_MAX_POINTS // 2
        result = {}

        for col in feature_cols:
            normal  = df_test.loc[df_test[TARGET_COLUMN] == 0, col].dropna()
            anomaly = df_test.loc[df_test[TARGET_COLUMN] == 1, col].dropna()

            result[col] = {
                "normal":  normal.sample(min(len(normal), n_sample), random_state=42).tolist(),
                "anomaly": anomaly.sample(min(len(anomaly), n_sample), random_state=42).tolist(),
                "stats_normal":  self._col_stats(normal),
                "stats_anomaly": self._col_stats(anomaly),
            }

        return result

    # ── Méthodes privées ───────────────────────────────────────────────────────

    @staticmethod
    def _read_featured(filepath: Path) -> pd.DataFrame:
        """
        Lit un fichier CSV featuiré avec nettoyage basique.
        Remplace les inf par NaN puis remplit les NaN avec 0.
        """
        if not filepath.exists():
            raise DataLoadError(
                f"Fichier introuvable : {filepath.name}.\n"
                "Lance d'abord les notebooks 01 → 03.",
                details=str(filepath),
            )

        logger.debug(f"Lecture de {filepath.name}")
        df = pd.read_csv(filepath)
        df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
        return df

    @staticmethod
    def _split_xy(
        df: pd.DataFrame,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Sépare features et labels, retourne des arrays numpy typés."""
        X = df.drop(columns=[TARGET_COLUMN]).values.astype(np.float32)
        y = df[TARGET_COLUMN].values.astype(np.int8)
        return X, y

    @staticmethod
    def _col_stats(series: pd.Series) -> dict:
        """Calcule mean, std, p95 sur une série. Retourne {} si vide."""
        if len(series) == 0:
            return {}
        return {
            "mean": round(float(series.mean()), 4),
            "std":  round(float(series.std()),  4),
            "p95":  round(float(np.percentile(series, 95)), 4),
        }
=======
def load_test_data() -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """
    Charge le jeu de test produit par le notebook 03.
    Retourne X (features), y (labels) et le DataFrame brut.

    Returns:
        tuple: (X_test, y_test, df_test)
            - X_test (np.ndarray) : Features (82332, 20)
            - y_test (np.ndarray) : Labels 0/1 (82332,)
            - df_test (DataFrame) : Données complètes pour l'affichage

    Raises:
        DataLoadError: Si le fichier est introuvable.
    """
    if not TEST_FEATURED_FILE.exists():
        raise DataLoadError(
            f"Fichier test introuvable : {TEST_FEATURED_FILE}\n"
            "Lance d'abord les notebooks 01 → 03."
        )

    logger.info(f"Chargement de {TEST_FEATURED_FILE}")
    df = pd.read_csv(TEST_FEATURED_FILE)

    X = df.drop(columns=[TARGET_COLUMN]).replace([np.inf, -np.inf], np.nan).fillna(0).values
    y = df[TARGET_COLUMN].values

    logger.info(f"Test set chargé : {X.shape[0]:,} lignes × {X.shape[1]} features")
    return X.astype(np.float32), y.astype(np.int8), df


def load_test_clean_data() -> pd.DataFrame:
    """
    Charge le jeu de test prétraité du notebook 02.

    Ce fichier contient les 42 variables après encodage + RobustScaler.
    Il sert de base cohérente pour reconstruire une observation unitaire
    avant le feature engineering du notebook 03.
    """
    if not TEST_CLEAN_FILE.exists():
        raise DataLoadError(
            f"Fichier test_clean introuvable : {TEST_CLEAN_FILE}\n"
            "Lance d'abord les notebooks 01 → 02."
        )

    logger.info(f"Chargement de {TEST_CLEAN_FILE}")
    return pd.read_csv(TEST_CLEAN_FILE)


def load_raw_test_data() -> pd.DataFrame:
    """
    Charge le dataset de test brut UNSW-NB15.

    Sert uniquement à retrouver des voisins proches sur les champs éditables
    du formulaire afin d'inférer les features non exposées comme `dinpkt`
    et `ct_state_ttl`.
    """
    if not RAW_TEST_FILE.exists():
        raise DataLoadError(
            f"Fichier brut introuvable : {RAW_TEST_FILE}\n"
            "Le dataset UNSW-NB15 de test est requis pour la prédiction unitaire."
        )

    logger.info(f"Chargement de {RAW_TEST_FILE}")
    return pd.read_csv(RAW_TEST_FILE)


def load_train_data() -> tuple[np.ndarray, np.ndarray]:
    """
    Charge le jeu d'entraînement produit par le notebook 03.
    Utilisé uniquement pour les stats de Page 1.

    Returns:
        tuple: (X_train, y_train)
    """
    if not TRAIN_FEATURED_FILE.exists():
        raise DataLoadError(f"Fichier train introuvable : {TRAIN_FEATURED_FILE}")

    logger.info(f"Chargement de {TRAIN_FEATURED_FILE}")
    df = pd.read_csv(TRAIN_FEATURED_FILE)

    X = df.drop(columns=[TARGET_COLUMN]).replace([np.inf, -np.inf], np.nan).fillna(0).values
    y = df[TARGET_COLUMN].values

    logger.info(f"Train set chargé : {X.shape[0]:,} lignes × {X.shape[1]} features")
    return X.astype(np.float32), y.astype(np.int8)


def load_model_comparison() -> pd.DataFrame | None:
    """
    Charge le rapport de comparaison généré par le notebook 07.
    Contient les métriques pré-calculées de tous les modèles.

    Returns:
        pd.DataFrame | None: Métriques pré-calculées, ou None si absent.
    """
    if not MODEL_COMPARISON_FILE.exists():
        logger.warning(f"model_comparison.csv introuvable : {MODEL_COMPARISON_FILE}")
        return None

    df = pd.read_csv(MODEL_COMPARISON_FILE, index_col=0)
    logger.info(f"Rapport de comparaison chargé : {len(df)} modèles")
    return df


def get_dataset_overview(df_test: pd.DataFrame, df_train: pd.DataFrame | None = None) -> dict:
    """
    Retourne les informations générales sur le dataset pour la Page 1.

    Args:
        df_test (DataFrame): Données de test.
        df_train (DataFrame | None): Données d'entraînement (optionnel).

    Returns:
        dict: Dimensions, distribution, statistiques descriptives.
    """
    y = df_test[TARGET_COLUMN].values
    n_total    = len(y)
    n_anomalies = int(y.sum())
    n_normal    = int((y == 0).sum())

    numeric_cols = df_test.drop(columns=[TARGET_COLUMN]).select_dtypes(include=[np.number])
    stats        = numeric_cols.describe(percentiles=[0.25, 0.5, 0.75, 0.95]).T

    return {
        "test_set": {
            "n_rows":        n_total,
            "n_features":    int(df_test.shape[1] - 1),
            "n_anomalies":   n_anomalies,
            "n_normal":      n_normal,
            "anomaly_rate":  round(n_anomalies / n_total * 100, 2),
        },
        "train_set": {
            "n_rows":    175_341,
            "n_features": 20,
        } if df_train is None else {
            "n_rows":    len(df_train),
            "n_features": df_train.shape[1] - 1,
        },
        "feature_names": list(numeric_cols.columns),
        "numeric_stats": {
            col: {k: round(float(v), 4) for k, v in stats.loc[col].items()}
            for col in stats.index
        },
    }


def get_feature_distributions(df_test: pd.DataFrame, top_n: int = 10) -> dict:
    """
    Distribution des features numériques séparée par classe (normal vs anomalie).
    Utilisé par Page 1 pour les histogrammes comparatifs.

    Args:
        df_test (DataFrame): Dataset de test avec la colonne label.
        top_n (int): Nombre de features à inclure.

    Returns:
        dict: {feature: {normal: [...], anomaly: [...], stats_normal, stats_anomaly}}
    """
    from config import VIZ_MAX_POINTS

    feature_cols = [c for c in df_test.columns if c != TARGET_COLUMN][:top_n]
    result = {}

    for col in feature_cols:
        normal  = df_test.loc[df_test[TARGET_COLUMN] == 0, col].dropna()
        anomaly = df_test.loc[df_test[TARGET_COLUMN] == 1, col].dropna()

        n_sample = VIZ_MAX_POINTS // 2
        result[col] = {
            "normal":  normal.sample(min(len(normal), n_sample), random_state=42).tolist(),
            "anomaly": anomaly.sample(min(len(anomaly), n_sample), random_state=42).tolist(),
            "stats_normal": {
                "mean": round(float(normal.mean()), 4),
                "std":  round(float(normal.std()), 4),
                "p95":  round(float(np.percentile(normal, 95)), 4),
            } if len(normal) else {},
            "stats_anomaly": {
                "mean": round(float(anomaly.mean()), 4),
                "std":  round(float(anomaly.std()), 4),
                "p95":  round(float(np.percentile(anomaly, 95)), 4),
            } if len(anomaly) else {},
        }
    return result
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
