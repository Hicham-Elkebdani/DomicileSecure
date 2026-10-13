"""Train the LSTM forecaster and save a versioned artifact.

    python -m training.train_lstm --events data/synthetic/events.csv \
        --anomalies data/synthetic/anomalies.csv --promote

Pipeline: events -> 5-min windows -> sequences -> chronological train/validation split ->
training on normal sequences only -> threshold chosen for a target false-alert rate ->
metrics -> artifacts/anomaly_lstm/<version>/ (copied to artifacts/anomaly_lstm/latest with
--promote, which is what the API loads).
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from app.anomaly.features import FEATURE_NAMES, TARGET_FEATURES, FeatureScaler
from app.anomaly.lstm.artifact import WEIGHTS_FILE, LSTMArtifactMetadata
from app.anomaly.lstm.model import (
    LSTMForecaster,
    anomaly_scores,
    compute_surprise,
    surprise,
    to_inputs_targets,
)
from app.core.config import BACKEND_DIR
from training.dataset import file_sha256, read_anomalies, read_events
from training.metrics import binary_metrics
from training.windows import build_history, label_sequences

logger = logging.getLogger("training")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def score_sequences(
    model: LSTMForecaster, scaled: np.ndarray, raw: np.ndarray, horizon: int, batch: int = 2048
) -> np.ndarray:
    scores = [
        anomaly_scores(
            compute_surprise(
                model,
                torch.from_numpy(scaled[i : i + batch]),
                torch.from_numpy(raw[i : i + batch]),
            ),
            horizon,
        ).numpy()
        for i in range(0, len(scaled), batch)
    ]
    return np.concatenate(scores) if scores else np.empty(0)


def threshold_for_rate(
    normal_scores: np.ndarray, false_alerts_per_day: float, window_minutes: int
) -> float:
    """Pick the threshold so that normal activity triggers about N alerts per day."""
    windows_per_day = 24 * 60 / window_minutes
    quantile = 1 - min(false_alerts_per_day / windows_per_day, 1.0)
    return float(np.quantile(normal_scores, quantile))


def train(args: argparse.Namespace) -> Path:
    set_seed(args.seed)
    tz = ZoneInfo(args.timezone)
    length = args.sequence_length + 1  # +1: the first window only provides history

    records = read_events(args.events)
    anomalies = read_anomalies(args.anomalies)
    history = build_history(records, window_minutes=args.window_minutes, tz=tz)
    raw = history.sequences(length).astype(np.float32)
    last_is_anomaly, touches_anomaly = label_sequences(history, length, anomalies)
    logger.info(
        "%d events -> %d windows -> %d sequences (%d touching a labelled anomaly)",
        len(records),
        len(history.windows),
        len(raw),
        int(touches_anomaly.sum()),
    )

    split = int(len(raw) * (1 - args.val_fraction))  # chronological: no future leak
    train_mask = np.zeros(len(raw), dtype=bool)
    train_mask[:split] = True
    train_mask &= ~touches_anomaly  # learn the *normal* routine only

    scaler = FeatureScaler().fit(history.windows[: split + length - 1])
    scaled = scaler.transform(raw)
    val_mask = ~touches_anomaly[split:]
    val_scaled = torch.from_numpy(scaled[split:][val_mask])
    val_raw = torch.from_numpy(raw[split:][val_mask])

    model = LSTMForecaster(
        len(FEATURE_NAMES), len(TARGET_FEATURES), args.hidden_size, args.num_layers, args.dropout
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(scaled[train_mask]), torch.from_numpy(raw[train_mask])),
        batch_size=args.batch_size,
        shuffle=True,
    )

    def validation_loss() -> float:
        return float(compute_surprise(model, val_scaled, val_raw).mean())

    best_state, best_loss, patience = None, float("inf"), 0
    for epoch in range(1, args.epochs + 1):
        started = time.perf_counter()
        model.train()
        total = 0.0
        for batch_scaled, batch_raw in loader:
            inputs, targets = to_inputs_targets(batch_scaled, batch_raw)
            optimizer.zero_grad()
            loss = surprise(model(inputs), targets).mean()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += loss.item() * len(batch_scaled)
        train_loss = total / max(1, int(train_mask.sum()))
        val_loss = validation_loss()
        logger.info(
            "epoch %02d  train=%.4f  val=%.4f  (%.1fs)",
            epoch,
            train_loss,
            val_loss,
            time.perf_counter() - started,
        )
        if val_loss < best_loss - 1e-4:
            best_loss, patience = val_loss, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            patience += 1
            if patience >= args.patience:
                logger.info("Early stopping (no improvement for %d epochs)", args.patience)
                break
    if best_state is not None:
        model.load_state_dict(best_state)

    val_scores = score_sequences(model, scaled[split:], raw[split:], args.score_horizon)
    threshold = threshold_for_rate(
        val_scores[val_mask], args.false_alerts_per_day, args.window_minutes
    )
    metrics: dict[str, float] = {
        "val_loss": round(best_loss, 6),
        "target_false_alerts_per_day": args.false_alerts_per_day,
    }
    if anomalies:
        window_metrics = binary_metrics(last_is_anomaly[split:], val_scores > threshold)
        metrics.update({f"window_{k}": v for k, v in window_metrics.items()})
    logger.info("threshold=%.4f metrics=%s", threshold, json.dumps(metrics))

    version = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output = args.output_root / version
    output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output / WEIGHTS_FILE)
    LSTMArtifactMetadata(
        version=version,
        created_at=datetime.now(UTC).isoformat(),
        feature_names=list(FEATURE_NAMES),
        window_minutes=args.window_minutes,
        sequence_length=args.sequence_length,
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        threshold=threshold,
        scaler=scaler.to_dict(),
        score_horizon=args.score_horizon,
        metrics=metrics,
        training_data={
            "events_file": str(args.events),
            "events_sha256": file_sha256(args.events),
            "n_events": len(records),
            "n_windows": len(history.windows),
            "period": [history.starts[0].isoformat(), history.starts[-1].isoformat()],
            "timezone": args.timezone,
            "hyperparameters": {k: str(v) for k, v in vars(args).items()},
        },
    ).save(output)
    logger.info("Model saved to %s", output)

    if args.promote:
        latest = args.output_root / "latest"
        shutil.rmtree(latest, ignore_errors=True)
        shutil.copytree(output, latest)
        logger.info("Promoted to %s — set ANOMALY_ENGINE=hybrid and restart the API", latest)
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--anomalies", type=Path, default=None)
    parser.add_argument("--timezone", default="Africa/Casablanca")
    parser.add_argument("--window-minutes", type=int, default=5)
    parser.add_argument("--sequence-length", type=int, default=24, help="history steps (2 h)")
    parser.add_argument("--score-horizon", type=int, default=3, help="windows averaged (15 min)")
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=2e-3)
    parser.add_argument("--val-fraction", type=float, default=0.25)
    parser.add_argument("--false-alerts-per-day", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-root", type=Path, default=BACKEND_DIR / "artifacts/anomaly_lstm")
    parser.add_argument("--promote", action="store_true", help="Copy the model to latest/")
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    torch.set_num_threads(max(1, torch.get_num_threads()))
    train(parse_args())
