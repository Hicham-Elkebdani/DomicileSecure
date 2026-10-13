"""End-to-end decision pipeline: worker observations -> identity -> events -> alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np

from app.container import Container
from app.scheduler import run_anomaly_tick
from tests.conftest import FakeFaceEmbedder, solid_image

RESIDENT_COLOR = (10, 200, 30)
STRANGER_COLOR = (200, 30, 90)


def observation(
    when: datetime,
    *,
    kind: str = "person",
    label: str = "person",
    face: np.ndarray | None = None,
    track_id: int = 1,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "observed_at": when.isoformat(),
        "kind": kind,
        "label": label,
        "confidence": 0.9,
        "track_id": track_id,
    }
    if face is not None:
        payload["face"] = {
            "embedding": face.tolist(),
            "model_name": "fake-model",
            "detection_score": 0.95,
        }
    return payload


async def ingest(
    client: httpx.AsyncClient, headers: dict[str, str], camera_id: str, *observations: dict
) -> dict:
    response = await client.post(
        "/ingest/observations",
        json={"camera_id": camera_id, "observations": list(observations)},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def alerts(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict]:
    return (await client.get("/alerts", headers=headers)).json()["items"]


async def test_ingest_requires_the_worker_key(client: httpx.AsyncClient, door_camera: dict) -> None:
    payload = {"camera_id": door_camera["id"], "observations": []}
    assert (await client.post("/ingest/observations", json=payload)).status_code == 401
    bad_key = {"X-API-Key": "wrong"}
    assert (
        await client.post("/ingest/observations", json=payload, headers=bad_key)
    ).status_code == 401


async def test_ingest_rejects_unknown_camera(
    client: httpx.AsyncClient, worker_headers: dict[str, str]
) -> None:
    payload = {
        "camera_id": "00000000-0000-0000-0000-000000000000",
        "observations": [observation(datetime.now(UTC))],
    }
    response = await client.post("/ingest/observations", json=payload, headers=worker_headers)
    assert response.status_code == 404


async def test_resident_is_recognised_and_stranger_raises_night_alert(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    worker_headers: dict[str, str],
    door_camera: dict,
    frozen_night: datetime,
) -> None:
    person = (
        await client.post(
            "/persons", json={"display_name": "Hicham", "role": "resident"}, headers=admin_headers
        )
    ).json()
    files = {"photo": ("f.png", solid_image(RESIDENT_COLOR), "image/png")}
    await client.post(f"/persons/{person['id']}/faces", files=files, headers=admin_headers)

    resident_face = FakeFaceEmbedder.vector_for_color(RESIDENT_COLOR)
    stranger_face = FakeFaceEmbedder.vector_for_color(STRANGER_COLOR)
    result = await ingest(
        client,
        worker_headers,
        door_camera["id"],
        observation(frozen_night, face=resident_face, track_id=1),
        observation(frozen_night + timedelta(minutes=1), face=stranger_face, track_id=2),
        observation(frozen_night + timedelta(minutes=2), kind="animal", label="cat", track_id=3),
    )
    assert result == {"events_created": 3, "alerts_created": 1}

    events = (await client.get("/events", headers=admin_headers)).json()["items"]
    identities = {e["kind"]: e["identity"] for e in events if e["kind"] != "person"}
    person_identities = sorted(e["identity"] for e in events if e["kind"] == "person")
    assert person_identities == ["resident", "unknown"]
    assert identities == {"animal": None}

    raised = await alerts(client, admin_headers)
    assert [(a["rule_code"], a["severity"]) for a in raised] == [("unknown_person_night", "high")]

    persons = (await client.get("/persons?role=visitor", headers=admin_headers)).json()
    assert len(persons) == 1 and persons[0]["display_name"].startswith("Visiteur")


async def test_repeated_stranger_is_deduplicated_then_suggested_as_guest(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    worker_headers: dict[str, str],
    door_camera: dict,
    container: Container,
) -> None:
    stranger = FakeFaceEmbedder.vector_for_color(STRANGER_COLOR)
    day = datetime.now(UTC).replace(hour=14, minute=0, second=0, microsecond=0)
    if day > datetime.now(UTC):
        day -= timedelta(days=1)

    # Three visits, each separated by more than the sighting gap (30 min).
    for i in range(3):
        await ingest(
            client,
            worker_headers,
            door_camera["id"],
            observation(day - timedelta(hours=3 - i), face=stranger, track_id=i),
        )

    raised = await alerts(client, admin_headers)
    codes = [a["rule_code"] for a in raised]
    # Same visitor within the cooldown => only one "away" alert, plus one guest suggestion.
    assert codes.count("unknown_person_away") == 1
    assert codes.count("recurring_visitor") == 1

    visitor = (await client.get("/persons?role=visitor", headers=admin_headers)).json()[0]
    assert visitor["sightings_count"] == 3 and visitor["is_recurring"] is True

    promoted = await client.patch(
        f"/persons/{visitor['id']}",
        json={"role": "guest", "display_name": "Tante Fatima"},
        headers=admin_headers,
    )
    assert promoted.json()["role"] == "guest"

    await ingest(
        client, worker_headers, door_camera["id"], observation(day, face=stranger, track_id=9)
    )
    latest = (await client.get("/events?limit=1", headers=admin_headers)).json()["items"][0]
    assert latest["identity"] == "guest"


async def test_door_left_open_alert_fires_once(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    worker_headers: dict[str, str],
    door_camera: dict,
    container: Container,
) -> None:
    opened = datetime.now(UTC) - timedelta(minutes=20)
    await ingest(
        client,
        worker_headers,
        door_camera["id"],
        observation(opened, kind="door", label="door_open"),
        observation(opened + timedelta(seconds=5), kind="door", label="door_open"),  # no change
    )
    camera = (await client.get(f"/cameras/{door_camera['id']}", headers=admin_headers)).json()
    assert camera["door_state"] == "open"

    assert await run_anomaly_tick(container) == 1
    assert await run_anomaly_tick(container) == 0  # same opening episode => no duplicate

    # "door_opened_night" may also fire depending on the wall-clock time; only check ours.
    left_open = [
        a for a in await alerts(client, admin_headers) if a["rule_code"] == "door_left_open"
    ]
    assert [a["severity"] for a in left_open] == ["high"]  # nobody home => high

    events = (await client.get("/events?kind=door", headers=admin_headers)).json()
    assert events["total"] == 1


async def test_alert_acknowledgement(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    worker_headers: dict[str, str],
    door_camera: dict,
    frozen_night: datetime,
) -> None:
    await ingest(client, worker_headers, door_camera["id"], observation(frozen_night))
    alert = (await alerts(client, admin_headers))[0]
    counts = (await client.get("/alerts/counts", headers=admin_headers)).json()
    assert counts["new"] == 1

    response = await client.patch(
        f"/alerts/{alert['id']}", json={"status": "dismissed"}, headers=admin_headers
    )
    assert response.json()["status"] == "dismissed"
    assert response.json()["resolved_at"] is not None
    assert (await client.get("/alerts/counts", headers=admin_headers)).json()["new"] == 0


async def test_daily_summary_and_activity(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    worker_headers: dict[str, str],
    door_camera: dict,
) -> None:
    now = datetime.now(UTC)
    await ingest(
        client,
        worker_headers,
        door_camera["id"],
        observation(now - timedelta(seconds=30), kind="animal", label="dog"),
        observation(now - timedelta(seconds=20), kind="door", label="door_open"),
        observation(now - timedelta(seconds=10), kind="door", label="door_closed"),
    )
    summary = (await client.get("/summaries/today", headers=admin_headers)).json()
    assert summary["stats"]["door_openings"] == 1
    assert summary["stats"]["animals"] == 1
    assert "Porte ouverte 1 fois" in summary["text"]

    generated = await client.post(f"/summaries/{summary['day']}/generate", headers=admin_headers)
    assert generated.status_code == 200 and generated.json()["is_final"] is True

    activity = (await client.get("/events/activity?days=7", headers=admin_headers)).json()
    assert len(activity) == 7
    assert activity[-1]["animals"] == 1 and activity[-1]["door_openings"] == 1


async def test_observation_validation(
    client: httpx.AsyncClient, worker_headers: dict[str, str], door_camera: dict
) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    naive = datetime.now().replace(tzinfo=None)
    for bad in (
        observation(future),
        {**observation(datetime.now(UTC)), "observed_at": naive.isoformat()},
        observation(datetime.now(UTC), kind="door", label="person"),
        observation(datetime.now(UTC), kind="animal", face=np.ones(128) / np.sqrt(128)),
    ):
        response = await client.post(
            "/ingest/observations",
            json={"camera_id": door_camera["id"], "observations": [bad]},
            headers=worker_headers,
        )
        assert response.status_code == 422, bad
