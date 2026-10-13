"""Rule interfaces. Adding a behaviour means adding a class, never editing the engine."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.anomaly.rules.config import RulesConfig
from app.anomaly.types import EventContext, Finding, TickContext


class EventRule(ABC):
    code: str

    @abstractmethod
    def evaluate(self, ctx: EventContext, config: RulesConfig) -> Finding | None: ...


class TickRule(ABC):
    code: str

    @abstractmethod
    def evaluate(self, ctx: TickContext, config: RulesConfig) -> list[Finding]: ...
