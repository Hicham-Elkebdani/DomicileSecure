from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import AlertSeverity, AlertStatus
from app.schemas.common import ORMModel


class AlertRead(ORMModel):
    id: uuid.UUID
    source: str
    rule_code: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    details: dict[str, Any]
    camera_id: uuid.UUID | None
    event_id: uuid.UUID | None
    person_id: uuid.UUID | None
    created_at: datetime
    resolved_at: datetime | None


class AlertUpdate(BaseModel):
    status: AlertStatus


class AlertCounts(BaseModel):
    new: int
    by_severity: dict[AlertSeverity, int]
