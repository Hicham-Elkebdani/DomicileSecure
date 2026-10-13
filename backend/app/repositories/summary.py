from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select

from app.models import DailySummary
from app.repositories.base import BaseRepository


class DailySummaryRepository(BaseRepository[DailySummary]):
    model = DailySummary

    async def get_by_day(self, day: date) -> DailySummary | None:
        return await self.session.scalar(select(DailySummary).where(DailySummary.day == day))

    async def list_recent(self, limit: int = 30) -> Sequence[DailySummary]:
        query = select(DailySummary).order_by(DailySummary.day.desc()).limit(limit)
        return (await self.session.scalars(query)).all()
