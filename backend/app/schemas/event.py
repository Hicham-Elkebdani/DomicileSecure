from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import EventKind, IdentityStatus
from app.schemas.common import ORMModel


class EventRead(ORMModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    occurred_at: datetime
    kind: EventKind
    label: str
    confidence: float
    track_id: int | None
    identity: IdentityStatus | None
    person_id: uuid.UUID | None
    match_score: float | None
    bbox: list[float] | None


class DailyActivity(BaseModel):
    day: date
    residents: int = 0
    guests: int = 0
    visitors: int = 0
    unknown: int = 0
    animals: int = 0
    vehicles: int = 0
    door_openings: int = 0
