"""Web Push notifications (VAPID), delivered even when the dashboard is closed."""

from __future__ import annotations

import asyncio
import json
import logging

from app.core.config import Settings
from app.db.session import Database
from app.models import PushSubscription
from app.repositories.notification import PushSubscriptionRepository
from app.schemas.alert import AlertRead
from app.services.notifications.base import NotificationChannel

logger = logging.getLogger(__name__)

_SEVERITY_LABEL = {
    "info": "Info",
    "low": "Faible",
    "medium": "Moyenne",
    "high": "Haute",
    "critical": "Critique",
}


class WebPushChannel(NotificationChannel):
    name = "webpush"

    def __init__(self, settings: Settings, database: Database) -> None:
        self._settings = settings
        self._database = database

    async def send_alert(self, alert: AlertRead) -> None:
        payload = {
            "title": f"[{_SEVERITY_LABEL.get(alert.severity, alert.severity)}] {alert.title}",
            "body": alert.message,
            "url": "/alerts",
            "tag": alert.rule_code,
            "severity": alert.severity,
        }
        await self._broadcast(payload)

    async def send_message(self, title: str, body: str, url: str = "/") -> None:
        await self._broadcast({"title": title, "body": body, "url": url, "tag": "message"})

    async def send_to_subscriptions(
        self, subscriptions: list[PushSubscription], payload: dict[str, str]
    ) -> list[str]:
        """Send and return the endpoints that are gone (to be deleted)."""
        results = await asyncio.gather(
            *(asyncio.to_thread(self._send_one, sub, payload) for sub in subscriptions)
        )
        return [
            sub.endpoint for sub, alive in zip(subscriptions, results, strict=True) if not alive
        ]

    async def _broadcast(self, payload: dict[str, str]) -> None:
        async with self._database.session() as session:
            repo = PushSubscriptionRepository(session)
            subscriptions = list(await repo.list_all())
            if not subscriptions:
                return
            expired = await self.send_to_subscriptions(subscriptions, payload)
            if expired:
                await repo.delete_by_endpoints(expired)
                await session.commit()
                logger.info("Removed %d expired push subscriptions", len(expired))

    def _send_one(self, subscription: PushSubscription, payload: dict[str, str]) -> bool:
        from pywebpush import WebPushException, webpush

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self._settings.vapid_private_key.get_secret_value(),
                vapid_claims={"sub": self._settings.vapid_subject},
                ttl=3600,
                timeout=10,
            )
            return True
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                return False
            logger.warning("Web push failed (%s): %s", status, exc)
            return True
        except Exception:
            logger.exception("Unexpected Web Push error")
            return True
