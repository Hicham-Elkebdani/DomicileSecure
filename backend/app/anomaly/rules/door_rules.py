from __future__ import annotations

from app.anomaly.rules.base import EventRule, TickRule
from app.anomaly.rules.config import RulesConfig
from app.anomaly.types import EventContext, Finding, TickContext
from app.models.enums import AlertSeverity, DoorState, EventKind


class DoorOpenedAtNightRule(EventRule):
    code = "door_opened_night"

    def evaluate(self, ctx: EventContext, config: RulesConfig) -> Finding | None:
        if ctx.kind is not EventKind.DOOR or ctx.label != "door_open":
            return None
        if not config.is_night(ctx.local_time):
            return None
        severity = AlertSeverity.MEDIUM if ctx.residents_present else AlertSeverity.HIGH
        return Finding(
            source="rules",
            rule_code=self.code,
            severity=severity,
            title="Porte ouverte pendant la nuit",
            message=f"La porte « {ctx.camera.name} » a été ouverte à {ctx.local_time:%H:%M}.",
            dedupe_key=f"{self.code}:{ctx.camera.id}:{ctx.event_id}",
            camera_id=ctx.camera.id,
            event_id=ctx.event_id,
            once=True,
        )


class DoorLeftOpenRule(TickRule):
    """Fires once per opening episode when a door stays open too long."""

    code = "door_left_open"

    def evaluate(self, ctx: TickContext, config: RulesConfig) -> list[Finding]:
        findings: list[Finding] = []
        for camera in ctx.cameras:
            if not camera.has_door or camera.door_state is not DoorState.OPEN:
                continue
            if camera.door_state_changed_at is None:
                continue
            open_seconds = (ctx.now - camera.door_state_changed_at).total_seconds()
            if open_seconds < config.door_open_max_seconds:
                continue
            nobody_home = not ctx.residents_present
            severity = (
                AlertSeverity.HIGH
                if nobody_home or config.is_night(ctx.local_time)
                else AlertSeverity.MEDIUM
            )
            minutes = int(open_seconds // 60)
            suffix = " et personne n'est à la maison" if nobody_home else ""
            findings.append(
                Finding(
                    source="rules",
                    rule_code=self.code,
                    severity=severity,
                    title="Porte restée ouverte",
                    message=f"La porte « {camera.name} » est ouverte depuis {minutes} min{suffix}.",
                    dedupe_key=(
                        f"{self.code}:{camera.id}:{camera.door_state_changed_at.isoformat()}"
                    ),
                    camera_id=camera.id,
                    details={"open_minutes": minutes},
                    once=True,
                )
            )
        return findings
