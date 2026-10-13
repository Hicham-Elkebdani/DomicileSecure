from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, UUIDPrimaryKeyMixin, str_enum, utcnow
from app.models.enums import EventKind, IdentityStatus


class Event(UUIDPrimaryKeyMixin, Base):
    """One meaningful observation: a tracked person/animal/vehicle, or a door state change.

    The worker reports one observation per track rather than per frame, so this table stays
    small and each row is also a training sample for the LSTM.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_camera_time", "camera_id", "occurred_at"),
        Index("ix_events_kind_time", "kind", "occurred_at"),
    )

    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    kind: Mapped[EventKind] = mapped_column(str_enum(EventKind))
    label: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity: Mapped[IdentityStatus | None] = mapped_column(str_enum(IdentityStatus), nullable=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True
    )
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
