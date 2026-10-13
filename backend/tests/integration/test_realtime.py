"""WebSocket tests use Starlette's synchronous TestClient (httpx has no WebSocket support)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.container import Container
from app.core.security import create_access_token
from app.models import Camera, User


async def _seed(container: Container) -> tuple[str, str]:
    async with container.database.session() as session:
        user = User(email="ws@example.com", hashed_password="x", is_active=True, is_admin=False)
        camera = Camera(name="Salon", has_door=False)
        session.add_all([user, camera])
        await session.commit()
        token = create_access_token(
            str(user.id),
            secret=container.settings.jwt_secret_key.get_secret_value(),
            algorithm="HS256",
            expires_minutes=5,
        )
        return token, str(camera.id)


async def test_websocket_receives_alerts(
    app: FastAPI, container: Container, frozen_night: datetime
) -> None:
    token, camera_id = await _seed(container)
    night = frozen_night

    with TestClient(app) as client, client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "ready"

        response = client.post(
            "/api/v1/ingest/observations",
            headers={"X-API-Key": container.settings.worker_api_key.get_secret_value()},
            json={
                "camera_id": camera_id,
                "observations": [
                    {
                        "observed_at": night.isoformat(),
                        "kind": "person",
                        "label": "person",
                        "confidence": 0.9,
                    }
                ],
            },
        )
        assert response.status_code == 200

        assert ws.receive_json()["type"] == "event.created"
        alert = ws.receive_json()
        assert alert["type"] == "alert.created"
        assert alert["data"]["rule_code"] == "unknown_person_night"


async def test_websocket_rejects_missing_or_bad_auth(app: FastAPI) -> None:
    with TestClient(app) as client, client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json({"type": "auth", "token": "garbage"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1008
