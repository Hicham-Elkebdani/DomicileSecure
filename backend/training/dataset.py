"""CSV dataset format shared by the simulator, the DB export and the trainer.

events.csv     occurred_at,camera,kind,label,identity
anomalies.csv  start,end,type,description        (optional ground truth)
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.anomaly.features import EventRecord

EVENT_FIELDS = ("occurred_at", "camera", "kind", "label", "identity")
ANOMALY_FIELDS = ("start", "end", "type", "description")


@dataclass(frozen=True, slots=True)
class LabelledAnomaly:
    start: datetime
    end: datetime
    type: str
    description: str = ""

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start < end and start < self.end


def write_events(path: Path, rows: Iterable[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def read_events(path: Path) -> list[EventRecord]:
    with path.open(newline="", encoding="utf-8") as handle:
        records = [
            EventRecord(
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                kind=row["kind"],
                label=row["label"],
                identity=row.get("identity") or None,
            )
            for row in csv.DictReader(handle)
        ]
    records.sort(key=lambda r: r.occurred_at)
    return records


def write_anomalies(path: Path, anomalies: Sequence[LabelledAnomaly]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANOMALY_FIELDS)
        writer.writeheader()
        for anomaly in anomalies:
            writer.writerow(
                {
                    "start": anomaly.start.isoformat(),
                    "end": anomaly.end.isoformat(),
                    "type": anomaly.type,
                    "description": anomaly.description,
                }
            )


def read_anomalies(path: Path | None) -> list[LabelledAnomaly]:
    if path is None or not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            LabelledAnomaly(
                datetime.fromisoformat(row["start"]),
                datetime.fromisoformat(row["end"]),
                row["type"],
                row.get("description", ""),
            )
            for row in csv.DictReader(handle)
        ]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
