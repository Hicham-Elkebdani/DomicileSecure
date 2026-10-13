"""Background jobs: periodic anomaly checks and the daily summary.

Runs inside the API process. With several API instances, enable it on one instance only
(SCHEDULER_ENABLED=false elsewhere) or move the jobs to a dedicated process.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.container import Container
from app.db.base import utcnow
from app.services.alert_service import AlertService
from app.services.anomaly_service import AnomalyService
from app.services.summary_service import SummaryService

logger = logging.getLogger(__name__)


async def run_anomaly_tick(container: Container) -> int:
    now = utcnow()
    async with container.database.session() as session:
        findings = await AnomalyService(
            session, container.settings, container.anomaly_detector
        ).evaluate_tick(now)
        alert_service = AlertService(session, container.settings, container.dispatcher)
        alerts = await alert_service.create_from_findings(findings, now=now)
        await session.commit()
        await alert_service.publish(alerts)
    return len(alerts)


async def run_daily_summary(container: Container) -> None:
    async with container.database.session() as session:
        service = SummaryService(session, container.settings)
        summary = await service.generate(service.today())
    await container.dispatcher.broadcast_message("Résumé du jour", summary.text, "/summary")
    logger.info("Daily summary generated for %s", summary.day)


def build_scheduler(container: Container) -> AsyncIOScheduler:
    settings = container.settings
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    async def tick_job() -> None:
        try:
            await run_anomaly_tick(container)
        except Exception:
            logger.exception("Anomaly tick failed")

    async def summary_job() -> None:
        try:
            await run_daily_summary(container)
        except Exception:
            logger.exception("Daily summary failed")

    scheduler.add_job(
        tick_job,
        "interval",
        seconds=settings.anomaly_tick_seconds,
        id="anomaly_tick",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        summary_job,
        CronTrigger(hour=settings.daily_summary_hour, minute=0, timezone=settings.tz),
        id="daily_summary",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return scheduler
