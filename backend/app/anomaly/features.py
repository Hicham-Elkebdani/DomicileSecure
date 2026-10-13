"""Feature engineering shared by LSTM training and live inference.

Keeping a single implementation for both removes "training/serving skew", one of the most
common causes of models that work offline and fail in production.

A household's activity is cut into fixed windows (e.g. 5 minutes). Each window becomes one
vector: how many residents / guests / unknown people / animals / vehicles were seen, whether
a door was open, and cyclic encodings of the time of day and day of week.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

FEATURE_NAMES: tuple[str, ...] = (
    "residents",
    "guests",
    "visitors",
    "unknown",
    "animals",
    "vehicles",
    "door_open",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
)
COUNT_FEATURES: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
# What the model predicts (activity) vs. what it is told (calendar context).
TARGET_FEATURES: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)
CONTEXT_FEATURES: tuple[int, ...] = (7, 8, 9, 10)
_IDENTITY_COLUMN = {"resident": 0, "guest": 1, "visitor": 2, "unknown": 3}
_KIND_COLUMN = {"animal": 4, "vehicle": 5}
_DOOR = 6


@dataclass(frozen=True, slots=True)
class EventRecord:
    """Minimal, storage-agnostic view of an event (built from DB rows or CSV lines)."""

    occurred_at: datetime
    kind: str
    label: str
    identity: str | None = None


def floor_to_window(moment: datetime, window_minutes: int) -> datetime:
    moment = moment.astimezone(UTC)
    epoch_minutes = int(moment.timestamp() // 60)
    floored = epoch_minutes - epoch_minutes % window_minutes
    return datetime.fromtimestamp(floored * 60, tz=UTC)


def build_window_features(
    records: Iterable[EventRecord],
    *,
    start: datetime,
    n_windows: int,
    window_minutes: int,
    tz: ZoneInfo,
    initial_door_open: bool = False,
) -> np.ndarray:
    """Return an array of shape (n_windows, len(FEATURE_NAMES)) starting at `start`."""
    width = timedelta(minutes=window_minutes)
    start = start.astimezone(UTC)
    features = np.zeros((n_windows, len(FEATURE_NAMES)), dtype=np.float32)

    door_changes: list[tuple[int, bool]] = []
    for record in records:
        index = int((record.occurred_at.astimezone(UTC) - start) // width)
        if not 0 <= index < n_windows:
            continue
        if record.kind == "person" and record.identity in _IDENTITY_COLUMN:
            features[index, _IDENTITY_COLUMN[record.identity]] += 1
        elif record.kind == "person":
            features[index, _IDENTITY_COLUMN["unknown"]] += 1
        elif record.kind in _KIND_COLUMN:
            features[index, _KIND_COLUMN[record.kind]] += 1
        elif record.kind == "door":
            door_changes.append((index, record.label == "door_open"))

    # A window counts as "door open" if the door was open at any moment during it.
    door_changes.sort(key=lambda change: change[0])
    is_open = initial_door_open
    pointer = 0
    for index in range(n_windows):
        open_in_window = is_open
        while pointer < len(door_changes) and door_changes[pointer][0] == index:
            is_open = door_changes[pointer][1]
            open_in_window = open_in_window or is_open
            pointer += 1
        features[index, _DOOR] = 1.0 if open_in_window else 0.0

    for index in range(n_windows):
        local = (start + index * width).astimezone(tz)
        hour = local.hour + local.minute / 60
        features[index, 7] = math.sin(2 * math.pi * hour / 24)
        features[index, 8] = math.cos(2 * math.pi * hour / 24)
        features[index, 9] = math.sin(2 * math.pi * local.weekday() / 7)
        features[index, 10] = math.cos(2 * math.pi * local.weekday() / 7)
    return features


class FeatureScaler:
    """log1p on counts, then centring and scaling.

    The standard deviation is floored (`min_std`): rare signals such as "unknown person" have
    a tiny spread, and dividing by it would make a single sighting outweigh everything else.
    """

    def __init__(
        self, mean: np.ndarray | None = None, std: np.ndarray | None = None, min_std: float = 1.0
    ) -> None:
        self.mean = mean
        self.std = std
        self.min_std = min_std

    @staticmethod
    def _log_counts(features: np.ndarray) -> np.ndarray:
        out = features.astype(np.float32, copy=True)
        out[..., COUNT_FEATURES] = np.log1p(out[..., COUNT_FEATURES])
        return out

    def fit(self, features: np.ndarray) -> FeatureScaler:
        logged = self._log_counts(features).reshape(-1, features.shape[-1])
        self.mean = logged.mean(axis=0)
        self.std = np.maximum(logged.std(axis=0), self.min_std).astype(np.float32)
        return self

    def transform(self, features: np.ndarray) -> np.ndarray:
        if self.mean is None or self.std is None:
            raise RuntimeError("FeatureScaler must be fitted before transform")
        return ((self._log_counts(features) - self.mean) / self.std).astype(np.float32)

    def to_dict(self) -> dict[str, Any]:
        if self.mean is None or self.std is None:
            raise RuntimeError("FeatureScaler is not fitted")
        return {"mean": self.mean.tolist(), "std": self.std.tolist(), "min_std": self.min_std}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureScaler:
        return cls(
            np.asarray(data["mean"], np.float32),
            np.asarray(data["std"], np.float32),
            float(data.get("min_std", 1.0)),
        )
