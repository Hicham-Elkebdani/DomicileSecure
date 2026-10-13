"""Daily summary: a few readable lines instead of hundreds of notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utcnow
from app.models import DailySummary, Event
from app.models.enums import AlertSeverity, EventKind, IdentityStatus
from app.repositories.alert import AlertRepository
from app.repositories.event import EventRepository
from app.repositories.person import PersonRepository
from app.repositories.summary import DailySummaryRepository
from app.schemas.summary import DailySummaryRead

_SEVERITY_FR = {
    AlertSeverity.CRITICAL: "critique",
    AlertSeverity.HIGH: "haute",
    AlertSeverity.MEDIUM: "moyenne",
    AlertSeverity.LOW: "faible",
    AlertSeverity.INFO: "info",
}


class SummaryWriter(ABC):
    """Turns statistics into text. A future LLM-based writer plugs in here."""

    @abstractmethod
    def write(self, day: date, stats: dict[str, Any]) -> str: ...


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


class TemplateSummaryWriter(SummaryWriter):
    def write(self, day: date, stats: dict[str, Any]) -> str:
        header = f"Résumé du {day:%d/%m/%Y} :"
        if stats["total_events"] == 0 and not any(stats["alerts"].values()):
            return f"{header} journée calme, aucune activité détectée."

        parts: list[str] = []
        residents = stats["residents"]
        if residents:
            members = _plural(len(residents), "membre du foyer vu", "membres du foyer vus")
            parts.append(f"{members} ({', '.join(residents)}).")
        else:
            parts.append("Aucun membre du foyer détecté.")
        if stats["guests"]:
            parts.append(f"Invité(s) : {', '.join(stats['guests'])}.")

        unrecognised = stats["unknown_sightings"] + stats["visitor_sightings"]
        if unrecognised:
            passages = _plural(
                unrecognised,
                "passage de personne non reconnue",
                "passages de personnes non reconnues",
            )
            parts.append(f"{passages}.")
        else:
            parts.append("Aucune personne inconnue.")

        if stats["door_openings"]:
            text = f"Porte ouverte {_plural(stats['door_openings'], 'fois', 'fois')}"
            longest = stats.get("longest_door_open")
            if longest and longest["minutes"] >= 1:
                text += (
                    f" (plus longue ouverture : {longest['minutes']} min à {longest['started_at']})"
                )
            parts.append(text + ".")
        if stats["animals"]:
            parts.append(f"{_plural(stats['animals'], 'passage', 'passages')} d'animaux.")

        alerts = {AlertSeverity(k): v for k, v in stats["alerts"].items() if v}
        if alerts:
            detail = ", ".join(
                f"{count} {_SEVERITY_FR[sev]}"
                for sev, count in sorted(alerts.items(), key=lambda kv: -kv[0].rank)
            )
            parts.append(f"Alertes : {detail}.")
        else:
            parts.append("Aucune alerte.")
        return f"{header} " + " ".join(parts)


class SummaryService:
    def __init__(
        self, session: AsyncSession, settings: Settings, writer: SummaryWriter | None = None
    ) -> None:
        self._session = session
        self._events = EventRepository(session)
        self._alerts = AlertRepository(session)
        self._persons = PersonRepository(session)
        self._summaries = DailySummaryRepository(session)
        self._settings = settings
        self._writer = writer or TemplateSummaryWriter()

    def today(self) -> date:
        return utcnow().astimezone(self._settings.tz).date()

    async def get(self, day: date) -> DailySummaryRead:
        """Stored summary for past days, live computation for today (or if missing)."""
        stored = await self._summaries.get_by_day(day)
        if stored is not None and day < self.today():
            return DailySummaryRead(
                day=stored.day,
                text=stored.text,
                stats=stored.stats,
                generated_at=stored.generated_at,
                is_final=True,
            )
        stats = await self.compute_stats(day)
        return DailySummaryRead(day=day, text=self._writer.write(day, stats), stats=stats)

    async def generate(self, day: date) -> DailySummaryRead:
        stats = await self.compute_stats(day)
        text = self._writer.write(day, stats)
        summary = await self._summaries.get_by_day(day)
        if summary is None:
            summary = DailySummary(day=day, text=text, stats=stats)
            self._summaries.add(summary)
        else:
            summary.text, summary.stats, summary.generated_at = text, stats, utcnow()
        await self._session.commit()
        return DailySummaryRead(
            day=day, text=text, stats=stats, generated_at=summary.generated_at, is_final=True
        )

    async def list_recent(self, limit: int = 30) -> list[DailySummaryRead]:
        return [
            DailySummaryRead(
                day=s.day, text=s.text, stats=s.stats, generated_at=s.generated_at, is_final=True
            )
            for s in await self._summaries.list_recent(limit)
        ]

    async def compute_stats(self, day: date) -> dict[str, Any]:
        tz = self._settings.tz
        start = datetime.combine(day, time.min, tzinfo=tz)
        end = start + timedelta(days=1)
        events = list(await self._events.list_between(start, end))

        person_ids = {e.person_id for e in events if e.person_id}
        persons = await self._persons.get_many(list(person_ids))

        def names(identity: IdentityStatus) -> list[str]:
            ids = {e.person_id for e in events if e.identity is identity and e.person_id}
            return sorted(persons[i].display_name for i in ids if i in persons)

        person_events = [e for e in events if e.kind is EventKind.PERSON]
        alerts = await self._alerts.count_by_severity_between(start, end)
        return {
            "total_events": len(events),
            "residents": names(IdentityStatus.RESIDENT),
            "guests": names(IdentityStatus.GUEST),
            "unknown_sightings": sum(
                1 for e in person_events if e.identity is IdentityStatus.UNKNOWN
            ),
            "visitor_sightings": sum(
                1 for e in person_events if e.identity is IdentityStatus.VISITOR
            ),
            "animals": sum(1 for e in events if e.kind is EventKind.ANIMAL),
            "vehicles": sum(1 for e in events if e.kind is EventKind.VEHICLE),
            "door_openings": sum(
                1 for e in events if e.kind is EventKind.DOOR and e.label == "door_open"
            ),
            "longest_door_open": self._longest_door_open(events, end),
            "first_activity": self._local_hhmm(person_events[0].occurred_at)
            if person_events
            else None,
            "last_activity": self._local_hhmm(person_events[-1].occurred_at)
            if person_events
            else None,
            "alerts": {str(k): v for k, v in alerts.items()},
        }

    def _longest_door_open(
        self, events: Sequence[Event], day_end: datetime
    ) -> dict[str, Any] | None:
        opened_at: dict[Any, datetime] = {}
        best: tuple[float, datetime] | None = None
        horizon = min(day_end, utcnow())
        for event in events:
            if event.kind is not EventKind.DOOR:
                continue
            if event.label == "door_open":
                opened_at.setdefault(event.camera_id, event.occurred_at)
            elif event.camera_id in opened_at:
                start = opened_at.pop(event.camera_id)
                duration = (event.occurred_at - start).total_seconds()
                if best is None or duration > best[0]:
                    best = (duration, start)
        for start in opened_at.values():  # still open at the end of the period
            duration = (horizon - start).total_seconds()
            if best is None or duration > best[0]:
                best = (duration, start)
        if best is None:
            return None
        return {"minutes": int(best[0] // 60), "started_at": self._local_hhmm(best[1])}

    def _local_hhmm(self, moment: datetime) -> str:
        return moment.astimezone(self._settings.tz).strftime("%H:%M")
