from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select

from app.models import Event
from app.models.enums import EventKind, IdentityStatus
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    model = Event

    def filtered_query(
        self,
        *,
        camera_id: uuid.UUID | None = None,
        kind: EventKind | None = None,
        identity: IdentityStatus | None = None,
        person_id: uuid.UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Select[Any]:
        query = select(Event).order_by(Event.occurred_at.desc())
        if camera_id is not None:
            query = query.where(Event.camera_id == camera_id)
        if kind is not None:
            query = query.where(Event.kind == kind)
        if identity is not None:
            query = query.where(Event.identity == identity)
        if person_id is not None:
            query = query.where(Event.person_id == person_id)
        if start is not None:
            query = query.where(Event.occurred_at >= start)
        if end is not None:
            query = query.where(Event.occurred_at < end)
        return query

    async def list_between(self, start: datetime, end: datetime) -> Sequence[Event]:
        query = (
            select(Event)
            .where(Event.occurred_at >= start, Event.occurred_at < end)
            .order_by(Event.occurred_at)
        )
        return (await self.session.scalars(query)).all()

    async def last_resident_seen_at(self) -> datetime | None:
        query = select(func.max(Event.occurred_at)).where(Event.identity == IdentityStatus.RESIDENT)
        return await self.session.scalar(query)

    async def last_door_event_before(self, camera_id: uuid.UUID, before: datetime) -> Event | None:
        query = (
            select(Event)
            .where(
                Event.camera_id == camera_id,
                Event.kind == EventKind.DOOR,
                Event.occurred_at < before,
            )
            .order_by(Event.occurred_at.desc())
            .limit(1)
        )
        return await self.session.scalar(query)
