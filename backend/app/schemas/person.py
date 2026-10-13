from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import PersonRole
from app.schemas.common import ORMModel


class PersonCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    # Visitor profiles are created automatically by the system, never by hand.
    role: Literal[PersonRole.RESIDENT, PersonRole.GUEST]
    notes: str = Field(default="", max_length=2000)


class PersonUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    role: PersonRole | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PersonRead(ORMModel):
    id: uuid.UUID
    display_name: str
    role: PersonRole
    notes: str
    sightings_count: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    face_count: int = 0
    is_recurring: bool = False
    created_at: datetime


class FaceEnrollmentResult(BaseModel):
    person_id: uuid.UUID
    embedding_id: uuid.UUID
    face_count: int
    detection_score: float
