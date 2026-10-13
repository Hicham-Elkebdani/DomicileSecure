"""Plain data structures exchanged with anomaly detectors (no ORM, no I/O)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from app.models.enums import AlertSeverity, DoorState, EventKind, IdentityStatus


@dataclass(frozen=True, slots=True)
class Finding:
    """An anomaly reported by a detector; the alert service turns it into an alert."""

    source: str
    rule_code: str
    severity: AlertSeverity
    title: str
    message: str
    dedupe_key: str
    camera_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)
    # True: never raise twice for the same dedupe_key. False: cooldown-based deduplication.
    once: bool = False


@dataclass(frozen=True, slots=True)
class CameraSnapshot:
    id: uuid.UUID
    name: str
    has_door: bool
    door_state: DoorState
    door_state_changed_at: datetime | None


@dataclass(frozen=True, slots=True)
class EventContext:
    event_id: uuid.UUID
    camera: CameraSnapshot
    occurred_at: datetime  # UTC
    local_time: datetime  # household timezone
    kind: EventKind
    label: str
    identity: IdentityStatus | None
    person_id: uuid.UUID | None
    person_name: str | None
    sightings_count: int
    residents_present: bool


@dataclass(frozen=True, slots=True)
class TickContext:
    now: datetime  # UTC
    local_time: datetime
    cameras: tuple[CameraSnapshot, ...]
    residents_present: bool
    # Only filled when the detector declares a `history_spec` (e.g. the LSTM).
    recent_windows: np.ndarray | None = None
    window_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class HistorySpec:
    window_minutes: int
    n_windows: int
