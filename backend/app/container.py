"""Composition root: the only place where concrete implementations are chosen.

Everything else depends on abstractions and receives its collaborators from here, which is
what makes the application testable (tests build a container with fakes) and configurable.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.anomaly.base import AnomalyDetector
from app.anomaly.factory import build_anomaly_detector
from app.core.config import Settings
from app.core.exceptions import ServiceUnavailableError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.session import Database
from app.models.enums import AlertSeverity
from app.services.face_gallery import FaceGallery
from app.services.notifications.dispatcher import ChannelRoute, NotificationDispatcher
from app.services.notifications.realtime import RealtimeHub
from app.services.notifications.webpush import WebPushChannel
from vision.face.base import FaceEmbedder

logger = logging.getLogger(__name__)


class FaceEmbedderProvider:
    """Loads the face model on first use, so the API starts even if models are missing."""

    def __init__(self, factory: Callable[[], FaceEmbedder]) -> None:
        self._factory = factory
        self._instance: FaceEmbedder | None = None
        self._lock = threading.Lock()

    def get(self) -> FaceEmbedder:
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    try:
                        self._instance = self._factory()
                    except FileNotFoundError as exc:
                        logger.error("Face model unavailable: %s", exc)
                        raise ServiceUnavailableError(
                            "Modèle de reconnaissance faciale absent. "
                            "Lancez `python scripts/download_models.py` côté serveur."
                        ) from exc
        return self._instance


@dataclass
class Container:
    settings: Settings
    database: Database
    gallery: FaceGallery
    realtime: RealtimeHub
    webpush: WebPushChannel | None
    dispatcher: NotificationDispatcher
    anomaly_detector: AnomalyDetector
    face_embedder: FaceEmbedderProvider
    login_limiter: SlidingWindowRateLimiter


def _default_face_embedder(settings: Settings) -> Callable[[], FaceEmbedder]:
    def factory() -> FaceEmbedder:
        from vision.face.sface import SFaceEmbedder

        return SFaceEmbedder(
            settings.face_detector_model_path,
            settings.face_recognizer_model_path,
            score_threshold=settings.face_min_detection_score,
        )

    return factory


def build_container(
    settings: Settings,
    *,
    database: Database | None = None,
    face_embedder_factory: Callable[[], FaceEmbedder] | None = None,
    anomaly_detector: AnomalyDetector | None = None,
) -> Container:
    database = database or Database(settings.database_url, echo=settings.database_echo)
    realtime = RealtimeHub()
    webpush = WebPushChannel(settings, database) if settings.push_enabled else None

    routes = [ChannelRoute(realtime, AlertSeverity.INFO)]
    if webpush is not None:
        routes.append(ChannelRoute(webpush, AlertSeverity(settings.push_min_severity)))
    else:
        logger.info("Web Push disabled (VAPID keys not configured)")

    return Container(
        settings=settings,
        database=database,
        gallery=FaceGallery(settings.face_match_threshold),
        realtime=realtime,
        webpush=webpush,
        dispatcher=NotificationDispatcher(routes),
        anomaly_detector=anomaly_detector or build_anomaly_detector(settings),
        face_embedder=FaceEmbedderProvider(
            face_embedder_factory or _default_face_embedder(settings)
        ),
        login_limiter=SlidingWindowRateLimiter(settings.login_rate_limit_per_minute, 60.0),
    )
