from __future__ import annotations

from collections.abc import Sequence

from app.anomaly.base import AnomalyDetector
from app.anomaly.types import EventContext, Finding, HistorySpec, TickContext


class HybridDetector(AnomalyDetector):
    """Runs several detectors and merges their findings (rules for safety-critical cases,
    LSTM for everything that "doesn't look like the usual routine")."""

    name = "hybrid"

    def __init__(self, detectors: Sequence[AnomalyDetector]) -> None:
        self.detectors = list(detectors)

    @property
    def history_spec(self) -> HistorySpec | None:
        specs = [d.history_spec for d in self.detectors if d.history_spec is not None]
        return specs[0] if specs else None

    def on_event(self, ctx: EventContext) -> list[Finding]:
        return [finding for d in self.detectors for finding in d.on_event(ctx)]

    def on_tick(self, ctx: TickContext) -> list[Finding]:
        return [finding for d in self.detectors for finding in d.on_tick(ctx)]
