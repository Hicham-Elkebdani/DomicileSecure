from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.enums import AlertSeverity
from app.schemas.alert import AlertRead
from app.services.notifications.base import NotificationChannel

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChannelRoute:
    channel: NotificationChannel
    min_severity: AlertSeverity = AlertSeverity.INFO


class NotificationDispatcher:
    """Fans alerts out to every channel whose severity threshold is met.

    A failing channel is logged and skipped: a broken push service must not prevent the
    dashboard from receiving the alert.
    """

    def __init__(self, routes: Sequence[ChannelRoute]) -> None:
        self._routes = list(routes)

    async def dispatch(self, alerts: Sequence[AlertRead]) -> None:
        for alert in alerts:
            targets = [r for r in self._routes if alert.severity.rank >= r.min_severity.rank]
            await asyncio.gather(*(self._safe_send(r.channel, alert) for r in targets))

    async def broadcast_message(self, title: str, body: str, url: str = "/") -> None:
        for route in self._routes:
            try:
                await route.channel.send_message(title, body, url)
            except Exception:
                logger.exception("Channel %s failed to send a message", route.channel.name)

    @staticmethod
    async def _safe_send(channel: NotificationChannel, alert: AlertRead) -> None:
        try:
            await channel.send_alert(alert)
        except Exception:
            logger.exception("Channel %s failed to deliver alert %s", channel.name, alert.id)
