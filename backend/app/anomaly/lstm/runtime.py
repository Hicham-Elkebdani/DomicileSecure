"""Loads a trained artifact and scores window sequences (shared by the API and evaluation)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from app.anomaly.features import FEATURE_NAMES, TARGET_FEATURES, FeatureScaler
from app.anomaly.lstm.artifact import WEIGHTS_FILE, LSTMArtifactMetadata
from app.anomaly.lstm.model import LSTMForecaster, anomaly_scores, compute_surprise


class LoadedForecaster:
    def __init__(self, model_dir: Path) -> None:
        self.metadata = LSTMArtifactMetadata.load(model_dir)
        if tuple(self.metadata.feature_names) != FEATURE_NAMES:
            raise ValueError("Model trained with different features: retrain it")
        self.scaler = FeatureScaler.from_dict(self.metadata.scaler)
        self.model = LSTMForecaster(
            len(FEATURE_NAMES),
            len(TARGET_FEATURES),
            self.metadata.hidden_size,
            self.metadata.num_layers,
        )
        state = torch.load(model_dir / WEIGHTS_FILE, map_location="cpu", weights_only=True)
        self.model.load_state_dict(state)
        self.model.eval()

    @property
    def windows_needed(self) -> int:
        return self.metadata.sequence_length + 1

    def score(self, sequences: np.ndarray, batch_size: int = 2048) -> tuple[np.ndarray, np.ndarray]:
        """sequences: raw windows, shape (batch, sequence_length + 1, features).

        Returns the anomaly scores (batch,) and the mean surprise per target over the scoring
        horizon (batch, targets), used to explain alerts.
        """
        horizon = self.metadata.score_horizon
        scores, explanations = [], []
        for i in range(0, len(sequences), batch_size):
            raw = sequences[i : i + batch_size].astype(np.float32)
            chunk = compute_surprise(
                self.model,
                torch.from_numpy(self.scaler.transform(raw)),
                torch.from_numpy(raw),
            )
            scores.append(anomaly_scores(chunk, horizon).numpy())
            explanations.append(chunk[:, -horizon:, :].mean(dim=1).numpy())
        if not scores:
            return np.empty(0), np.empty((0, len(TARGET_FEATURES)))
        return np.concatenate(scores), np.concatenate(explanations)
