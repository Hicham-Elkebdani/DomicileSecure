"""Phase 2: LSTM-based detector, same interface as the rule engine."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from app.anomaly.base import AnomalyDetector
from app.anomaly.features import FEATURE_NAMES, TARGET_FEATURES
from app.anomaly.types import EventContext, Finding, HistorySpec, TickContext
from app.models.enums import AlertSeverity

logger = logging.getLogger(__name__)

_FEATURE_LABELS_FR = {
    "residents": "présence des membres du foyer",
    "guests": "présence d'invités",
    "visitors": "visiteurs",
    "unknown": "personnes inconnues",
    "animals": "animaux",
    "vehicles": "véhicules",
    "door_open": "ouverture de la porte",
}


class LSTMAnomalyDetector(AnomalyDetector):
    name = "lstm"

    def __init__(self, model_dir: Path) -> None:
        from app.anomaly.lstm.runtime import LoadedForecaster

        self._runtime = LoadedForecaster(model_dir)
        self.metadata = self._runtime.metadata
        self._last_window_end: datetime | None = None
        logger.info(
            "LSTM model %s loaded (threshold=%.4f)", self.metadata.version, self.metadata.threshold
        )

    @property
    def history_spec(self) -> HistorySpec:
        return HistorySpec(self.metadata.window_minutes, self._runtime.windows_needed)

    def on_event(self, ctx: EventContext) -> list[Finding]:
        return []  # the LSTM reasons on completed time windows, see on_tick

    def score(self, windows: np.ndarray) -> tuple[float, np.ndarray]:
        scores, explanations = self._runtime.score(windows[None, ...])
        return float(scores[0]), explanations[0]

    def on_tick(self, ctx: TickContext) -> list[Finding]:
        if ctx.recent_windows is None or ctx.window_end is None:
            return []
        if ctx.window_end == self._last_window_end:
            return []  # each window is scored once
        self._last_window_end = ctx.window_end

        score, explanation = self.score(ctx.recent_windows)
        threshold = self.metadata.threshold
        if score <= threshold:
            return []

        ratio = score / threshold
        names = [FEATURE_NAMES[i] for i in TARGET_FEATURES]
        top = [names[i] for i in np.argsort(explanation)[::-1]][:2]
        reasons = ", ".join(_FEATURE_LABELS_FR[name] for name in top) or "activité globale"
        window_end = ctx.window_end.astimezone(ctx.local_time.tzinfo)
        window_start = window_end - timedelta(
            minutes=self.metadata.window_minutes * self.metadata.score_horizon
        )
        return [
            Finding(
                source="lstm",
                rule_code="lstm_behaviour_anomaly",
                severity=AlertSeverity.HIGH if ratio >= 3 else AlertSeverity.MEDIUM,
                title="Activité inhabituelle",
                message=(
                    f"L'activité entre {window_start:%H:%M} et {window_end:%H:%M} sort de "
                    f"l'ordinaire à cette heure (principalement : {reasons})."
                ),
                # Constant key: the alert cooldown groups a burst of unusual windows into one alert.
                dedupe_key="lstm_behaviour_anomaly",
                details={
                    "score": round(score, 5),
                    "threshold": round(threshold, 5),
                    "ratio": round(ratio, 2),
                    "top_features": top,
                    "model_version": self.metadata.version,
                },
            )
        ]
