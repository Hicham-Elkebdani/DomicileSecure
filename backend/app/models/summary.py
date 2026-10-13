from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, UUIDPrimaryKeyMixin, utcnow


class DailySummary(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "daily_summaries"

    day: Mapped[date] = mapped_column(Date, unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
