"""Train a tiny model end to end and plug it into the API's anomaly engine."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from app.anomaly.composite import HybridDetector  # noqa: E402
from app.anomaly.factory import build_anomaly_detector  # noqa: E402
from app.anomaly.lstm.detector import LSTMAnomalyDetector  # noqa: E402
from app.anomaly.types import TickContext  # noqa: E402
from app.core.config import Settings  # noqa: E402
from training.dataset import write_anomalies, write_events  # noqa: E402
from training.simulate_events import simulate  # noqa: E402
from training.train_lstm import parse_args, train  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("lstm")
    sim = simulate(
        days=21, start=date(2026, 1, 5), tz=ZoneInfo("UTC"), anomalies_per_week=1, seed=1
    )
    write_events(root / "events.csv", sim.rows)
    write_anomalies(root / "anomalies.csv", sim.anomalies)
    args = parse_args(
        [
            "--events", str(root / "events.csv"),
            "--anomalies", str(root / "anomalies.csv"),
            "--timezone", "UTC",
            "--epochs", "2",
            "--hidden-size", "16",
            "--output-root", str(root / "artifacts"),
            "--promote",
        ]
    )  # fmt: skip
    train(args)
    return root / "artifacts" / "latest"


def test_artifact_is_complete(model_dir: Path) -> None:
    assert (model_dir / "model.pt").is_file()
    assert (model_dir / "metadata.json").is_file()


def test_detector_scores_windows_once(model_dir: Path) -> None:
    from datetime import UTC, datetime

    detector = LSTMAnomalyDetector(model_dir)
    spec = detector.history_spec
    assert spec.n_windows == detector.metadata.sequence_length + 1

    now = datetime(2026, 2, 1, 3, 0, tzinfo=UTC)
    windows = np.zeros((spec.n_windows, 11), dtype=np.float32)
    windows[-3:, 0] = 5  # several residents moving around at 3 a.m.
    ctx = TickContext(
        now=now,
        local_time=now,
        cameras=(),
        residents_present=True,
        recent_windows=windows,
        window_end=now,
    )
    first = detector.on_tick(ctx)
    assert all(f.source == "lstm" for f in first)
    assert detector.on_tick(ctx) == []  # same window is not scored twice

    quiet = np.zeros_like(windows)
    later = TickContext(
        now + timedelta(minutes=5), now, (), True, quiet, now + timedelta(minutes=5)
    )
    busy_score, _ = detector.score(windows)
    quiet_score, _ = detector.score(quiet)
    assert busy_score > quiet_score
    assert isinstance(detector.on_tick(later), list)


def test_factory_builds_hybrid_and_falls_back(model_dir: Path, tmp_path: Path) -> None:
    hybrid = build_anomaly_detector(
        Settings(_env_file=None, anomaly_engine="hybrid", lstm_model_dir=model_dir)
    )
    assert isinstance(hybrid, HybridDetector)
    assert hybrid.history_spec is not None

    missing = build_anomaly_detector(
        Settings(_env_file=None, anomaly_engine="lstm", lstm_model_dir=tmp_path / "nothing")
    )
    assert missing.name == "rules"
