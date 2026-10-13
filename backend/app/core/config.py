"""Application settings, loaded from environment variables and the `.env` file.

Every tunable value (thresholds, schedules, secrets) lives here so that behaviour can be
changed per environment without touching code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

_DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me-0123456789"  # noqa: S105
_DEV_WORKER_KEY = "dev-only-insecure-worker-key"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "DomicileSecure"
    environment: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = False
    timezone: str = "Africa/Casablanca"
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Database ---
    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'domicilesecure.db').as_posix()}"
    database_echo: bool = False

    # --- Security ---
    jwt_secret_key: SecretStr = SecretStr(_DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=24 * 60)
    worker_api_key: SecretStr = SecretStr(_DEV_WORKER_KEY)
    login_rate_limit_per_minute: int = Field(default=5, ge=1)

    # --- Face recognition (model 2) ---
    face_detector_model_path: Path = Path("artifacts/vision/face_detection_yunet_2023mar.onnx")
    face_recognizer_model_path: Path = Path("artifacts/vision/face_recognition_sface_2021dec.onnx")
    face_match_threshold: float = Field(default=0.363, ge=0.0, le=1.0)
    face_min_detection_score: float = Field(default=0.8, ge=0.0, le=1.0)
    max_upload_size_mb: int = Field(default=5, ge=1, le=50)
    sighting_gap_minutes: int = Field(default=30, ge=1)
    recurring_visitor_threshold: int = Field(default=3, ge=2)

    # --- Anomaly engine (model 3) ---
    anomaly_engine: Literal["rules", "lstm", "hybrid"] = "rules"
    night_start_hour: int = Field(default=23, ge=0, le=23)
    night_end_hour: int = Field(default=6, ge=0, le=23)
    door_open_max_seconds: int = Field(default=600, ge=30)
    resident_presence_minutes: int = Field(default=30, ge=1)
    alert_cooldown_minutes: int = Field(default=10, ge=0)
    anomaly_tick_seconds: int = Field(default=60, ge=5)
    lstm_model_dir: Path = Path("artifacts/anomaly_lstm/latest")

    # --- Notifications ---
    vapid_public_key: str = ""
    vapid_private_key: SecretStr = SecretStr("")
    vapid_subject: str = "mailto:admin@example.com"
    push_min_severity: Literal["info", "low", "medium", "high", "critical"] = "medium"

    # --- Scheduler ---
    scheduler_enabled: bool = True
    daily_summary_hour: int = Field(default=21, ge=0, le=23)

    @field_validator("face_detector_model_path", "face_recognizer_model_path", "lstm_model_dir")
    @classmethod
    def _resolve_relative_to_backend(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)  # raises if unknown
        return value

    @model_validator(mode="after")
    def _forbid_insecure_defaults_in_production(self) -> Settings:
        if self.environment != "production":
            return self
        if self.jwt_secret_key.get_secret_value() == _DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set to a strong random value in production")
        if len(self.jwt_secret_key.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        if self.worker_api_key.get_secret_value() == _DEV_WORKER_KEY:
            raise ValueError("WORKER_API_KEY must be set in production")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS cannot contain '*' in production")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
