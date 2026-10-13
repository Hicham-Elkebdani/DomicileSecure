from __future__ import annotations


class DoorStateDebouncer:
    """Reports a door state only once it has been seen on N consecutive frames.

    Filters out single-frame misclassifications (someone passing in front of the door,
    lighting change) that would otherwise create fake open/close events.
    """

    def __init__(self, frames_required: int = 5) -> None:
        self._required = frames_required
        self._stable: str | None = None
        self._candidate: str | None = None
        self._count = 0

    @property
    def state(self) -> str | None:
        return self._stable

    def update(self, label: str | None) -> str | None:
        """Feed the label seen on this frame; returns the new state when it changes."""
        if label is None:
            return None
        if label == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = label, 1
        if self._count >= self._required and label != self._stable:
            self._stable = label
            return label
        return None
