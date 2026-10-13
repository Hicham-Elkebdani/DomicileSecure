"""Contract between the vision worker and the API.

This module is the single source of truth for the payload: the worker imports these models
to build its requests, so both sides cannot drift apart.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.models.enums import EventKind


class FaceObservation(BaseModel):
    embedding: list[float] = Field(min_length=32, max_length=1024)
    model_name: str = Field(min_length=1, max_length=64)
    detection_score: float = Field(ge=0.0, le=1.0)


class Observation(BaseModel):
    observed_at: AwareDatetime
    kind: EventKind
    label: str = Field(min_length=1, max_length=40)
    confidence: float = Field(ge=0.0, le=1.0)
    track_id: int | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    face: FaceObservation | None = None

    @field_validator("observed_at")
    @classmethod
    def _not_in_future(cls, value: datetime) -> datetime:
        if value > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("observed_at is in the future (check the worker clock)")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> Observation:
        if self.face is not None and self.kind is not EventKind.PERSON:
            raise ValueError("a face can only be attached to a person observation")
        if self.kind is EventKind.DOOR and self.label not in {"door_open", "door_closed"}:
            raise ValueError("door observations must be labelled door_open or door_closed")
        return self


class ObservationBatch(BaseModel):
    camera_id: uuid.UUID
    observations: list[Observation] = Field(min_length=1, max_length=200)


class IngestResult(BaseModel):
    events_created: int
    alerts_created: int
