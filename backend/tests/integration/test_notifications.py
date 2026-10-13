from __future__ import annotations

import httpx

from app.models.enums import AlertSeverity
from app.schemas.alert import AlertRead
from app.services.notifications.base import NotificationChannel
from app.services.notifications.dispatcher import ChannelRoute, NotificationDispatcher

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/send/abc123",
    "keys": {"p256dh": "BPublicKeyExample", "auth": "authSecret"},
}


async def test_push_config_reports_disabled_without_vapid_keys(
    client: httpx.AsyncClient, user_headers: dict[str, str]
) -> None:
    config = (await client.get("/notifications/config", headers=user_headers)).json()
    assert config == {"enabled": False, "vapid_public_key": ""}
    test = await client.post("/notifications/test", headers=user_headers)
    assert test.status_code == 503


async def test_subscribe_is_idempotent_and_unsubscribe_is_owner_only(
    client: httpx.AsyncClient, user_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    for _ in range(2):
        response = await client.post(
            "/notifications/subscriptions", json=SUBSCRIPTION, headers=user_headers
        )
        assert response.status_code == 201

    other = await client.request(
        "DELETE",
        "/notifications/subscriptions",
        json={"endpoint": SUBSCRIPTION["endpoint"]},
        headers=admin_headers,
    )
    assert other.status_code == 404

    mine = await client.request(
        "DELETE",
        "/notifications/subscriptions",
        json={"endpoint": SUBSCRIPTION["endpoint"]},
        headers=user_headers,
    )
    assert mine.status_code == 204


async def test_insecure_push_endpoint_is_rejected(
    client: httpx.AsyncClient, user_headers: dict[str, str]
) -> None:
    payload = {**SUBSCRIPTION, "endpoint": "http://insecure.example.com/x"}
    response = await client.post("/notifications/subscriptions", json=payload, headers=user_headers)
    assert response.status_code == 422


class RecordingChannel(NotificationChannel):
    def __init__(self, name: str, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.received: list[str] = []

    async def send_alert(self, alert: AlertRead) -> None:
        if self.fail:
            raise RuntimeError("channel down")
        self.received.append(alert.rule_code)


async def test_dispatcher_respects_severity_and_isolates_failures() -> None:
    import uuid
    from datetime import UTC, datetime

    dashboard, push, broken = (
        RecordingChannel("ws"),
        RecordingChannel("push"),
        RecordingChannel("broken", fail=True),
    )
    dispatcher = NotificationDispatcher(
        [
            ChannelRoute(broken, AlertSeverity.INFO),
            ChannelRoute(dashboard, AlertSeverity.INFO),
            ChannelRoute(push, AlertSeverity.MEDIUM),
        ]
    )

    def alert(code: str, severity: AlertSeverity) -> AlertRead:
        return AlertRead(
            id=uuid.uuid4(),
            source="rules",
            rule_code=code,
            severity=severity,
            status="new",
            title="t",
            message="m",
            details={},
            camera_id=None,
            event_id=None,
            person_id=None,
            created_at=datetime.now(UTC),
            resolved_at=None,
        )

    await dispatcher.dispatch(
        [alert("low_one", AlertSeverity.LOW), alert("high_one", AlertSeverity.HIGH)]
    )
    assert dashboard.received == ["low_one", "high_one"]
    assert push.received == ["high_one"]
