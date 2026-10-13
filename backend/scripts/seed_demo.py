"""Fill the database with a realistic week of activity, for demos and UI development.

    python scripts/seed_demo.py                # after `alembic upgrade head`

Everything goes through the real decision pipeline (IngestService): identity resolution,
visitor profiles, anomaly rules, alerts and daily summaries. Face vectors are synthetic
(model "demo-model"), so no camera or photo is needed.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import build_container
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.db.base import utcnow
from app.models import Camera, FaceEmbedding, Person
from app.models.enums import EmbeddingSource, EventKind, PersonRole
from app.schemas.ingest import FaceObservation, Observation, ObservationBatch
from app.schemas.user import UserCreate
from app.services.alert_service import AlertService
from app.services.auth_service import AuthService
from app.services.ingest_service import IngestService
from app.services.summary_service import SummaryService
from training.simulate_events import Simulation, inject_anomaly, simulate_day
from vision.face.similarity import l2_normalize, vector_to_bytes

MODEL = "demo-model"


def noisy(vector: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return l2_normalize(vector + rng.normal(scale=0.05, size=vector.shape))


async def seed(email: str, password: str, days: int) -> None:
    settings = get_settings()
    container = build_container(settings)
    rng = np.random.default_rng(7)
    db = container.database

    async with db.session() as session:
        try:
            await AuthService(session, settings).create_user(
                UserCreate(email=email, password=password, full_name="Démo", is_admin=True)
            )
            print(f"Admin: {email} / {password}")
        except ConflictError:
            print(f"Admin {email} already exists")

        entrance = Camera(name="Entrée", location="Porte d'entrée", has_door=True)
        garden = Camera(name="Jardin", location="Portail du jardin", has_door=False)
        people = {
            "resident": [
                Person(display_name="Hicham", role=PersonRole.RESIDENT),
                Person(display_name="Sara", role=PersonRole.RESIDENT),
            ],
            "guest": [Person(display_name="Tante Fatima", role=PersonRole.GUEST)],
        }
        session.add_all([entrance, garden, *[p for group in people.values() for p in group]])
        await session.flush()
        vectors: dict[str, list[np.ndarray]] = defaultdict(list)
        for identity, persons in people.items():
            for person in persons:
                vector = l2_normalize(rng.normal(size=128))
                vectors[identity].append(vector)
                for _ in range(3):
                    session.add(
                        FaceEmbedding(
                            person_id=person.id,
                            vector=vector_to_bytes(noisy(vector, rng)),
                            dim=128,
                            model_name=MODEL,
                            source=EmbeddingSource.ENROLLMENT,
                        )
                    )
        await session.commit()
        camera_ids = [entrance.id, garden.id]

    # A few strangers come back several times (delivery driver...), others are one-offs.
    regular_strangers = [l2_normalize(rng.normal(size=128)) for _ in range(2)]
    sim = Simulation(tz=settings.tz, rng=random.Random(3))
    today = utcnow().astimezone(settings.tz).date()
    for offset in range(days, 0, -1):
        day = today - timedelta(days=offset)
        away = simulate_day(sim, day)
        if offset in (2, 5):
            inject_anomaly(sim, day, away)
    simulate_day(sim, today)

    now = utcnow()
    rows = sorted(
        (r for r in sim.rows if datetime.fromisoformat(r["occurred_at"]) < now),
        key=lambda r: r["occurred_at"],
    )

    def to_observation(row: dict[str, str], track: int) -> tuple[Observation, int]:
        kind = EventKind(row["kind"])
        face = None
        if kind is EventKind.PERSON:
            identity = row["identity"]
            if identity in vectors:
                base = vectors[identity][track % len(vectors[identity])]
            elif rng.random() < 0.6:
                base = regular_strangers[track % 2]
            else:
                base = l2_normalize(rng.normal(size=128))
            face = FaceObservation(
                embedding=noisy(base, rng).tolist(), model_name=MODEL, detection_score=0.93
            )
        camera = 0 if kind is EventKind.DOOR or rng.random() < 0.7 else 1
        observation = Observation(
            observed_at=datetime.fromisoformat(row["occurred_at"]),
            kind=kind,
            label=row["label"],
            confidence=round(float(rng.uniform(0.6, 0.97)), 3),
            track_id=track,
            face=face,
        )
        return observation, camera

    created_alerts = 0
    for track, row in enumerate(rows):
        observation, camera = to_observation(row, track)
        async with db.session() as session:
            alert_service = AlertService(session, settings, container.dispatcher)
            service = IngestService(
                session,
                settings,
                gallery=container.gallery,
                detector=container.anomaly_detector,
                alert_service=alert_service,
                realtime=container.realtime,
            )
            batch = ObservationBatch(camera_id=camera_ids[camera], observations=[observation])
            result = await service.ingest(batch)
            created_alerts += result.alerts_created

    async with db.session() as session:
        summaries = SummaryService(session, settings)
        for offset in range(days, 0, -1):
            await summaries.generate(today - timedelta(days=offset))
    await db.dispose()
    print(f"{len(rows)} observations ingested, {created_alerts} alerts raised, {days} summaries.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="demo@example.com")
    parser.add_argument("--password", default="demo-password-123")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.password, args.days))


if __name__ == "__main__":
    main()
