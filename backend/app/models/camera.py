from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import DoorState


class Camera(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A camera known to the system.

    The stream URL (often containing RTSP credentials) is deliberately *not* stored here: it
    lives only in the worker's environment, so a database leak does not expose camera access.
    """

    __tablename__ = "cameras"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    location: Mapped[str] = mapped_column(String(120), default="")
    has_door: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    door_state: Mapped[DoorState] = mapped_column(str_enum(DoorState), default=DoorState.UNKNOWN)
    door_state_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
