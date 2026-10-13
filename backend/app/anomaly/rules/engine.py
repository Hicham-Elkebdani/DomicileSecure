"""Phase 1: explicit, explainable rules."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.anomaly.base import AnomalyDetector
from app.anomaly.rules.base import EventRule, TickRule
from app.anomaly.rules.config import RulesConfig
from app.anomaly.rules.door_rules import DoorLeftOpenRule, DoorOpenedAtNightRule
from app.anomaly.rules.person_rules import (
    RecurringVisitorRule,
    UnknownPersonAtNightRule,
    UnknownPersonWhileAwayRule,
    UnknownPersonWhileHomeRule,
)
from app.anomaly.types import EventContext, Finding, TickContext

logger = logging.getLogger(__name__)


def default_event_rules() -> list[EventRule]:
    return [
        UnknownPersonAtNightRule(),
        UnknownPersonWhileAwayRule(),
        UnknownPersonWhileHomeRule(),
        RecurringVisitorRule(),
        DoorOpenedAtNightRule(),
    ]


def default_tick_rules() -> list[TickRule]:
    return [DoorLeftOpenRule()]


class RuleBasedDetector(AnomalyDetector):
    name = "rules"

    def __init__(
        self,
        config: RulesConfig,
        event_rules: Sequence[EventRule] | None = None,
        tick_rules: Sequence[TickRule] | None = None,
    ) -> None:
        self.config = config
        self.event_rules = list(event_rules) if event_rules is not None else default_event_rules()
        self.tick_rules = list(tick_rules) if tick_rules is not None else default_tick_rules()

    def on_event(self, ctx: EventContext) -> list[Finding]:
        findings: list[Finding] = []
        for rule in self.event_rules:
            try:
                finding = rule.evaluate(ctx, self.config)
            except Exception:
                # A buggy rule must never stop the others from protecting the home.
                logger.exception("Rule %s failed", rule.code)
                continue
            if finding is not None:
                findings.append(finding)
        return findings

    def on_tick(self, ctx: TickContext) -> list[Finding]:
        findings: list[Finding] = []
        for rule in self.tick_rules:
            try:
                findings.extend(rule.evaluate(ctx, self.config))
            except Exception:
                logger.exception("Rule %s failed", rule.code)
        return findings
