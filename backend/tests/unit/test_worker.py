from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import numpy as np
import pytest

from app.schemas.ingest import Observation
from vision.face.similarity import l2_normalize
from vision.types import BoundingBox, Detection, FaceEmbedding
from worker.client import IngestClient, WorkerAuthenticationError
from worker.door import DoorStateDebouncer
from worker.tracking import TrackAggregator

BOX = BoundingBox(10, 10, 110, 210)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def face(score: float = 0.95, size: float = 50) -> FaceEmbedding:
    return FaceEmbedding(
        BoundingBox(0, 0, size, size), score, l2_normalize(np.ones(128)), "sface-2021dec"
    )


def person(track_id: int = 1) -> Detection:
    return Detection("person", 0.9, BOX, track_id)


def test_animal_is_reported_once_immediately() -> None:
    aggregator = TrackAggregator()
    cat = Detection("cat", 0.8, BOX, 7)
    first = aggregator.update([cat], {})
    assert [o.label for o in first] == ["cat"]
    assert aggregator.update([cat], {}) == []


def test_unknown_labels_and_untracked_detections_are_ignored() -> None:
    aggregator = TrackAggregator()
    assert aggregator.update([Detection("chair", 0.9, BOX, 1)], {}) == []
    assert aggregator.update([Detection("person", 0.9, BOX, None)], {}) == []


def test_person_waits_for_face_frames_and_keeps_best_face() -> None:
    clock = FakeClock()
    aggregator = TrackAggregator(face_frames=3, max_wait_seconds=10, clock=clock)
    assert aggregator.update([person()], {1: face(size=20)}) == []
    assert aggregator.update([person()], {1: face(size=80)}) == []
    assert aggregator.needs_face(1)
    result = aggregator.update([person()], {1: None})
    assert len(result) == 1 and result[0].face is not None
    assert not aggregator.needs_face(1)


def test_person_without_face_is_reported_after_timeout() -> None:
    clock = FakeClock()
    aggregator = TrackAggregator(face_frames=5, max_wait_seconds=3, clock=clock)
    assert aggregator.update([person()], {1: None}) == []
    clock.now = 3.5
    result = aggregator.update([person()], {1: None})
    assert len(result) == 1 and result[0].face is None


def test_blurry_face_is_not_sent() -> None:
    clock = FakeClock()
    aggregator = TrackAggregator(face_frames=1, min_face_score=0.9, clock=clock)
    result = aggregator.update([person()], {1: face(score=0.85)})
    assert result[0].face is None


def test_lost_tracks_are_forgotten() -> None:
    clock = FakeClock()
    aggregator = TrackAggregator(lost_seconds=5, clock=clock)
    aggregator.update([Detection("dog", 0.8, BOX, 3)], {})
    clock.now = 6
    aggregator.update([], {})
    assert aggregator.active_tracks == 0


def test_door_debouncer() -> None:
    debouncer = DoorStateDebouncer(frames_required=3)
    sequence = ["door_closed"] * 3 + ["door_open", "door_closed"] + ["door_open"] * 3 + [None]
    changes = [c for c in (debouncer.update(label) for label in sequence) if c]
    assert changes == ["door_closed", "door_open"]


def _observation() -> Observation:
    return Observation(
        observed_at=datetime.now(UTC), kind="animal", label="cat", confidence=0.9, track_id=1
    )


def _client(handler) -> IngestClient:  # type: ignore[no-untyped-def]
    return IngestClient(
        "http://api/api/v1", "key", uuid.uuid4(), transport=httpx.MockTransport(handler)
    )


def test_client_keeps_observations_when_api_is_down() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        body = json.loads(request.content)
        assert request.headers["X-API-Key"] == "key"
        return httpx.Response(
            200, json={"events_created": len(body["observations"]), "alerts_created": 0}
        )

    client = _client(handler)
    client.enqueue([_observation(), _observation()])
    assert client.flush() == 0 and client.pending == 2
    assert client.flush() == 2 and client.pending == 0


def test_client_drops_rejected_batches_and_stops_on_bad_key() -> None:
    client = _client(lambda _: httpx.Response(422, json={"error": {}}))
    client.enqueue([_observation()])
    assert client.flush() == 0 and client.pending == 0

    client = _client(lambda _: httpx.Response(401))
    client.enqueue([_observation()])
    with pytest.raises(WorkerAuthenticationError):
        client.flush()


class FakeSource:
    is_live = False

    def __init__(self, frames: int) -> None:
        self._left = frames
        self.released = False

    def read(self) -> np.ndarray | None:
        if self._left == 0:
            return None
        self._left -= 1
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True


class FakeDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, frame: np.ndarray) -> list[Detection]:
        return self._detections


class FakeEmbedder:
    model_name = "sface-2021dec"
    embedding_dim = 128

    def embed(self, image: np.ndarray) -> list[FaceEmbedding]:
        return [face()]


def test_pipeline_end_to_end_with_fakes() -> None:
    import threading

    from worker.pipeline import CameraPipeline

    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/observations"):
            body = json.loads(request.content)
            sent.extend(body["observations"])
            return httpx.Response(200, json={"events_created": 1, "alerts_created": 0})
        return httpx.Response(204)

    source = FakeSource(frames=8)
    pipeline = CameraPipeline(
        source=source,  # type: ignore[arg-type]
        detector=FakeDetector([person(1), Detection("chair", 0.9, BOX, 2)]),  # type: ignore[arg-type]
        face_embedder=FakeEmbedder(),  # type: ignore[arg-type]
        door_detector=FakeDetector([Detection("door_open", 0.8, BOX)]),  # type: ignore[arg-type]
        client=_client(handler),
        aggregator=TrackAggregator(face_frames=3),
        door_debouncer=DoorStateDebouncer(frames_required=4),
        target_fps=1000,
        flush_interval_seconds=0.0001,
        heartbeat_seconds=0.0001,
    )
    pipeline.run(threading.Event())

    kinds = sorted((o["kind"], o["label"]) for o in sent)
    assert kinds == [("door", "door_open"), ("person", "person")]  # one per track, chair ignored
    person_obs = next(o for o in sent if o["kind"] == "person")
    assert person_obs["face"]["model_name"] == "sface-2021dec"
    assert source.released
