"""Central backend configuration for the NetGuard API."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
MODELS_DIR = PROJECT_DIR / "models_saved"
LOGS_DIR = BASE_DIR / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_FEATURED_FILE = DATA_DIR / "featured" / "train_featured.csv"
TEST_FEATURED_FILE = DATA_DIR / "featured" / "test_featured.csv"
TEST_CLEAN_FILE = DATA_DIR / "preprocessed" / "test_clean.csv"
RAW_TEST_FILE = DATA_DIR / "UNSW_NB15_testing-set.csv"
MODEL_COMPARISON_FILE = DATA_DIR / "reports" / "model_comparison.csv"

QT_FILE = MODELS_DIR / "qt_improvements.pkl"
QT_IF_FILE = MODELS_DIR / "qt_if.pkl"
SCALER_FILE = MODELS_DIR / "scaler.pkl"
IF_FILE = MODELS_DIR / "if_base.pkl"
LOF_FILE = MODELS_DIR / "lof.pkl"
ENS2_FILE = MODELS_DIR / "ensemble_if_lof.pkl"
AE_FILE = MODELS_DIR / "autoencoder.pt"
ENS3_FILE = MODELS_DIR / "ensemble_3models.pkl"
BEST_CONFIG_FILE = MODELS_DIR / "best_model_config.pkl"
SELECTED_FEATURES_FILE = MODELS_DIR / "selected_features.pkl"

TARGET_COLUMN = "label"
ATTACK_CAT_COLUMN = "attack_cat"

FEATURE_NAMES = [
    "bytes_total",
    "bytes_per_pkt_src",
    "bytes_ratio",
    "bytes_diff_norm",
    "sbytes",
    "sttl",
    "bytes_per_pkt_dst",
    "dbytes",
    "ct_state_ttl",
    "dttl",
    "rate",
    "sload",
    "dur",
    "smean",
    "log1p_dbytes",
    "dmean",
    "pkts_total",
    "dinpkt",
    "dload",
    "dpkts",
]

EDITABLE_INPUT_FIELDS = (
    "sbytes",
    "dbytes",
    "spkts",
    "dpkts",
    "dur",
    "rate",
    "sload",
    "dload",
    "sttl",
    "dttl",
)
INFERRED_RAW_FIELDS = ("ct_state_ttl", "smean", "dmean", "dinpkt")

N_FEATURES = 20
CONTAMINATION = 0.5506000097167566
REFERENCE_SAMPLE_SIZE = 5_000
VIZ_MAX_POINTS = 5_000
PCA_N_COMPONENTS = 2
CHUNK_SIZE = 10_000

AE_INPUT_DIM = 20
AE_HIDDEN_DIMS = [16, 8, 4]

LOG_FILE = LOGS_DIR / "app.log"
LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3


class Settings(BaseSettings):
    """Server settings read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=5000, ge=1024, le=65535)
    api_debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level


settings = Settings()
