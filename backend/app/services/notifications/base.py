from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.alert import AlertRead


class NotificationChannel(ABC):
    """A way to reach the household (WebSocket, Web Push, e-mail, SMS...)."""

    name: str

    @abstractmethod
    async def send_alert(self, alert: AlertRead) -> None: ...

    async def send_message(self, title: str, body: str, url: str = "/") -> None:  # noqa: B027
        """Free-form notification (e.g. the daily summary). Optional for channels."""
