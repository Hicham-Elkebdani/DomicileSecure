"""Builds the context each detector needs and runs it. Detectors themselves do no I/O."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.base import AnomalyDetector
from app.anomaly.features import EventRecord, build_window_features, floor_to_window
from app.anomaly.types import CameraSnapshot, EventContext, Finding, TickContext
from app.core.config import Settings
from app.models import Camera, Event, Person
from app.repositories.camera import CameraRepository
from app.repositories.event import EventRepository


def camera_snapshot(camera: Camera) -> CameraSnapshot:
    return CameraSnapshot(
        id=camera.id,
        name=camera.name,
        has_door=camera.has_door,
        door_state=camera.door_state,
        door_state_changed_at=camera.door_state_changed_at,
    )


def event_record(event: Event) -> EventRecord:
    return EventRecord(
        occurred_at=event.occurred_at,
        kind=str(event.kind),
        label=event.label,
        identity=str(event.identity) if event.identity else None,
    )


class AnomalyService:
    def __init__(
        self, session: AsyncSession, settings: Settings, detector: AnomalyDetector
    ) -> None:
        self._events = EventRepository(session)
        self._cameras = CameraRepository(session)
        self._settings = settings
        self._detector = detector

    async def residents_present(self, now: datetime) -> bool:
        last_seen = await self._events.last_resident_seen_at()
        window = timedelta(minutes=self._settings.resident_presence_minutes)
        return last_seen is not None and now - last_seen <= window

    async def evaluate_event(
        self, event: Event, camera: Camera, person: Person | None, *, residents_present: bool
    ) -> list[Finding]:
        ctx = EventContext(
            event_id=event.id,
            camera=camera_snapshot(camera),
            occurred_at=event.occurred_at,
            local_time=event.occurred_at.astimezone(self._settings.tz),
            kind=event.kind,
            label=event.label,
            identity=event.identity,
            person_id=person.id if person else None,
            person_name=person.display_name if person else None,
            sightings_count=person.sightings_count if person else 0,
            residents_present=residents_present,
        )
        return self._detector.on_event(ctx)

    async def evaluate_tick(self, now: datetime) -> list[Finding]:
        cameras = tuple(camera_snapshot(c) for c in await self._cameras.list_with_open_door())
        windows = None
        window_end = None
        spec = self._detector.history_spec
        if spec is not None:
            window_end = floor_to_window(now, spec.window_minutes)
            start = window_end - timedelta(minutes=spec.window_minutes * spec.n_windows)
            records = [event_record(e) for e in await self._events.list_between(start, window_end)]
            windows = build_window_features(
                records,
                start=start,
                n_windows=spec.n_windows,
                window_minutes=spec.window_minutes,
                tz=self._settings.tz,
                initial_door_open=await self._any_door_open_at(start),
            )

        ctx = TickContext(
            now=now,
            local_time=now.astimezone(self._settings.tz),
            cameras=cameras,
            residents_present=await self.residents_present(now),
            recent_windows=windows,
            window_end=window_end,
        )
        return self._detector.on_tick(ctx)

    async def _any_door_open_at(self, moment: datetime) -> bool:
        for camera in await self._cameras.list_all():
            if not camera.has_door:
                continue
            last = await self._events.last_door_event_before(camera.id, moment)
            if last is not None and last.label == "door_open":
                return True
        return False
