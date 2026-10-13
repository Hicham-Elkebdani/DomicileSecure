from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utcnow
from app.models.enums import EventKind, IdentityStatus
from app.repositories.event import EventRepository
from app.schemas.common import Page
from app.schemas.event import DailyActivity, EventRead

_IDENTITY_FIELD = {
    IdentityStatus.RESIDENT: "residents",
    IdentityStatus.GUEST: "guests",
    IdentityStatus.VISITOR: "visitors",
    IdentityStatus.UNKNOWN: "unknown",
}


class EventService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._events = EventRepository(session)
        self._settings = settings

    async def list(
        self,
        *,
        camera_id: uuid.UUID | None,
        kind: EventKind | None,
        identity: IdentityStatus | None,
        person_id: uuid.UUID | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        offset: int,
    ) -> Page[EventRead]:
        query = self._events.filtered_query(
            camera_id=camera_id,
            kind=kind,
            identity=identity,
            person_id=person_id,
            start=start,
            end=end,
        )
        rows, total = await self._events.paginate(query, limit=limit, offset=offset)
        return Page(
            items=[EventRead.model_validate(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def daily_activity(self, days: int) -> list[DailyActivity]:
        """Per-day counts for the dashboard chart, in the household's timezone.

        Aggregated in Python to stay database-agnostic; at larger scale this becomes a
        GROUP BY on a pre-computed local date column or a materialised view.
        """
        tz = self._settings.tz
        today = utcnow().astimezone(tz).date()
        first_day = today - timedelta(days=days - 1)
        start = datetime.combine(first_day, time.min, tzinfo=tz)
        end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz)

        buckets = {
            first_day + timedelta(days=i): DailyActivity(day=first_day + timedelta(days=i))
            for i in range(days)
        }
        for event in await self._events.list_between(start, end):
            bucket = buckets.get(event.occurred_at.astimezone(tz).date())
            if bucket is None:
                continue
            if event.kind is EventKind.PERSON:
                field = _IDENTITY_FIELD[event.identity or IdentityStatus.UNKNOWN]
                setattr(bucket, field, getattr(bucket, field) + 1)
            elif event.kind is EventKind.ANIMAL:
                bucket.animals += 1
            elif event.kind is EventKind.VEHICLE:
                bucket.vehicles += 1
            elif event.kind is EventKind.DOOR and event.label == "door_open":
                bucket.door_openings += 1
        return list(buckets.values())
