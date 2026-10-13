"""Start the worker for one camera:  python -m worker"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from app.core.logging import configure_logging
from worker.client import IngestClient, WorkerAuthenticationError
from worker.config import WorkerSettings
from worker.door import DoorStateDebouncer
from worker.labels import KIND_BY_LABEL
from worker.pipeline import CameraPipeline
from worker.sources import OpenCVFrameSource
from worker.tracking import TrackAggregator

logger = logging.getLogger("worker")


def build_pipeline(settings: WorkerSettings) -> CameraPipeline:
    from vision.detection.yolo import YoloDetector
    from vision.face.sface import SFaceEmbedder

    detector = YoloDetector(
        settings.detector_weights_path,
        confidence=settings.detector_confidence,
        labels=KIND_BY_LABEL.keys(),
        track=True,
        device=settings.device,
    )
    try:
        face_embedder = SFaceEmbedder(
            settings.face_detector_model_path,
            settings.face_recognizer_model_path,
            score_threshold=settings.face_min_detection_score,
        )
    except FileNotFoundError as exc:
        logger.error("%s -> face recognition disabled, every person will be 'unknown'", exc)
        face_embedder = None

    door_detector = None
    if settings.door_model_path is not None:
        door_detector = YoloDetector(
            settings.door_model_path,
            confidence=settings.door_confidence,
            track=False,
            device=settings.device,
        )

    return CameraPipeline(
        source=OpenCVFrameSource(settings.camera_source),
        detector=detector,
        face_embedder=face_embedder,
        door_detector=door_detector,
        client=IngestClient(
            settings.api_base_url,
            settings.api_key.get_secret_value(),
            settings.camera_id,
            max_buffer=settings.max_buffered_observations,
        ),
        aggregator=TrackAggregator(
            face_frames=settings.face_frames,
            max_wait_seconds=settings.max_track_wait_seconds,
            lost_seconds=settings.track_lost_seconds,
            min_face_score=settings.face_min_detection_score,
        ),
        door_debouncer=DoorStateDebouncer(settings.door_debounce_frames),
        target_fps=settings.target_fps,
        flush_interval_seconds=settings.flush_interval_seconds,
        heartbeat_seconds=settings.heartbeat_seconds,
        preview=settings.preview,
    )


def main() -> int:
    settings = WorkerSettings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    logger.info("Starting worker for camera %s", settings.camera_id)

    stop = threading.Event()

    def _stop(signum: int, _frame: object) -> None:
        logger.info("Signal %s received, stopping...", signum)
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        build_pipeline(settings).run(stop)
    except WorkerAuthenticationError:
        logger.error("The API rejected WORKER_API_KEY: check it matches the API's .env")
        return 2
    logger.info("Worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
