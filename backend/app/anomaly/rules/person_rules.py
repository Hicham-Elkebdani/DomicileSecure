from __future__ import annotations

from app.anomaly.rules.base import EventRule
from app.anomaly.rules.config import RulesConfig
from app.anomaly.types import EventContext, Finding
from app.models.enums import AlertSeverity, EventKind, IdentityStatus

_NOT_RECOGNISED = {IdentityStatus.UNKNOWN, IdentityStatus.VISITOR}


def _is_unrecognised_person(ctx: EventContext) -> bool:
    return ctx.kind is EventKind.PERSON and ctx.identity in _NOT_RECOGNISED


def _person_key(ctx: EventContext) -> str:
    return str(ctx.person_id) if ctx.person_id else f"track:{ctx.event_id}"


class UnknownPersonAtNightRule(EventRule):
    code = "unknown_person_night"

    def evaluate(self, ctx: EventContext, config: RulesConfig) -> Finding | None:
        if not (_is_unrecognised_person(ctx) and config.is_night(ctx.local_time)):
            return None
        return Finding(
            source="rules",
            rule_code=self.code,
            severity=AlertSeverity.HIGH,
            title="Personne non reconnue pendant la nuit",
            message=(
                f"Une personne non reconnue a été détectée par « {ctx.camera.name} » "
                f"à {ctx.local_time:%H:%M}."
            ),
            dedupe_key=f"{self.code}:{ctx.camera.id}:{_person_key(ctx)}",
            camera_id=ctx.camera.id,
            event_id=ctx.event_id,
            person_id=ctx.person_id,
        )


class UnknownPersonWhileAwayRule(EventRule):
    code = "unknown_person_away"

    def evaluate(self, ctx: EventContext, config: RulesConfig) -> Finding | None:
        if not _is_unrecognised_person(ctx) or config.is_night(ctx.local_time):
            return None
        if ctx.residents_present:
            return None
        return Finding(
            source="rules",
            rule_code=self.code,
            severity=AlertSeverity.MEDIUM,
            title="Personne non reconnue en votre absence",
            message=(
                f"Une personne non reconnue est passée devant « {ctx.camera.name} » "
                f"à {ctx.local_time:%H:%M} alors qu'aucun membre du foyer n'est présent."
            ),
            dedupe_key=f"{self.code}:{ctx.camera.id}:{_person_key(ctx)}",
            camera_id=ctx.camera.id,
            event_id=ctx.event_id,
            person_id=ctx.person_id,
        )


class UnknownPersonWhileHomeRule(EventRule):
    code = "unknown_person_home"

    def evaluate(self, ctx: EventContext, config: RulesConfig) -> Finding | None:
        if not _is_unrecognised_person(ctx) or config.is_night(ctx.local_time):
            return None
        if not ctx.residents_present:
            return None
        return Finding(
            source="rules",
            rule_code=self.code,
            severity=AlertSeverity.LOW,
            title="Personne non reconnue",
            message=(
                f"Une personne non reconnue a été vue par « {ctx.camera.name} » "
                f"à {ctx.local_time:%H:%M}. Un membre du foyer est présent."
            ),
            dedupe_key=f"{self.code}:{ctx.camera.id}:{_person_key(ctx)}",
            camera_id=ctx.camera.id,
            event_id=ctx.event_id,
            person_id=ctx.person_id,
        )


class RecurringVisitorRule(EventRule):
    """Suggests promoting a frequently seen visitor to 'guest' (fires once per profile)."""

    code = "recurring_visitor"

    def evaluate(self, ctx: EventContext, config: RulesConfig) -> Finding | None:
        if ctx.identity is not IdentityStatus.VISITOR or ctx.person_id is None:
            return None
        if ctx.sightings_count != config.recurring_visitor_threshold:
            return None
        return Finding(
            source="rules",
            rule_code=self.code,
            severity=AlertSeverity.INFO,
            title="Visiteur récurrent",
            message=(
                f"Cette personne a été vue {ctx.sightings_count} fois. "
                "Souhaitez-vous l'enregistrer comme invité ?"
            ),
            dedupe_key=f"{self.code}:{ctx.person_id}",
            camera_id=ctx.camera.id,
            event_id=ctx.event_id,
            person_id=ctx.person_id,
            details={"sightings_count": ctx.sightings_count},
            once=True,
        )
