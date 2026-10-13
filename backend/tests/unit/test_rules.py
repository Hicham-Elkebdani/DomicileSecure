from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.anomaly.rules import RuleBasedDetector, RulesConfig
from app.anomaly.rules.base import EventRule
from app.anomaly.types import CameraSnapshot, EventContext, TickContext
from app.models.enums import AlertSeverity, DoorState, EventKind, IdentityStatus

CONFIG = RulesConfig(
    night_start_hour=23, night_end_hour=6, door_open_max_seconds=600, recurring_visitor_threshold=3
)
CAMERA = CameraSnapshot(uuid.uuid4(), "Entrée", True, DoorState.CLOSED, None)
NIGHT = datetime(2026, 10, 1, 2, 30, tzinfo=UTC)
DAY = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)


def event_ctx(
    *,
    when: datetime = DAY,
    kind: EventKind = EventKind.PERSON,
    label: str = "person",
    identity: IdentityStatus | None = IdentityStatus.UNKNOWN,
    residents_present: bool = False,
    sightings: int = 1,
) -> EventContext:
    return EventContext(
        event_id=uuid.uuid4(),
        camera=CAMERA,
        occurred_at=when,
        local_time=when,
        kind=kind,
        label=label,
        identity=identity,
        person_id=uuid.uuid4(),
        person_name=None,
        sightings_count=sightings,
        residents_present=residents_present,
    )


@pytest.fixture
def detector() -> RuleBasedDetector:
    return RuleBasedDetector(CONFIG)


@pytest.mark.parametrize(
    ("hour", "expected"), [(22, False), (23, True), (0, True), (5, True), (6, False), (14, False)]
)
def test_night_window_crosses_midnight(hour: int, expected: bool) -> None:
    assert CONFIG.is_night(datetime(2026, 1, 1, hour, tzinfo=UTC)) is expected


def test_night_window_without_midnight_crossing() -> None:
    config = RulesConfig(night_start_hour=1, night_end_hour=5)
    assert config.is_night(datetime(2026, 1, 1, 3, tzinfo=UTC))
    assert not config.is_night(datetime(2026, 1, 1, 23, tzinfo=UTC))


def test_unknown_person_at_night_is_high(detector: RuleBasedDetector) -> None:
    findings = detector.on_event(event_ctx(when=NIGHT))
    assert [f.rule_code for f in findings] == ["unknown_person_night"]
    assert findings[0].severity is AlertSeverity.HIGH


def test_unknown_person_while_away_is_medium(detector: RuleBasedDetector) -> None:
    findings = detector.on_event(event_ctx(residents_present=False))
    assert [(f.rule_code, f.severity) for f in findings] == [
        ("unknown_person_away", AlertSeverity.MEDIUM)
    ]


def test_unknown_person_while_home_is_low(detector: RuleBasedDetector) -> None:
    findings = detector.on_event(event_ctx(residents_present=True))
    assert [(f.rule_code, f.severity) for f in findings] == [
        ("unknown_person_home", AlertSeverity.LOW)
    ]


@pytest.mark.parametrize("identity", [IdentityStatus.RESIDENT, IdentityStatus.GUEST])
def test_known_people_never_raise_alerts(
    detector: RuleBasedDetector, identity: IdentityStatus
) -> None:
    assert detector.on_event(event_ctx(when=NIGHT, identity=identity)) == []


def test_animals_are_ignored(detector: RuleBasedDetector) -> None:
    ctx = event_ctx(when=NIGHT, kind=EventKind.ANIMAL, label="cat", identity=None)
    assert detector.on_event(ctx) == []


def test_recurring_visitor_suggestion_fires_exactly_at_threshold(
    detector: RuleBasedDetector,
) -> None:
    def codes(sightings: int) -> list[str]:
        ctx = event_ctx(
            identity=IdentityStatus.VISITOR, residents_present=True, sightings=sightings
        )
        return [f.rule_code for f in detector.on_event(ctx)]

    assert "recurring_visitor" not in codes(2)
    assert "recurring_visitor" in codes(3)
    assert "recurring_visitor" not in codes(4)


def test_door_opened_at_night(detector: RuleBasedDetector) -> None:
    ctx = event_ctx(when=NIGHT, kind=EventKind.DOOR, label="door_open", identity=None)
    findings = detector.on_event(ctx)
    assert [(f.rule_code, f.severity) for f in findings] == [
        ("door_opened_night", AlertSeverity.HIGH)
    ]


def _tick(open_since: datetime, now: datetime, residents_present: bool) -> TickContext:
    camera = CameraSnapshot(uuid.uuid4(), "Garage", True, DoorState.OPEN, open_since)
    return TickContext(
        now=now, local_time=now, cameras=(camera,), residents_present=residents_present
    )


def test_door_left_open_threshold(detector: RuleBasedDetector) -> None:
    assert detector.on_tick(_tick(DAY - timedelta(minutes=9), DAY, True)) == []
    findings = detector.on_tick(_tick(DAY - timedelta(minutes=11), DAY, True))
    assert [(f.rule_code, f.severity) for f in findings] == [
        ("door_left_open", AlertSeverity.MEDIUM)
    ]
    assert findings[0].once is True


def test_door_left_open_is_high_when_nobody_home(detector: RuleBasedDetector) -> None:
    findings = detector.on_tick(_tick(DAY - timedelta(hours=1), DAY, False))
    assert findings[0].severity is AlertSeverity.HIGH


def test_a_failing_rule_does_not_block_the_others() -> None:
    class BrokenRule(EventRule):
        code = "broken"

        def evaluate(self, ctx, config):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    detector = RuleBasedDetector(CONFIG)
    detector.event_rules.insert(0, BrokenRule())
    assert [f.rule_code for f in detector.on_event(event_ctx(when=NIGHT))] == [
        "unknown_person_night"
    ]
