from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime

import numpy as np

from app.models.enums import EventKind
from app.schemas.ingest import Observation
from vision.detection.base import ObjectDetector
from vision.face.base import FaceEmbedder
from vision.types import BoundingBox, Detection, FaceEmbedding
from worker.client import IngestClient
from worker.door import DoorStateDebouncer
from worker.labels import DOOR_LABELS
from worker.sources import FrameSource
from worker.tracking import TrackAggregator

logger = logging.getLogger(__name__)


class CameraPipeline:
    """frame -> objects (model 1) -> faces (model 2) -> observations -> API."""

    def __init__(
        self,
        *,
        source: FrameSource,
        detector: ObjectDetector,
        face_embedder: FaceEmbedder | None,
        door_detector: ObjectDetector | None,
        client: IngestClient,
        aggregator: TrackAggregator,
        door_debouncer: DoorStateDebouncer,
        target_fps: float,
        flush_interval_seconds: float,
        heartbeat_seconds: float,
        preview: bool = False,
    ) -> None:
        self._source = source
        self._detector = detector
        self._face_embedder = face_embedder
        self._door_detector = door_detector
        self._client = client
        self._aggregator = aggregator
        self._door = door_debouncer
        self._frame_interval = 1.0 / target_fps
        self._flush_interval = flush_interval_seconds
        self._heartbeat_interval = heartbeat_seconds
        self._preview = preview

    def run(self, stop: threading.Event) -> None:
        last_frame = last_flush = 0.0
        last_heartbeat = -self._heartbeat_interval
        processed = 0
        try:
            while not stop.is_set():
                frame = self._source.read()
                if frame is None:
                    if not self._source.is_live:
                        logger.info("End of video file")
                        break
                    continue

                now = time.monotonic()
                if self._source.is_live:
                    if now - last_frame < self._frame_interval:
                        continue  # keep draining the stream, but process at the target FPS
                    last_frame = now
                # Video files are analysed frame by frame: results must not depend on CPU speed.

                observations = self.process_frame(frame)
                processed += 1
                if observations:
                    self._client.enqueue(observations)
                if now - last_flush >= self._flush_interval:
                    self._client.flush()
                    last_flush = now
                if now - last_heartbeat >= self._heartbeat_interval:
                    self._client.heartbeat()
                    last_heartbeat = now
                    logger.info(
                        "Alive: %d frames processed, %d active tracks, %d pending observations",
                        processed,
                        self._aggregator.active_tracks,
                        self._client.pending,
                    )
        finally:
            self._client.flush()
            self._source.release()
            if self._preview:
                import cv2

                cv2.destroyAllWindows()

    def process_frame(self, frame: np.ndarray) -> list[Observation]:
        detections = self._detector.detect(frame)
        faces: dict[int, FaceEmbedding | None] = {}
        if self._face_embedder is not None:
            for det in detections:
                if det.label == "person" and self._aggregator.needs_face(det.track_id):
                    faces[det.track_id] = self._face_in(frame, det.bbox)  # type: ignore[index]

        observations = self._aggregator.update(detections, faces)
        door_observation = self._update_door(frame)
        if door_observation is not None:
            observations.append(door_observation)

        if self._preview:
            self._show(frame, detections)
        return observations

    def _face_in(self, frame: np.ndarray, person: BoundingBox) -> FaceEmbedding | None:
        """Look for a face in the upper part of the person's box only (faster, fewer errors)."""
        height, width = frame.shape[:2]
        head = BoundingBox(person.x1, person.y1, person.x2, person.y1 + person.height * 0.6)
        x1, y1, x2, y2 = head.expand(0.1, width, height).as_int_tuple()
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or min(crop.shape[:2]) < 40:
            return None
        if self._face_embedder is None:
            return None
        faces = self._face_embedder.embed(crop)
        return faces[0] if faces else None

    def _update_door(self, frame: np.ndarray) -> Observation | None:
        if self._door_detector is None:
            return None
        doors = [d for d in self._door_detector.detect(frame) if d.label in DOOR_LABELS]
        label = max(doors, key=lambda d: d.confidence).label if doors else None
        changed = self._door.update(label)
        if changed is None:
            return None
        logger.info("Door state changed: %s", changed)
        best = max(doors, key=lambda d: d.confidence)
        return Observation(
            observed_at=datetime.now(UTC),
            kind=EventKind.DOOR,
            label=changed,
            confidence=round(best.confidence, 4),
            bbox=best.bbox.as_list(),
        )

    @staticmethod
    def _show(frame: np.ndarray, detections: list[Detection]) -> None:
        import cv2

        canvas = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox.as_int_tuple()
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 200, 0), 2)
            text = f"{det.label} #{det.track_id} {det.confidence:.2f}"
            cv2.putText(
                canvas, text, (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1
            )
        cv2.imshow("DomicileSecure", canvas)
        cv2.waitKey(1)
