"""Turn an event history into windows and training sequences (used by train and evaluate)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.anomaly.features import EventRecord, build_window_features, floor_to_window
from training.dataset import LabelledAnomaly


@dataclass
class WindowedHistory:
    windows: np.ndarray  # (n_windows, n_features)
    starts: list[datetime]  # start of each window (UTC)
    window_minutes: int

    def sequences(self, length: int) -> np.ndarray:
        """All sliding sequences, shape (n_windows - length + 1, length, n_features)."""
        view = sliding_window_view(self.windows, (length, self.windows.shape[1]))
        return np.ascontiguousarray(view[:, 0])

    def sequence_end_windows(self, length: int) -> list[tuple[datetime, datetime]]:
        """(start, end) of the last window of each sequence."""
        width = timedelta(minutes=self.window_minutes)
        return [(start, start + width) for start in self.starts[length - 1 :]]


def build_history(
    records: Sequence[EventRecord], *, window_minutes: int, tz: ZoneInfo
) -> WindowedHistory:
    if not records:
        raise ValueError("No events: generate or export a dataset first")
    start = floor_to_window(records[0].occurred_at, window_minutes)
    end = floor_to_window(records[-1].occurred_at, window_minutes) + timedelta(
        minutes=window_minutes
    )
    n_windows = int((end - start) / timedelta(minutes=window_minutes))
    windows = build_window_features(
        records, start=start, n_windows=n_windows, window_minutes=window_minutes, tz=tz
    )
    starts = [start + timedelta(minutes=window_minutes * i) for i in range(n_windows)]
    return WindowedHistory(windows, starts, window_minutes)


def label_sequences(
    history: WindowedHistory, length: int, anomalies: Sequence[LabelledAnomaly]
) -> tuple[np.ndarray, np.ndarray]:
    """Return (last_window_is_anomalous, sequence_touches_an_anomaly) boolean arrays."""
    width = timedelta(minutes=history.window_minutes)
    window_flags = np.zeros(len(history.starts), dtype=bool)
    for anomaly in anomalies:
        for i, start in enumerate(history.starts):
            if anomaly.overlaps(start, start + width):
                window_flags[i] = True
    last = window_flags[length - 1 :]
    touched = sliding_window_view(window_flags, length).any(axis=1)
    return last, touched
