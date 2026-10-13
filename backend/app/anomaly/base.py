from __future__ import annotations

from abc import ABC, abstractmethod

from app.anomaly.types import EventContext, Finding, HistorySpec, TickContext


class AnomalyDetector(ABC):
    """Common interface of every anomaly engine (rules, LSTM, hybrid)."""

    name: str = "base"

    @property
    def history_spec(self) -> HistorySpec | None:
        """Feature history the detector needs on each tick; None if it needs none."""
        return None

    @abstractmethod
    def on_event(self, ctx: EventContext) -> list[Finding]:
        """Called for every new event, right after it is stored."""

    @abstractmethod
    def on_tick(self, ctx: TickContext) -> list[Finding]:
        """Called periodically, for anomalies that are about time passing (e.g. door left open)."""
