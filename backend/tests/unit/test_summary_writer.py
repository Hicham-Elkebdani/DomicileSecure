from __future__ import annotations

from datetime import date

from app.services.summary_service import TemplateSummaryWriter


def _stats(**overrides: object) -> dict:
    stats = {
        "total_events": 10,
        "residents": ["Hicham", "Sara"],
        "guests": [],
        "unknown_sightings": 0,
        "visitor_sightings": 0,
        "animals": 3,
        "vehicles": 0,
        "door_openings": 2,
        "longest_door_open": {"minutes": 12, "started_at": "14:05"},
        "alerts": {"info": 0, "low": 0, "medium": 1, "high": 1, "critical": 0},
    }
    stats.update(overrides)
    return stats


def test_quiet_day() -> None:
    no_alerts = {"info": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    text = TemplateSummaryWriter().write(
        date(2026, 10, 1), _stats(total_events=0, alerts=no_alerts)
    )
    assert "journée calme" in text


def test_a_day_with_alerts_is_never_called_quiet() -> None:
    text = TemplateSummaryWriter().write(date(2026, 10, 1), _stats(total_events=0))
    assert "journée calme" not in text
    assert "Alertes : 1 haute, 1 moyenne" in text


def test_full_day() -> None:
    text = TemplateSummaryWriter().write(date(2026, 10, 1), _stats())
    assert text.startswith("Résumé du 01/10/2026")
    assert "2 membres du foyer vus (Hicham, Sara)" in text
    assert "Aucune personne inconnue" in text
    assert "Porte ouverte 2 fois (plus longue ouverture : 12 min à 14:05)" in text
    assert "Alertes : 1 haute, 1 moyenne" in text


def test_unrecognised_people_are_counted() -> None:
    text = TemplateSummaryWriter().write(
        date(2026, 10, 1), _stats(unknown_sightings=1, visitor_sightings=2)
    )
    assert "3 passages de personnes non reconnues" in text
