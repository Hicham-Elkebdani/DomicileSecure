from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from app.anomaly.features import (
    FEATURE_NAMES,
    EventRecord,
    FeatureScaler,
    build_window_features,
    floor_to_window,
)

START = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)  # a Monday
UTC_TZ = ZoneInfo("UTC")


def col(name: str) -> int:
    return FEATURE_NAMES.index(name)


def test_floor_to_window() -> None:
    moment = datetime(2026, 10, 5, 8, 7, 42, tzinfo=UTC)
    assert floor_to_window(moment, 5) == datetime(2026, 10, 5, 8, 5, tzinfo=UTC)


def test_counts_are_assigned_to_the_right_window() -> None:
    records = [
        EventRecord(START + timedelta(minutes=1), "person", "person", "resident"),
        EventRecord(START + timedelta(minutes=2), "person", "person", "resident"),
        EventRecord(START + timedelta(minutes=6), "person", "person", "unknown"),
        EventRecord(START + timedelta(minutes=7), "animal", "cat"),
        EventRecord(START + timedelta(minutes=60), "person", "person", "guest"),  # out of range
    ]
    features = build_window_features(records, start=START, n_windows=3, window_minutes=5, tz=UTC_TZ)
    assert features.shape == (3, len(FEATURE_NAMES))
    assert features[0, col("residents")] == 2
    assert features[1, col("unknown")] == 1
    assert features[1, col("animals")] == 1
    assert features[:, col("guests")].sum() == 0


def test_door_state_is_carried_across_windows() -> None:
    records = [
        EventRecord(START + timedelta(minutes=6), "door", "door_open"),
        EventRecord(START + timedelta(minutes=17), "door", "door_closed"),
    ]
    features = build_window_features(records, start=START, n_windows=5, window_minutes=5, tz=UTC_TZ)
    assert features[:, col("door_open")].tolist() == [0, 1, 1, 1, 0]


def test_initial_door_state() -> None:
    features = build_window_features(
        [], start=START, n_windows=2, window_minutes=5, tz=UTC_TZ, initial_door_open=True
    )
    assert features[:, col("door_open")].tolist() == [1, 1]


def test_time_encoding_uses_local_timezone() -> None:
    features = build_window_features(
        [], start=START, n_windows=1, window_minutes=5, tz=ZoneInfo("Asia/Tokyo")
    )
    local_hour = 17  # 08:00 UTC = 17:00 in Tokyo
    assert np.isclose(features[0, col("hour_sin")], np.sin(2 * np.pi * local_hour / 24), atol=1e-5)


def test_scaler_roundtrip() -> None:
    rng = np.random.default_rng(0)
    data = rng.poisson(2, size=(100, len(FEATURE_NAMES))).astype(np.float32)
    scaler = FeatureScaler().fit(data)
    restored = FeatureScaler.from_dict(scaler.to_dict())
    np.testing.assert_allclose(scaler.transform(data), restored.transform(data), rtol=1e-6)
    assert np.allclose(scaler.transform(data).mean(axis=0), 0, atol=1e-4)
    assert (scaler.std >= 1.0).all()  # rare features are not blown up
