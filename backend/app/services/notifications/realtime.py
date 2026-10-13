"""WebSocket hub pushing alerts and events to connected dashboards.

In-process by design: correct for a single API instance. To run several API instances,
back `broadcast` with Redis pub/sub so every instance relays messages to its own clients.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from app.schemas.alert import AlertRead
from app.schemas.event import EventRead
from app.services.notifications.base import NotificationChannel

logger = logging.getLogger(__name__)


class RealtimeHub(NotificationChannel):
    name = "websocket"

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message_type: str, data: Any) -> None:
        payload = {"type": message_type, "data": jsonable_encoder(data)}
        async with self._lock:
            clients = list(self._clients)
        dead: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        if dead:
            async with self._lock:
                self._clients.difference_update(dead)
            logger.debug("Removed %d dead WebSocket clients", len(dead))

    async def send_alert(self, alert: AlertRead) -> None:
        await self.broadcast("alert.created", alert)

    async def publish_events(self, events: list[EventRead]) -> None:
        for event in events:
            await self.broadcast("event.created", event)

    async def send_message(self, title: str, body: str, url: str = "/") -> None:
        await self.broadcast("message", {"title": title, "body": body, "url": url})
