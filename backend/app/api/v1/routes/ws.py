"""Real-time channel for the dashboard.

Authentication happens in the first message (`{"type": "auth", "token": "<jwt>"}`) rather
than in the URL, because query strings end up in proxy and server logs.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.api.deps import authenticate_token
from app.container import Container
from app.core.exceptions import AuthenticationError

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)

_AUTH_TIMEOUT_SECONDS = 5


@router.websocket("/ws")
async def realtime(websocket: WebSocket) -> None:
    container: Container = websocket.app.state.container
    await websocket.accept()
    try:
        message = await asyncio.wait_for(websocket.receive_json(), _AUTH_TIMEOUT_SECONDS)
        if not isinstance(message, dict) or message.get("type") != "auth":
            raise AuthenticationError("Premier message attendu : auth")
        async with container.database.session() as session:
            user = await authenticate_token(
                str(message.get("token", "")), session, container.settings
            )
    except (TimeoutError, AuthenticationError, ValueError, WebSocketDisconnect):
        await _safe_close(websocket, status.WS_1008_POLICY_VIOLATION)
        return

    await container.realtime.register(websocket)
    await websocket.send_json({"type": "ready", "data": {"user": user.email}})
    try:
        while True:
            # Clients may send pings; content is ignored. Disconnection ends the loop.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await container.realtime.unregister(websocket)


async def _safe_close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        logger.debug("WebSocket already closed")
