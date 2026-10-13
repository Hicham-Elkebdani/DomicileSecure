from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select

from app.models import Alert
from app.models.enums import AlertSeverity, AlertStatus
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    model = Alert

    def filtered_query(
        self,
        *,
        status: AlertStatus | None = None,
        min_severity: AlertSeverity | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Select[Any]:
        query = select(Alert).order_by(Alert.created_at.desc())
        if status is not None:
            query = query.where(Alert.status == status)
        if min_severity is not None:
            allowed = [s for s in AlertSeverity if s.rank >= min_severity.rank]
            query = query.where(Alert.severity.in_(allowed))
        if start is not None:
            query = query.where(Alert.created_at >= start)
        if end is not None:
            query = query.where(Alert.created_at < end)
        return query

    async def exists_since(self, dedupe_key: str, since: datetime) -> bool:
        query = select(Alert.id).where(Alert.dedupe_key == dedupe_key, Alert.created_at >= since)
        return await self.session.scalar(query.limit(1)) is not None

    async def count_new_by_severity(self) -> dict[AlertSeverity, int]:
        query = (
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.status == AlertStatus.NEW)
            .group_by(Alert.severity)
        )
        counts = {sev: 0 for sev in AlertSeverity}
        for severity, count in (await self.session.execute(query)).all():
            counts[AlertSeverity(severity)] = int(count)
        return counts

    async def count_by_severity_between(
        self, start: datetime, end: datetime
    ) -> dict[AlertSeverity, int]:
        query = (
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.created_at >= start, Alert.created_at < end)
            .group_by(Alert.severity)
        )
        counts = {sev: 0 for sev in AlertSeverity}
        for severity, count in (await self.session.execute(query)).all():
            counts[AlertSeverity(severity)] = int(count)
        return counts
