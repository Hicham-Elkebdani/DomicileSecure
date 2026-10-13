from __future__ import annotations

import logging

from app.anomaly.base import AnomalyDetector
from app.anomaly.composite import HybridDetector
from app.anomaly.rules import RuleBasedDetector, RulesConfig
from app.core.config import Settings

logger = logging.getLogger(__name__)


def build_rules_detector(settings: Settings) -> RuleBasedDetector:
    return RuleBasedDetector(
        RulesConfig(
            night_start_hour=settings.night_start_hour,
            night_end_hour=settings.night_end_hour,
            door_open_max_seconds=settings.door_open_max_seconds,
            recurring_visitor_threshold=settings.recurring_visitor_threshold,
        )
    )


def build_anomaly_detector(settings: Settings) -> AnomalyDetector:
    """Build the configured engine.

    If the LSTM cannot be loaded (missing model, PyTorch not installed) the system falls back
    to the rules and logs an error: a security system must degrade gracefully, not stop.
    """
    rules = build_rules_detector(settings)
    if settings.anomaly_engine == "rules":
        return rules

    try:
        from app.anomaly.lstm.detector import LSTMAnomalyDetector

        lstm = LSTMAnomalyDetector(settings.lstm_model_dir)
    except Exception:
        logger.exception(
            "Cannot load the LSTM model from %s, falling back to the rule engine",
            settings.lstm_model_dir,
        )
        return rules

    if settings.anomaly_engine == "lstm":
        return lstm
    return HybridDetector([rules, lstm])
