"""Enumerations shared by the ORM models, the API schemas and the anomaly engine."""

from __future__ import annotations

from enum import StrEnum


class EventKind(StrEnum):
    PERSON = "person"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    DOOR = "door"


class IdentityStatus(StrEnum):
    """How a detected person was identified."""

    RESIDENT = "resident"  # household member
    GUEST = "guest"  # known, trusted visitor
    VISITOR = "visitor"  # auto-created profile: seen before but never confirmed
    UNKNOWN = "unknown"  # first sighting or face not visible


class PersonRole(StrEnum):
    RESIDENT = "resident"
    GUEST = "guest"
    VISITOR = "visitor"


class DoorState(StrEnum):
    UNKNOWN = "unknown"
    OPEN = "open"
    CLOSED = "closed"


class AlertSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {
    AlertSeverity.INFO: 0,
    AlertSeverity.LOW: 1,
    AlertSeverity.MEDIUM: 2,
    AlertSeverity.HIGH: 3,
    AlertSeverity.CRITICAL: 4,
}


class AlertStatus(StrEnum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"  # false positive, useful feedback for tuning rules and the LSTM


class EmbeddingSource(StrEnum):
    ENROLLMENT = "enrollment"  # photo uploaded by the user
    OBSERVATION = "observation"  # captured by a camera (visitor profiles)


ROLE_TO_IDENTITY = {
    PersonRole.RESIDENT: IdentityStatus.RESIDENT,
    PersonRole.GUEST: IdentityStatus.GUEST,
    PersonRole.VISITOR: IdentityStatus.VISITOR,
}
