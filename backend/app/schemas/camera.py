from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DoorState
from app.schemas.common import ORMModel


class CameraBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    location: str = Field(default="", max_length=120)
    has_door: bool = False
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    has_door: bool | None = None
    is_active: bool | None = None


class CameraRead(ORMModel):
    id: uuid.UUID
    name: str
    location: str
    has_door: bool
    is_active: bool
    door_state: DoorState
    door_state_changed_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
