"""Maps detector labels (COCO + custom door model) to the event kinds the API understands."""

from __future__ import annotations

from app.models.enums import EventKind

KIND_BY_LABEL: dict[str, EventKind] = {
    "person": EventKind.PERSON,
    "cat": EventKind.ANIMAL,
    "dog": EventKind.ANIMAL,
    "bird": EventKind.ANIMAL,
    "horse": EventKind.ANIMAL,
    "sheep": EventKind.ANIMAL,
    "cow": EventKind.ANIMAL,
    "car": EventKind.VEHICLE,
    "truck": EventKind.VEHICLE,
    "bus": EventKind.VEHICLE,
    "motorcycle": EventKind.VEHICLE,
    "bicycle": EventKind.VEHICLE,
}

DOOR_LABELS = frozenset({"door_open", "door_closed"})
