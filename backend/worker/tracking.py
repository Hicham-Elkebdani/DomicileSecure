"""Turns per-frame detections into one observation per tracked object.

Sending every frame would flood the API and trigger dozens of alerts for the same person.
Instead, each ByteTrack id is followed for a few frames: for people, the sharpest face is
kept, then a single observation is emitted.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.enums import EventKind
from app.schemas.ingest import FaceObservation, Observation
from vision.types import BoundingBox, Detection, FaceEmbedding
from worker.labels import KIND_BY_LABEL


@dataclass
class TrackState:
    track_id: int
    label: str
    kind: EventKind
    first_seen_at: datetime  # wall clock, sent to the API
    started: float  # monotonic, used for durations
    last_seen: float
    confidence: float
    bbox: BoundingBox
    face_attempts: int = 0
    best_face: FaceEmbedding | None = field(default=None, repr=False)
    reported: bool = False

    def consider_face(self, face: FaceEmbedding | None) -> None:
        self.face_attempts += 1
        if face is None:
            return
        quality = face.detection_score * face.bbox.area
        if self.best_face is None or quality > (
            self.best_face.detection_score * self.best_face.bbox.area
        ):
            self.best_face = face


class TrackAggregator:
    def __init__(
        self,
        *,
        face_frames: int = 5,
        max_wait_seconds: float = 3.0,
        lost_seconds: float = 5.0,
        min_face_score: float = 0.8,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._face_frames = face_frames
        self._max_wait = max_wait_seconds
        self._lost = lost_seconds
        self._min_face_score = min_face_score
        self._clock = clock
        self._wall_clock = wall_clock
        self._tracks: dict[int, TrackState] = {}

    @property
    def active_tracks(self) -> int:
        return len(self._tracks)

    def needs_face(self, track_id: int | None) -> bool:
        """Only compute face embeddings while they are still useful (saves CPU)."""
        if track_id is None:
            return False
        state = self._tracks.get(track_id)
        return state is None or (
            state.kind is EventKind.PERSON
            and not state.reported
            and state.face_attempts < self._face_frames
        )

    def update(
        self, detections: list[Detection], faces: dict[int, FaceEmbedding | None]
    ) -> list[Observation]:
        now = self._clock()
        ready: list[Observation] = []
        for detection in detections:
            kind = KIND_BY_LABEL.get(detection.label)
            if kind is None or detection.track_id is None:
                continue
            state = self._tracks.get(detection.track_id)
            if state is None:
                state = TrackState(
                    track_id=detection.track_id,
                    label=detection.label,
                    kind=kind,
                    first_seen_at=self._wall_clock(),
                    started=now,
                    last_seen=now,
                    confidence=detection.confidence,
                    bbox=detection.bbox,
                )
                self._tracks[detection.track_id] = state
            state.last_seen = now
            state.confidence = max(state.confidence, detection.confidence)
            state.bbox = detection.bbox
            if detection.track_id in faces:
                state.consider_face(faces[detection.track_id])

            if not state.reported and self._is_ready(state, now):
                ready.append(self._to_observation(state))
                state.reported = True

        self._forget_lost_tracks(now)
        return ready

    def _is_ready(self, state: TrackState, now: float) -> bool:
        if state.kind is not EventKind.PERSON:
            return True
        has_good_face = state.best_face is not None and state.face_attempts >= self._face_frames
        return has_good_face or now - state.started >= self._max_wait

    def _forget_lost_tracks(self, now: float) -> None:
        lost = [tid for tid, s in self._tracks.items() if now - s.last_seen > self._lost]
        for track_id in lost:
            del self._tracks[track_id]

    def _to_observation(self, state: TrackState) -> Observation:
        face = None
        if state.best_face is not None and state.best_face.detection_score >= self._min_face_score:
            face = FaceObservation(
                embedding=state.best_face.vector.astype(float).tolist(),
                model_name=state.best_face.model_name,
                detection_score=round(state.best_face.detection_score, 4),
            )
        return Observation(
            observed_at=state.first_seen_at,
            kind=state.kind,
            label=state.label,
            confidence=round(state.confidence, 4),
            track_id=state.track_id,
            bbox=state.bbox.as_list(),
            face=face,
        )
