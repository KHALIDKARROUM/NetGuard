"""
config.py — Configuration via pydantic-settings.
Les modèles sont déjà entraînés et sauvegardés dans models_saved/.
Le backend les charge au démarrage, il ne réentraîne rien.
"""

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level doit être parmi {allowed}")
        return upper


settings = Settings()
