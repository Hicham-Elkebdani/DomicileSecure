from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import BACKEND_DIR


class WorkerSettings(BaseSettings):
    """Variables prefixed with WORKER_ (e.g. WORKER_CAMERA_SOURCE) in the environment/.env."""

    model_config = SettingsConfigDict(
        env_prefix="WORKER_", env_file=BACKEND_DIR / ".env", extra="ignore"
    )

    api_base_url: str = "http://localhost:8000/api/v1"
    api_key: SecretStr = SecretStr("dev-only-insecure-worker-key")  # same var as the API
    camera_id: uuid.UUID
    # Webcam index ("0"), RTSP URL ("rtsp://user:pass@192.168.1.20/stream") or a video file.
    camera_source: str = "0"

    detector_weights: str = "artifacts/vision/yolo11n.pt"
    detector_confidence: float = Field(default=0.45, ge=0.05, le=0.99)
    door_model_path: Path | None = None
    door_confidence: float = Field(default=0.5, ge=0.05, le=0.99)
    device: str | None = None  # "cpu", "cuda:0"... None = auto

    face_detector_model_path: Path = Path("artifacts/vision/face_detection_yunet_2023mar.onnx")
    face_recognizer_model_path: Path = Path("artifacts/vision/face_recognition_sface_2021dec.onnx")
    face_min_detection_score: float = Field(default=0.8, ge=0.0, le=1.0)

    target_fps: float = Field(default=5.0, gt=0, le=30)
    face_frames: int = Field(default=5, ge=1)
    max_track_wait_seconds: float = Field(default=3.0, gt=0)
    track_lost_seconds: float = Field(default=5.0, gt=0)
    door_debounce_frames: int = Field(default=5, ge=1)
    flush_interval_seconds: float = Field(default=2.0, gt=0)
    heartbeat_seconds: float = Field(default=30.0, gt=0)
    max_buffered_observations: int = Field(default=2000, ge=10)
    preview: bool = False
    log_level: str = "INFO"

    @field_validator("face_detector_model_path", "face_recognizer_model_path", "door_model_path")
    @classmethod
    def _resolve(cls, value: Path | None) -> Path | None:
        if value is None or value.is_absolute():
            return value
        return (BACKEND_DIR / value).resolve()

    @property
    def detector_weights_path(self) -> str:
        path = Path(self.detector_weights)
        return str(path if path.is_absolute() else BACKEND_DIR / path)
