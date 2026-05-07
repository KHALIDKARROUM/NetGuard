"""
<<<<<<< HEAD
config.py — Configuration centrale du backend.

Toutes les constantes, chemins et paramètres sont ici.
On n'écrit jamais un chemin ou une valeur magique ailleurs dans le code.

Utilisation :
    from config import settings, MODELS_DIR, TARGET_COLUMN
=======
config.py — Configuration via pydantic-settings.
Les modèles sont déjà entraînés et sauvegardés dans models_saved/.
Le backend les charge au démarrage, il ne réentraîne rien.
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
"""

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

<<<<<<< HEAD

# ── Chemins de base ────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).resolve().parent          # backend/
DATA_DIR   = BASE_DIR.parent / "data"                 # data/
MODELS_DIR = BASE_DIR.parent / "models_saved"         # models_saved/
LOGS_DIR   = BASE_DIR / "logs"                        # backend/logs/

# On crée les dossiers s'ils n'existent pas encore
MODELS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ── Fichiers de données (produits par les notebooks) ──────────────────────────

TRAIN_FEATURED_FILE   = DATA_DIR / "featured" / "train_featured.csv"
TEST_FEATURED_FILE    = DATA_DIR / "featured" / "test_featured.csv"
MODEL_COMPARISON_FILE = DATA_DIR / "reports"  / "model_comparison.csv"


# ── Fichiers des modèles sauvegardés ──────────────────────────────────────────
# On déploie uniquement le meilleur modèle : Ensemble IF + LOF + Autoencoder

QT_FILE      = MODELS_DIR / "qt_improvements.pkl"   # QT original (ensemble)
QT_IF_FILE   = MODELS_DIR / "qt_if.pkl"              # QT pour Isolation Forest
IF_FILE   = MODELS_DIR / "if_base.pkl"           # Isolation Forest
LOF_FILE  = MODELS_DIR / "lof.pkl"               # Local Outlier Factor
AE_FILE   = MODELS_DIR / "autoencoder.pt"        # Autoencoder PyTorch
ENS3_FILE = MODELS_DIR / "ensemble_3models.pkl"  # Poids de l'ensemble (meilleur)


# ── Paramètres du dataset ──────────────────────────────────────────────────────

TARGET_COLUMN  = "label"

# Ordre exact des colonnes du modèle (extrait de test_featured.csv)
# NE PAS MODIFIER — le QT et l'IF ont été entraînés dans cet ordre
FEATURE_NAMES = [
    "bytes_total", "bytes_per_pkt_src", "bytes_ratio", "bytes_diff_norm",
    "sbytes", "sttl", "bytes_per_pkt_dst", "dbytes", "ct_state_ttl", "dttl",
    "rate", "sload", "dur", "smean", "log1p_dbytes", "dmean",
    "pkts_total", "dinpkt", "dload", "dpkts",
]    # Colonne cible : 0 = normal, 1 = anomalie
N_FEATURES             = 20     # Nombre de features après feature engineering
CONTAMINATION          = 0.551  # Taux réel du test set — utilisé pour les métriques uniquement
CONTAMINATION_PREDICT  = 0.10   # Seuil pour la prédiction unitaire (10% → percentile 90%)
CHUNK_SIZE             = 10_000 # Taille des chunks pour la lecture par générateur


# ── Architecture de l'Autoencoder ─────────────────────────────────────────────
# Doit correspondre exactement au notebook 06

AE_INPUT_DIM   = 20          # = N_FEATURES
AE_HIDDEN_DIMS = [16, 8, 4]  # Couches de l'encodeur


# ── Paramètres de visualisation ───────────────────────────────────────────────

VIZ_MAX_POINTS   = 5_000   # Max points dans les graphiques (performance)
PCA_N_COMPONENTS = 2       # Réduction en 2D pour le scatter plot


# ── Logging ────────────────────────────────────────────────────────────────────

