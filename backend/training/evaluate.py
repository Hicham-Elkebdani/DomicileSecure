"""Compare the rule engine, the LSTM and the hybrid mode on a labelled dataset.

    python -m training.evaluate --events data/synthetic/events.csv \
        --anomalies data/synthetic/anomalies.csv --report reports/evaluation.json

The rules are *replayed* over the event history with exactly the same classes the API uses,
so the comparison measures the production logic, not a re-implementation.

Metrics are computed per anomaly (was it detected at least once?) and as false alerts per
day (pushed alerts, severity >= medium, that match no labelled anomaly).
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from app.anomaly.features import EventRecord
from app.anomaly.rules import RuleBasedDetector, RulesConfig
from app.anomaly.types import CameraSnapshot, EventContext, TickContext
from app.core.config import BACKEND_DIR
from app.models.enums import AlertSeverity, DoorState, EventKind, IdentityStatus
from training.dataset import LabelledAnomaly, read_anomalies, read_events
from training.windows import build_history

TOLERANCE = timedelta(minutes=10)
CAMERA_ID = uuid.uuid4()


@dataclass(frozen=True, slots=True)
class RaisedAlert:
    at: datetime
    code: str


def replay_rules(
    records: Sequence[EventRecord],
    *,
    config: RulesConfig,
    tz: ZoneInfo,
    presence_minutes: int = 30,
    cooldown_minutes: int = 10,
    tick_minutes: int = 1,
) -> list[RaisedAlert]:
    detector = RuleBasedDetector(config)
    presence = timedelta(minutes=presence_minutes)
    cooldown = timedelta(minutes=cooldown_minutes)
    door_state, door_changed_at = DoorState.CLOSED, None
    last_resident: datetime | None = None
    raised: list[RaisedAlert] = []
    last_by_key: dict[str, datetime] = {}
    once_keys: set[str] = set()

    def camera() -> CameraSnapshot:
        return CameraSnapshot(CAMERA_ID, "Entrée", True, door_state, door_changed_at)

    def present(now: datetime) -> bool:
        return last_resident is not None and now - last_resident <= presence

    def keep(findings: list, now: datetime) -> None:  # type: ignore[type-arg]
        for finding in findings:
            if finding.severity.rank < AlertSeverity.MEDIUM.rank:
                continue  # only pushed alerts count towards alert fatigue
            if finding.once:
                if finding.dedupe_key in once_keys:
                    continue
                once_keys.add(finding.dedupe_key)
            else:
                previous = last_by_key.get(finding.dedupe_key)
                if previous is not None and now - previous < cooldown:
                    continue
                last_by_key[finding.dedupe_key] = now
            raised.append(RaisedAlert(now, finding.rule_code))

    tick = records[0].occurred_at if records else None
    step = timedelta(minutes=tick_minutes)
    for record in records:
        now = record.occurred_at
        while tick is not None and tick <= now:
            ctx = TickContext(tick, tick.astimezone(tz), (camera(),), present(tick))
            keep(detector.on_tick(ctx), tick)
            tick += step

        if record.kind == "door":
            new_state = DoorState.OPEN if record.label == "door_open" else DoorState.CLOSED
            if new_state is door_state:
                continue
            door_state, door_changed_at = new_state, now
        if record.kind == "person" and record.identity == "resident":
            last_resident = now

        identity = IdentityStatus(record.identity) if record.identity else None
        if record.kind == "person" and identity is None:
            identity = IdentityStatus.UNKNOWN
        ctx = EventContext(
            event_id=uuid.uuid4(),
            camera=camera(),
            occurred_at=now,
            local_time=now.astimezone(tz),
            kind=EventKind(record.kind),
            label=record.label,
            identity=identity,
            person_id=None,
            person_name=None,
            sightings_count=0,
            residents_present=present(now),
        )
        keep(detector.on_event(ctx), now)
    return raised


def lstm_alerts(
    model_dir: Path, records: Sequence[EventRecord], tz: ZoneInfo, cooldown_minutes: int = 10
) -> list[RaisedAlert]:
    from app.anomaly.lstm.runtime import LoadedForecaster

    runtime = LoadedForecaster(model_dir)
    history = build_history(records, window_minutes=runtime.metadata.window_minutes, tz=tz)
    scores, _ = runtime.score(history.sequences(runtime.windows_needed))
    ends = history.sequence_end_windows(runtime.windows_needed)
    threshold = runtime.metadata.threshold
    cooldown = timedelta(minutes=cooldown_minutes)  # same grouping as the API's AlertService
    alerts: list[RaisedAlert] = []
    for (_, end), value in zip(ends, scores, strict=True):
        if value > threshold and (not alerts or end - alerts[-1].at >= cooldown):
            alerts.append(RaisedAlert(end, "lstm"))
    return alerts


def evaluate(
    alerts: Sequence[RaisedAlert], anomalies: Sequence[LabelledAnomaly], days: float
) -> dict[str, object]:
    detected_by_type: dict[str, list[bool]] = defaultdict(list)
    delays: list[float] = []
    for anomaly in anomalies:
        hits = [a.at for a in alerts if anomaly.start <= a.at <= anomaly.end + TOLERANCE]
        detected_by_type[anomaly.type].append(bool(hits))
        if hits:
            delays.append((min(hits) - anomaly.start).total_seconds() / 60)
    false_alerts = [
        a
        for a in alerts
        if not any(an.start - TOLERANCE <= a.at <= an.end + TOLERANCE for an in anomalies)
    ]
    detected = sum(sum(v) for v in detected_by_type.values())
    return {
        "recall": round(detected / len(anomalies), 3) if anomalies else None,
        "recall_by_type": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(detected_by_type.items())},
        "median_delay_minutes": round(float(np.median(delays)), 1) if delays else None,
        "alerts_total": len(alerts),
        "false_alerts_per_day": round(len(false_alerts) / days, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--anomalies", type=Path, required=True)
    parser.add_argument(
        "--model-dir", type=Path, default=BACKEND_DIR / "artifacts/anomaly_lstm/latest"
    )
    parser.add_argument("--timezone", default="Africa/Casablanca")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone)
    records = read_events(args.events)
    anomalies = read_anomalies(args.anomalies)
    days = (records[-1].occurred_at - records[0].occurred_at).total_seconds() / 86400

    rules = replay_rules(records, config=RulesConfig(), tz=tz)
    results: dict[str, dict[str, object]] = {"rules": evaluate(rules, anomalies, days)}
    if (args.model_dir / "metadata.json").is_file():
        lstm = lstm_alerts(args.model_dir, records, tz)
        results["lstm"] = evaluate(lstm, anomalies, days)
        results["hybrid"] = evaluate(sorted([*rules, *lstm], key=lambda a: a.at), anomalies, days)
    else:
        print(f"No LSTM model in {args.model_dir}: evaluating the rules only.")

    types = sorted({a.type for a in anomalies})
    print(f"\n{len(anomalies)} labelled anomalies over {days:.0f} days\n")
    print(
        "| Détecteur | Rappel | "
        + " | ".join(types)
        + " | Délai médian (min) | Fausses alertes/jour |"
    )
    print("|---|---|" + "---|" * len(types) + "---|---|")
    for name, res in results.items():
        by_type = res["recall_by_type"]
        if not isinstance(by_type, dict):
            continue
        cells = " | ".join(str(by_type.get(t, "-")) for t in types)
        print(
            f"| {name} | {res['recall']} | {cells} | {res['median_delay_minutes']} | "
            f"{res['false_alerts_per_day']} |"
        )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {args.report}")


if __name__ == "__main__":
    main()
