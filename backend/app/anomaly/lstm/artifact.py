"""Model artifact format (MLOps).

Each trained model is a versioned folder:

    artifacts/anomaly_lstm/<version>/
        model.pt        weights (state_dict only: safe to load, no pickled code)
        metadata.json   everything needed to reproduce preprocessing and decisions

`artifacts/anomaly_lstm/latest` contains the same files for the version in production,
so promoting or rolling back a model is a copy, not a code change.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

METADATA_FILE = "metadata.json"
WEIGHTS_FILE = "model.pt"


@dataclass
class LSTMArtifactMetadata:
    version: str
    created_at: str
    feature_names: list[str]
    window_minutes: int
    sequence_length: int  # number of predicted steps; the model reads sequence_length + 1 windows
    hidden_size: int
    num_layers: int
    threshold: float
    scaler: dict[str, Any]
    score_horizon: int = 3
    metrics: dict[str, float] = field(default_factory=dict)
    training_data: dict[str, Any] = field(default_factory=dict)
    model_type: str = "lstm_forecaster"

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / METADATA_FILE).write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path) -> LSTMArtifactMetadata:
        path = directory / METADATA_FILE
        if not path.is_file():
            raise FileNotFoundError(f"No LSTM metadata found at {path}")
        return cls(**json.loads(path.read_text(encoding="utf-8")))
