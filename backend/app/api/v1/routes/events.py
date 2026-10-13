from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_event_service
from app.models.enums import EventKind, IdentityStatus
from app.schemas.common import Page
from app.schemas.event import DailyActivity, EventRead
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])

EventServiceDep = Annotated[EventService, Depends(get_event_service)]


@router.get("", response_model=Page[EventRead])
async def list_events(
    _: CurrentUser,
    service: EventServiceDep,
    camera_id: uuid.UUID | None = None,
    kind: EventKind | None = None,
    identity: IdentityStatus | None = None,
    person_id: uuid.UUID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EventRead]:
    return await service.list(
        camera_id=camera_id,
        kind=kind,
        identity=identity,
        person_id=person_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )


@router.get("/activity", response_model=list[DailyActivity], summary="Activité par jour")
async def daily_activity(
    _: CurrentUser,
    service: EventServiceDep,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> list[DailyActivity]:
    return await service.daily_activity(days)
