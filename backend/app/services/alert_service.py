from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.types import Finding
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.db.base import utcnow
from app.models import Alert, User
from app.models.enums import AlertSeverity, AlertStatus
from app.repositories.alert import AlertRepository
from app.schemas.alert import AlertCounts, AlertRead
from app.schemas.common import Page
from app.services.notifications.dispatcher import NotificationDispatcher

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class AlertService:
    def __init__(
        self, session: AsyncSession, settings: Settings, dispatcher: NotificationDispatcher
    ) -> None:
        self._session = session
        self._alerts = AlertRepository(session)
        self._settings = settings
        self._dispatcher = dispatcher

    async def create_from_findings(
        self, findings: Sequence[Finding], *, now: datetime | None = None
    ) -> list[Alert]:
        """Persist findings as alerts, skipping duplicates. Does not commit."""
        now = now or utcnow()
        cooldown = timedelta(minutes=self._settings.alert_cooldown_minutes)
        seen: set[str] = set()
        created: list[Alert] = []
        for finding in findings:
            if finding.dedupe_key in seen:
                continue
            seen.add(finding.dedupe_key)
            since = _EPOCH if finding.once else now - cooldown
            if (finding.once or cooldown) and await self._alerts.exists_since(
                finding.dedupe_key, since
            ):
                continue
            alert = Alert(
                source=finding.source,
                rule_code=finding.rule_code,
                severity=finding.severity,
                status=AlertStatus.NEW,
                title=finding.title,
                message=finding.message,
                dedupe_key=finding.dedupe_key,
                details=finding.details,
                camera_id=finding.camera_id,
                event_id=finding.event_id,
                person_id=finding.person_id,
                created_at=now,
            )
            self._alerts.add(alert)
            created.append(alert)
        if created:
            await self._alerts.flush()
        return created

    async def publish(self, alerts: Sequence[Alert]) -> None:
        """Notify channels. Call only after the transaction is committed."""
        if alerts:
            await self._dispatcher.dispatch([AlertRead.model_validate(a) for a in alerts])

    async def list(
        self,
        *,
        status: AlertStatus | None,
        min_severity: AlertSeverity | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        offset: int,
    ) -> Page[AlertRead]:
        query = self._alerts.filtered_query(
            status=status, min_severity=min_severity, start=start, end=end
        )
        rows, total = await self._alerts.paginate(query, limit=limit, offset=offset)
        return Page(
            items=[AlertRead.model_validate(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def counts(self) -> AlertCounts:
        by_severity = await self._alerts.count_new_by_severity()
        return AlertCounts(new=sum(by_severity.values()), by_severity=by_severity)

    async def update_status(self, alert_id: uuid.UUID, status: AlertStatus, user: User) -> Alert:
        alert = await self._alerts.get(alert_id)
        if alert is None:
            raise NotFoundError("Alerte introuvable")
        alert.status = status
        if status is AlertStatus.NEW:
            alert.resolved_at = None
            alert.resolved_by_id = None
        else:
            alert.resolved_at = utcnow()
            alert.resolved_by_id = user.id
        await self._session.commit()
        return alert
