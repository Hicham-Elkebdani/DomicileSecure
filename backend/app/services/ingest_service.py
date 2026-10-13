"""Entry point of the decision pipeline: worker observations -> events -> anomalies -> alerts."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.base import AnomalyDetector
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.db.base import utcnow
from app.models import Alert, Camera, Event, Person
from app.models.enums import DoorState, EventKind
from app.repositories.camera import CameraRepository
from app.repositories.event import EventRepository
from app.schemas.event import EventRead
from app.schemas.ingest import IngestResult, Observation, ObservationBatch
from app.services.alert_service import AlertService
from app.services.anomaly_service import AnomalyService
from app.services.face_gallery import FaceGallery
from app.services.identity_service import IdentityService
from app.services.notifications.realtime import RealtimeHub

logger = logging.getLogger(__name__)


class IngestService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        gallery: FaceGallery,
        detector: AnomalyDetector,
        alert_service: AlertService,
        realtime: RealtimeHub,
    ) -> None:
        self._session = session
        self._cameras = CameraRepository(session)
        self._events = EventRepository(session)
        self._identity = IdentityService(session, settings, gallery)
        self._anomaly = AnomalyService(session, settings, detector)
        self._alerts = alert_service
        self._realtime = realtime
        self._gallery = gallery

    async def heartbeat(self, camera_id: uuid.UUID) -> None:
        camera = await self._get_active_camera(camera_id)
        camera.last_seen_at = utcnow()
        await self._session.commit()

    async def ingest(self, batch: ObservationBatch) -> IngestResult:
        camera = await self._get_active_camera(batch.camera_id)
        camera.last_seen_at = utcnow()

        events: list[Event] = []
        alerts: list[Alert] = []
        try:
            for observation in sorted(batch.observations, key=lambda o: o.observed_at):
                event, person = await self._to_event(camera, observation)
                if event is None:
                    continue
                events.append(event)
                findings = await self._anomaly.evaluate_event(
                    event,
                    camera,
                    person,
                    residents_present=await self._anomaly.residents_present(event.occurred_at),
                )
                alerts.extend(await self._alerts.create_from_findings(findings))
            await self._session.commit()
        except Exception:
            self._gallery.invalidate()  # in-memory additions may reference rolled-back rows
            raise

        # Notify only once data is safely stored.
        await self._realtime.publish_events([EventRead.model_validate(e) for e in events])
        await self._alerts.publish(alerts)
        if alerts:
            logger.info("Camera %s raised %d alert(s)", camera.name, len(alerts))
        return IngestResult(events_created=len(events), alerts_created=len(alerts))

    async def _get_active_camera(self, camera_id: uuid.UUID) -> Camera:
        camera = await self._cameras.get(camera_id)
        if camera is None:
            raise NotFoundError("Caméra inconnue", details={"camera_id": str(camera_id)})
        if not camera.is_active:
            raise ConflictError("Caméra désactivée")
        return camera

    async def _to_event(
        self, camera: Camera, observation: Observation
    ) -> tuple[Event | None, Person | None]:
        person: Person | None = None
        identity = None
        score = None

        if observation.kind is EventKind.DOOR:
            new_state = DoorState.OPEN if observation.label == "door_open" else DoorState.CLOSED
            if not camera.has_door or camera.door_state is new_state:
                return None, None  # no change: nothing to record
            camera.door_state = new_state
            camera.door_state_changed_at = observation.observed_at
        elif observation.kind is EventKind.PERSON:
            resolution = await self._identity.resolve(observation.face, observation.observed_at)
            identity, person, score = resolution.identity, resolution.person, resolution.score

        event = Event(
            id=uuid.uuid4(),
            camera_id=camera.id,
            occurred_at=observation.observed_at,
            kind=observation.kind,
            label=observation.label,
            confidence=observation.confidence,
            track_id=observation.track_id,
            identity=identity,
            person_id=person.id if person else None,
            match_score=score,
            bbox=observation.bbox,
            extra={},
        )
        self._events.add(event)
        await self._events.flush()
        return event, person