LOG_FILE        = LOGS_DIR / "app.log"
LOG_FORMAT      = "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES   = 5 * 1024 * 1024   # 5 MB par fichier de log
LOG_BACKUP_COUNT = 3


# ── Paramètres de prédiction unitaire ─────────────────────────────────────────

REFERENCE_SAMPLE_SIZE = 15_000   # Nombre de points pour le seuil de référence


# ── Settings serveur (lus depuis .env) ────────────────────────────────────────

class Settings(BaseSettings):
    """
    Paramètres du serveur FastAPI.
    Lus depuis le fichier .env à la racine du backend.

    Variables disponibles :
        API_HOST    : adresse d'écoute (défaut : 0.0.0.0)
        API_PORT    : port d'écoute   (défaut : 5000)
        API_DEBUG   : mode debug      (défaut : false)
        LOG_LEVEL   : niveau de log   (défaut : INFO)
    """

=======
# ── Chemins ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
DATA_DIR    = BASE_DIR.parent / "data"
MODELS_DIR  = BASE_DIR.parent / "models_saved"
LOGS_DIR    = BASE_DIR / "logs"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Données ────────────────────────────────────────────────────────────────────
# Fichiers produits par les notebooks
TRAIN_FEATURED_FILE    = DATA_DIR / "featured" / "train_featured.csv"
TEST_FEATURED_FILE     = DATA_DIR / "featured" / "test_featured.csv"
TEST_CLEAN_FILE        = DATA_DIR / "preprocessed" / "test_clean.csv"
RAW_TEST_FILE          = DATA_DIR / "UNSW_NB15_testing-set.csv"
MODEL_COMPARISON_FILE  = DATA_DIR / "reports"  / "model_comparison.csv"

# ── Modèles sauvegardés (produits par notebook 06) ─────────────────────────────
QT_FILE            = MODELS_DIR / "qt_improvements.pkl"   # QuantileTransformer
SCALER_FILE        = MODELS_DIR / "scaler.pkl"            # RobustScaler notebook 02
IF_FILE            = MODELS_DIR / "if_base.pkl"           # Isolation Forest
LOF_FILE           = MODELS_DIR / "lof.pkl"               # Local Outlier Factor
ENS2_FILE          = MODELS_DIR / "ensemble_if_lof.pkl"   # Config Ensemble IF+LOF
AE_FILE            = MODELS_DIR / "autoencoder.pt"        # Poids Autoencoder PyTorch
ENS3_FILE          = MODELS_DIR / "ensemble_3models.pkl"  # Config Ensemble IF+LOF+AE ← meilleur
BEST_CONFIG_FILE   = MODELS_DIR / "best_model_config.pkl" # Copie du meilleur

# ── Dataset : colonnes ─────────────────────────────────────────────────────────
TARGET_COLUMN      = "label"
ATTACK_CAT_COLUMN  = "attack_cat"
N_FEATURES         = 20   # Nombre de features dans train/test_featured.csv
CONTAMINATION      = 0.551  # Taux d'anomalies dans le test set (55.1%)

# ── Autoencoder : architecture (doit correspondre au notebook 06) ──────────────
AE_INPUT_DIM    = 20  # = N_FEATURES
AE_HIDDEN_DIMS  = [16, 8, 4]  # Encoder

# ── Visualisation ──────────────────────────────────────────────────────────────
VIZ_MAX_POINTS  = 5_000
PCA_N_COMPONENTS = 2

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE        = LOGS_DIR / "app.log"
LOG_FORMAT      = "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── Settings ───────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    """Lit les variables depuis .env — uniquement la config serveur."""
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_host:  str  = Field(default="0.0.0.0")
    api_port:  int  = Field(default=5000, ge=1024, le=65535)
    api_debug: bool = Field(default=False)
    log_level: str  = Field(default="INFO")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
<<<<<<< HEAD
        """Vérifie que le niveau de log est valide."""
=======
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level doit être parmi {allowed}")
        return upper


<<<<<<< HEAD
settings = Settings()
=======
settings = Settings()
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
