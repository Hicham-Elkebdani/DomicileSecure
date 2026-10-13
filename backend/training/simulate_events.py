"""Generate a realistic synthetic household history with labelled anomalies.

Two months of internship are not enough to collect real anomalies, so the LSTM is first
trained on simulated routines, then fine-tuned on the real events exported from the API.

    python -m training.simulate_events --days 120 --out data/synthetic

Simulated household (all parameters are randomised around these values):
* resident "A" works on weekdays, leaves ~08:00 and returns ~18:00;
* resident "B" works Monday/Wednesday/Friday ~09:00-17:00;
* both are regularly seen inside the hall while at home (07:00-23:00);
* a guest often visits on weekend afternoons; a delivery driver (unknown) some weekdays;
* a cat wanders around all day.

Injected anomalies (ground truth written to anomalies.csv):
* night_intruder       unknown person + door opening between 01:00 and 04:00
* door_left_open       door stays open for 1-3 hours while nobody is home
* unusual_crowd        many unknown people within 30 minutes while residents are away
* resident_at_night    a resident moving around repeatedly in the middle of the night
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from training.dataset import LabelledAnomaly, write_anomalies, write_events

CAMERA = "entree"


@dataclass
class Simulation:
    tz: ZoneInfo
    rng: random.Random
    rows: list[dict[str, str]] = field(default_factory=list)
    anomalies: list[LabelledAnomaly] = field(default_factory=list)

    def at(self, day: date, hour: float, jitter_minutes: float = 0) -> datetime:
        minutes = hour * 60 + self.rng.gauss(0, jitter_minutes)
        minutes = min(max(minutes, 0), 24 * 60 - 1)
        return datetime.combine(day, time.min, tzinfo=self.tz) + timedelta(minutes=minutes)

    def emit(self, moment: datetime, kind: str, label: str, identity: str = "") -> None:
        self.rows.append(
            {
                "occurred_at": moment.astimezone(ZoneInfo("UTC")).isoformat(),
                "camera": CAMERA,
                "kind": kind,
                "label": label,
                "identity": identity,
            }
        )

    def passage(
        self, moment: datetime, identity: str, *, door_seconds: tuple[int, int] = (20, 90)
    ) -> None:
        """Someone enters or leaves: door opens, person seen, door closes."""
        self.emit(moment, "door", "door_open")
        self.emit(moment + timedelta(seconds=self.rng.randint(2, 10)), "person", "person", identity)
        self.emit(
            moment + timedelta(seconds=self.rng.randint(*door_seconds)), "door", "door_closed"
        )

    def presence(self, start: datetime, end: datetime, identity: str, every_minutes: float) -> None:
        """Occasional sightings of someone who is at home."""
        moment = start + timedelta(minutes=self.rng.expovariate(1 / every_minutes))
        while moment < end:
            self.emit(moment, "person", "person", identity)
            moment += timedelta(minutes=self.rng.expovariate(1 / every_minutes))


def simulate_day(sim: Simulation, day: date) -> list[tuple[datetime, datetime]]:
    """Simulate one normal day. Returns the periods when nobody is at home."""
    rng = sim.rng
    weekday = day.weekday()
    wake, sleep = sim.at(day, 7, 20), sim.at(day, 23, 25)

    a_works = weekday < 5 and rng.random() > 0.05
    b_works = weekday in (0, 2, 4) and rng.random() > 0.05
    a_out = (sim.at(day, 8, 15), sim.at(day, 18, 30)) if a_works else None
    b_out = (sim.at(day, 9, 15), sim.at(day, 17, 30)) if b_works else None

    if not a_works and rng.random() < 0.6:  # weekend outing
        a_out = (sim.at(day, 10.5, 60), sim.at(day, 12.5, 60))
    for out, who in ((a_out, "resident"), (b_out, "resident")):
        if out:
            sim.passage(out[0], who)
            sim.passage(out[1], who)

    # In-home sightings when each resident is there and awake.
    for out in (a_out, b_out):
        if out:
            sim.presence(wake, out[0], "resident", 50)
            sim.presence(out[1], sleep, "resident", 50)
        else:
            sim.presence(wake, sleep, "resident", 50)

    if weekday >= 5 and rng.random() < 0.5:
        arrival = sim.at(day, 15, 60)
        sim.passage(arrival, "guest")
        sim.presence(arrival, arrival + timedelta(hours=2), "guest", 40)
        sim.passage(arrival + timedelta(hours=rng.uniform(1.5, 3)), "guest")
    if weekday < 5 and rng.random() < 0.3:
        sim.passage(sim.at(day, 11, 90), "unknown", door_seconds=(15, 45))  # delivery

    cat_moment = sim.at(day, 0, 0)
    while cat_moment.date() == day:
        cat_moment += timedelta(minutes=rng.expovariate(1 / 70))
        if cat_moment.date() == day:
            sim.emit(cat_moment, "animal", "cat")
    if rng.random() < 0.2:
        sim.emit(sim.at(day, 13, 180), "vehicle", "car")

    away: list[tuple[datetime, datetime]] = []
    if a_out and b_out:
        away.append((max(a_out[0], b_out[0]), min(a_out[1], b_out[1])))
    return [(start, end) for start, end in away if end - start > timedelta(hours=2)]


def inject_anomaly(sim: Simulation, day: date, away: list[tuple[datetime, datetime]]) -> None:
    rng = sim.rng
    kinds = ["night_intruder", "resident_at_night"]
    if away:
        kinds += ["door_left_open", "unusual_crowd"]
    kind = rng.choice(kinds)

    if kind == "night_intruder":
        start = sim.at(day, rng.uniform(1, 4))
        sim.passage(start, "unknown")
        sim.emit(start + timedelta(minutes=rng.uniform(2, 6)), "person", "person", "unknown")
        end = start + timedelta(minutes=10)
        description = "Personne inconnue la nuit"
    elif kind == "resident_at_night":
        start = sim.at(day, rng.uniform(2, 4))
        for i in range(rng.randint(4, 7)):
            sim.emit(start + timedelta(minutes=4 * i), "person", "person", "resident")
        end = start + timedelta(minutes=30)
        description = "Membre du foyer très actif en pleine nuit"
    elif kind == "door_left_open":
        window_start, window_end = rng.choice(away)
        start = window_start + (window_end - window_start) * rng.uniform(0.1, 0.4)
        duration = timedelta(minutes=rng.uniform(60, 180))
        sim.emit(start, "door", "door_open")
        sim.emit(start + duration, "door", "door_closed")
        end = start + duration
        description = "Porte restée ouverte en l'absence des résidents"
    else:
        window_start, window_end = rng.choice(away)
        start = window_start + (window_end - window_start) * rng.uniform(0.2, 0.7)
        for _ in range(rng.randint(5, 10)):
            sim.emit(start + timedelta(minutes=rng.uniform(0, 30)), "person", "person", "unknown")
        end = start + timedelta(minutes=30)
        description = "Nombreuses personnes inconnues en l'absence des résidents"

    sim.anomalies.append(LabelledAnomaly(start, end, kind, description))


def simulate(
    *, days: int, start: date, tz: ZoneInfo, anomalies_per_week: float, seed: int
) -> Simulation:
    sim = Simulation(tz=tz, rng=random.Random(seed))
    for offset in range(days):
        day = start + timedelta(days=offset)
        away = simulate_day(sim, day)
        # Keep the first week clean so the model always starts from a normal baseline.
        if offset >= 7 and sim.rng.random() < anomalies_per_week / 7:
            inject_anomaly(sim, day, away)
    sim.rows.sort(key=lambda row: row["occurred_at"])
    return sim


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 5))
    parser.add_argument("--timezone", default="Africa/Casablanca")
    parser.add_argument("--anomalies-per-week", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args()

    sim = simulate(
        days=args.days,
        start=args.start,
        tz=ZoneInfo(args.timezone),
        anomalies_per_week=args.anomalies_per_week,
        seed=args.seed,
    )
    count = write_events(args.out / "events.csv", sim.rows)
    write_anomalies(args.out / "anomalies.csv", sim.anomalies)
    print(f"{count} events and {len(sim.anomalies)} labelled anomalies written to {args.out}/")


if __name__ == "__main__":
    main()
