"""Central backend configuration for the NetGuard API."""

from pathlib import Path
import os
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
MODELS_DIR = PROJECT_DIR / "models_saved"
LOGS_DIR = Path(os.environ.get("NETGUARD_LOG_DIR", BASE_DIR / "logs"))

LOGS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_FEATURED_FILE = DATA_DIR / "featured" / "train_featured.csv"
TEST_FEATURED_FILE = DATA_DIR / "featured" / "test_featured.csv"
TEST_CLEAN_FILE = DATA_DIR / "preprocessed" / "test_clean.csv"
RAW_TEST_FILE = DATA_DIR / "UNSW_NB15_testing-set.csv"
RAW_TRAIN_FILE = DATA_DIR / "UNSW_NB15_training-set.csv"
MODEL_COMPARISON_FILE = DATA_DIR / "reports" / "model_comparison.csv"

# Historical experiment configuration below is used only by model_loader.py.
# Current serving uses the complete artifact configured by prediction_artifact.
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
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=5000, ge=1024, le=65535)
    api_debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    prediction_artifact: Path = Field(default=MODELS_DIR / "deployed/xgboost.pkl")
    prediction_registry: Path | None = Field(default=MODELS_DIR / "deployed/registry.json")
    deployment_mode: Literal["local", "shared"] = Field(default="local", validation_alias="NETGUARD_DEPLOYMENT_MODE")
    api_key: SecretStr | None = Field(default=None, validation_alias="NETGUARD_API_KEY")
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "backend"])
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:8501", "http://127.0.0.1:8501",
        "http://localhost:8502", "http://127.0.0.1:8502",
    ])
    max_request_bytes: int = Field(default=1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    request_body_timeout: float = Field(default=10, gt=0, le=60)
    requests_per_minute: int = Field(default=120, ge=1, le=10_000)
    max_inflight_requests: int = Field(default=2, ge=1, le=8)

    @field_validator("api_key", mode="before")
    @classmethod
    def empty_key_is_unset(cls, value):
        return None if value == "" else value

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value):
        if value is not None:
            secret = value.get_secret_value()
            if len(secret) < 32 or not secret.isascii() or any(char.isspace() for char in secret):
                raise ValueError("NETGUARD_API_KEY must contain at least 32 ASCII characters without whitespace")
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def validate_hosts(cls, hosts):
        if not hosts or any(not host or any(char in host for char in "*/:@ ") for host in hosts):
            raise ValueError("allowed_hosts must contain explicit hostnames without wildcards, schemes or ports")
        return hosts

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins):
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or "*" in origin:
                raise ValueError("cors_origins must contain exact HTTP(S) origins without paths or wildcards")
        return origins

    @model_validator(mode="after")
    def require_shared_authentication(self):
        if self.deployment_mode == "shared" and self.api_key is None:
            raise ValueError("Shared deployments require NETGUARD_API_KEY")
        return self

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level


settings = Settings()
